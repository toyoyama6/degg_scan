from degg_measurements.utils import startIcebootSession
import time
import click
import os, sys
from copy import deepcopy
import json
import numpy as np

from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils.stack_fmt import stripStackSize

from degg_measurements.monitoring import readout, reboot, SENSOR_TO_VALUE

from degg_measurements.daq_scripts.master_scope import initialize, initialize_dual
from degg_measurements.daq_scripts.master_scope import setup_plot, take_waveform
from degg_measurements.daq_scripts.master_scope import write_to_hdf5, update_plot, exit_gracefully
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.daq_scripts.master_scope import setup_scalers, take_scalers, write_scaler_to_hdf5
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline

from degg_measurements.analysis import calc_baseline


from tqdm import tqdm
from datetime import datetime
from datetime import timedelta
from termcolor import colored
##for interface with chiba-daq slack channel

from degg_measurements import DATA_DIR


@click.command()
@click.argument('json_file')
@click.argument('set_time', default=None)
@click.argument('comment')
def main(json_file, set_time, comment):
    try:
        from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
    except ImportError:
        raise ValueError('The library function_generators is missing! Go check!')# WARNING:
    fg = FG3101()
    fg.disable()

    readout_and_readout(json_file, set_time, comment)


def remeasure_baseline(port, channel, hv, ramp_time, n_wfs, pmt_name):
    wf_aves = []
    session = startIcebootSession(host='localhost', port=port)
    session = initialize(session, channel=channel, n_samples=1024,
                         high_voltage0=hv, dac_value=30000)
    for i in tqdm(range(ramp_time)):
        time.sleep(1)
    temperature = session.sloAdcReadChannel(SENSOR_TO_VALUE['temperature_sensor'])
    if channel == 0:
        voltage = session.sloAdcReadChannel(SENSOR_TO_VALUE['voltage_channel0'])
    if channel == 1:
        voltage = session.sloAdcReadChannel(SENSOR_TO_VALUE['voltage_channel1'])

    print(f"-- Updating {pmt_name} --")
    wf_channel = -1
    dummy_wfs = 0
    dummy_wf = []
    while wf_channel != channel and len(dummy_wf) != 1024:
        session, x, wf, t, pc_t, wf_channel = take_waveform(session)
        if wf_channel == channel and len(dummy_wf) == 1024:
            break
        dummy_wfs += 1
    print(f"Emptying Buffer needed {dummy_wfs} waveforms.")

    for j in tqdm(range(n_wfs)):
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
        if session is None:
            break
        if wf is None:
            print("WF is none!")
            continue
        if len(wf) != 1024:
            print(f"BUFF ERR?? - len(wf) {len(wf)} != samples 1024")
            continue
        wf_ave = np.mean(wf)
        wf_aves.append(wf_ave)
    updated_baseline = np.median(wf_aves)
    exit_gracefully(session)
    session.close()
    del session
    time.sleep(3)
    if len(wf_aves) == 0:
        print("WARNING - NO DATA COLLECTED!")
    if channel == 0:
        print(f"New Baseline L: {updated_baseline}")
    if channel == 1:
        print(f"New Baseline U: {updated_baseline}")
    return updated_baseline, temperature, voltage

def double_scalers(port, hv_l, hv_u, updated_threshold_l, updated_threshold_u,
                   out_files):
    ##NOTE:session closed from remeasure_baseline
    ##scalers data
    print(colored("-- Starting scaler measurements --", 'yellow'))
    period = 100000
    deadtime = 24

    hvs = [hv_l, hv_u]
    threshs = [updated_threshold_l, updated_threshold_u]

    for channel in [0, 1]:
        session = startIcebootSession(host='localhost', port=port)
        session = setup_scalers(session,
                                channel=channel,
                                high_voltage=hvs[channel],
                                dac_value=30000,
                                threshold=threshs[channel],
                                period=period,
                                deadtime=deadtime)
        time.sleep(5)
        scaler_count_sum = 0
        for j in tqdm(range(200)):
            session, scaler_count = take_scalers(session, channel=channel)
            scaler_count_sum += scaler_count
            write_scaler_to_hdf5(out_files[channel], j, scaler_count)
            time.sleep(period / 1e6)
        ##ch1
        exit_gracefully(session)
        session.close()
        del session
        time.sleep(3)


def primary_loop(session, index, filename, samples, wf_filenames):
    ##readout sensors
    ##readout given -1 because no reboot
    readout(session, -1, filename)

    ##try to read waveform stream
    try:
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
    except:
        print(colored(f"[readout_and_readout] Error: take_waveform: {session}",
                        'yellow'))
        print("[readout_and_readout] Waveform stream error")
    ##wf stream error handling
    if wf is None:
        print(f"WF was None! : {channel}")
        return
    if len(wf) != samples:
        print(f"WF Size mis-match: {len(wf)} vs {samples}")
        return
    try:
        ref_time = time.monotonic()
        time_diff = (pc_time - ref_time)
    except:
        print(colored("Could not calculate measurement time - setting to 0",
                       'yellow'))
        time_diff = 0
    if timestamp == None:
        timestamp = 0

    ##running with ch0 & ch1, so get
    ##correct D-Egg (session) then channel
    write_to_hdf5(wf_filenames[channel], int(index), xdata, wf, timestamp, time_diff)


def readout_and_readout(json_file, set_time, comment):
    measurement_type = 'ReadoutOnly'

    #load all degg files
    list_of_deggs = load_run_json(json_file)

    ##filepath for saving data
    dirpath = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    session_list = []
    filename_list = []
    wf_filename_list = []
    scaler_filename_list = []
    key_list = []

    threshold_above_baseline = 18  # nominal
    ramp_time = 8
    dac_value = 30000
    samples = 128
    default_hv = 1500
    constants = {
        'Samples': 128,
        'DacValue': 30000
    }

    bl_names = measure_baseline(json_file, constants=constants,
                                n_jobs=4)

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        port = degg_dict['Port']
        key = create_key(degg_dict, measurement_type)
        key_list.append(key)
        degg_dict[key] = dict()
        degg_id = degg_dict['DEggSerialNumber']
        filename = os.path.join(dirpath, degg_id + '.csv')
        degg_dict[key]['Filename'] = filename
        degg_dict[key]['Comment'] = comment
        degg_dict[key]['Time'] = set_time
        degg_dict[key]['RampTime'] = ramp_time
        degg_dict[key]['DacValue'] = dac_value
        degg_dict[key]['Samples'] = samples

        try:
            hv_l = degg_dict['LowerPmt']['HV1e7Gain']
            hv_u = degg_dict['UpperPmt']['HV1e7Gain']
            if hv_l == -1:
                hv_l = default_hv
            if hv_u == -1:
                hv_u = default_hv
        except KeyError:
            print(colored(f"Could not find key for HV1e7Gain \
                        - using default {default_hv} V", 'yellow'))
            hv_l = default_hv
            hv_u = default_hv

        degg_dict[key]['HighVoltage0'] = hv_l
        degg_dict[key]['HighVoltage1'] = hv_u

        session = startIcebootSession(host='localhost', port=port)
        try:
            fpgaVersion = session.cmd('fpgaVersion .s drop')
            firmware_version = stripStackSize(fpgaVersion)
        except:
            print("Could not determine the fpgaVersion")
            fpgaVersion = -1
        degg_dict[key]['FirmwareVersion'] = firmware_version

        baseline_filename_l = degg_dict['LowerPmt']['BaselineFilename']
        baseline_filename_u = degg_dict['UpperPmt']['BaselineFilename']
#        try:
#            print('Grabbing baselines from before to start...')
#            baseline_filename_l = degg_dict['LowerPmt']['BaselineFilename']
#            baseline_filename_u = degg_dict['UpperPmt']['BaselineFilename']
#        except KeyError:
#            print(colored('Baselines not yet calculated for this run!', 'red'))
#            bl_names = measure_baseline(json_file, constants=constants)

        baseline_key = create_key(degg_dict[key], 'Baseline')
        degg_dict[key][baseline_key] = dict()
        degg_dict[key][baseline_key]['Baseline_L'] = float(calc_baseline(baseline_filename_l)['baseline'].values[0])
        degg_dict[key][baseline_key]['Baseline_U'] = float(calc_baseline(baseline_filename_u)['baseline'].values[0])
        degg_dict[key][baseline_key]['BaselineFilename_L'] = baseline_filename_l
        degg_dict[key][baseline_key]['BaselineFilename_U'] = baseline_filename_u

        pmt_threshold_l = degg_dict[key][baseline_key]['Baseline_L'] + threshold_above_baseline
        pmt_threshold_u = degg_dict[key][baseline_key]['Baseline_U'] + threshold_above_baseline
        degg_dict[key]['ThresholdAboveBaseline'] = threshold_above_baseline

        update_json(degg_file, degg_dict)

        session = initialize_dual(session, n_samples=samples,
                    high_voltage0=hv_l, high_voltage1=hv_u,
                    threshold0=pmt_threshold_l,
                    threshold1=pmt_threshold_u, dac_value=dac_value)

        wf_filename_0 = os.path.join(dirpath, degg_id + '_wf_ch0.hdf5')
        wf_filename_1 = os.path.join(dirpath, degg_id + '_wf_ch1.hdf5')
        s_filename_0  = os.path.join(dirpath, degg_id + '_scaler_ch0.hdf5')
        s_filename_1  = os.path.join(dirpath, degg_id + '_scaler_ch1.hdf5')

        session_list.append(session)
        filename_list.append(filename)
        wf_filename_list.append((wf_filename_0, wf_filename_1))
        scaler_filename_list.append((s_filename_0, s_filename_1))

        time.sleep(5)

    print(colored(f"Waiting {ramp_time}s for HV to stabilise after set", 'yellow'))
    for i in tqdm(range(ramp_time)):
        time.sleep(1)

    n_events = 0
    readout_index = 0

    ##take data until set_time has elapsed
    start = datetime.now()
    now = start
    stop = start + timedelta(seconds=float(set_time))
    while (stop - now).total_seconds() > 0:
        index = 0

        ##loop over D-Eggs (sessions) - ensure all D-Eggs have same number of measurements
        for session in session_list:
            primary_loop(session, index=index,
                         filename=filename_list[index],
                         samples=samples,
                         wf_filenames=wf_filename_list[index])
            readout_index += 1 ##for printing at the end
            index += 1

        ## periodically re-evaluate baseline once all D-Eggs have been readout
        if n_events % 200 == 0 and n_events != 0:
            print(colored('-- Updating Baselines --', 'yellow'))
            for ind in range(len(session_list))[::-1]:
                exit_gracefully(session_list[ind])
                session_list[ind].close()
                del session_list[ind]
                time.sleep(3)
            session_list = []

            i = 0
            for degg_file in list_of_deggs:
                degg_dict = load_degg_dict(degg_file)
                key = key_list[i]
                pmt_l = degg_dict['LowerPmt']['SerialNumber']
                pmt_u = degg_dict['UpperPmt']['SerialNumber']
                hv_l = degg_dict['LowerPmt']['HV1e7Gain']
                hv_u = degg_dict['UpperPmt']['HV1e7Gain']
                port = degg_dict['Port']

                pc_time = time.monotonic()

                ##baseline
                updated_baseline_l, temp, v0 = remeasure_baseline(port=port,
                                        channel=0, hv=hv_l,
                                        ramp_time=ramp_time,
                                        n_wfs=50, pmt_name=pmt_l)

                updated_baseline_u, temp, v1 = remeasure_baseline(port=port,
                                        channel=1, hv=hv_u,
                                        ramp_time=ramp_time,
                                        n_wfs=50, pmt_name=pmt_u)
                baseline_key = create_key(degg_dict[key], 'Baseline')
                degg_dict[key][baseline_key] = dict()
                degg_dict[key][baseline_key]['Event'] = n_events
                degg_dict[key][baseline_key]['PCTime'] = pc_time
                degg_dict[key][baseline_key]['Temperature'] = temp
                degg_dict[key][baseline_key]['Baseline_L'] = updated_baseline_l
                degg_dict[key][baseline_key]['Baseline_U'] = updated_baseline_u
                degg_dict[key][baseline_key]['Voltage_L'] = v0
                degg_dict[key][baseline_key]['Voltage_U'] = v1
                update_json(degg_file, degg_dict)

                updated_threshold_l = updated_baseline_l + threshold_above_baseline
                updated_threshold_u = updated_baseline_u + threshold_above_baseline

                double_scalers(port=port, hv_l=hv_l, hv_u=hv_u,
                                updated_threshold_l=updated_threshold_l,
                                updated_threshold_u=updated_threshold_u,
                                out_files=scaler_filename_list[i])
                session = startIcebootSession(host='localhost', port=port)
                session = initialize_dual(session, n_samples=128,
                    high_voltage0=hv_l, high_voltage1=hv_u,
                    threshold0=updated_threshold_l,
                    threshold1=updated_threshold_u, dac_value=30000)
                time.sleep(5)
                session_list.append(session)
                i += 1

        n_events += 1
        ##if no time - only run once
        if set_time is None:
            break
        now = datetime.now()

    print(f"Number of sensor readouts total: {readout_index}")
    print(f"Number of waveforms per PMT: {n_events}")

    for degg_file, wf_filenames in zip(list_of_deggs, wf_filename_list):
        degg_dict = load_degg_dict(degg_file)
        add_dict_to_hdf5(degg_dict, wf_filenames[0])
        add_dict_to_hdf5(degg_dict, wf_filenames[1])

if __name__ == '__main__':
    main()

