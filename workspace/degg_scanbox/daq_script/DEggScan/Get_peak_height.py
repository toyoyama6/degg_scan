import os, sys
from tqdm import tqdm
from termcolor import colored
import time
import click
from copy import deepcopy
import json
import numpy as np
from datetime import datetime
from src.oriental_motor import *
from src.thorlabs_hdr50 import *


################################
from degg_measurements.utils import startIcebootSession
from master_scope import initialize_dual, initialize, setup_plot
from master_scope import take_waveform_block
from master_scope import write_to_hdf5, update_plot, exit_gracefully
from master_scope import add_dict_to_hdf5

from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils.check_laser_freq import light_system_check

from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline

from degg_measurements.analysis import calc_baseline

from degg_measurements.monitoring import readout_sensor

from multi_processing import run_jobs_with_mfhs
################################

from degg_measurements import DATA_DIR



def measure(session, params):
    debug = False
    host = 'localhost'
    port = params['Port']
    filename_l = params['LowerPmt']['filename']

    ## constants - some overrides in main()
    samples = params['samples']
    nevents = params['Constants']['Events']
    try:
        dac_value = params['dac']
    except KeyError:
        dac_value = params['Constants']['DacValue']

    filenames = []
    hvs = []
    baselines = []
    pmt_thresholds = []
    for channel, pmt in zip([0, 1], ['LowerPmt', 'UpperPmt']):
        hvs.append(params[pmt]['HV1e7Gain'])
        filenames.append(params[pmt]['filename'])

        try:
            baseline = float(calc_baseline(
                params[pmt]['BaselineFilename'])['baseline'].values[0])
        except KeyError:
            ##using default
            if dac_value != 30000:
                print(colored(f"Not using DAC at 30000 (current: {dac_value}", 'red'))
                print(colored("No appropriate default!", 'red'))
                exit(1)
            ##corresponds to DAC around 30,000!
            baseline = 8000
            print(colored(
                f"Using default baselines {pmt_baseline0} and {pmt_baseline1}.", "red"))
        baselines.append(baseline)
        pmt_thresholds.append(baseline + params[f'threshold{channel}'])

    filter_strength = params['strength']

    ##temp ---
    channels = [0, 1]
    tags = ['LowerPmt', 'UpperPmt']
    for channel, tag in zip(channels, tags):
        pmt_name = params[tag]['SerialNumber']
        print(f"Start Measuring {port}, {channel}, {pmt_name}")
        session = initialize(session,
                             channel=channel,
                             n_samples=samples,
                             dac_value=dac_value,
                             high_voltage0=hvs[channel],
                             threshold0=pmt_thresholds[channel],
                             modHV=False)
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
                        print("Channel mis-match! WTF!")

                    write_to_hdf5(filenames[trig_channel],
                                  i, xdata, wf,
                                  timestamp, pc_time-ref_time)
                    progress_bar.update(1)
                    i += 1
                    if i >= nevents:
                        break

        temp = readout_sensor(session, 'temperature_sensor')
        params['degg_temp'] = temp
        add_dict_to_hdf5(params, filenames[channel])

    exit_gracefully(session)
    session.close()
    del session


def measure_degg(session, degg_file, degg_dict, constants, dirname,
                 fw_strength, threshold, mode, burst_num,
                 burst_freq, trigger_interval, keys):
    
    degg_dict['Constants'] = constants

    name_u = degg_dict['UpperPmt']['SerialNumber']
    name_l = degg_dict['LowerPmt']['SerialNumber']

    current_dict = deepcopy(degg_dict)
    current_dict['strength'] = fw_strength
    current_dict['threshold0'] = threshold
    current_dict['threshold1'] = threshold
    if mode == 'double':
        current_dict['samples'] = 300
        if fw_strength == 1.0:
            current_dict['dac'] = 2000
        if fw_strength == 0.5:
            current_dict['dac'] = 3000
        if fw_strength == 0.34:
            current_dict['dac'] = 3000
        if fw_strength == 0.25:
            current_dict['dac'] = 3000
    if mode == 'droop':
        current_dict['samples'] = 1000
    current_dict['UpperPmt']['filename'] = os.path.join(
        dirname, name_u + '_' + 'droop' + '.hdf5')
    current_dict['LowerPmt']['filename'] = os.path.join(
        dirname, name_l + '_' + 'droop' + '.hdf5')
    measure(session, current_dict)

    for pmt, key in zip(['LowerPmt', 'UpperPmt'], keys):
        meta_dict = degg_dict[pmt][key]
        meta_dict['Folder'] = dirname
        meta_dict['Filter'] = str(fw_strength)
        meta_dict['Mode'] = str(mode)
        meta_dict['Bursts'] = burst_num
        meta_dict['BurstFrequency'] = burst_freq
        meta_dict['TriggerInterval'] = trigger_interval

    update_json(degg_file, degg_dict)


def measure_pulsed_waveform(run_json, comment, n_jobs, mode=None):
    if mode is None:
        raise Exception("mode option must be configured at run-time: set either 'double' or 'droop'")
    elif mode == 'double':
        measurement_type = "double_pulse"
        print(colored("Running with double-pulse setting", 'yellow'))
    elif mode == 'droop':
        measurement_type = "droop_calibration"
        print(colored("Running with droop setting", 'yellow'))
    else:
        raise Exception("Unable to determine 'mode', exiting...")

    constants = {
        'DacValue': 30000, #noise should be the smallest
        'Events': 5000,
        'Samples': 1024 #gurai 4ns
    }

    #load all degg files
    list_of_deggs = load_run_json(run_json)

    # Create a new area in the json file
    if mode == 'droop':
        meas_key = 'BurstPulse'
    if mode == 'double':
        meas_key = 'DoublePulse'

    ##verify the light system is working before taking data
    light_system_check(500)

    ##sorting session also happens in measure baseline
    session_list = measure_baseline(
        run_json, constants=constants,
        n_jobs=n_jobs, modHV=False,
        return_sessions=True)

    ##filepath for saving data
    dirname = create_save_dir("/home/deggscambox/initialtest/peak_height/", measurement_type=measurement_type)

    strength = 1
    if mode == 'double':
        burst_num = 2
        if float(strength) == 0.01:
            threshold = 150
        elif float(strength) == 0.05:
            threshold = 280 ##2022-11-22, same as linearity
        elif float(strength) == 0.10:
            threshold = 600 #1300, marginally missed one/two PMT
        elif float(strength) == 0.25:
            threshold = 800 #1300, marginally missed one/two PMT
        elif float(strength) == 0.32:
            threshold = 800 #1300, marginally missed one/two PMT
        elif float(strength) == 0.50:
            threshold = 1400
        elif float(strength) == 1.0:
            threshold = 100
        else:
            raise ValueError("No valid strength given for burst mode!")

    burst_freq = 5e7
    trigger_interval =  1.0e-3 #seconds
   

    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        meas_key,
        comment
    )

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        session=session_list,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        constants=constants,
        dirname=dirname,
        fw_strength=strength,
        threshold=threshold,
        mode=mode,
        burst_num=burst_num,
        burst_freq=burst_freq,
        trigger_interval=trigger_interval,
        keys=keys)

    for result in aggregated_results:
        print(result.result())

   
    ##return filter wheel to prev setting
    #print(f"Returning filter wheel to position {fw_info['Position']}")
    #fw.command('pos='+str(fw_info['Position']))



    




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


def measure_r_steps(run_json, commnet, n_jobs, mode, r_step, r_scan_points):
    rotate_slave_address = 5
    r_slave_adress = 3
    r_stage = setup_top_devices(rotate_slave_address, r_slave_adress)
    for event_num, r_point in enumerate(r_scan_points):
        print(r_point)
        measure_pulsed_waveform(run_json, commnet, n_jobs, mode)
        r_stage.moveRelative(r_slave_adress, r_step)
        time.sleep(5)


@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--mode', '-m', default='double')
@click.option('--n_jobs', '-j', default=1)
@click.option('--force',  is_flag=True)

def main(run_json, comment, n_jobs, mode):
    r_step = 3 ##mm
    r_max = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_max, r_step)

    measure_r_steps(run_json, comment, n_jobs, mode, r_step, r_scan_points)    

if __name__ == "__main__":
    main()