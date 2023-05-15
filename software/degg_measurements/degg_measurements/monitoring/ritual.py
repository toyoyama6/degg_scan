##################################
##Run this script for monitoring
##at a constant temperature
##it does not re-calibrate gain!
##################################


import sys, os
import click
import time
import numpy as np
from termcolor import colored
from datetime import datetime
from tqdm import tqdm

from scipy.optimize import curve_fit
from scipy.optimize import least_squares
from scipy.optimize import brentq
from scipy import stats as scs

from chiba_slackbot import send_warning
from chiba_slackbot import send_message

#####
from degg_measurements.utils import load_run_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.analysis import calc_baseline

from degg_measurements.daq_scripts.degg_cal import DEggCal
from degg_measurements.daq_scripts.degg_cal import PMTCal
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.master_scope import exit_gracefully
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.daq_scripts.measure_gain_online import min_gain_check
from degg_measurements.daq_scripts.measure_dt import min_delta_t
from degg_measurements.daq_scripts.measure_spe import min_charge_stamp_gain_calibration
from degg_measurements.daq_scripts.measure_scaler import min_measure_scaler
from degg_measurements.daq_scripts.measure_scaler import min_measure_scaler_fir
from degg_measurements.analysis.gain.analyze_gain import run_fit
from degg_measurements.analysis.gain.analyze_gain import calc_avg_spe_peak_height
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils import log_crash
from degg_measurements.monitoring import readout_sensor
#####
from degg_measurements import DATA_DIR
LOG_FOLDER = os.path.join(DATA_DIR, "crash_logs")

from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101

E_CONST = 1.60217662e-7

def monitor_scaler(session, channel, dac_value, period, deadtime, use_fir,
                   baseline, deggCal, pmt_names, rep, dirname, verbose):
    pmtCal = deggCal.get_pmt_cal(channel)
    hv = pmtCal.hv
    if verbose:
        print(f'Measuring Scalers {pmt_names[channel]}')
    frac_t = 0.25
    threshold = int(baseline + (pmtCal.spe_peak_height * frac_t))
    darkrate_file = os.path.join(dirname, f'{pmt_names[channel]}_scaler_{hv}_{frac_t}_{rep}i.hdf5')
    if use_fir:
        session = min_measure_scaler_fir(
            session,
            channel,
            darkrate_file,
            dac_value,
            frac_t*pmtCal.spe_peak_height,
            period,
            deadtime,
            n_runs=1000
        )
    else:
        session = min_measure_scaler(
            session,
            channel,
            darkrate_file,
            hv,
            dac_value,
            threshold,
            period,
            deadtime,
            n_runs=1000,
            modHV=False)

    session.endStream()

def monitor_gain(session, channel, threshold, dac_value,
                 pmtCal, pmt_names, rep, dirname, verbose, port):
    hv = pmtCal.hv
    samples = 128
    g_file1 = os.path.join(dirname, f'{pmt_names[channel]}_gain_{hv}_{rep}i_1.hdf5')
    if verbose:
        print(f"Gain Check {pmt_names[channel]}")
    session = min_gain_check(session, channel, g_file1, samples,
                             hv, threshold, dac_value, burn_in=0,
                             nevents=30000, modHV=False, port=port)

    ###run analysis, update peak height
    fit_info = run_fit(g_file1, None, 'waveform', save_fig=False)
    new_peak_height = calc_avg_spe_peak_height(
        fit_info['time']*CALIBRATION_FACTORS.fpga_clock_to_s,
        fit_info['waveforms']*CALIBRATION_FACTORS.adc_to_volts,
        fit_info['charges'],
        fit_info['hv'],
        fit_info['popt'][1],
        bl_start=50,
        bl_end=120,
        use_adc=True)
    pmtCal.spe_peak_height = new_peak_height
    if verbose:
        print(f"New Peak Height: {pmt_names[channel]} {new_peak_height} ADC")

    spe_peak_pos = fit_info['popt'][1]
    if np.logical_or(spe_peak_pos < 1.4, spe_peak_pos > 1.8):
        send_warning(
            f'Gain Check for {pmt_names[channel]}:\n' +
            f'SPE peak position is {spe_peak_pos}, which is far away from ' +
            f'the expected peak position of 1.6! '
        )

    ##min_gain_check already ends the stream
    #session.endStream()

def monitor_baseline(session, channel, hv, dac_value, pmt_names,
                     rep, dirname, verbose, modHV=False, setRep=0):
    bl_file0 = os.path.join(dirname, f'{pmt_names[channel]}_baseline_{hv}_{rep}i_{setRep}.hdf5')
    subRep = 0
    while os.path.exists(bl_file0):
        bl_file0 = os.path.join(dirname,
                    f'{pmt_names[channel]}_baseline_{hv}_{rep}i_{setRep}_{subRep}.hdf5')
        subRep += 1
    if verbose:
        print(f"Measure Baseline {pmt_names[channel]}")
    ##NOTE: min_measure_baseline ends the stream
    session = min_measure_baseline(session, channel, bl_file0, 1024, dac_value,
                                   hv, nevents=100, modHV=modHV)
    baseline = calc_baseline(bl_file0)['baseline'].values[0]
    if verbose:
        print(f"Baseline {pmt_names[channel]}: {baseline}")
    return baseline

def monitor_delta_t(session, channel, dac_value, dirname, rep,
                    threshold, deggCal, pmt_names,
                    use_fir, verbose, port):
    pmtCal = deggCal.get_pmt_cal(channel)
    frac_t = 0.25
    burn_in = 0
    if verbose:
        print(f"Delta-T {pmt_names[channel]}")

    ###run delta-t
    hvs = [deggCal.get_pmt_cal(0).hv, deggCal.get_pmt_cal(1).hv]
    if use_fir == True:
        dt_file = os.path.join(
            dirname,
            f'{pmt_names[channel]}_delta_t_{hvs[channel]}_withFIR_{rep}i.hdf5')
    if use_fir == False:
        dt_file = os.path.join(
            dirname,
            f'{pmt_names[channel]}_delta_t_{hvs[channel]}_noFIR_{rep}i.hdf5')
    ##NOTE: min_delta_t ends the stream
    setup_time = datetime.now()
    try:
        session = min_delta_t(
            session=session,
            channel=channel,
            hv0=hvs[0], hv1=hvs[1],
            filename=dt_file,
            threshold=threshold,
            threshold_over_baseline=frac_t*pmtCal.spe_peak_height,
            dac_value=dac_value,
            burn_in=burn_in,
            nevents=10000,
            use_fir=use_fir,
            port=port
        )
    except Exception as e:
        crash_time = datetime.now()
        print(f'Error in min_delta_t: {pmt_names[channel]}')
        print(e)
        send_message(f'Error in {port}:{channel} min_delta_t: {pmt_names[channel]} (use_fir={use_fir})')
        send_message(f'Exception was: {e}')
        send_message(f'Threshold over baseline was: {frac_t*pmtCal.spe_peak_height}')

        temp = np.nan
        if session is not None:
            temp = readout_sensor(session, 'temperature_sensor')
        readout_hv = readout_sensor(session, f'voltage_channel{channel}')
        ##let's keep track of the errors
        log_crash(
            "{}_delta_t_crash.csv".format(pmt_names[channel]),
            setup_time,
            crash_time,
            port,
            channel,
            temp,
            readout_hv,
            hvs[channel],
            0.0, # darkrate
            threshold,
            pmtCal.spe_peak_height, # spe peak height,
            use_fir
        )
        try:
            comms_log = session.getCommsLogs()
            if len(comms_log)<60:
                send_message(comms_log)
            else:
                logfile = open(os.path.join(LOG_FOLDER, "comms_logs.txt"), 'at')
                logfile.write(comms_log)
                logfile.write("\n")
                logfile.close()
        except Exception as e:
            send_message("I tried getting the comms logs in ritual.py but failed to.")

    ##just to separate the issues
    try:
        session.endStream()
    except:
        send_message(f'Problem ending the stream for {pmt_names[channel]}')

def measure_degg(deggCal, index, dirname, rep, use_fir, verbose=False):
    degg_file = deggCal.degg_file
    degg_dict = deggCal.degg_dict
    port = degg_dict['Port']
    meas_key = deggCal.key
    if audit_ignore_list(degg_file, degg_dict, meas_key) == True:
        return index

    session = startIcebootSession(host='localhost', port=int(port))
    deggCal.session = session

    dac_value = 30000
    period = 100000
    deadtime = 24

    pmt_names = [degg_dict['LowerPmt']['SerialNumber'],
                 degg_dict['UpperPmt']['SerialNumber']]

    ##work in progress
    #pressure = -1
    pressure = readout_sensor(session, 'pressure')
    ############################

    channels = [0, 1]
    pmt_dict = ['LowerPmt', 'UpperPmt']
    for channel in channels:
        ts_now = datetime.now().timestamp()
        readback_hv = readout_sensor(session, f'voltage_channel{channel}')

        meas_dict = degg_dict[pmt_dict[channel]][meas_key]
        meas_dict[f'Pressure{rep}'] = pressure
        meas_dict[f'HVReadBack{rep}'] = readback_hv

        ##measure baseline
        baseline = monitor_baseline(session, channel,
                                    deggCal.get_pmt_cal(channel).hv,
                                    dac_value,
                                    pmt_names, rep, dirname, verbose)
        threshold = int(baseline + 25)

        ##monitor gain without changing HV, get peak height
        monitor_gain(session, channel, threshold, dac_value,
                     deggCal.get_pmt_cal(channel),
                     pmt_names, rep, dirname,
                     verbose, port)

        ###run dark rate (scaler)
        monitor_scaler(session, channel, dac_value,
                       period, deadtime, use_fir,
                       baseline, deggCal, pmt_names,
                       rep, dirname, verbose)

        monitor_delta_t(session, channel, dac_value,
                        dirname, rep, threshold,
                        deggCal, pmt_names,
                        use_fir, verbose, port)

        ts_later = datetime.now().timestamp()
        print(f'Time Elasped {port}:{channel} {(ts_later - ts_now):.1f} s')

        ##end for ch0 or ch1
        deggCal.session.endStream()

    update_json(degg_file, degg_dict)

    #exit_gracefully(session)
    print(f'Ending Stream {port}')
    deggCal.session.endStream()
    print(f'Closing session {port}')
    deggCal.session.close()
    deggCal.session = None
    del session
    return index

def gain_func(x, norm, exponent):
    val = norm * np.power(x, exponent)
    return val

def shifted_gain_func(x, norm, exponent, shift=1e7):
    shifted_val = gain_func(x, norm, exponent) - shift
    return shifted_val

def calculate_gain(high_voltages, gain_list):
    if len(high_voltages) != len(gain_list):
        raise ValueError('HV and SPE peak positions should have the same length!')
    sys_err = [0] * len(gain_list)
    for i, gain in enumerate(gain_list):
        g_err = gain * 0.02
        sys_err[i] = g_err
    combined_err = sys_err

    if len(gain_list) == 1:
        return gain, combined_err, None, None

    p0 = [1e-18, 7]
    popt, pcov = curve_fit(gain_func, high_voltages, gain_list,
                           p0=p0, sigma=combined_err, maxfev=10000)

    fitted_gain = gain_func(high_voltages, *popt)

    min_voltage = np.maximum(1000, np.min(high_voltages) - 480)
    max_voltage = np.minimum(2000, np.max(high_voltages) + 480)
    try:
        ctrl_v_at_1e7_gain = brentq(shifted_gain_func,
                                    min_voltage,
                                    max_voltage,
                                    args=tuple(popt))
    except ValueError:
        print(colored(
            'Can not find a solution with brentq. Using min/max voltage!', 'red'))
        if (shifted_gain_func(min_voltage, *popt) <
                shifted_gain_func(max_voltage, *popt)):
            ctrl_v_at_1e7_gain = min_voltage
        else:
            ctrl_v_at_1e7_gain = max_voltage
    return ctrl_v_at_1e7_gain


def setup_classes(run_file, max_i, use_fir, gain_reference='latest'):
    DEggCalList = []
    #load all degg files
    list_of_deggs = load_run_json(run_file)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)
    ##this name is depricated!
    #measurement_type = "darkrate_temperature"
    ##filepath for saving data
    measurement_type = "advanced_monitoring"
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    ##this name is depricated!
    #meas_key = 'DarkrateTemperature'
    meas_key = 'AdvancedMonitoring'
    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        meas_key,
        comment='',
        Folder=dirname,
        MaxIter=max_i,
        UseFir=use_fir
    )

    for degg_file in sorted_degg_files:
        degg = DEggCal(degg_file, keys[0][0], gain_reference=gain_reference)
        DEggCalList.append(degg)

    return DEggCalList, dirname


def constant_monitor(run_file, max_i, n_jobs, use_fir=False, verbose=False, ignoreWarn=False):
    ignoreWarn = bool(ignoreWarn)
    print(f'Configured to run for {max_i} iterations')

    ##disable the function generator
    fg = FG3101()
    fg.disable()

    max_i = int(max_i)
    DEggCalList, dirname = setup_classes(run_file, max_i, use_fir)
    indexList = np.arange(len(DEggCalList))
    do_run = True
    i = 0

    hvOn = 0
    for deggCal in DEggCalList:
        degg_dict = deggCal.degg_dict
        port = degg_dict['Port']
        pmtName = ['LowerPmt', 'UpperPmt']
        #deggCal.session = startIcebootSession(host='localhost', port=int(port))
        session = startIcebootSession(host='localhost', port=int(port))
        for channel in [0, 1]:
            hv_enabled = checkHV(session, channel)
            hvOn += hv_enabled
            pmt = pmtName[channel]
            if hv_enabled == False:
                session.enableHV(channel)
                session.setDEggHV(channel, degg_dict[pmt]['HV1e7Gain'])
                if ignoreWarn == False:
                    msg_str = 'During constant Temp monitoring, HV should be constantly enabled.'
                    msg_str = msg_str + f' However Port {port}:{channel} was observed to be less'
                    msg_str = msg_str + f' than 1000 V! HV will ramp, but this will be logged.'
                    send_warning(msg_str)
                degg_dict[pmt][deggCal.key]['ResetHV'] = 'Yes'
            if hv_enabled == True:
                degg_dict[pmt][deggCal.key]['ResetHV'] = 'No'

        ##make the session available for inside the loop
        session.close()
        del session
    ##hv needs to be ramped
    if hvOn != (len(DEggCalList)*2):
        for i in tqdm(range(40), desc='HV Ramp'):
            time.sleep(1)

    if n_jobs == 1:
        print("Running in series - testing 1 module!")
        measure_degg(deggCal=DEggCalList[0], index=indexList[0],
                     dirname=dirname, rep=i, use_fir=use_fir, verbose=verbose)
        return

    before = datetime.now().timestamp()
    while do_run:
        print(i)
        results = run_jobs_with_mfhs(
            measure_degg,
            n_jobs,
            deggCal=DEggCalList,
            index=indexList,
            dirname=dirname,
            rep=i,
            use_fir=use_fir,
            verbose=verbose)
        for result in results:
            #_deggCal, index = result.result()
            index = result.result()
            #DEggCalList[index] = _deggCal
        if i >= max_i:
            break
        i += 1
    now = datetime.now().timestamp()
    fullTime = (now - before)/3600 #hr
    print(f"Done - This script ran for {i} iterations ({fullTime:.2f} hrs)")

@click.command()
@click.argument('run_file')
@click.argument('max_i')
@click.option('--n_jobs', '-j', default=4)
@click.option('--use_fir', is_flag=True)
@click.option('--verbose', is_flag=True)
@click.option('--ignoreWarn', '-i', is_flag=True)
def main(run_file, max_i, n_jobs, use_fir, verbose, ignoreWarn):
    max_i = int(max_i)
    if max_i < 0:
        raise ValueError(f'max_i of {max_i} is not valid!')
    constant_monitor(run_file, max_i, n_jobs, use_fir, verbose, ignoreWarn)

if __name__ == "__main__":
    main()

##end
