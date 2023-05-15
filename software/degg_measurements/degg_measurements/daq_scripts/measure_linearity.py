import os, sys
from datetime import datetime
import time
import click
from copy import deepcopy
import json
import numpy as np
from tqdm import tqdm
from termcolor import colored
from concurrent.futures import ProcessPoolExecutor, wait

####
from master_scope import initialize_dual, initialize, setup_plot
from master_scope import take_waveform_block
from master_scope import write_to_hdf5, update_plot, exit_gracefully
from master_scope import add_dict_to_hdf5

from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import update_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.filter_wheel_helper import setup_fw
from degg_measurements.utils.filter_wheel_helper import change_filter_str
from degg_measurements.utils.filter_wheel_helper import create_str_list
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.monitoring import readout_sensor
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.analysis import calc_baseline
from degg_measurements import DATA_DIR
from degg_measurements.utils.check_laser_freq import light_system_check

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

##measuring MPE level signals with the D-Egg through minifield hub
##alternate measuring the top and bottom PMTs with the same settings

def measure(session, params):
    debug = False
    host = 'localhost'
    port = params['Port']
    filename_u = params['UpperPmt']['filename']
    filename_l = params['LowerPmt']['filename']

    ## constants - some overrides in main()
    samples = params['Constants']['Samples']
    nevents = params['Constants']['Events']
    dac_value = params['Constants']['DacValue']

    hv_l = params['LowerPmt']['HV1e7Gain']
    hv_u = params['UpperPmt']['HV1e7Gain']

    try:
        pmt_baseline0 = float(calc_baseline(
            params['LowerPmt']['BaselineFilename'])['baseline'].values[0])
        pmt_baseline1 = float(calc_baseline(
            params['UpperPmt']['BaselineFilename'])['baseline'].values[0])
    except KeyError:
        ##using default
        if dac_value != 5000:
            print(colored(f"Not using DAC at 5000 (current: {dac_value}) - no appropriate default!", 'red'))
            exit(1)
        ##corresponds to DAC around 30,000!
        pmt_baseline0 = 8000
        pmt_baseline1 = 8000
        print(colored(f"Using default baselines {pmt_baseline0} and {pmt_baseline1}.", "red"))

    threshold0 = params['threshold0']
    pmt_threshold0 = pmt_baseline0 + threshold0
    threshold1 = params['threshold1']
    pmt_threshold1 = pmt_baseline1 + threshold1

    filter_strength = params['strength']

    ##temp ---
    channels = [0, 1]
    tags = ['LowerPmt', 'UpperPmt']
    for channel, tag in zip(channels, tags):
        pmt_name = params[tag]['SerialNumber']
        print(f"Start Measuring {port}, {channel}, {pmt_name}, {filter_strength}")
    ##issue due to buffer in dual readout?
    #session = initialize_dual(session, n_samples=samples, dac_value=dac_value,
    #                high_voltage0=hv0, high_voltage1=hv1, threshold0=pmt_threshold0,
    #                threshold1=pmt_threshold1)
        if channel == 0:
            session = initialize(session, channel=channel, n_samples=samples, dac_value=dac_value,
                                    high_voltage0=hv_l, threshold0=pmt_threshold0, modHV=False)
        if channel == 1:
            session = initialize(session, channel=channel, n_samples=samples, dac_value=dac_value,
                                    high_voltage0=hv_u, threshold0=pmt_threshold1, modHV=False)

        ref_time = time.time()

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
                        print("Channel mis-match!")

                    if trig_channel == 0:
                        write_to_hdf5(filename_l, i, xdata,
                            wf, timestamp, pc_time-ref_time)
                    if trig_channel == 1:
                        write_to_hdf5(filename_u, i, xdata,
                            wf, timestamp, pc_time-ref_time)

                    progress_bar.update(1)
                    i += 1
                    if i >= nevents:
                        break

        temp = readout_sensor(session, 'temperature_sensor')
        params['degg_temp'] = temp
        if channel == 0:
            add_dict_to_hdf5(params, filename_l)
        if channel == 1:
            add_dict_to_hdf5(params, filename_u)
    ##end channel for loop -- temp
    time.sleep(1)


def measure_degg(degg_file, degg_dict, constants, keys, dirname,
                 fw_strength, threshold,
                 valid_strengths, thresholds, laser_freq):
    if audit_ignore_list(degg_file, degg_dict, keys[0]) == True:
        return
    degg_dict['Constants'] = constants
    name_u = degg_dict['UpperPmt']['SerialNumber']
    name_l = degg_dict['LowerPmt']['SerialNumber']

    port = degg_dict['Port']
    hvList = [
        degg_dict['LowerPmt']['HV1e7Gain'],
        degg_dict['UpperPmt']['HV1e7Gain']
    ]
    session = startIcebootSession(host='localhost', port=port)

    hvOn = 0
    for _channel in [0, 1]:
        hv_enabled = checkHV(session, _channel)
        hvOn += hv_enabled
        if hv_enabled == False:
            session.enableHV(_channel)
            session.setDEggHV(_channel, int(hvList[_channel]))

    if hvOn < 2:
        print("Waiting for HV to ramp")
        for t in tqdm(range(40)):
            time.sleep(1)

    current_dict = deepcopy(degg_dict)
    current_dict['strength'] = fw_strength
    current_dict['threshold0'] = threshold
    current_dict['threshold1'] = threshold
    current_dict['UpperPmt']['filename'] = os.path.join(
        dirname, name_u + '_' + str(fw_strength) + '.hdf5')
    current_dict['LowerPmt']['filename'] = os.path.join(
        dirname, name_l + '_' + str(fw_strength) + '.hdf5')
    measure(session, current_dict)

    # After the measurement was successful fill the dirname
    for pmt, key in zip(['LowerPmt', 'UpperPmt'], keys):
        degg_dict[pmt][key]['Folder'] = dirname

    update_json(degg_file, degg_dict)
    session.endStream()
    session.close()
    del session
    return


def measure_linearity(run_json, comment, n_jobs):
    constants = {
        'DacValue': 5000,
        'Events': 5000,
        # 'Events': 500,
        'Samples': 128
    }
    ##sessions are not returned, but HV should still be conserved
    measure_baseline(run_json, constants=constants,
                     n_jobs=n_jobs, modHV=False,
                     return_sessions=False)

    ##open must happen AFTER baseline, to get newest file
    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')

    # filepath for saving data
    measurement_type = "linearity"
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    meas_key = 'LinearityMeasurement'

    # setup filter wheel
    fw0, fw1, validList = setup_fw(get_list=True)
    valid_strengths = create_str_list(validList)

    ##DEPRECATED!
    # thresholds = [35, 140, 550, 1300, 2000, 2500] # 3000
    #thresholds = [350, 700, 1300, 1300, 2000, 2500] # 3000
    ##new size is 10!, not 6
    ##thresholds as of 2022-10-24
    #thresholds = [50, 135, 280, 600, 650, 700, 1150, 1200, 1600, 2100] # 3000
    thresholds = [40, 95, 280, 600, 650, 700, 1150, 1200, 1600, 2100] # 3000

    if len(valid_strengths) != len(thresholds):
        raise ValueError(f'Lengths of thresholds and filter settings should be the same!')

    # configure function generator
    laser_freq = 100 #Hz
    fg = FG3101()
    fg.startup()
    fg.waveform_frequency(laser_freq)


    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int,
        return_sorting_index=False)

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        meas_key,
        comment,
        laserFreq=laser_freq
    )

    aggregated_results = []
    for strength, threshold in zip(valid_strengths, thresholds):
        str0, str1 = strength
        fw_strength = float(str0) * float(str1)
        change_filter_str(fw0, str0, fw1, str1)

        ##verify the light system is working before taking data
        light_system_check()

        ##measure all D-Eggs before moving the filter
        results = run_jobs_with_mfhs(
            measure_degg,
            n_jobs,
            force_static=['valid_strengths', 'thresholds'],
            degg_file=sorted_degg_files,
            degg_dict=sorted_degg_dicts,
            dirname=dirname,
            constants=constants,
            keys=keys,
            fw_strength=fw_strength,
            threshold=threshold,
            valid_strengths=valid_strengths,
            thresholds=thresholds,
            laser_freq=laser_freq)

        aggregated_results.extend(results)
        time.sleep(1)

    for result in aggregated_results:
        print(result.result())

    ##disabling laser output
    print("Measurement Finished - Disabling Laser Output")
    fg.disable()

@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=1)
@click.option('--force', is_flag=True)
def main(run_json, comment, n_jobs, force):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')
    measure_linearity(run_json, comment, n_jobs)


if __name__ == "__main__":
    main()

##end
