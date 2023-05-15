import os
import numpy as np
from datetime import datetime
from iceboot import iceboot_session_cmd
import time
import click
import tables
from tqdm import tqdm
from copy import deepcopy


###
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils.load_dict import check_dirname_in_pmt_dict
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils import startIcebootSession

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature

from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.daq_scripts.master_scope import initialize, take_waveform
from degg_measurements.daq_scripts.master_scope import take_waveform_block
from degg_measurements.daq_scripts.master_scope import write_to_hdf5, exit_gracefully
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.measure_spe import measure as measure_charge_stamp

from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis import fit_charge_hist
from degg_measurements.analysis.gain.analyze_gain import estimate_next_point
from degg_measurements.analysis.spe.analyze_spe import run_fit as fit_charge_stamp_hist
###

from termcolor import colored

from degg_measurements import DATA_DIR

E_CONST = 1.60217662e-7
KEY_NAME = 'GainMeasurement'


def check_approx_trigger_frequency(filename):
    with tables.open_file(filename) as open_f:
        data = open_f.get_node('/data')
        timestamps = data.col('timestamp')
        delta_t = (timestamps[-1] - timestamps[0]) / 240e6
        approx_frequency = len(timestamps) / delta_t
    return approx_frequency


def min_gain_check(session, channel, filename, samples, hv, threshold, dac_value,
                   burn_in, nevents, modHV=True, verbose=False, port=0):
    params = {}
    params['filename'] = filename
    params['unixTime'] = datetime.timestamp(datetime.now())
    if verbose:
        print(f'Threshold for Min Measure Gain Scan: {threshold}')
    session = initialize(session, channel=channel, n_samples=samples,
                         high_voltage0=hv, threshold0=threshold,
                         dac_value=dac_value, burn_in=burn_in, modHV=modHV)
    n_pts = 5
    hv_mon_pre = np.full(n_pts, np.nan)
    if session is not None:
        if channel == 0:
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel0')
        if channel == 1:
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel1')

    ref_time = time.monotonic()
    prev_pc_time = ref_time
    i = 0
    with tqdm(total=nevents) as progress_bar:
        while i <= nevents:
            session, readouts, pc_time = take_waveform_block(session)
            if session is None:
                break
            if readouts is None:
                print("READOUTS IS NONE!")
                continue

            time_since_last_block_readout = pc_time - prev_pc_time
            if (time_since_last_block_readout) > 60:
                print(colored(
                    'Reading out a block took more than 60 seconds!',
                    'red'))
            prev_pc_time = pc_time

            for readout in readouts:
                wf = readout['waveform']
                timestamp = readout['timestamp']
                xdata = np.arange(len(wf))
                readout_channel = readout['channel']
                if readout_channel != channel:
                    raise ValueError(
                        f'Readout channel {readout_channel} does not match '
                        f'with the set channel {channel}!')

                write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)
                progress_bar.update(1)
                i += 1
                if i >= nevents:
                    break

    temp = np.nan
    hv_mon = np.full(n_pts, np.nan)

    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
        if channel == 0:
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel0')
        if channel == 1:
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel1')
    if session is None:
        print(colored("None session object!", 'yellow'))

    params['degg_temp'] = temp
    params['hv_mon_pre'] = str(hv_mon_pre)
    params['hv_mon'] = str(hv_mon)
    params['hv'] = hv
    params['hv_scan_value'] = hv
    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    time.sleep(1)
    return session

def measure(session, params, mode='scan'):
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
    ##ignoring burn in because modHV=True, so will wait for 40s anyway
    burn_in = 0
    params['burnin'] = burn_in

    print(f"Start Measuring port:{port}, channel:{channel}, hv:{hv}V, bl:{baseline}, th:{threshold}")
    if mode != 'check':
        modHV=True
    if mode == 'check':
        modHV=False
        print('NOTE - HV is not modified in check mode...')

    session = initialize(session, channel=channel,
                         n_samples=samples, high_voltage0=hv,
                         threshold0=threshold, dac_value=dac_value,
                         burn_in=burn_in, modHV=modHV)
    n_pts = 5
    hv_mon_pre = np.full(n_pts, np.nan)

    if session is not None:
        if pmt == 'LowerPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel0')
        if pmt == 'UpperPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel1')

    print(f"--- Measuring on Port: {port}:{channel} for PMT: {pmt_id} ---")
    print(f'HV is currently {np.mean(hv_mon_pre)} V for {port}:{channel}')
    if np.mean(hv_mon_pre) <= 1000:
        print(f'--- HV is too low on {port}:{channel}! {np.mean(hv_mon_pre)} V')
        ##already 1 exception observed where HV is low, but performance looks normal!
        params['lowHV'] = True

        #raise ValueError(f'--- HV is too low on {port}:{channel}! {np.mean(hv_mon_pre)} V')

    ref_time = time.monotonic()
    prev_pc_time = ref_time
    i = 0
    with tqdm(total=nevents) as progress_bar:
        while i <= nevents:
            session, readouts, pc_time = take_waveform_block(session)
            if session is None:
                break
            if readouts is None:
                print("READOUTS IS NONE!")
                continue

            time_since_last_block_readout = pc_time - prev_pc_time
            if (time_since_last_block_readout) > 60:
                print(colored(
                    'Reading out a block took more than 60 seconds!',
                    'red'))
            prev_pc_time = pc_time

            for readout in readouts:
                wf = readout['waveform']
                timestamp = readout['timestamp']
                xdata = np.arange(len(wf))
                readout_channel = readout['channel']
                if readout_channel != channel:
                    raise ValueError(
                        f'Readout channel {readout_channel} does not match '
                        f'with the set channel {channel}!')

                write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)
                progress_bar.update(1)
                i += 1
                if i >= nevents:
                    break

    temp = np.nan
    hv_mon = np.full(n_pts, np.nan)

    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
        if pmt == 'LowerPmt':
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel0')
        if pmt == 'UpperPmt':
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel1')
    if session is None:
        print(colored(f"None session object for Port: {port}!", 'yellow'))

    params['degg_temp'] = temp
    params['hv_mon_pre'] = str(hv_mon_pre)
    params['hv_mon'] = str(hv_mon)
    params['hv'] = hv
    add_dict_to_hdf5(params, params['filename'])
    time.sleep(1)


def calculate_gain(filename, pmt, pmt_id, config):
    if config == 'waveform':
        fit_info = fit_charge_hist(filename, pmt, pmt_id, save_fig=False)
    elif config == 'stamp':
        fit_info, center, hist = fit_charge_stamp_hist(filename, pmt, pmt_id, degg_id='', save_fig=False)

    gain = fit_info['popt'][1] / E_CONST
    gain_err = fit_info['pcov'][1, 1] / E_CONST
    return gain, gain_err


def measure_degg(session,
                 degg_file,
                 degg_dict,
                 dirname,
                 constants,
                 mode,
                 n_checks,
                 config,
                 keys):
    #if audit_ignore_list(degg_file, degg_dict, keys[0]) == True:
       # return

    degg_dict['Constants'] = constants


    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        # Do some setup and json file bookkeeping
        threshold = 25
        name = degg_dict[pmt]['SerialNumber']

        dirname_exists = check_dirname_in_pmt_dict(dirname,
                                                   degg_dict[pmt],
                                                   KEY_NAME)
        if dirname_exists:
            print(f'Directory: {dirname} already exists in the D-Egg'
                  f'dict. Skipping {pmt}.')
            continue

        print(f'Collecting {config} events!')
        meta_dict = degg_dict[pmt][keys[channel]]
        meta_dict['mode'] = mode
        meta_dict['config'] = config

        # Before measuring check the D-Egg surface temp

        meta_dict['Folder'] = dirname

        baseline_filename = degg_dict[pmt]['BaselineFilename']
        meta_dict['BaselineFilename'] = baseline_filename
        meta_dict['Baseline'] = \
            float(calc_baseline(baseline_filename)['baseline'].values[0])

        ##want to seed the scan - some PMTs have very low HV requirements
        if mode == 'scan':
            hv_scan = int(degg_dict[pmt]['HV1e7Gain'])
            if hv_scan <= 0:
                hv_scan = 1500
        elif mode == 'check':
            hv_scan = int(degg_dict[pmt]['HV1e7Gain'])

        converged = False
        nominal_gain = 1e7
        hv_points = 0
        hv_scan_values = []
        prev_failed_attempts = []
        gain_values = []
        gain_err_values = []

        already_retry = False
        while not converged:
            current_dict = deepcopy(degg_dict)
            current_dict['Constants'] = constants
            current_dict['channel'] = channel
            current_dict['pmt'] = pmt
            current_dict['measurement'] = keys[channel]
            current_dict['threshold_over_baseline'] = threshold
            current_dict['hv_scan_value'] = hv_scan
            current_dict['hv'] = hv_scan ##charge stamp method looks for this key

            filename = os.path.join(
                dirname, name + f'_{hv_scan}V' + '.hdf5')
            valid_file_found = False
            counter = 0
            while not valid_file_found:
                if not os.path.isfile(filename):
                    break
                else:
                    if counter == 0:
                        counter += 1
                        filename = filename.replace('.hdf5',
                                                    f'_{counter:02d}.hdf5')
                    else:
                        counter += 1
                        filename = filename.replace(f'_{counter-1:02d}.hdf5',
                                                    f'_{counter:02d}.hdf5')

            current_dict['filename'] = filename

            ##switch config point - waveforms or charge stamp
            if config == 'waveform':
                measure(session, current_dict, mode)
            elif config == 'stamp':
                measure_charge_stamp(session, current_dict)
            else:
                raise NotImplementedError(f'Configuration Choice Not supported!: {config}')

            # Check the observed data rate from the output file. If the observed rate is
            # below 200Hz it is a possible indication for the HV being far too low and
            # the PMT only/mostly triggering on atmospheric muons and not on dark-noise
            freq = check_approx_trigger_frequency(current_dict['filename'])
            if freq < 200:
                hv_scan = np.minimum(hv_scan + 200, 2000)
                if hv_scan in prev_failed_attempts:
                    raise ValueError(
                        f'Failed to obtain darknoise gain data with more '
                        f'than 200 Hz the same HV of {hv_scan}! '
                        f'Please investigate PMT '
                        f'{current_dict[pmt]["SerialNumber"]}.')
                else:
                    prev_failed_attempts.append(hv_scan)
                    continue


            try:
                gain, gain_err = calculate_gain(current_dict['filename'], pmt,
                                            current_dict[pmt]['SerialNumber'],
                                            config)
            except:
                print("File Error while calculating gain! Try again")
                if not already_retry:
                    already_retry = True
                    continue
                if already_retry:
                    break
            print(f'Current gain is {gain}.')

            hv_scan_values.append(hv_scan)
            gain_values.append(gain)
            gain_err_values.append(gain_err)
            hv_points += 1

            if mode == 'check':
                if hv_points >= n_checks:
                    break
                else:
                    continue

            hv_scan = estimate_next_point(hv_scan_values, gain_values,
                                          gain_err_values, nominal_gain)

            if hv_scan == -1:
                print('Terminating gain scan, because next HV value '
                      'can not be estimated')
                converged = True

            if (np.abs(gain - nominal_gain) / gain) < 0.02 and hv_points >= 5:
                converged = True

            if hv_scan in hv_scan_values:
                print('Terminating gain scan, because same HV value '
                      'is attempted to be run twice!')
                converged = True

            if hv_points >= 10:
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


def measure_gain(run_json, comment, n_jobs=1, resume=False, mode='scan', n_checks=1, configuration='waveform', test=False):
    ##get function generator - turn laser off

    constants = {
        'Samples': 128,
        'Events': 10000,
        'DacValue': 30000
    }

    session_list = measure_baseline(
        run_json,
        constants=constants,
        n_jobs=n_jobs,
        modHV=False,
        return_sessions=True
    )

    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')


    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    if resume:
        print('Getting dirname from resume')
        dirname = get_recent_dirname_from_degg_dicts(sorted_degg_dicts, KEY_NAME)
    else:
        print('Creating new dirname')
        measure_type = 'gain_online'
        dirname = create_save_dir(DATA_DIR, measure_type)
    print(f'dirname: {dirname}')

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        KEY_NAME,
        comment
    )

    if test:
        measure_degg(
            session=session_list[0],
            degg_file=sorted_degg_files[0],
            degg_dict=sorted_degg_dicts[0],
            dirname=dirname,
            constants=constants,
            mode=mode,
            n_checks=n_checks,
            config=configuration,
            keys=keys
        )
    else:
        aggregated_results = run_jobs_with_mfhs(
            measure_degg,
            n_jobs,
            session=session_list,
            degg_file=sorted_degg_files,
            degg_dict=sorted_degg_dicts,
            dirname=dirname,
            constants=constants,
            mode=mode,
            n_checks=n_checks,
            config=configuration,
            keys=keys
        )

        for result in aggregated_results:
            print(result.result())


@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('-j', '--n_jobs', default=1)
@click.option('-r', '--resume', is_flag=True)
@click.option('-m', '--mode',
              type=click.Choice(['scan', 'check'],
              case_sensitive=False),
              default='scan')
@click.option('-n', '--n_checks', default=1)
@click.option('-c', '--configuration',
              type=click.Choice(['waveform', 'stamp'],
              case_sensitive=False),
              default='waveform')
@click.option('--force', is_flag=True)
@click.option('--test', is_flag=True)
def main(run_json, comment, n_jobs, resume, mode, n_checks, configuration, force, test):
    measure_gain(
        run_json,
        comment,
        n_jobs,
        resume,
        mode,
        n_checks,
        configuration,
        test
    )


if __name__ == "__main__":
    main()

