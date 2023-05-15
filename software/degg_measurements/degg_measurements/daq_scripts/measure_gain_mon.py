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
import datetime

from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from master_scope import initialize

from master_scope import add_dict_to_hdf5

from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_git_infos_to_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils import DEVICES

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature

from measure_pmt_baseline import measure_baseline
from degg_measurements.analysis import calc_baseline

from degg_measurements.utils.load_dict import check_dirname_in_pmt_dict

from degg_measurements.utils.flash_fpga import loadFPGA
from degg_measurements.utils.control_data_charge import write_qstamp_mon_to_hdf5

from multi_processing import run_jobs_with_mfhs

from termcolor import colored

from degg_measurements import DATA_DIR

KEY_NAME = 'ChargeGainMonitoring'

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:


def measure(params):
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
    baseline = params['baseline']
    threshold = int(threshold_over_bl + baseline)
    params['threshold'] = threshold
    pmt_id = params[pmt]['SerialNumber']

    #print(f'Start Iceboot Session for {params}')
    session = startIcebootSession(host=host,port=port)
    session = initialize(session, channel=channel,
                        high_voltage0=hv, n_samples=256,
                        threshold0=threshold, dac_value=dac_value,
                        burn_in=int(5))

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

    pctime = time.time()
    print(datetime.datetime.fromtimestamp(int(pctime)))

    obs_hv = np.mean(hv_mon_pre)

    session.setDEggConstReadout(0,1,128)
    session.setDEggConstReadout(1,1,128)
    session.startDEggThreshTrigStream(channel, threshold)
    n_retry = 0
    NTRIAL = 3
    while True:
        try:
            block = session.DEggReadChargeBlock(10,15,14*nevents,timeout=60)
        except IOError:
            print('Timeout! Ending the session. Restart the session.')
            session.endStream()
            session.startDEggThreshTrigStream(channel, threshold)
            pctime = time.time()
            print(datetime.datetime.fromtimestamp(int(pctime)))
            n_retry += 1
            if n_retry == 3:
                print('Too many timeouts! Exit.')
                session.close()
                break
            continue
        break

    charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
    timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
    temp_mon = np.full(n_pts, np.nan)

    if session is not None:
        for pt in range(n_pts):
            try:
                temp_mon[pt] = readout_sensor(session, 'temperature_sensor')
            except IOError:
                temp_mon[pt] = 0
    if session is None:
        print(colored(f"None session object for Port: {port}!"), 'yellow')

    temp = np.mean(temp_mon)
    write_qstamp_mon_to_hdf5(filename,
                            charges,
                            timestamps,
                            pctime,
                            obs_hv,
                            temp)

    params['degg_temp'] = temp
    params['hv_mon_pre'] = str(hv_mon_pre)
    #add_dict_to_hdf5(params, params['filename'])
    session.close()
    del session
    time.sleep(5)


def measure_degg(degg_file,
                 degg_dict,
                 dirname,
                 comment,
                 constants,
                 tag):

    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        # Do some setup and json file bookkeeping
        threshold = 18
        name = degg_dict[pmt]['SerialNumber']

        key = KEY_NAME #create_key(degg_dict[pmt], KEY_NAME)
        meta_dict = dict()
        meta_dict = add_git_infos_to_dict(meta_dict)

        # Before measuring check the D-Egg surface temp
        meta_dict['DEggSurfaceTemp'] = readout_temperature(
                device=DEVICES.thermometer, channel=1)
        meta_dict['BoxSurfaceTemp'] = readout_temperature(
                device=DEVICES.thermometer, channel=2)

        meta_dict['Folder'] = dirname

        baseline_filename = degg_dict[pmt]['BaselineFilename']
        meta_dict['BaselineFilename'] = baseline_filename
        meta_dict['Baseline'] = float(calc_baseline(baseline_filename)['baseline'].values[0])
        meta_dict['Comment'] = comment
        #degg_dict[pmt][key] = meta_dict

        current_dict = deepcopy(degg_dict)
        current_dict['Constants'] = constants
        current_dict['channel'] = channel
        current_dict['pmt'] = pmt
        current_dict['measurement'] = key
        current_dict['threshold_over_baseline'] = threshold
        current_dict['baseline'] = meta_dict['Baseline']

        hv = int(degg_dict[pmt]['HV1e7Gain'])

        current_dict['hv'] = int(hv)

        filename = os.path.join(dirname, name + f'_{hv}.hdf5')
        current_dict['filename'] = filename
        if tag is not None:
            degg_dict[pmt][f'{KEY_NAME}Filename_{tag}'] = filename
        else:
            degg_dict[pmt][f'{KEY_NAME}Filename'] = filename
        measure(current_dict)

    update_json(degg_file, degg_dict)

def measure_gain_mon(run_json, comment, n_jobs=1, tag="Default", resume=False):
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    constants = {
            'Samples': 128,
            'Events': 20000,
            'DacValue': 30000
    }
    #bl_names = measure_baseline(run_json, constants=constants,
    #                            n_jobs=n_jobs)

    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')

    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    if resume:
        dirname = get_recent_dirname_from_degg_dicts(sorted_degg_dicts, KEY_NAME)
    else:
        measure_type = 'charge_gain_monitoring'
        json_file_dirs = run_json.split("/")
        json_file_name = json_file_dirs[len(json_file_dirs)-1]
        dirname = os.path.join(DATA_DIR,
                               measure_type,
                               json_file_name.split("json")[0],
                               f"{tag}")
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        comment=comment,
        constants=constants,
        tag=tag)

    for result in aggregated_results:
        print(result.result())


@click.command()
@click.argument('json_run_file')
@click.argument('comment')
@click.option('-j', '--n_jobs', default=1)
@click.option('--force', is_flag=True)
@click.option('--tag', default="Default")
def main(json_run_file, comment, n_jobs, tag, force):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')

    measure_gain_mon(json_run_file, comment, n_jobs, tag)


if __name__ == "__main__":
    main()

##end
