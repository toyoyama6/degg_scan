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

#####
from degg_measurements.daq_scripts.degg_cal import DEggCal
from degg_measurements.daq_scripts.degg_cal import PMTCal
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs
from degg_measurements.daq_scripts.master_scope import exit_gracefully
from degg_measurements.daq_scripts.measure_gain_online import min_gain_check
from degg_measurements.daq_scripts.measure_dt import min_delta_t
from degg_measurements.daq_scripts.measure_spe import min_charge_stamp_gain_calibration
from degg_measurements.daq_scripts.measure_scaler import min_measure_scaler

from degg_measurements.utils import load_run_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json

from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis.gain.analyze_gain import run_fit
from degg_measurements.analysis.gain.analyze_gain import calc_avg_spe_peak_height

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring.ritual import monitor_delta_t, monitor_scaler
from degg_measurements.monitoring.ritual import monitor_baseline
#####
from degg_measurements import DATA_DIR

from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101

E_CONST = 1.60217662e-7


def measure_degg(deggCal, index, dirname, rep, use_fir, verbose=False):
    degg_file = deggCal.degg_file
    degg_dict = deggCal.degg_dict
    meas_key = deggCal.key
    if audit_ignore_list(degg_file, degg_dict, meas_key) == True:
        return deggCal, index
    port = degg_dict['Port']
    dac_value = 30000
    burn_in = 1
    samples = 128
    period = 100000
    deadtime = 24

    pmt_names = [degg_dict['LowerPmt']['SerialNumber'],
                 degg_dict['UpperPmt']['SerialNumber']]

    ##make our session, return it throughout
    session = startIcebootSession(host='localhost', port=port)

    pmtCal0 = deggCal.get_pmt_cal(0)
    ##known 1e7 gain HV
    hv0 = pmtCal0.hv
    pmtCal1 = deggCal.get_pmt_cal(1)
    ##known 1e7 gain HV
    hv1 = pmtCal1.hv
    hvList = [hv0, hv1]
    hvOn = 0
    for channel in [0, 1]:
        hv_enabled = checkHV(session, channel)
        hvOn += hv_enabled
        if hv_enabled == False:
            session.enableHV(channel)
            session.setDEggHV(channel, int(hvList[channel]))
    if hvOn < 2:
        for i in tqdm(range(40), desc='HV Ramp'):
            time.sleep(1)

    updown = ['LowerPmt', 'UpperPmt']

    time_active = [0, 0]
    channels = [0, 1]
    for channel in channels:
        ##for uptime metrics
        time_start = datetime.now().timestamp()

        pmtCal = deggCal.get_pmt_cal(channel)
        hv = pmtCal.hv

        ##work in progress
        meas_dict = degg_dict[updown[channel]][meas_key]
        pressure = readout_sensor(session, 'pressure')
        meas_dict['Pressure'] = pressure
        meas_dict['hvOn'] = hvOn
        ############################

        ##measure baseline
        baseline = monitor_baseline(session, channel, hv, dac_value,
                                    pmt_names, rep, dirname, verbose)

        ##perform full gain calibration w/ charge stamp
        threshold = int(baseline + 25)
        if verbose:
            print(f"Gain Scan {pmt_names[channel]}")
        session, gFileList, gainVals, hvVals = \
            min_charge_stamp_gain_calibration(
                session=session, channel=int(channel),
                dirname=dirname, name=pmt_names[channel], hv=hv,
                threshold=int(threshold), dac_value=dac_value, burn_in=burn_in,
                nevents=30000, iteration=rep, mode='scan',
                modHV=False, verbose=True)
        if verbose:
            print(f'Gain Values {pmt_names[channel]}: {gainVals}')
            print(f'HV Values {pmt_names[channel]}: {hvVals}')
            print("-"*20)

        ###set the new HV - ramping will happen in min_measure_baseline
        hv_at_1e7_gain = calculate_gain(hvVals, gainVals)
        hv = int(hv_at_1e7_gain)
        if verbose:
            print(colored(f'HV at 1e7 Gain for {pmt_names[channel]}: {hv}', 'green'))
        pmtCal.hv = hv
        ###re-measure baseline
        baseline = monitor_baseline(session, channel, hv, dac_value,
                                    pmt_names, rep, dirname, verbose,
                                    modHV=True, setRep=1)

        ###run check at new HV
        threshold = int(baseline + 25)
        g_file1 = os.path.join(dirname, f'{pmt_names[channel]}_gain_{hv}_{rep}i_1.hdf5')
        if verbose:
            print(f"Gain Check Again {pmt_names[channel]}")
        session = min_gain_check(session, channel, g_file1, samples,
                                 hv, threshold, dac_value, burn_in,
                                 nevents=20000, modHV=False, port=port)

        ###run analysis, update peak height
        fit_info = run_fit(g_file1, None, 'waveform', save_fig=True)
        ##if calculating this way, peak height is in ADC!
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

        ###run dark rate (scaler)
        monitor_scaler(session, channel, dac_value,
                       period, deadtime, use_fir,
                       baseline, deggCal, pmt_names,
                       rep, dirname, verbose)

        ##reset iceboot here?
        #session.disableDEggTriggers(channel)
        # session.endStream()
        # session.close()
        # del session
        # session = startIcebootSession(host='localhost', port=port)

        ###run delta-t
        t = 0.25
        threshold = int(baseline + (pmtCal.spe_peak_height * t))

        monitor_delta_t(session, channel, dac_value,
                        dirname, rep, threshold, deggCal, pmt_names, 
                        use_fir, verbose, port)

        time_stop = datetime.now().timestamp()
        _time_active = (time_stop - time_start)
        #if we have many loops, should update
        time_active[channel] += _time_active
        meas_dict['tActive'] = time_active[channel]

    update_json(degg_file, degg_dict)

    exit_gracefully(session)
    session.close()
    del session

    return deggCal, index

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
    ##filepath for saving data
    measurement_type = "darkrate_temperature"
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    meas_key = 'DarkrateTemperature'
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


def slowmon(run_file, max_i, n_jobs, use_fir=False, verbose=False):
    print(f'Configured to run for {max_i} iterations')

    ##disable the function generator
    fg = FG3101()
    fg.disable()

    DEggCalList, dirname = setup_classes(run_file, max_i, use_fir)
    indexList = np.arange(len(DEggCalList))
    do_run = True
    i = 0
    if n_jobs == 1:
        print("running in series")
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
            _deggCal, index = result.result()
            DEggCalList[index] = _deggCal
        i += 1
        if i >= int(max_i):
            break

    now = datetime.now().timestamp()
    fullTime = (now - before)/3600 #hr
    print(f"Done - This script ran for {i} iterations ({fullTime:.2f} hrs)")
    print("Done")

@click.command()
@click.argument('run_file')
@click.argument('max_i')
@click.option('--n_jobs', '-j', default=4)
@click.option('--use_fir', is_flag=True)
@click.option('--verbose', is_flag=True)
def main(run_file, max_i, n_jobs, use_fir, verbose):
    slowmon(run_file, max_i, n_jobs, use_fir, verbose)

if __name__ == "__main__":
    main()

##end
