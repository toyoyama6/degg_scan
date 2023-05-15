import os
import numpy as np
import click
import threading
import time
from copy import deepcopy
from tqdm import tqdm
from datetime import datetime
from termcolor import colored

from chiba_slackbot import send_warning


from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import DEVICES
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.monitoring import readout_temperature
from degg_measurements.monitoring import readout_sensor

from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.master_scope import initialize
from degg_measurements.daq_scripts.master_scope import take_waveform
from degg_measurements.daq_scripts.master_scope import exit_gracefully
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5, write_scaler_to_hdf5
from degg_measurements.daq_scripts.master_scope import setup_scalers, take_scalers
from degg_measurements.daq_scripts.master_scope import setup_fir_trigger

from degg_measurements.analysis import calc_baseline

from degg_measurements import DATA_DIR

from chiba_slackbot import send_warning

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:


# Measuring scalar signals with the D-Egg through minifield hub
# Alternate measuring the top and bottom PMTs with the same settings
def min_measure_scaler_fir(session,
                           channel,
                           filename,
                           dac_value,
                           threshold_over_baseline,
                           period,
                           deadtime,
                           n_runs):
    params = {}
    params['filename'] = filename
    setup_fir_trigger(session,
                      channel,
                      dac_value,
                      int(threshold_over_baseline))
    session.enableScalers(channel, period, deadtime)
    time.sleep(period / 1e6)

    scaler_count_sum = 0
    for i in tqdm(range(n_runs)):
        session, scaler_count = take_scalers(session, channel)
        scaler_count_sum += scaler_count
        write_scaler_to_hdf5(params['filename'], i, scaler_count)
        time.sleep(period / 1e6)
    params['scaler_count'] = scaler_count_sum

    temp = readout_sensor(session, 'temperature_sensor')
    params['degg_temp'] = temp
    params['period'] = period
    params['threshold_over_baseline'] = threshold_over_baseline
    params['deadtime'] = deadtime
    params['n_runs'] = n_runs

    FPGA_CLOCK_TO_S = 1. / 240e6
    deadtime = params['deadtime'] * FPGA_CLOCK_TO_S
    total_duration = params['period'] / 1e6
    run_time = total_duration - (scaler_count_sum * deadtime)
    rate = scaler_count / run_time
    if temp < -12:
        rate_small = 2600
        rate_large = 4000
    elif temp >= -12 and temp < 0:
        rate_small = 3300
        rate_large = 4800
    elif temp > 0:
        rate_small = 6500
        rate_large = 11000
    else:
        raise ValueError(f'During monitoring, temperature = {temp}')
    if rate > rate_large:
        warn_str = f'During monitoring (FIR), '
        warn_str = warn_str + f'dark rate of {rate:.1f} Hz was found (> {rate_large} Hz) \n'
        warn_str = warn_str + f'{filename}, {temp} C.\n'
        warn_str = warn_str + f'If > {rate_large} Hz or consistently the same module,'
        warn_str = warn_str + ' contact an expert.\n'
        if temp < -12:
            warn_str = warn_str + f'{temp} < -12 C, please log this event. \n'
        send_warning(warn_str)

    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    time.sleep(1)
    return session

def min_measure_scaler(session, channel, filename, hv, dac_value, threshold,
                       period, deadtime, n_runs, modHV=False):
    params = {}
    params['filename'] = filename
    session.setDEggTriggerConditions(channel, int(threshold))
    session.enableDEggADCTrigger(channel)
    session.enableScalers(channel, period, deadtime)
    time.sleep(period / 1e6)

    scaler_count_sum = 0
    for i in tqdm(range(n_runs)):
        session, scaler_count = take_scalers(session, channel)
        scaler_count_sum += scaler_count
        write_scaler_to_hdf5(params['filename'], i, scaler_count)
        time.sleep(period / 1e6)
    params['scaler_count'] = scaler_count_sum

    temp = readout_sensor(session, 'temperature_sensor')
    params['degg_temp'] = temp
    params['period'] = period
    params['threshold'] = threshold
    params['deadtime'] = deadtime
    params['n_runs'] = n_runs

    FPGA_CLOCK_TO_S = 1. / 240e6
    deadtime = params['deadtime'] * FPGA_CLOCK_TO_S
    total_duration = params['period'] / 1e6
    run_time = total_duration - (scaler_count_sum * deadtime)
    rate = scaler_count / run_time
    if temp < -12:
        rate_small = 3500
        rate_large = 6000
    elif temp >= -12 and temp < 0:
        rate_small = 5000
        rate_large = 8000
    elif temp > 0:
        rate_small = 8200
        rate_large = 14000
    else:
        raise ValueError(f'During monitoring, temperature = {temp}')
    if rate > rate_large:
        warn_str = f'During monitoring (ADC),'
        warn_str = warn_str + f'dark rate of {rate:.1f} Hz was found (> {rate_large} Hz) \n'
        warn_str = warn_str + f'{filename}, {temp} C.\n'
        warn_str = warn_str + f'If > {rate_large} Hz or consistently the same module,'
        warn_str = warn_str + ' contact an expert.\n'
        if temp < -12:
            warn_str = warn_str + f'{temp} < -12 C, please log this event. \n'
        send_warning(warn_str)

    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    time.sleep(1)
    return session

##measures both PMTs at the same time
def measure(session, paramsList):
    host = 'localhost'
    ##port is the same
    port = paramsList[0]['Port']

    print(f'Starting Measurement on port={port}')

    for channel in [0, 1]:
        params = paramsList[channel]

        filename = params['filename']
        meas_key = params['measurement']
        pmt = params['pmt']
        hv = int(params[pmt]['HV1e7Gain'])
        baseline = params[pmt][meas_key]['Baseline']
        threshold_over_bl = int(params['threshold_over_baseline'])
        threshold = int(threshold_over_bl + baseline)
        period = params['period']
        deadtime = params['deadtime']
        dac_value = params['Constants']['DacValue']
        n_runs = params['n_runs']
        use_fir = params[pmt][meas_key]['use_fir']

        if not use_fir:
            # session = setup_scalers(session=session, channel=channel,
            #                         high_voltage=hv,
            #                         dac_value=dac_value, threshold=threshold,
            #                         period=period, deadtime=deadtime, modHV=False)
            session.setDEggTriggerConditions(channel, int(threshold))
            session.enableDEggADCTrigger(channel)
        else:
            session = setup_fir_trigger(
                session=session,
                channel=channel,
                dac_value=dac_value,
                threshold_over_baseline=threshold_over_bl)

        session.enableScalers(channel, period, deadtime)

        if params[pmt]['NoHVTest'] == 'False':
            hv_read = readout_sensor(session, f'voltage_channel{channel}')
            if hv_read < 1000:
                raise ValueError(f'HV too low! {hv_read} V !')

    time.sleep((period / 1e6) * 2)
    scaler_count_sum = [0, 0]
    scaler_list0 = []
    scaler_list1 = []

    for i in tqdm(range(n_runs)):
        for channel in [0, 1]:
            params = paramsList[channel]
            #hv_read = readout_sensor(session, f'voltage_channel{channel}')
            #print(f'{port}:{channel} - {hv_read} V')
            session, scaler_count = take_scalers(session, channel)
            scaler_count_sum[channel] += scaler_count
            write_scaler_to_hdf5(params['filename'], i, scaler_count)
            if channel == 0:
                scaler_list0.append(scaler_count)
            if channel == 1:
                scaler_list1.append(scaler_count)

        time.sleep(period / 1e6)

    print(f'{port}:0 - median cnt {np.median(scaler_list0)}')
    print(f'{port}:1 - median cnt {np.median(scaler_list1)}')
    if np.median(scaler_list0) > 10000 and use_fir == True:
        raise ValueError(f'scaler value of {np.median(scaler_list0)} is very high! ({port}:0)')
    if np.median(scaler_list1) > 10000 and use_fir == True:
        raise ValueError(f'scaler value of {np.median(scaler_list1)} is very high! ({port}:1)')

    for channel in [0, 1]:
        params = paramsList[channel]
        temp = readout_sensor(session, 'temperature_sensor')
        params['degg_temp'] = temp
        params['scaler_count'] = scaler_count_sum[channel]
        add_dict_to_hdf5(params, params['filename'])

    session.endStream()
    session.close()
    del session
    time.sleep(1)


def measure_degg(session,
                 degg_file,
                 degg_dict,
                 thresholds,
                 dirname,
                 keys,
                 use_alt_thresholds=False,
                 no_hv=False,
                 use_fir=False):
    if audit_ignore_list(degg_file, degg_dict, keys[0]) == True:
        return
    adc_to_volts = CALIBRATION_FACTORS.adc_to_volts
    if len(thresholds) == 4:
        small_step = [-1, 0, 1, 0]
    else:
        small_step = [0] * len(thresholds)

    degg_name = degg_dict['DEggSerialNumber']
    port = degg_dict['Port']
    for i, thresh in enumerate(tqdm(thresholds)):
        pmtDicts = []
        for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
            name = degg_dict[pmt]['SerialNumber']
            baseline_filename = degg_dict[pmt]['BaselineFilename']
            spe_peak_height = degg_dict[pmt]['SPEPeakHeight']

            ##peak height should usually be around 3 mV --> 40 ADC
            ##if this is wrong, raise an error
            if spe_peak_height > 0.01 or spe_peak_height < 0.001:
                msg_str = 'There was an error during the peak height calculation!'
                msg_str = msg_str + f'{port}:{channel} ({degg_name}), with {spe_peak_height} V!'
                msg_str = msg_str + ' The script will now exit!'
                send_warning(msg_str)
                raise ValueError(f'Issue with SPE Peak Height, cannot accuartely determine \
                                 threshold! {spe_peak_height}')
            if use_alt_thresholds:
                adc_thresh = int(np.ceil(
                    spe_peak_height * thresh / adc_to_volts) + small_step[i])
            else:
                adc_thresh = int(np.ceil(spe_peak_height * thresh / adc_to_volts))

            meta_dict = degg_dict[pmt][keys[channel]]
            meta_dict['Folder'] = dirname
            meta_dict['BaselineFilename'] = 'AltMethod'
            #meta_dict['Baseline'] = \
            #    float(calc_baseline(baseline_filename)['baseline'].values[0])

            meta_dict['use_fir'] = use_fir

            # Before measuring check the D-Egg surface temp
            meta_dict['DEggSurfaceTemp'] = readout_temperature(
                device=DEVICES.thermometer,
                channel=1)
            meta_dict['BoxSurfaceTemp'] = readout_temperature(
                device=DEVICES.thermometer,
                channel=2)

            current_dict = deepcopy(degg_dict)
            current_dict['period'] = 100000
            current_dict['deadtime'] = 24
            current_dict['n_runs'] = 5000
            current_dict['channel'] = channel
            if use_alt_thresholds:
                current_dict['filename'] = os.path.join(
                    dirname, name + f'_{thresh}_{small_step[i]}' + '.hdf5')
            else:
                current_dict['filename'] = os.path.join(
                    dirname, name + f'_{thresh}' + '.hdf5')
            current_dict['pmt'] = pmt
            current_dict['measurement'] = keys[channel]
            current_dict['threshold_over_baseline'] = int(adc_thresh)
            current_dict['pe_threshold'] = thresh
            current_dict[pmt]['NoHVTest'] = 'False'
            if no_hv == True:
                print('HV is turned off for this measurement!')
                current_dict[pmt]['HV1e7Gain'] = 0
                current_dict[pmt]['NoHVTest'] = 'True'

            pmtDicts.append(current_dict
                            )
        ##if they're both initialized
        ##we can measure the dark rates for both channels
        ##at the same time - the scalers are just running
        measure(session, pmtDicts)
        update_json(degg_file, degg_dict)

    #return (degg_dict['LowerPmt'][keys][0], degg_dict['UpperPmt'][keys][0])
    return "Done"

def remeasure_baseline(session, degg_dict, key, channel):
    if channel == 0:
        pmt = 'LowerPmt'
    if channel == 1:
        pmt = 'UpperPmt'
    session = initialize(session, channel=channel, n_samples=1024,
                         high_voltage0=0, modHV=False, dac_value=30000)
    wf_aves = []
    n_wfs = 50
    for j in range(n_wfs):
        session, x, wf, t, pc_t, wf_channel = take_waveform(session)
        wf_ave = np.mean(wf)
        wf_aves.append(wf_ave)
    updated_baseline = np.median(wf_aves)
    session.endStream()
    degg_dict[pmt][key[channel]]['Baseline'] = updated_baseline

def measure_scaler(run_json, comment,
                   n_jobs=4,
                   use_alt_thresholds=False,
                   no_hv=False,
                   use_fir=False):
    # get function generator - turn laser off
    fg = FG3101()
    fg.disable()
    print('Disabling the function generator')

    constants = {
        'Samples': 128,
        'Events': 10000,
        'DacValue': 30000,
    }
    list_of_deggs = load_run_json(run_json)
    print(f'n_jobs: {n_jobs}')

    ##filepath for saving data
    measurement_type = 'scaler'
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)
    meas_key = 'DarkrateScalerMeasurement'

    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        meas_key,
        comment,
        Constants=constants,
        use_fir=use_fir
    )

    #session_list = measure_baseline(
    #    run_json,
    #    constants=constants,
    #    n_jobs=n_jobs,
    #    modHV=False
    #)
    ##TEMP
    sessionList = []
    hvOn = 0
    for degg_dict in sorted_degg_dicts:
        port = degg_dict['Port']
        session = startIcebootSession(host='localhost', port=port)
        sessionList.append(session)
        for pmt, _channel in zip(['LowerPmt', 'UpperPmt'], [0, 1]):
            hv_enabled = checkHV(session, _channel, verbose=True)
            hvOn += hv_enabled
            if hv_enabled == False:
                session.enableHV(_channel)
                set_hv = int(degg_dict[pmt]['HV1e7Gain'])
                session.setDEggHV(_channel, set_hv)

    if hvOn < 32:
        print("="*20)
        print(f"Sleeping for HV to ramp before baseline measurement")
        for i in tqdm(range(40)):
            time.sleep(1)

    ##measure baseline for ch0 then ch1
    ##Since I'm doing this manually, need to check HV!
    threads = []
    for degg_dict, session in zip(sorted_degg_dicts, sessionList):
        channel = 0
        threads.append(threading.Thread(target=remeasure_baseline, args=[session,
                                                                          degg_dict,
                                                                          keys[0], channel]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(1)

    threads = []
    for degg_dict, session in zip(sorted_degg_dicts, sessionList):
        channel = 1
        threads.append(threading.Thread(target=remeasure_baseline, args=[session,
                                                                          degg_dict,
                                                                          keys[0], channel]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()


    # Passing thresholds in units of SPE peak height
    if use_alt_thresholds:
        pe_thresholds = np.array([0.25, 0.25, 0.25, 0.3])
    else:
        pe_thresholds = np.array([0.25])

    # for i in range(2):
    #     measure_degg(session=sessionList[i],
    #                  degg_file=sorted_degg_files[i],
    #                  degg_dict=sorted_degg_dicts[i],
    #                  thresholds=pe_thresholds,
    #                  dirname=dirname,
    #                  keys=keys[i],
    #                  use_fir=use_fir)
    # exit(1)

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        force_static=['thresholds'],
        session=sessionList,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        thresholds=pe_thresholds,
        keys=keys,
        use_alt_thresholds=use_alt_thresholds,
        no_hv=no_hv,
        use_fir=use_fir
    )

    for result in aggregated_results:
        print(result.result())
    print('Done')

@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=4)
@click.option('--force', is_flag=True)
@click.option('--alt', is_flag=True)
@click.option('--no-hv', is_flag=True)
@click.option('--use_fir', is_flag=True)
def main(run_json, comment, n_jobs, force, alt, no_hv, use_fir):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')
    use_alt_thresholds = bool(alt)
    measure_scaler(
        run_json,
        comment,
        n_jobs,
        use_alt_thresholds,
        no_hv,
        use_fir
    )


if __name__ == "__main__":
    main()

