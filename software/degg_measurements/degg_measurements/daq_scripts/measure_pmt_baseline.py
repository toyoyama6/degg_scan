import os
import numpy as np
import pandas as pd
from datetime import datetime
import time
import click
from tqdm import tqdm
from copy import deepcopy
from termcolor import colored
import threading

from degg_measurements.daq_scripts.master_scope import initialize, take_waveform
from degg_measurements.daq_scripts.master_scope import write_to_hdf5, exit_gracefully
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs

from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import update_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import MFH_SETUP_CONSTANTS
from degg_measurements.utils.hv_check import checkHV

from degg_measurements.monitoring import readout_sensor

from degg_measurements import DATA_DIR

##provide minimum implementation of measurement
def min_measure_baseline(session, channel, filename, samples=1024,
                         dac_value=30000, hv=1500, nevents=20, modHV=True):
    params = {}
    params['filename'] = filename
    session = initialize(session, channel=channel, n_samples=samples,
                         dac_value=dac_value, high_voltage0=hv, modHV=modHV)
    time.sleep(0.5)
    i = 0
    ref_time = time.monotonic()
    for i in tqdm(range(nevents)):
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
        if session is None:
            break
        write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)
    temp = readout_sensor(session, 'temperature_sensor')
    params['degg_temp'] = float(temp)
    params['name'] = 'minPMT'
    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    return session

# measuring scalar signals with the D-Egg through minifield hub
# alternate measuring the top and bottom PMTs with the same settings
def measure(session, params, mode=None, modHV=True):
    channel = params['channel']
    samples = params['Constants']['BaselineSamples']
    nevents = params['Constants']['BaselineEvents']
    dac_value = params['Constants']['DacValue']
    degg_id = params['DEggSerialNumber']

    ##UpperPmt or LowerPmt
    pmt = params['pmt']

    if mode == 'low_gain':
        filename = params[pmt]['BaselineLowGainFilename']
        hv = params['HVLowGain']
    else:
        filename = params[pmt]['BaselineFilename']
        hv = params['hv']


    ##FIXME
    filename = params['baseline_filename']
    params['filename'] = filename
    pmt_id = params[pmt]['SerialNumber']

    session = initialize(session,
                         channel=channel,
                         n_samples=samples,
                         dac_value=dac_value,
                         high_voltage0=hv,
                         modHV=modHV)

    ref_time = time.monotonic()

    i = 0
    for i in tqdm(range(nevents)):
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
        if session is None:
            break
        if wf is None:
            continue
        write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)

    temp = readout_sensor(session, 'temperature_sensor')
    params['degg_temp'] = float(temp)
    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    time.sleep(0.3)


def measure_degg(session, degg_dict, degg_file, high_voltage, default_voltage,
                 dirname, mode, baseline_constants, modHV=True):
    ##override with measurement specific configs here
    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        ##if mode is for flasher measurements only
        if mode == 'low_gain' and pmt == 'UpperPmt':
            continue

        name = degg_dict[pmt]['SerialNumber']
        baseline_filename = os.path.join(
            dirname, name + '.hdf5')

        if mode == 'low_gain':
            degg_dict[pmt]['BaselineLowGainFilename'] = baseline_filename
        else:
            ##overwrite the current BaselineFilename
            degg_dict[pmt]['BaselineFilename'] = baseline_filename
        update_json(degg_file, degg_dict)

        ##FIXME
        print(degg_dict[pmt]['BaselineFilename'])

        current_dict = deepcopy(degg_dict)
        current_dict['Constants'] = baseline_constants
        current_dict['name'] = name
        current_dict['pmt'] = pmt
        current_dict['channel'] = channel
        current_dict['baseline_filename'] = baseline_filename

        if mode is None:
            ##check user configured high voltage
            if high_voltage is not None:
                current_dict['hv'] = high_voltage
            elif degg_dict[pmt]['HV1e7Gain'] != -1:
                current_dict['hv'] = degg_dict[pmt]['HV1e7Gain']
            else:
                print('HV is neither given nor found in the hv_dict! '
                    f'Using default of {default_voltage}V.')
                current_dict['hv'] = default_voltage
        if mode == 'low_gain':
            if degg_dict[pmt]['HV1e7Gain'] == -1:
                raise ValueError('low gain mode requires known operating voltage!')
            current_dict['HVLowGain'] = int(degg_dict[pmt]['HV1e7Gain'] / 1.3)
            degg_dict[pmt]['HVLowGain'] = current_dict['HVLowGain']

        measure(session, current_dict, mode, modHV)
        update_json(degg_file, degg_dict)


def measure_baseline(run_json, high_voltage=None,
                    #  constants={'DacValue': 30000},
                     constants={'DacValue': 22891},
                     mode=None, n_jobs=1, modHV=True,
                     return_sessions=True,
                     ignoreList=[]):
    baseline_constants = {
        'BaselineSamples': 1024,
        'BaselineEvents': 50
    }
    baseline_constants.update(constants)

    if mode is None:
        measure_type = 'baseline'
    elif mode == 'low_gain':
        measure_type = 'baseline_low_gain'
    else:
        print(f'Could not find setting for mode: {mode}')
        raise NotImplementedError("Mode not implemented!")

    if mode == 'low_gain' and high_voltage != None:
        raise NotImplementedError("To avoid accidents, low_gain mode does not"
                                   " allow configuring HV on the command-line")

    dirname = create_save_dir(DATA_DIR, measure_type)
    baseline_filenames = []

    default_hv = 1500

    #load all degg files
    list_of_deggs = load_run_json(run_json)

    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    sorted_session_list = []
    active_ports = []
    hvOn = 0
    for degg_dict, degg_file in zip(sorted_degg_dicts, sorted_degg_files):
        port = degg_dict['Port']
        if port in ignoreList:
            sorted_session_list.append(None)
            continue
        active_ports.append(port)
        session = startIcebootSession(host='localhost', port=port)
        for pmt, _channel in zip(['LowerPmt', 'UpperPmt'], [0, 1]):
            hv_enabled = checkHV(session, _channel, verbose=True)
            hvOn += hv_enabled
            if hv_enabled == False:
                session.enableHV(_channel)
                set_hv = int(degg_dict[pmt]['HV1e7Gain'])
                if int(degg_dict[pmt]['HV1e7Gain']) == -1:
                    set_hv = default_hv
                session.setDEggHV(_channel, set_hv)
        sorted_session_list.append(session)

    if hvOn < 32:
        print("="*20)
        print(f"Sleeping for HV to ramp before baseline measurement - Active Ports: {active_ports}")
        for i in tqdm(range(40)):
            time.sleep(1)

    ##in series baseline measurement
    print(f'n_jobs = {n_jobs}')
    n_jobs = int(n_jobs)
    if n_jobs >= 1:
        for session, degg_dict, degg_file in zip(sorted_session_list,
                                                 sorted_degg_dicts,
                                                 sorted_degg_files):
            if session == None:
                print(f'session was none in the baseline check!: {degg_dict["Port"]}')
                continue
            measure_degg(session=session,
                         degg_dict=degg_dict,
                         degg_file=degg_file,
                         high_voltage=high_voltage,
                         default_voltage=default_hv,
                         dirname=dirname,
                         mode=mode,
                         baseline_constants=baseline_constants,
                         modHV=modHV)

    ##experimental parallel measurement
    ##not currently working...
    # elif n_jobs > 1:
    #     threads = []
    #     for session, degg_dict, degg_file in zip(session_list, sorted_degg_dicts, sorted_degg_files):
    #         threads.append(threading.Thread(target=measure_degg, args=[session,
    #                                         degg_dict, degg_file, high_voltage,
    #                                         default_hv, dirname, mode, baseline_constants,
    #                                         modHV]))
    #     for t in threads:
    #         t.start()
    #     for t in threads:
    #         t.join()
    else:
        raise ValueError(f'n_jobs (-j) should be 1 or more! Not {n_jobs}')

    if return_sessions:
        return sorted_session_list
    else:
        for session in sorted_session_list:
            if session != None:
                session.close()
        for _ in range(len(sorted_session_list)):
            del sorted_session_list[0]
        return

@click.command()
@click.argument('run_json')
@click.option('-v', '--high_voltage', type=int, default=None)
@click.option('-m', '--mode', type=str, default=None)
@click.option('-j', '--n_jobs', type=int, default=1)
def main(run_json, high_voltage, mode, n_jobs):
    print(f'n_jobs: {n_jobs}')
    if mode == 'low_gain':
        measure_baseline(run_json, high_voltage,
                         constants={'DacValue':30000}, mode=mode,
                         n_jobs=n_jobs)
    else:
        measure_baseline(run_json, high_voltage,
                         n_jobs=n_jobs)


if __name__ == "__main__":
    main()

