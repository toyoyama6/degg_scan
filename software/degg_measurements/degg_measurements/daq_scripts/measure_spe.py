import os, sys
import click
import json
import requests
from glob import glob
from copy import deepcopy
import numpy as np
import time
from tqdm import tqdm
import tables
from termcolor import colored
from datetime import datetime

from chiba_slackbot import send_message
from chiba_slackbot import send_warning

from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from degg_measurements.daq_scripts.master_scope import initialize, initialize_dual
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_default_meas_dict
#from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils.load_dict import check_dirname_in_pmt_dict
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.flash_fpga import loadFPGA
from degg_measurements.utils.control_data_charge import write_chargestamp_to_hdf5

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature

from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline


from degg_measurements.analysis.gain.analyze_gain import run_fit as fit_charge_hist
from degg_measurements.analysis.gain.analyze_gain import estimate_next_point
from degg_measurements.analysis import calc_baseline

from degg_measurements import DATA_DIR

E_CONST = 1.60217662e-7
KEY_NAME = 'SpeMeasurement'

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

def quick_baseline(session, channel, hv, dac_value, pmt_name,
                     rep, dirname, verbose, modHV=False, setRep=0):
    bl_file0 = os.path.join(dirname, f'{pmt_name}_baseline_{hv}_{rep}i_{setRep}.hdf5')
    while os.path.exists(bl_file0):
        setRep += 1
        bl_file0 = os.path.join(dirname, f'{pmt_name}_baseline_{hv}_{rep}i_{setRep}.hdf5')
    if verbose:
        print(f"Measure Baseline {pmt_name}")
    session = min_measure_baseline(session, channel, bl_file0, 1024, dac_value,
                                   hv, nevents=100, modHV=modHV)
    baseline = calc_baseline(bl_file0)['baseline'].values[0]
    if verbose:
        print(f"Baseline {pmt_name}: {baseline}")
    return baseline


def min_charge_stamp_gain_calibration(session, channel, dirname, name, hv,
                                      threshold, dac_value, burn_in, nevents,
                                      iteration, mode='scan', modHV=True, verbose=False):
    fileList = []
    converged = False
    nominal_gain = 1e7
    hv_points = 0
    hv_scan_values = []
    gain_values = []
    gain_err_values = []

    pmts = ['LowerPmt', 'UpperPmt']
    pmt = pmts[channel]

    prev_hv = hv
    fig_dir_path = os.path.join(dirname, f'figs_{iteration}')
    ##multi-threading catch
    if not os.path.exists(fig_dir_path):
        try:
            os.mkdir(fig_dir_path)
        except:
            pass

    if nevents > 10000:
        splitData = True
    else:
        splitData = False

    while not converged:
        filename = os.path.join(dirname, name + f'_chargeStamp_{hv}_{iteration}i_{hv_points}' + '.hdf5')
        valid_file_found = False
        counter = 0
        while not valid_file_found:
            if not os.path.isfile(filename):
                break
            else:
                if counter == 0:
                    counter += 1
                    filename = filename.replace('.hdf5', f'_{counter:02d}.hdf5')
                else:
                    counter += 1
                    filename = filename.replace(f'_{counter-1:02d}.hdf5', f'_{counter:02d}.hdf5')
        params = {}
        params['filename'] = filename
        params['unixTime'] = datetime.timestamp(datetime.now())
        fileList.append(filename)
        ##measure baseline
        dac_value = 30000
        pmt_name = name
        rep = 0
        verbose = False
        print(f'Threshold for Min Measure Gain Scan: {threshold}')
        if modHV == False:
            if hv_points == 0:
                time.sleep(1)
            else:
                session.setDEggHV(channel, int(hv))
                sleep_time = np.ceil(np.abs(prev_hv - hv) / 50) + 5
                print(f'Sleeping for HV to change: {prev_hv}V, {hv}V, --> {sleep_time}s')
                time.sleep(sleep_time)
        baseline = quick_baseline(session=session, channel=channel, hv=hv,
                                  dac_value=dac_value, pmt_name=pmt_name,
                                  rep=rep, dirname=dirname, verbose=verbose)
        threshold = int(baseline + 25)
        if threshold == None:
                raise ValueError('Threshold can not be None!')
        if channel == 0:
            threshold1 = 15000
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                          high_voltage0=hv, high_voltage1=0,
                          threshold0=threshold, threshold1=threshold1,
                          burn_in=burn_in, modHV=modHV)

        if channel == 1:
            threshold0 = 15000
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                          high_voltage0=0, high_voltage1=hv,
                          threshold0=threshold0, threshold1=threshold,
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
        if verbose:
            print(f'HV Mon {name}: {hv_mon_pre}')

        if splitData == False:
            try:
                block = session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=120)
            except OSError as e:
                temp = readout_sensor(session, 'temperature_sensor')
                print(f'DEggReadChargeBlock timed out. \n'
                      f'Channel: {channel} \n'
                      f'Threshold: {threshold} \n'
                      f'HV (set): {hv} \n'
                      f'HV (mon): {hv_mon_pre} \n'
                      f'MB temperature: {temp}')
                raise
            charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
            timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
        if splitData == True:
            nblocks = np.ceil(nevents/400)
            charges = np.array([])
            timestamps = np.array([])
            for b in range(int(nblocks)):
                try:
                    block = session.DEggReadChargeBlock(10, 15, 14*400, timeout=120)
                except OSError as e:
                    temp = readout_sensor(session, 'temperature_sensor')
                    print(f'DEggReadChargeBlock timed out. \n'
                          f'Channel: {channel} \n'
                          f'Threshold: {threshold} \n'
                          f'HV (set): {hv} \n'
                          f'HV (mon): {hv_mon_pre} \n'
                          f'MB temperature: {temp}')
                    raise
                _charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
                _timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
                charges = np.append(charges, _charges)
                timestamps = np.append(timestamps, _timestamps)

        write_chargestamp_to_hdf5(filename, charges, timestamps)
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
            print(colored(f"None session object for Port: {port}!"), 'yellow')

        params['degg_temp'] = temp
        params['hv'] = hv
        params['hv_mon_pre'] = str(hv_mon_pre)
        params['hv_mon'] = str(hv_mon)
        add_dict_to_hdf5(params, params['filename'])

        fit_info = fit_charge_hist(filename, pmt=pmt, pmt_id=pmt_name, save_fig=True,
                                   chargeStamp=True, ext_fig_path=fig_dir_path)
        gain = fit_info['popt'][1] / E_CONST
        gain_err = fit_info['pcov'][1, 1] / E_CONST
        hv_scan_values.append(hv)
        gain_values.append(gain)
        gain_err_values.append(gain_err)
        if mode == 'check':
            session.endStream()
            return session, fileList, gain_values, hv_scan_values

        hv_points += 1
        hv_scan = estimate_next_point(hv_scan_values, gain_values, gain_err_values, nominal_gain)
        if hv_scan == -1:
            print('Terminating gain scan, because next HV value '
                  'can not be estimated')
            converged = True
        if (np.abs(gain - nominal_gain) / gain) < 0.03 and hv_points >= 3:
            converged = True
        if hv_scan in hv_scan_values:
            print('Terminating gain scan, because same HV value '
                  'is attempted to be run twice!')
            converged = True
        if hv_points >= 6:
            converged = True
        ##update hv to next point
        prev_hv = hv
        hv = hv_scan
        ##anyway the stream gets rebuilt
        session.endStream()

    session.endStream()
    return session, fileList, gain_values, hv_scan_values


def measure(session, params):
    host = 'localhost'
    port = params['Port']
    channel = params['channel']
    threshold_over_bl = params['threshold_over_baseline']
    nevents = params['Constants']['Events']
    dac_value = params['Constants']['DacValue']
    filename = params['filename']
    pmt = params['pmt']
    hv = params['hv']
    meas_key = params['measurement']
    baseline = params[pmt][meas_key]['Baseline']
    threshold = int(threshold_over_bl + baseline)
    params['threshold'] = threshold
    pmt_id = params[pmt]['SerialNumber']

    session = initialize(session, channel=channel,
                        high_voltage0=hv, n_samples=128,
                        threshold0=threshold, dac_value=dac_value,
                        burn_in=int(10), modHV=False)

    n_pts = 5
    hv_mon_pre = np.full(n_pts, np.nan)

    if session is not None:
        if pmt == 'LowerPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel0')
        if pmt == 'UpperPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel1')

    print(f"--- Measuring on Port: {port} for PMT: {pmt_id} ---")

    ref_time = time.monotonic()
    prev_pc_time = ref_time

    session.setDEggConstReadout(0,1,128)
    session.setDEggConstReadout(1,1,128)
    session.startDEggThreshTrigStream(channel, threshold)
    n_retry = 0
    NTRIAL = 3
    while(True):
        try:
            block = session.DEggReadChargeBlock(10,15,14*nevents,timeout=60)
        except IOError:
            print('Timeout! Ending the session.')
            send_message(f"### TIMEOUT occurred in measure_spe.py in reading charge blocks for PMT {pmt_id} with HV {hv} V, at trial {n_retry+1}. ###")
            session.endStream()
            session.startDEggThreshTrigStream(channel, threshold)
            n_retry += 1
            if n_retry == 3:
                send_message(f"### PMT {pmt_id} charge SPE meas was failed. Skip. ###")
                session.close()
                break
            continue
        break

    charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
    timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
    write_chargestamp_to_hdf5(filename, charges, timestamps)


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
        print(colored(f"None session object for Port: {port}!"), 'yellow')

    params['degg_temp'] = temp
    params['hv_mon_pre'] = str(hv_mon_pre)
    params['hv_mon'] = str(hv_mon)
    params['hv_scan_value'] = hv
    add_dict_to_hdf5(params, params['filename'])
    time.sleep(2)


def measure_degg(session,
                 degg_file,
                 degg_dict,
                 dirname,
                 constants,
                 keys):
    if audit_ignore_list(degg_file, degg_dict, keys[0]) == True:
        return
    degg_dict['Constants'] = constants

    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        # Do some setup and json file bookkeeping
        threshold = 9
        name = degg_dict[pmt]['SerialNumber']

        dirname_exists = check_dirname_in_pmt_dict(dirname,
                                                   degg_dict[pmt],
                                                   KEY_NAME)
        if dirname_exists:
            continue

        meta_dict = degg_dict[pmt][keys[channel]]
        # Before measuring check the D-Egg surface temp
        meta_dict['Folder'] = dirname

        baseline_filename = degg_dict[pmt]['BaselineFilename']
        meta_dict['BaselineFilename'] = baseline_filename
        meta_dict['Baseline'] = float(
            calc_baseline(baseline_filename)['baseline'].values[0])

        current_dict = deepcopy(degg_dict)
        current_dict['Constants'] = constants
        current_dict['channel'] = channel
        current_dict['pmt'] = pmt
        current_dict['measurement'] = keys[channel]
        current_dict['threshold_over_baseline'] = threshold
        current_dict['hv'] = int(degg_dict[pmt]['HV1e7Gain'])

        filename = os.path.join(dirname, name + '.hdf5')
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
                    filename = filename.replace('_{counter-1:02d}.hdf5',
                                                f'_{counter:02d}.hdf5')

        current_dict['filename'] = filename
        measure(session, current_dict)

    update_json(degg_file, degg_dict)


def measure_spe(run_json, comment, n_jobs=1, n_events=10000):
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    constants = {
            'Events': n_events,
            'DacValue': 30000
    }
    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')

    session_list = measure_baseline(
        run_json,
        constants=constants,
        n_jobs=n_jobs,
        modHV=False,
        return_sessions=True
    )

    sorted_degg_files, sorted_degg_dicts  = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        KEY_NAME,
        comment,
        Constants=constants
    )

    ##filepath for saving data
    measurement_type = 'spe_measurement'
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        session=session_list,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        constants=constants,
        keys=keys)

    for result in aggregated_results:
        print(result.result())


@click.command()
@click.argument('json_run_file')
@click.argument('comment')
@click.option('-j', '--n_jobs', default=1)
@click.option('--force', is_flag=True)
@click.option('--n_events', default=10000)
def main(json_run_file, comment, n_jobs, force, n_events):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')

    measure_spe(json_run_file, comment, n_jobs, n_events)


if __name__ == "__main__":
    main()

##end
