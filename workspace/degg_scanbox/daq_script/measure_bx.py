import os, sys
import click
import numpy as np
import skippylab as sl
import tables
import pandas as pd
from tqdm import tqdm
import time

from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *
from termcolor import colored

####
from read_waveform import init as reference_init
from read_waveform import set_DAQ
from infoContainer import infoContainer
from deggContainer import *
####

####
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import write_to_hdf5
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import update_json, create_key
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.monitoring import readout_sensor
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.analysis import calc_baseline
####

def measure_degg_charge_stamp(degg, nevents=100, event_num=0, r_point=0, t_point=0, data_dir=''):
    infoval = []
    num_retry = 0
    retry = True
    while retry == True:
        try:
            block = degg.session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=200)
            channels = list(block.keys())
            for channel in channels:
                charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
                timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
                for ts, q in zip(timestamps, charges):
                    info = infoContainer(ts, q, channel, event_num, r_point, t_point)
                    try:
                        infoval.append([ts, q, channel, event_num, r_point, t_point])
                    except:
                        continue
                    degg.addInfo(info, channel)
            try:
                dfs = pd.read_hdf(f'{data_dir}/charge_stamp.hdf')
                df = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                df_total = pd.concat([dfs, df])
            except:
                df_total = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
            df_total.to_hdf(f'{data_dir}/charge_stamp.hdf', key='df')
            retry = False

        except:
            print(f'no measure {r_point}: {t_point} - retry {num_retry}')
            retry = True
            num_retry += 1

            if num_retry > 5:
                info = infoContainer(-1, -1, -1, -1, r_point, t_point)
                infoval.append([-1, -1, -1, -1, r_point, t_point])
                degg.addInfo(info, -1)
                try:
                    dfs = pd.read_hdf(f'{data_dir}/charge_stamp.hdf')
                    df = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                    df_total = pd.concat([dfs, df])
                except:
                    df_total = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                df_total.to_hdf(f'{data_dir}/charge_stamp.hdf', key='df')
                retry = False


def measure_r_steps(data_dir, degg, nevents, r_stage, slave_address, t_point, r_step, r_scan_points,
                    mtype='stamp', forward_backward='forward'):
    print(f'Measuring: {forward_backward}\n{r_scan_points}')
    for event_num, r_point in enumerate(r_scan_points):
        print(r_point)
        ##take DEgg data
        if mtype == 'stamp':
            measure_degg_charge_stamp(degg, nevents, event_num, r_point, t_point, data_dir)
        elif mtype == 'waveform':
            raise NotImplementedError('Not ready yet!')
            #measure_degg_waveform()
        else:
            raise ValueError(f'option for measurement type: {mtype} not valid')

        if forward_backward == 'forward':
            r_stage.moveRelative(slave_address, r_step)
            time.sleep(5)
        elif forward_backward == 'backward':
            r_stage.moveRelative(slave_address, -r_step)
            time.sleep(5)
        else:
            raise ValueError(f'option for scan direction: {forward_backward} not valid')

        

    ##when finished, return motor to home
    r_stage.moveToHome(slave_address)
    time.sleep(10)

def setup_motors(slave_address):
    print(colored("Setting up motors...", 'green'))
    rotate_stage = None
    ##USB3 - THORLABS
    try:
        rotate_stage = HDR50(serial_port="/dev/ttyUSB3", serial_number="40106754", home=True, swap_limit_switches=True)
        rotate_stage.wait_up()
    except:
        print(colored('Error in connecting to Thorlabs Motor!', 'red'))
    ##USB2 - ORIENTAL MOTORS
    try:
        r_stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    # rotate_stage.home()
    # rotate_stage.wait_up()

    r_stage.moveToHome(slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))

    return rotate_stage, r_stage

def setup_reference(reference_pmt_channel):
    print(colored("Setting up reference pmt readout (scope)...", 'green'))
    scope_ip = "10.25.121.219"
    scope = sl.instruments.RohdeSchwarzRTM3004(ip=scope_ip)
    scope.ping()
    return scope

def convert_wf(raw_wf):
    times, volts = raw_wf
    #times_and_volts = np.array(raw_wf.split(','), dtype=float)
    #times = times_and_volts[::2]
    #volts = times_and_volts[1::2]
    return times, volts


def measure_reference(filename, scope, reference_pmt_channel=1, num_reference_wfs=1000):
    print(colored(f"Reference Measurement - {num_reference_wfs} WFs", 'green'))
    for i in range(num_reference_wfs):
        raw_wf = scope.acquire_waveform(reference_pmt_channel)
        times, wf = convert_wf(raw_wf)
        write_to_hdf5(filename, i, times, wf, 0, 0)

def setup_degg(run_file, filepath, measure_mode, nevents, config_threshold0, config_threshold1):
    tSleep = 40 #seconds
    list_of_deggs = load_run_json(run_file)
    degg_file = list_of_deggs[0]
    degg_dict = load_degg_dict(degg_file)

    port = degg_dict['Port']
    hv_l = degg_dict['LowerPmt']['HV1e7Gain']
    hv_u = degg_dict['UpperPmt']['HV1e7Gain']

    pmt_name0 = degg_dict['LowerPmt']['SerialNumber']
    pmt_name1 = degg_dict['UpperPmt']['SerialNumber']

    ##connect to D-Egg mainboard
    session = startIcebootSession(host='localhost', port=port)

    ##turn on HV - ramping happens on MB, need about 40s
    session.enableHV(0)
    session.enableHV(1)
    session.setDEggHV(0, int(hv_l))
    session.setDEggHV(1, int(hv_u))
    
    ##make temporary directory for baseline files
    if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')):
        os.mkdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp'))
    
    baselineFiles = []
    for channel, pmt in zip([0, 1], ['LowerPmt', 'UpperPmt']):
        bl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                f'tmp/{degg_dict[pmt]["SerialNumber"]}_baseline_{channel}.hdf5')
        baselineFiles.append(bl_file)
        if os.path.isfile(bl_file):
            os.remove(bl_file)

    ##wait for HV to ramp
    for i in tqdm(range(tSleep)):
        time.sleep(1)

    v0 = readout_sensor(session, 'voltage_channel0')
    v1 = readout_sensor(session, 'voltage_channel1')
    print(f"Voltage is currently: {v0}, {v1}")
    time.sleep(0.25)

    ##measure baseline for both PMTs
    session = min_measure_baseline(session, 0, baselineFiles[0], 
                                1024, 30000, 0, nevents=50, modHV=False)
    session = min_measure_baseline(session, 1, baselineFiles[1], 
                                1024, 30000, 0, nevents=50, modHV=False)
    
    baseline0 = calc_baseline(baselineFiles[0])['baseline'].values[0]
    baseline1 = calc_baseline(baselineFiles[1])['baseline'].values[0]

    threshold0 = int(baseline0 + config_threshold0)
    threshold1 = int(baseline1 + config_threshold1)
    thresholdList = [threshold0, threshold1]

    dac_value = 30000
    session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                             high_voltage0=hv_l, high_voltage1=hv_u,
                             threshold0=threshold0, threshold1=threshold1,
                             modHV=False)

    f0_string = f'{pmt_name0}_{measure_mode}_{hv_l}.hdf5'
    f1_string = f'{pmt_name1}_{measure_mode}_{hv_u}.hdf5'
    f0 = os.path.join(filepath, f0_string)
    f1 = os.path.join(filepath, f1_string)
    files = [f0, f1]

    _degg = deggContainer()
    _degg.port = port
    _degg.session = session
    _degg.files = files
    _degg.lowerPMT = pmt_name0
    _degg.upperPMT = pmt_name1
    _degg.createInfoFiles(nevents, overwrite=False)
    return _degg, degg_dict, degg_file

def setup_paths(measurement_type):
    data_dir = '/home/icecube/data/'
    dirname = create_save_dir(data_dir, measurement_type)
    dirname_ref = os.path.join(dirname, 'ref')
    dirname_sig = os.path.join(dirname, 'sig')
    if not os.path.exists(dirname_ref):
        os.mkdir(dirname_ref)
    if not os.path.exists(dirname_sig):
        os.mkdir(dirname_sig)

    return dirname_ref, dirname_sig

def save_degg_data(degg, measure_mode, data_dir):
    dfList = []
    for info in [degg.info0, degg.info1]:
        if measure_mode == 'stamp':
            timestampL = [0] * len(info)
            chargeL    = [0] * len(info)
        channelL  = [0] * len(info)
        eventNumL = [0] * len(info)
        rL        = [0] * len(info)
        tL        = [0] * len(info)

        for m, _info in enumerate(info):
            timestampL[m] = _info.timestamp
            chargeL[m]    = _info.charge
            channelL[m]   = _info.channel
            eventNumL[m]  = _info.event_number
            rL[m]         = _info.r_point
            tL[m]         = _info.t_point

        data = {
                'timestamp': timestampL,
                'charge':    chargeL,
                'channel':   channelL,
                'event':     eventNumL,
                'rVal':      rL,
                'tVal':      tL
                }

        for d in degg.__dict__:
            if d == 'session':
                continue
            if d != 'info0' and d!= 'info1' and d != 'files':
                vals = degg.__dict__[d]
                if vals == -1:
                    continue
                valsList = [vals] * len(info)
                _dict = {f'{d}': valsList}
                data.update(_dict)

        df = pd.DataFrame(data=data)
        dfList.append(df)

    df_total = pd.concat(dfList, sort=False)
    for i in df_total:
        outfile = os.path.join(data_dir, f'degg_scan_data_{measure_mode}.hdf5')
        i.to_hdf(outfile, key='df', mode='a')

def daq_wrapper(run_json, comment):
    
    ##setup paths
    measurement_type = 'scanbox'
    dir_ref, dir_sig = setup_paths(measurement_type)

    theta_step = 6 ##deg
    theta_max = 180 ##deg
    theta_scan_points = np.arange(0, theta_max, theta_step)
    
    r_step = 3 ##mm
    r_range = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_range, r_step)

    slave_address = 1
    rotate_stage, r_stage = setup_motors(slave_address)

    LD = PMX70_1A('10.25.123.249')
    LD.connect_instrument()
    
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    ##initialise DEgg settings
    config_threshold0 = 100 ##units of ADC
    config_threshold1 = 6000 ##units of ADC
    ##wf/chargestamp per scan point
    nevents = 3000
    ##wf (waveform) or chargestamp (stamp)
    measure_mode = 'stamp'
    degg, degg_dict, degg_file = setup_degg(run_json, dir_sig, measure_mode, 
                                    nevents, config_threshold0, config_threshold1)
    ##wait for motors to go home
    time.sleep(5)

    for pmt in ['LowerPmt', 'UpperPmt']:
        key = create_key(degg_dict[pmt], measurement_type)
        meta_dict = dict()
        meta_dict['Folder']     = dir_sig
        meta_dict['threshold0'] = config_threshold0
        meta_dict['threshold1'] = config_threshold1
        meta_dict['nevents']    = nevents
        meta_dict['mode']       = measure_mode
        meta_dict['Comment']    = comment
        degg_dict[pmt][key] = meta_dict
    update_json(degg_file, degg_dict)

    voltage = 6
    LD.set_volt_current(voltage, 0.02)

    for theta_point in theta_scan_points:
        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point, r_step, 
                        r_scan_points, mtype=measure_mode, forward_backward='forward')

        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(20)

        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point+180, r_step, 
                        r_scan_points, mtype=measure_mode, forward_backward='backward') 

        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(20)
        
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()
    ##save data
    save_degg_data(degg, measure_mode, dir_sig)

    ## motor home
    # r_stage.moveToHome(slave_address)
    # rotate_stage.home()
    # rotate_stage.wait_up()


@click.command()
@click.argument('run_json')
@click.argument('comment')
def main(run_json, comment):
    daq_wrapper(run_json, comment)

if __name__ == "__main__":
    main()
##end
