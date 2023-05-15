import os
import numpy as np
from datetime import datetime
from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from master_scope import initialize, take_waveform
from master_scope import write_to_hdf5, exit_gracefully
from master_scope import add_dict_to_hdf5
import time
import click
from tqdm import tqdm
from copy import deepcopy
from scipy.interpolate import interp1d
from scipy.optimize import brentq
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature

from measure_pmt_baseline import measure_baseline
from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis import fit_charge_hist
from degg_measurements.analysis import calculate_hv_at_1e7_gain

from concurrent.futures import ProcessPoolExecutor, wait
from concurrent.futures import ThreadPoolExecutor

from termcolor import colored


E_CONST = 1.60217662e-7
KEY_NAME = 'GainMeasurement'


def measure(params):
    host = 'localhost'
    port = params['Port']
    channel = params['channel']
    samples = params['Constants']['Samples']
    threshold_over_bl = params['threshold_over_baseline']
    nevents = params['Constants']['Events']
    dac_value = params['Constants']['DacValue']
    filename = params['filename']
    pmt = params['pmt']
    hv = params['hv_scan_value']
    meas_key = params['measurement']
    baseline = params[pmt][meas_key]['Baseline']
    threshold = int(threshold_over_bl + baseline)
    params['threshold'] = threshold
    pmt_id = params[pmt]['SerialNumber']

    print(f"Start Iceboot Session for {params}")
    session = startIcebootSession(host=host, port=port)
    session = initialize(session, channel=channel, 
                         n_samples=samples, high_voltage0=hv,
                         threshold0=threshold, dac_value=dac_value)

    print(f"--- Measuring on Port: {port} for PMT: {pmt_id} ---")

    ref_time = time.time()
    for i in tqdm(range(nevents)):
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
        if session is None:
            break
        if wf is None:
            continue
        # Fix for 0x6a firmware
        if len(wf) != samples:
            continue

        write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)

    temp = -1
    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
    if session is None:
        print(color(f"None session object for Port: {port}!"), 'yellow')

    params['degg_temp'] = temp
    add_dict_to_hdf5(params, params['filename'])
    exit_gracefully(session)
    session.close()
    del session
    time.sleep(5)


def calculate_gain(filename, pmt):
    fit_info = fit_charge_hist(filename, pmt, save_fig=False)
    gain = fit_info['popt'][1] / E_CONST
    gain_err = fit_info['pcov'][1, 1] / E_CONST
    return gain, gain_err


def estimate_next_point(hv_values, gain_values, gain_err_values,
                        nominal_gain):
    bounds = [1250, 1950]
    if len(gain_values) <= 2:
        volt_step = 40
        if gain_values[-1] < nominal_gain:
            new_hv = hv_values[-1] + volt_step
            while new_hv in hv_values:
                new_hv += volt_step
        else:
            new_hv = hv_values[-1] - volt_step
            while new_hv in hv_values:
                new_hv -= volt_step
    else:
        try:
            _, _, _, hv_at_1e7_gain = calculate_hv_at_1e7_gain(
                hv_values,
                np.asarray(gain_values)*E_CONST,
                np.asarray(gain_err_values)*E_CONST)
            new_hv = hv_at_1e7_gain
        except RuntimeError:
            min_gain_idx = np.argmin(gain_values)
            max_gain_idx = np.argmax(gain_values)
            gain_f = interp1d([hv_values[min_gain_idx], hv_values[max_gain_idx]],
                              np.log10([gain_values[min_gain_idx],
                                        gain_values[max_gain_idx]]) - 7,
                              fill_value='extrapolate')
            try:
                new_hv = brentq(gain_f,
                                bounds[0], bounds[1])
            except ValueError:
                return -1

    new_hv = np.maximum(new_hv, bounds[0])
    new_hv = np.minimum(new_hv, bounds[1])
    return new_hv


def measure_degg(degg_file, degg_dict, dirname, comment, constants):
    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        # # # # # # # # # # # # # # # # # # # # # # # # #
        # Do some setup and json file bookkeeping
        # # # # # # # # # # # # # # # # # # # # # # # # #
        threshold = 25
        name = degg_dict[pmt]['SerialNumber']

        dirname_exists = check_dirname_in_pmt_dict(dirname,
                                                   degg_dict[pmt],
                                                   KEY_NAME)
        if dirname_exists:
            continue

        key = create_key(degg_dict[pmt], KEY_NAME)
        degg_dict[pmt][key] = dict()
        print(key)
        degg_dict[pmt][key]['mode'] = 'Scan'

        # Before measuring check the D-Egg surface temp
        # TODO: move device path to config file ? 
        #degg_dict[pmt][key]['DEggSurfaceTemp'] = readout_temperature(
        #    device='/dev/ttyUSB1', channel=1)
        #degg_dict[pmt][key]['BoxSurfaceTemp'] = readout_temperature(
        #    device='/dev/ttyUSB1', channel=2)

        degg_dict[pmt][key]['Folder'] = dirname

        baseline_filename = degg_dict[pmt]['BaselineFilename']
        degg_dict[pmt][key]['BaselineFilename'] = baseline_filename
        degg_dict[pmt][key]['Baseline'] = \
            float(calc_baseline(baseline_filename)['baseline'].values[0])
        degg_dict[pmt][key]['Comment'] = comment
        # # # # # # # # # # # # # # # # # # # # # # # # #
        # # # # # # # # # # # # # # # # # # # # # # # # #
        # # # # # # # # # # # # # # # # # # # # # # # # #

        converged = False
        nominal_gain = 1e7
        hv_points = 0
        hv_scan = 1500
        hv_scan_values = []
        gain_values = []
        gain_err_values = []

        while not converged:
            current_dict = deepcopy(degg_dict)
            current_dict['Constants'] = constants
            current_dict['channel'] = channel
            current_dict['filename'] = os.path.join(
                dirname, name + f'_{hv_scan}V' + '.hdf5')
            current_dict['pmt'] = pmt
            current_dict['measurement'] = key
            current_dict['threshold_over_baseline'] = threshold
            current_dict['hv_scan_value'] = hv_scan

            if os.path.isfile(current_dict['filename']):
                os.rename(current_dict['filename'],
                          current_dict['filename'].replace('.hdf5', '_bkp.hdf5'))

            measure(current_dict)
            gain, gain_err = calculate_gain(current_dict['filename'], pmt)

            hv_scan_values.append(hv_scan)
            gain_values.append(gain)
            gain_err_values.append(gain_err)
            hv_points += 1

            hv_scan = estimate_next_point(hv_scan_values, gain_values,
                                          gain_err_values, nominal_gain)

            if hv_scan == -1:
                print('Terminating gain scan, because next HV value '
                      'can not be estimated')
                converged = True

            if (np.abs(gain - nominal_gain) / gain) < 0.02 and hv_points >= 3:
                converged = True

            if hv_scan in hv_scan_values:
                print('Terminating gain scan, because same HV value '
                      'is attempted to be run twice!')
                converged = True

            if hv_points >= 8:
                converged = True
            
        update_json(degg_file, degg_dict)


def get_recent_dirname_from_degg_dicts(degg_dicts, key_name):
    # Grab key related to this measurement from all dicts
    total_cts = []
    for degg_dict in degg_dicts:
        for pmt in ['LowerPmt', 'UpperPmt']:
            relevant_keys = [key for key in degg_dict[pmt].keys()
                             if key.startswith(key_name)]
            cts = [int(key.split('_')[1]) for key in relevant_keys]
            total_cts.extend(cts)

    if len(total_cts) == 0:
        raise ValueError(f'No previous {key_name} measurement found! '
                         'Can not resume.')

    measurement_number = np.max(total_cts)
    key = key_name + f'_{measurement_number:02d}'
    for degg_dict in degg_dicts:
        for pmt in ['LowerPmt', 'UpperPmt']:
            try:
                meas_dict = degg_dict[pmt][key]
            except KeyError:
                continue
            else:
                dirname = meas_dict['Folder']
                return dirname


def check_dirname_in_pmt_dict(dirname, pmt_dict, key_name):
    relevant_keys = [key for key in pmt_dict.keys()
                     if key.startswith(key_name)]
    dirname_exists = False
    for key in relevant_keys:
        if pmt_dict[key]['Folder'] == dirname:
            dirname_exists = True
            return dirname_exists
    return dirname_exists


def measure_gain(run_json, comment, n_jobs=1, resume=False):
    constants = {
        'Samples': 128,
        'Events': 10000,
        'DacValue': 30000
    }
    bl_names = measure_baseline(run_json, constants=constants,
                                n_jobs=n_jobs)


    list_of_deggs = load_run_json(run_json)

    print(f'n_jobs: {n_jobs}')

    degg_dicts = []
    ports = []
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        degg_dicts.append(degg_dict)
        port = int(degg_dict['Port'])
        ports.append(port)

    if resume:
        dirname = get_recent_dirname_from_degg_dicts(degg_dicts, KEY_NAME)
    else:
        filepath = os.path.expandvars("$HOME/data/fat_calibration/")
        measure_type = 'gain_online'
        dirname = create_save_dir(filepath, measure_type)

    sort_idx = np.argsort(ports)
    sorted_degg_dicts = np.array(degg_dicts)[sort_idx]
    sorted_degg_files = np.array(list_of_deggs)[sort_idx]

    n_per_wp = 4
    n_wirepairs = 4
    aggregated_results = []
    for i in range(n_per_wp):
        degg_dicts_i = sorted_degg_dicts[i::n_wirepairs]
        degg_files_i = sorted_degg_files[i::n_wirepairs]

        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = []
            for degg_dict_i, degg_file_i in zip(degg_dicts_i, degg_files_i):
                port = int(degg_dict_i['Port'])
                print(f"Port: {port}")
                print("Submitting measure_degg (online gain)")

                futures.append(
                    executor.submit(
                        measure_degg,
                        degg_file=degg_file_i,
                        degg_dict=degg_dict_i,
                        dirname=dirname,
                        comment=comment,
                        constants=constants))
        results = wait(futures)
        aggregated_results.extend(results.done)

    for result in aggregated_results:
        print(result.result())


def measure_gain_scan(run_json, comment, n_jobs=1):
    measure_gain(run_json, comment, n_jobs, 'gain_scan')


def measure_gain_check(run_json, comment, n_jobs=1):
    measure_gain(run_json, comment, n_jobs, 'gain_check')


@click.command()
@click.argument('run_json')
@click.option('-j', '--n_jobs', default=1)
@click.argument('comment')
@click.option('-r', '--resume', is_flag=True)
def main(run_json, comment, n_jobs, resume):
    measure_gain(run_json, comment, n_jobs, resume)


if __name__ == "__main__":
    main()
