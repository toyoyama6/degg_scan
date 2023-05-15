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
import pandas as pd

####
from master_scope import initialize_dual, initialize, setup_plot
from master_scope import take_waveform_block
from master_scope import write_to_hdf5, update_plot, exit_gracefully
from master_scope import add_dict_to_hdf5
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.filter_wheel_helper import setup_fw
from degg_measurements.utils.filter_wheel_helper import change_filter_str

from degg_measurements.monitoring import readout_sensor

from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis.linearity.analyze_linearity import make_laser_freq_mask

from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline

from degg_measurements import DATA_DIR

##for interface with chiba-daq slack channel
from chiba_slackbot import send_message
from chiba_slackbot import send_warning

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

HIGH_VOLTAGE = 1500

##measuring MPE level signals with the D-Egg through minifield hub
##alternate measuring the top and bottom PMTs with the same settings

def measure(session, params, hv_readouts):
    debug = False
    host = 'localhost'
    port = params['Port']
    degg_name = params['DEggSerialNumber']
    filename_u = params['UpperPmt']['filename']
    filename_l = params['LowerPmt']['filename']

    pmt_names = [params['LowerPmt']['SerialNumber'], params['UpperPmt']['SerialNumber']]
    hv1e7gains = [params['LowerPmt']['HV1e7Gain'], params['UpperPmt']['HV1e7Gain']]

    ## constants - some overrides in main()
    samples = params['Constants']['Samples']
    nevents = params['Constants']['Events']
    dac_value = params['Constants']['DacValue']

    try:
        pmt_baseline0 = float(calc_baseline(
            params['LowerPmt']['BaselineFilename'])['baseline'].values[0])
        pmt_baseline1 = float(calc_baseline(
            params['UpperPmt']['BaselineFilename'])['baseline'].values[0])
    except KeyError:
        ##using default
        if dac_value != 30000:
            print(colored(f"Not using DAC at 30000 (current: {dac_value}) - no appropriate default!", 'red'))
            exit(1)
        ##corresponds to DAC around 30,000!
        pmt_baseline0 = 8000
        pmt_baseline1 = 8000
        print(colored(f"Using default baselines {pmt_baseline0} and {pmt_baseline1}.", "red"))

    threshold0 = params['threshold0']
    pmt_threshold0 = pmt_baseline0 + threshold0
    threshold1 = params['threshold1']
    pmt_threshold1 = pmt_baseline1 + threshold1
    pmt_thresholds = [pmt_threshold0, pmt_threshold1]

    ##temp ---
    channels = [0, 1]
    tags = ['LowerPmt', 'UpperPmt']
    timestamp_list = []
    for channel, tag in zip(channels, tags):
        pmt_name = params[tag]['SerialNumber']
        print(f"Start Measuring {port}, {channel}, {pmt_name}")
        if session == None:
            try:
                session.close()
            except:
                pass
            session = startIcebootSession(host='localhost', port=port)

        ##place-holder hv is fine since modHV is false!!!
        session = initialize(session,
                             channel=channel,
                             n_samples=samples,
                             dac_value=dac_value,
                             high_voltage0=1500,
                             threshold0=pmt_thresholds[channel],
                             modHV=False)
        ref_time = time.time()

        timestamps = []
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
                    timestamps.append(timestamp)
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
        timestamp_list.append(timestamps)
    ##end channel for loop -- temp
    time.sleep(1)
    return port, timestamp_list, [filename_l, filename_u], degg_name, hv_readouts, pmt_names, hv1e7gains, temp

def validate_hv(session, port, pass_val=1000):
    hv_readouts = [0, 0]
    for ch in [0, 1]:
        hv_readout = readout_sensor(session, f'voltage_channel{ch}')
        print(f'Port {port} --- HV{ch}: {hv_readout}')
        if hv_readout >= pass_val:
            hv_readouts[ch] = hv_readout
        elif hv_readout < pass_val:
            hv_l = []
            for i in range(5):
                hv_readout = readout_sensor(session, f'voltage_channel{ch}')
                hv_l.append(hv_readout)
            hv_ave = np.mean(hv_l)
            if hv_ave >= pass_val:
                print(f'HV Mon checked again, now valid - Port {port} --- HV{ch}: {hv_ave}')
            if hv_ave < pass_val:
                print(colored(f'After re-check HV for Port {port} still invalid {hv_ave} < {pass_val} V', 'red'))
            hv_readouts[ch] = hv_ave
        else:
            raise ValueError(f'Unexpected handling of evaluationg {hv_readout} vs {pass_val}')

    return hv_readouts

def measure_degg(session, degg_file, degg_dict,
                 constants, keys, dirname,
                 threshold, laser_freq,
                 outfile):
    degg_dict['Constants'] = constants
    name_u = degg_dict['UpperPmt']['SerialNumber']
    name_l = degg_dict['LowerPmt']['SerialNumber']
    port = degg_dict['Port']

    current_dict = deepcopy(degg_dict)
    current_dict['threshold0'] = threshold
    current_dict['threshold1'] = threshold
    ##2 lists, one for each channel
    avg_dt = [100, 100]
    i_loop = 0
    while (avg_dt[0] >= 0.015) or (avg_dt[1] >= 0.015):
        threshold0 = current_dict['threshold0']
        threshold1 = current_dict['threshold1']

        current_dict['UpperPmt']['filename'] = os.path.join(
            dirname, f'{name_u}_{threshold0}_{i_loop}.hdf5')
        current_dict['LowerPmt']['filename'] = os.path.join(
            dirname, f'{name_l}_{threshold1}_{i_loop}.hdf5')
        hv_readouts = validate_hv(session, port)
        ret_val = measure(session, current_dict, hv_readouts)
        for ch, ts_ in enumerate(ret_val[1]):
            avg_dt[ch] = (ts_[-1] - ts_[0])/240e6/len(ts_)
            print(f'{ch}: {avg_dt[ch]} s')
            if avg_dt[ch] >= 0.015:
                current_dict[f'threshold{ch}'] = threshold - 10
        i_loop += 1

    # After the measurement was successful fill the dirname
    for pmt, key in zip(['LowerPmt', 'UpperPmt'], keys):
        degg_dict[pmt][key]['Folder'] = dirname
        degg_dict[pmt][key]['Output'] = outfile

    update_json(degg_file, degg_dict)
    print(session)
    session.close()
    del session
    return ret_val

def check_laser_visibility(run_json, comment, n_jobs):
    constants = {
        'DacValue': 5000,
        'Events': 3000,
        'Samples': 128
    }
    session_list = measure_baseline(
        run_json,
        high_voltage=HIGH_VOLTAGE,
        constants=constants,
        n_jobs=n_jobs, modHV=False,
        return_sessions=True)

    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')

    # filepath for saving data
    measurement_type = "laser_visibility"
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)
    ##and for analysis output
    plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../analysis/monitoring/laser_output/plots')
    ana_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../analysis/monitoring/laser_output/')
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
    if not os.path.exists(ana_dir):
        os.mkdir(ana_dir)
    run_number = extract_runnumber_from_path(run_json)

    meas_key = 'LaserVisibilityMeasurement'

    # setup filter wheel
    fw0, fw1 = setup_fw()
    ##set filters to 25%
    change_filter_str(fw0, 0.25, fw1, 1.0)
    filterSetting = 0.25

    # configure function generator
    laser_freq = 100 #Hz
    fg = FG3101()
    fg.startup()
    fg.waveform_frequency(laser_freq)

    ##for 100%
    #threshold = 2500
    ##for 10%
    threshold = 150

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
    )
    outfile = os.path.join(ana_dir, f'{run_number}_{keys[0][0]}.hdf5')


    results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        session=session_list,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        constants=constants,
        keys=keys,
        threshold=threshold,
        laser_freq=laser_freq,
        outfile=outfile)

    df_l = []

    dt_lim = 0.015
    for result in results:
        res = result.result()
        print(f'Port: {res[0]}')
        ts = res[1]
        files = res[2]
        degg_name = res[3]
        for ch, ts_ in enumerate(ts):
            avg_dt = (ts_[-1] - ts_[0])/240e6/len(ts_)
            if avg_dt < dt_lim:
                print(colored(f'Port {res[0]}, Channel: {ch} can see the laser! Ave dT = {avg_dt} and is < {dt_lim}', 'green'))
            else:
                print(colored(f'Port {res[0]}, Channel: {ch} can not see the laser! Please investigate! Ave dT = {avg_dt} and is > {dt_lim}', 'red'))
                print('More info: http://www.ppl.phys.chiba-u.jp/only/fat_shift_manual/texts/laboratory/1_operation.html')

            ##----------------------------
            ##do more detailed analysis
            f = files[ch]
            e_id, time, waveforms, ts, pc_t, datetime_timestamp, params = read_data(f)
            mask = make_laser_freq_mask(ts,
                                        filterSetting)
            if np.sum(mask) == 0:
                print(f'No laser triggers found for {res[0]}:{ch}. Skipping it!')
                continue
            waveforms = waveforms[mask]
            x_l1_list = time[0, 0:128] * CALIBRATION_FACTORS.fpga_clock_to_s
            yy = np.zeros(128)
            # Get the base line
            pre_trigger_wf = waveforms[:, :10]
            baselines = np.mean(pre_trigger_wf, axis=1)
            # charge pC
            charges = get_charges(waveforms*CALIBRATION_FACTORS.adc_to_volts,
                               gate_start=13,
                               gate_width=15,
                               baseline=baselines*CALIBRATION_FACTORS.adc_to_volts)
            npes = charges / 1.602 # PE
            send_message(f'{degg_name}:{ch} on Port {res[0]} reports <{np.mean(npes)}> PE')

            d = {'DEgg': degg_name, 'PMT': res[5][ch], 'Channel': ch, 'HV': res[4][ch],
                 'HV1e7Gain': res[6][ch], 'Temperature': res[7],
                 'Port': res[0], 'NPEs': npes, 'Efficiency': np.sum(mask)/len(mask)}
            df = pd.DataFrame(data=d)
            df_l.append(df)
            ##----------------------------

    df_full = pd.concat(df_l)
    df_full.to_hdf(outfile, key='df', mode='w')

    # disabling laser output
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
    check_laser_visibility(run_json, comment, n_jobs)


if __name__ == "__main__":
    main()

##end
