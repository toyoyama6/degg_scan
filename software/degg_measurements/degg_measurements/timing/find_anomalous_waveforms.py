import sys, os
import tables
import numpy as np
import click
import time
from datetime import datetime, timedelta

from icmnet import ICMNet
from RapCal import rapcal as rp
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils.icm_manipulation import enable_external_osc
from degg_measurements.utils.icm_manipulation import run_rapcal_all
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.analysis import calc_baseline
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.daq_scripts.master_scope import write_to_hdf5
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.utils import startIcebootSession
from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature
from degg_measurements.daq_scripts.master_scope import take_waveform_block
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline

from degg_measurements import DATA_DIR


class deggContainer(object):
    def __init__(self):
        self.port = -1
        self.icm_port = -1
        self.threshold0 = -1
        self.threshold1 = -1
        self.dac_value = -1
        self.session = -1
        self.rapcals = -1
        self.files = []
        self.wfFiles = []
        self.info0 = []
        self.info1 = []
        self.offset = -1
        self.hvSet0 = -1
        self.hvSet1 = -1
        self.period = -1
        self.rapcal_utcs = []
        self.rapcal_icms = []
        self.dac = -1

    def addInfo(self, infoContainer, channel):
        if channel == 0:
            self.info0.append(infoContainer)
        if channel == 1:
            self.info1.append(infoContainer)

    def resetInfo(self):
        self.info0 = []
        self.info1 = []

    def saveInfo(self, channel):
        if channel == 0:
            info = self.info0
            f = self.files[0]
        if channel == 1:
            info = self.info1
            f = self.files[1]

        with tables.open_file(f, 'a') as open_file:
            table = open_file.get_node('/data')
            for m, _info in enumerate(info):
                event = table.row
                event['timestamp'] = _info.timestamp
                event['charge']    = _info.charge
                event['channel']   = _info.channel
                event['mfhTime']   = _info.mfh_t
                event['offset']    = _info.datetime_offset
                event['blockNum']  = _info.i_pair
                event.append()
                table.flush()

    def createInfoFiles(self, nevents, overwrite=False):
        for ch in [0, 1]:
            f = self.files[ch]
            if os.path.isfile(f):
                if not overwrite:
                    raise IOError(f'File name not unique! Risk overwriting file {f}')
                else:
                    print(f"Will overwrite file {f}")
                    time.sleep(3)
                    os.remove(f)
            dummy = [0] * nevents
            dummy = np.array(dummy)
            if not os.path.isfile(f):
                class Event(tables.IsDescription):
                    mfhTime     = tables.Float128Col()
                    timestamp   = tables.Float128Col()
                    charge      = tables.Float64Col()
                    offset      = tables.Float128Col()
                    channel     = tables.Int32Col()
                    blockNum    = tables.Int32Col()
                with tables.open_file(f, 'w') as open_file:
                    table = open_file.create_table('/','data',Event)

class infoContainer(object):
    def __init__(self, timestamp, charge, channel, i_pair):
        #self.counts = counts
        self.timestamp = timestamp
        self.charge = charge
        self.channel = channel
        self.i_pair = i_pair
        self.mfh_t = -1
        self.datetime_offset = -1

def reRampHV(degg, mode='fast', info='Ramping'):
    session = degg.session
    hv_set0 = degg.hvSet0
    hv_set1 = degg.hvSet1
    print(info)
    session.enableHV(0)
    session.enableHV(1)
    #re-ramp HV quickly
    step = 50 # Ramping step in V
    if hv_set0 >= hv_set1:
        hv_set = hv_set0
    if hv_set1 > hv_set0:
        hv_set = hv_set1
    hv_ramp_values = np.arange(100, hv_set+step, step)
    for hv_ramp_value in hv_ramp_values:
        session.setDEggHV(0, int(hv_ramp_value))
        session.setDEggHV(1, int(hv_ramp_value))
        if mode == 'fast':
            time.sleep(0.4)
        if mode == 'slow':
            time.sleep(1.5)

def recreateStreams(degg):
    hv_set0 = degg.hvSet0
    hv_set1 = degg.hvSet1
    dac_value = degg.dac
    threshold0 = degg.threshold0
    threshold1 = degg.threshold1
    session = degg.session
    session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                              high_voltage0=hv_set0, high_voltage1=hv_set1,
                              threshold0=threshold0, threshold1=threshold1)
    time.sleep(0.1)

def setupRapCalData(rapcal_ports):
    icmConnectList = []
    for icm_port in rapcal_ports:
        print(f"--- ICM {icm_port} ---")
        icms = ICMNet(icm_port, host='localhost')
        icms.request('write 8 0 0x0100')
        icms.request('gps_enable')
        time.sleep(1.1)
        if icms.request('get_gps_ctrl')['value'] != '0x0002':
            raise RuntimeError(f'GPS Time Not Valid!: {icms.request("get_gps_ctrl")}')
        if icms.request('get_gps_status')['value'] != '0x000e':
            raise RuntimeError(f'GPS not locked: {icms.request("get_gps_status")}')
        icmConnectList.append(icms)
    return icmConnectList

def getRapCalData(icms, icm_port, degg):
    #print(f'Starting RapCal Procedure for {icm_port}')

    icm_time = icms.request('get_icm_time 8')['value']
    utc_time_str = icms.request('read 8 0x2B')['value']
    utc_time_str = utc_time_str.split('T')
    ##Years, days, hours, min, sec
    years   = int(utc_time_str[0].split('-')[0])
    days    = int(utc_time_str[0].split('-')[1])
    hours   = int(utc_time_str[1].split(':')[0])
    minutes = int(utc_time_str[1].split(':')[1])
    seconds = int(utc_time_str[1].split(':')[2])
    dt = datetime(years, 1, 1, hours, minutes, seconds) + timedelta(days=(days-1))

    time.sleep(1e-5)
    ##run RapCal twice to build the RapCalPair
    for i in range(2):
        icms.request('rapcal_all')
        session = degg.session
        rapcals = degg.rapcals
        header_info = rp.RapCalEvent.parse_rapcal_header(session._read_n(4))
        rapcal_pkt = session._read_n(header_info['size'])
        if not header_info.get('size'):
            raise Exception(header_info['error'])
        event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
        event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
        rapcals.add_rapcal(event)
        degg.rapcal_utcs.append(dt.timestamp())
        degg.rapcal_icms.append(icm_time)
    time.sleep(1e-5)

def getEventDataParallel(degg, channel, nevents, i_pair=0, collected_waveform=False):
    session = degg.session
    rapcals = degg.rapcals
    rp_pair = rp.RapCalPair(rapcals.rapcals[0], rapcals.rapcals[1],
                            utc=degg.rapcal_utcs[0], icm=degg.rapcal_icms[0])
    offset_datetime = datetime(2021, 10, 1)
    t_offset_datetime = offset_datetime.timestamp()

    if channel == 0:
        hv = degg.hvSet0
    if channel == 1:
        hv = degg.hvSet1

    ##take some charge stamps
    ##if rate is high, transition to second part
    ##take some waveforms

    ##configure number of events in a block (up to some limit)
    block = session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=25)
    channels = list(block.keys())
    rates = [0, 0]
    triggers = [0, 0]
    times = [0, 0]
    for ch in channels:
        charges = [(rec.charge * 1e12) for rec in block[ch] if not rec.flags]
        timestamps = [(rec.timeStamp) for rec in block[ch] if not rec.flags]
        mfhTimes = [0] * len(timestamps)
        j = 0
        for ts, q in zip(timestamps, charges):
            info = infoContainer(ts, q, ch, i_pair)
            degg.addInfo(info, ch)
            mfh_t = rp_pair.dom2surface(ts, device_type='DEGG')
            mfhTimes[j] = mfh_t
            info.datetime_offset = t_offset_datetime
            info.mfh_t = (mfh_t-t_offset_datetime)
            j += 1

        total_time = (np.max(mfhTimes) - np.min(mfhTimes)) - (len(timestamps) * 500e-9)
        if len(timestamps) > 1:
            rates[ch] = len(timestamps) / total_time
            triggers[ch] = len(timestamps)
            times[ch] = total_time

    if rates[channel] != 0:
        print(f'Rate: {rates[channel]} = {triggers[channel]} / {times[channel]}')

    #threshold at 20 kHz, then take waveforms
    if rates[channel] > 20e3:
        print(f"Taking Waveforms - {rates[channel]} Hz")
        session.endStream()
        time.sleep(1)
        filename = degg.wfFiles[channel]
        params = {}
        params['filename'] = filename
        n_samples = 128
        triggerThreshold = [degg.threshold0, degg.threshold1]
        session.setDEggConstReadout(int(channel), 1, int(n_samples))
        session.startDEggThreshTrigStream(int(channel), triggerThreshold[channel])
        n_pts = 5
        hv_mon_pre = np.full(n_pts, np.nan)
        for pt in range(n_pts):
            hv_mon_pre[pt] = readout_sensor(session, f'voltage_channel{channel}')
        session, readouts, pc_time = take_waveform_block(session)
        for readout in readouts:
            wf = readout['waveform']
            timestamp = readout['timestamp']
            xdata = np.arange(len(wf))
            readout_channel = readout['channel']
            write_to_hdf5(filename, i_pair, xdata, wf, timestamp, 0)
        temp = readout_sensor(session, 'temperature_sensor')
        hv_mon = np.full(n_pts, np.nan)
        for pt in range(n_pts):
            hv_mon[pt] = readout_sensor(session, f'voltage_channel{channel}')

        params['degg_temp'] = temp
        params['hv_mon_pre'] = str(hv_mon_pre)
        params['hv_mon'] = str(hv_mon)
        params['hv'] = hv
        params['hv_scan_value'] = hv
        if collected_waveform == False:
            add_dict_to_hdf5(params, params['filename'])
            collected_waveform = True

        session.endStream()
        time.sleep(1)
        session.startDEggDualChannelTrigStream(int(degg.threshold0), int(degg.threshold1))

    ##write the converted times to file
    degg.saveInfo(channel)
    ##clear degg info
    degg.resetInfo()
    time.sleep(2)

def analysis_wrapper(run_file, port, icm_port, channel, overwrite=False):

    #load all degg files
    list_of_deggs = load_run_json(run_file)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        if degg_dict['Port'] == port:
            degg_pmts = [degg_dict['LowerPmt']['SerialNumber'], degg_dict['UpperPmt']['SerialNumber']]
            hv_set0 = degg_dict['LowerPmt']['HV1e7Gain']
            hv_set1 = degg_dict['UpperPmt']['HV1e7Gain']
            if hv_set0 == -1:
                hv_set0 = 1500
            if hv_set1 == -1:
                hv_set1 = 1500
            spe_peak_height = []
            hv_setting = [hv_set0, hv_set1]
            for pmt in ['LowerPmt', 'UpperPmt']:
                try:
                    spe_peak_height.append(degg_dict[pmt]['SPEPeakHeight'])
                except KeyError:
                    print(f"Estimating Peak height for {degg_dict[pmt]['SerialNumber']}")
                    spe_peak_height.append(0.004)
            break

    nevents = 1000
    dac_value = 30000

    degg = deggContainer()
    degg.port = port
    degg.icm_port = icm_port
    rapcal_ports = [icm_port]
    session = startIcebootSession(port=port, host='localhost')
    degg.session = session
    degg.hvSet0 = hv_set0
    degg.hvSet1 = hv_set1
    reRampHV(degg, 'fast')
    baseline_filename = f'{degg_pmts[channel]}_baseline_{hv_set0}v_0.hdf5'
    if os.path.isfile(baseline_filename):
        if not overwrite:
            raise IOError(f'File name not unique! Risk overwriting file {baseline_filename}')
        else:
            print(f"Will overwrite file {baseline_filename}")
            time.sleep(1)
            os.remove(baseline_filename)
    min_measure_baseline(session, channel, baseline_filename, samples=1024, dac_value=30000, hv=hv_setting[channel], nevents=20)
    session.endStream()
    baseline = float(calc_baseline(baseline_filename)['baseline'].values[0])

    threshold0 = baseline + (0.25 * spe_peak_height[0] / CALIBRATION_FACTORS.adc_to_volts)
    threshold1 = baseline + (0.25 * spe_peak_height[1] / CALIBRATION_FACTORS.adc_to_volts)
    threshold_list = [threshold0, threshold1]
    filepath = os.path.join(DATA_DIR, "darkrate_timing")
    pmt_name0 = degg_pmts[0]
    f0    = os.path.join(filepath, f'{pmt_name0}_charge_stamp_{hv_set0}v_{threshold0}_0.hdf5')
    wf_f0 = f'{pmt_name0}_waveform_{hv_set0}v_{threshold0}_0.hdf5'
    pmt_name1 = degg_pmts[1]
    f1    = os.path.join(filepath, f'{pmt_name1}_charge_stamp_{hv_set1}v_{threshold1}_0.hdf5')
    wf_f1 = f'{pmt_name1}_waveform_{hv_set1}v_{threshold1}_0.hdf5'

    degg.files = [f0, f1]
    degg.wfFiles = [wf_f0, wf_f1]

    for ch in [0, 1]:
        f = degg.wfFiles[ch]
        if os.path.isfile(f):
            if not overwrite:
                raise IOError(f'File name not unique! Risk overwriting file {f}')
            else:
                print(f"Will overwrite file {f}")
                time.sleep(1)
                os.remove(f)

    degg.rapcals = rp.RapCalCollection()
    degg.threshold0 = threshold0
    degg.threshold1 = threshold1
    degg.dac = dac_value
    degg.createInfoFiles(nevents, overwrite)

    if channel == 0:
        degg.threshold1 = 14000
    elif channel == 1:
        degg.threshold0 = 14000
    else:
        raise ValueError('Channel must be 0 or 1!')
    recreateStreams(degg)
    print('-'*20)
    print(f'Channel {channel} Baseline   : {baseline}')
    print(f'Channel {channel} Peak Height: {spe_peak_height[channel] / CALIBRATION_FACTORS.adc_to_volts}')
    print(f'Channel {channel} Threshold  : {threshold_list[channel]}')
    print('-'*20)
    icmConnectList = setupRapCalData(rapcal_ports)
    collected_waveform = False
    for i in range(100):
        getRapCalData(icmConnectList[0], icm_port, degg)
        time.sleep(0.05)
        getEventDataParallel(degg, channel, nevents, i, collected_waveform)

@click.command()
@click.argument('run_file')
@click.argument('port')
@click.argument('icm_port')
@click.argument('channel')
@click.option('--overwrite', '-ow', is_flag=True)
def main(run_file, port, icm_port, channel, overwrite):
    channel = int(channel)
    port = int(port)
    icm_port = int(icm_port)
    analysis_wrapper(run_file, port, icm_port, channel, overwrite)

if __name__ == "__main__":
    main()

##end
