import os, sys
from tqdm import tqdm
from termcolor import colored
import time
import pandas as pd
import click
from copy import deepcopy
import json
import numpy as np
from datetime import datetime
from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

################################
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.daq_scripts.master_scope import take_waveform_block
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.daq_scripts.master_scope import exit_gracefully
from degg_measurements.analysis import calc_baseline
from degg_measurements.monitoring import readout_sensor
from deggContainer import *
################################




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
    _degg.createInfoFiles(nevents, overwrite=True)
    return session, degg_dict, degg_file





def setup_top_devices(rotate_slave_address, r_slave_address):
    print(colored("Setting up motors...", 'green'))
    stage = None
    ##USB2 - ORIENTAL MOTORS
    try:
        stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    stage.moveToHome(rotate_slave_address)
    time.sleep(5)
    stage.moveToHome(r_slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))
    return stage


def measure_r_steps(session, r_step, r_scan_points):
    rotate_slave_address = 5
    r_slave_adress = 3
    r_stage = setup_top_devices(rotate_slave_address, r_slave_adress)
    for event_num, r_point in enumerate(r_scan_points):
        print("r_point", r_point)
        take_data(session, r_point)
        r_stage.moveRelative(r_slave_adress, r_step)
        time.sleep(5)
        
def take_data(session, r_point, nevents=2000):
      ##temp ---
    info = []
    channels = [0, 1]
    tags = ['LowerPmt', 'UpperPmt']
    for channel, tag in zip(channels, tags):
        ref_time = time.monotonic()

        i = 0
        with tqdm(total=nevents) as progress_bar:
            while i <= nevents:
                session, readouts, pc_time = take_waveform_block(session)
                if session is None:
                    break
                if readouts is None:
                    continue

                for readout in readouts:
                    wf = readout['waveform']
                    timestamp = readout['timestamp']
                    xdata = np.arange(len(wf))
                    trig_channel = readout['channel']
                    if trig_channel != channel:
                        print(channel, trig_channel)
                        print("Channel mis-match! WTF!")

                    info.append([trig_channel,
                                i, xdata, wf,
                                timestamp, pc_time-ref_time])
                    progress_bar.update(1)
                    i += 1
                    if i >= nevents:
                        break

        # temp = readout_sensor(session, 'temperature_sensor')
    df_total = pd.DataFrame(data=info, columns=["triggerchannel", "nevents", "xdata", "wf", "timestamp", "pc_time-ref_time"])
    df_total.to_hdf(f'/home/scanbox/initialtest/peak_height/data/wf_data_{r_point}.hdf5', key='df')



@click.command()
@click.argument('run_json')

def main(run_json):
    r_step = 3 ##mm
    r_max = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_max, r_step)

    ##wf/chargestamp per scan point
    nevents = 3000
    n_jobs = 1
    filepath = "/home/scanbox/initialtest/peak_height/"
    measure_mode = 'waveform'

    ##initialise DEgg settings
    config_threshold0 = 6000 ##units of ADC
    config_threshold1 = 100 ##units of ADC
    session, degg_dict, degg_file = setup_degg(run_json, filepath, measure_mode, nevents, config_threshold0, config_threshold1)
    measure_r_steps(session, r_step, r_scan_points)    

if __name__ == "__main__":
    main()
