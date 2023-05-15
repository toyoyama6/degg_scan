import sys, os
import time
import tables
import numpy as np
import matplotlib.pyplot as plt
import click
import datetime
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm

#########
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet
import RapCal
from RapCal import rapcal as rp

from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import setup_scalers, take_scalers
from degg_measurements.utils.icm_manipulation import run_rapcal_all
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.utils.icm_manipulation import enable_pmt_hv_interlock
from degg_measurements.utils.flash_fpga import fpga_set
from read_times import read_times
from setupHelper import infoContainer, deggContainer
from rapcalHelper import calculateTimingInfoAfterDataTaking
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.analysis import calc_baseline

def saveContainer(degg, ind, nowList=None):
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
        print(f'Created directory {data_dir}')

    dfList = []
    #for info in [degg.info0, degg.info1]:
    for info in [degg.info1]:
        timestampList = [0] * len(info)
        chargeList = [0] * len(info)
        channelList = [0] * len(info)
        mfh_tList = [0] * len(info)
        mfh_t2List = [0] * len(info)
        deltaList = [0] * len(info)
        offsetList = [0] * len(info)
        blockNumList = [0] * len(info)
        cableDelayList = [[0,0]] * len(info)
        clockDriftList = [0] * len(info)
        for m, _info in enumerate(info):
            timestampList[m]  = _info.timestamp
            chargeList[m]     = _info.charge
            channelList[m]    = _info.channel
            mfh_tList[m]      = _info.mfh_t
            mfh_t2List[m]     = _info.mfh_t2
            deltaList[m]      = _info.delta
            offsetList[m]     = _info.datetime_offset
            blockNumList[m]   = _info.i_pair
            cableDelayList[m] = [_info.cable_delay0, _info.cable_delay1]
            clockDriftList[m] = _info.clockDrift
        data = {'timestamp': timestampList, 'charge': chargeList,
             'channel': channelList, 'mfhTime': mfh_tList,
             'mfhTime2': mfh_t2List, 'delta': deltaList,
             'offset': offsetList, 'blockNum': blockNumList,
             'cableDelay': cableDelayList, 'clockDrift': clockDriftList,
             'triggerTime': nowList}
        for d in degg.__dict__:
            if d == 'session' or d == 'rapcals' or d == 'lock' or d == 'condition':
                continue
            if d != 'info' and d != 'info0' and d != 'info1' and d != 'files':
                vals = degg.__dict__[d]
                valsList = [vals] * len(info)
                _dict = {f'{d}':valsList}
                data.update(_dict)
        df = pd.DataFrame(data=data)
        dfList.append(df)

    df_total = pd.concat(dfList, sort=False)
    df.to_hdf(os.path.join(data_dir, f'tabletop_dark_rate_{ind}.hdf5'), key='df', mode='w')
    print(f"Created Output File")

def setup(port=10007, threshold_over_baseline=9000, samples=128, dac_value=30000, period=10000, deadtime=24):
    fpga_set(port, auto_flash=True)
    channel = 1
    session = startIcebootSession(host='localhost', port=port)
    #session = initialize_dual(session, n_samples=samples, dac_value=dac_value,
    #                          high_voltage0=0, high_voltage1=0,
    #                          threshold0=threshold, threshold1=9600,
    #                          modHV=False)
    #session = initialize_dual(session, n_samples=samples, dac_value=dac_value,
    #                          high_voltage0=0, high_voltage1=0,
    #                          threshold0=9600, threshold1=threshold,
    #                          modHV=False)
    ##measure baseline
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    bl_file = os.path.join(data_dir, f'tabletop_baseline_tmp.hdf5')
    if os.path.exists(bl_file):
        os.remove(bl_file)
    session = min_measure_baseline(session, channel, bl_file, 1024, dac_value=30000, hv=0, nevents=20, modHV=False)
    baseline = calc_baseline(bl_file)['baseline'].values[0]
    threshold = baseline+threshold_over_baseline
    session = setup_scalers(session, channel=channel, high_voltage=0,
                            dac_value=30000, threshold=threshold,
                            period=period, deadtime=deadtime, modHV=False)

    rapcals = rp.RapCalCollection()
    return session, rapcals

def doRapCal(icms, degg, FirstTime=False):
    if FirstTime == True:
        num_rapcals = 2
    else:
        num_rapcals = 1

    session = degg.session
    rapcals = degg.rapcals

    for i in range(num_rapcals):
        icms.request('rapcal_all')
        #reply = run_rapcal_all(icm_port)
        header_info = rp.RapCalEvent.parse_rapcal_header(session._read_n(4))
        rapcal_pkt = session._read_n(header_info['size'])
        if not header_info.get('size'):
            raise Exception(header_info['error'])
        event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
        event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
        rapcals.add_rapcal(event)
    #return rapcals

def getRapCalPair(rapcals, utc_time, icm_time):
    if len(rapcals.rapcals) >= 2:
        print(f'UTC Time: {utc_time}')
        print(f'ICM Time: {icm_time}')
        rp_pair = rp.RapCalPair(rapcals.rapcals[-2], rapcals.rapcals[-1], utc=utc_time, icm=icm_time)
    else:
        raise NotImplementedError("Some error - not enough rapcals to build pairs and get a time")
    return rp_pair

def initFile(filename, nevents):
    if not os.path.isfile(filename):
        dummy = [0] * nevents
        dummy = np.array(dummy)
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            timestamp = tables.Float128Col()
            mfh_times = tables.Float128Col(shape=np.asarray(dummy).shape)
            mb_timestamps = tables.Float128Col(shape=np.asarray(dummy).shape)
            offset_time = tables.Float128Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/', 'data', Event)

def monitorTime(degg, nevents, i_pair, nowList=None):
    ##laser will be running at 10 - 100 Hz
    session = degg.session
    '''
    block = session.DEggReadChargeBlock(0, 20, 14*nevents, timeout=40)
    channels = list(block.keys())
    for channel in channels:
        charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
        timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
        for ts, q in zip(timestamps, charges):
            info = infoContainer(ts, q, channel, i_pair)
            degg.addInfo(info, channel)
    '''
    scaler_count_sum = 0
    channel = 1
    period = degg.period
    for i in tqdm(range(nevents)):
        session, scaler_count = take_scalers(session, channel)
        info = infoContainer(session.domClock()*(4.), scaler_count, channel, i_pair)
        nowList.append(datetime.now())
        degg.addInfo(info, channel)
        time.sleep(period / 1e6)

def saveTime(mb_timestamps, icm_timestamp, rapCalPair, counter, t_offset_datetime, filename):

    #use rapCalPair to get MFH time
    mfh_ts = [0] * len(mb_timestamps)
    for i, mb_timestamp in enumerate(mb_timestamps):
        mfh_t = rapCalPair.dom2surface(mb_timestamp, 'DEGG')
        mfh_ts[i] = mfh_t - t_offset_datetime

    #save to file
    with tables.open_file(filename, 'a') as open_file:
        table = open_file.get_node('/data')
        event = table.row

        event['event_id'] = counter
        event['timestamp'] = icm_timestamp
        event['mfh_times'] = mfh_ts
        event['mb_timestamps'] = mb_timestamps
        event['offset_time'] = t_offset_datetime
        event.append()
        table.flush()

def configureICMs(icm_port):
    enable_pmt_hv_interlock(icm_port)

def getTimeSeeds(icm_port):
    icms = ICMNet(icm_port, host='localhost')

    icms.request('write 8 0 0x0100')
    icms.request('gps_enable')
    time.sleep(1.1)

    if icms.request('get_gps_ctrl')['value'] != '0x0002':
        raise RuntimeError(f'GPS Time Not Valid!: {icms.request("get_gps_ctrl")}')
    if icms.request('get_gps_status')['value'] != '0x000e':
        raise RuntimeError(f'GPS not locked: {icms.request("get_gps_status")}')

    ##NOTE - I have modified the function in RapCal to work with this formatting
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
    print(f'Datetime:{dt}')
    print(f'Now:{datetime.now()}')

    return icms, dt.timestamp(), icm_time

def tabletop(port=None, outfile='trigger_monitor.hdf5'):
    default_port_start = 10000
    if port == None:
        port = default_port_start + 7
        icm_port = default_port_start + 1000

    ##configure ICM settings
    configureICMs(icm_port)
    ##setup file
    nevents = 10000 ##block size

    #initFile(outfile, nevents)
    offset_datetime = datetime(2022, 2, 1)

    t_offset_datetime = offset_datetime.timestamp()

    ##setup the board & rapcal info
    period = 10000 #micro-seconds
    deadtime = 24
    session, rapcals = setup(port, threshold_over_baseline=12, period=period, deadtime=deadtime)
    degg = deggContainer()
    degg.session = session
    degg.port = port
    degg.rapcals = rapcals

    degg.period   = period
    degg.deadtime = deadtime

    ##get the timing seeds
    ##run it twice to ensure GPS time at MFH is updated
    icm, utc_time, icm_time = getTimeSeeds(icm_port)
    time.sleep(1.1)
    icm, utc_time, icm_time = getTimeSeeds(icm_port)

    #n_groups = 20
    n_groups = 20
    n_blocks = 20
    for group in range(n_groups):
        print(group)
        nowList = []
        for counter in range(n_blocks):
            ##run rapcal
            doRapCal(icm, degg)
            ##legacy workaround
            degg.rapcal_utcs.append(utc_time)
            degg.rapcal_icms.append(icm_time)

            ##saved into degg obj
            monitorTime(degg, nevents, counter, nowList)

            doRapCal(icm, degg)
            ##legacy workaround
            degg.rapcal_utcs.append(utc_time)
            degg.rapcal_icms.append(icm_time)

            time.sleep(1)

        print(len(degg.info0))
        print(len(degg.info1))
        print(len(nowList))

        print("Doing calculations")
        calculateTimingInfoAfterDataTaking([degg], method='charge_stamp')
        print("Saving data")
        saveContainer(degg, group, nowList)
        ##reset info and rapcals
        degg.resetInfo()
        rapcals = degg.rapcals
        rapcals = rp.RapCalCollection()
        degg.rapcals = rapcals

@click.command()
@click.option('--port', '-p', default=None)
def main(port):
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    outfile = os.path.join(data_dir, 'block_fpga_monitor_ext_out_100hz_7.hdf5')
    tabletop(port, outfile)
    print("data taking done, exiting") ##output file format changed
    exit(1)

    ids, timestamps, mbtimestamps, times, t_offset = read_times(outfile)
    fig, ax = plt.subplots()
    binning = np.linspace(0.005, 0.2, 200)

    timesTotal = []
    for time in times:
        for t in time:
            timesTotal.append(t)

    ax.hist(np.diff(timesTotal), bins=200, histtype='step', color='royalblue')
    ax.set_yscale('log')
    figs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if not os.path.exists(figs_dir):
        os.mkdir(figs_dir)
        print(f'Created directory: {figs_dir}')

    fig.savefig(os.path.join(figs_dir, 'monitor_diff.pdf'))

if __name__ == "__main__":
    main()

##end
