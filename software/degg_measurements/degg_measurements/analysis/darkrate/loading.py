import matplotlib.pyplot as plt

import tables
import numpy as np
from degg_measurements.utils import read_data
import os
import pandas as pd
import time as t
from datetime import datetime
from warnings import warn

# Average SPE peak heights for
# SQ0286, 0289, 0290, 0331 calculated from digital measurements
SPE_PEAK_HEIGHT_DICT = {
    'sq0286': 0.00515506,
    'sq0289': 0.00464652,
    'sq0290': 0.00523450,
    'sq0331': 0.00477576
}
VOLT_SCALING = {'Rev4.1': 0.075e-3,
                'Rev3' : 0.089e-3}
FPGA_CLOCK_TO_S = 1. / 240e6


def make_darkrate_df(filenames,
                     adc_threshold=None,
                     pe_threshold=None,
                     deadtime=24,
                     **kwargs):
    final_df = pd.DataFrame()

    for filename in filenames:
        event_id, time, waveforms, timestamp, pc_time, parameter_dict = \
            read_data(filename)
        pmt = parameter_dict[parameter_dict['pmt'] + '.SerialNumber']
        pmt_loc = parameter_dict['pmt']

        df = pd.DataFrame()
        df['pmt'] = pd.Series(pmt)
        df['pmt_loc'] = pd.Series(pmt_loc)
        df['filename'] = pd.Series(filename)

        mainboard = parameter_dict.get('MainboardNumber', '')
        if mainboard.startswith('4.1') or mainboard.startswith('4A'):
            volt_scaling = VOLT_SCALING['Rev4.1']
        else:
            print('Using volt scaling for Rev3 mainboards!')
            volt_scaling = VOLT_SCALING['Rev3']
        spe_peak_height = SPE_PEAK_HEIGHT_DICT.get(pmt.lower(), None)
        if spe_peak_height is None:
            spe_peak_height = float(
                parameter_dict[parameter_dict['pmt'] + '.SPEPeakHeight'])

        if adc_threshold is not None and pe_threshold is not None:
            raise ValueError('Can only use adc_threshold or pe_threshold!')

        if adc_threshold is not None:
            df['thresh'] = adc_threshold * volt_scaling / spe_peak_height
            threshold = adc_threshold
        elif pe_threshold is not None:
            df['thresh'] = pe_threshold
            threshold = np.ceil(spe_peak_height * pe_threshold / volt_scaling)

        df['deadtime'] = deadtime * FPGA_CLOCK_TO_S
        baseline = np.median(waveforms)

        # t0 = t.monotonic()
        # deadtime_fill = np.ones((waveforms.shape[0], deadtime)) * baseline
        # waveforms_ = np.append(waveforms, deadtime_fill, axis=1).flatten()
        # unique_diffs = np.unique(np.diff(np.where(waveforms_ - baseline > threshold)[0]))
        # mask = np.logical_or(unique_diffs <= 1, unique_diffs > deadtime)
        # n_noise = np.sum(mask)
        # print(f'n_noise: {n_noise}')

        # t1 = t.monotonic()
        n_noise = 0
        for i, wf in enumerate(waveforms):
            unique_diffs = np.unique(np.diff(np.where(wf - baseline > threshold)[0]))
            mask = np.logical_or(unique_diffs <= 1, unique_diffs > deadtime)
            n_noise += np.sum(mask)

        # print(f'n_noise: {n_noise}')
        # t2 = t.monotonic()
        # print(t1-t0, t2-t1)
        total_time = (waveforms.shape[0] * waveforms.shape[1]
            - n_noise * deadtime) * FPGA_CLOCK_TO_S

        df['darkrate'] = n_noise / total_time
        df['darkrate_err'] = np.sqrt(n_noise) / total_time
        for key, val in kwargs.items():
            df[key] = val
        df['temp'] = parameter_dict['degg_temp']
        final_df = final_df.append(df, ignore_index=True)
    return final_df


def read_scaler_data(filename, return_indiv_counts=False, get_time=False):
    print(f'Loading scaler data: {filename}')
    with tables.open_file(filename) as open_file:
        if return_indiv_counts:
            data = open_file.get_node('/data')
            scaler_counts = data.col('scaler_count')
            try:
                datetime_timestamp = data.col('datetime_timestamp')
            except:
                warning_str = filename + " does not include datetime timing information (file is probably older than 2022/05/11)."
                warn(warning_str)
                ##this was the start of FAT
                datetime_timestamp = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
            if get_time == True:
                try:
                    time = data.col('time')
                except:
                    print("No time, Legacy Data? Or just scalers?")
                    time = -1
                try:
                    temperature = data.col('temp')
                except:
                    print("No temp, Legacy Data? Or just scalers?")
                    temperature = -1
                try:
                    high_voltage = data.col('hv')
                except:
                    print("No hv, Legacy Data? Or just scalers?")
                    high_voltage = -1
        parameters = open_file.get_node('/parameters')

        parameter_keys = parameters.keys[:]
        parameter_values = parameters.values[:]
        parameter_dict = {}
        for key, val in zip(parameter_keys, parameter_values):
            key = key.decode('utf-8')
            val = val.decode('utf-8')
            try:
                parameter_dict[key] = int(val)
            except ValueError:
                parameter_dict[key] = val
    if return_indiv_counts and get_time:
        return parameter_dict, scaler_counts, datetime_timestamp, time, temperature, high_voltage
    elif return_indiv_counts:
        return parameter_dict, scaler_counts, datetime_timestamp
    else:
        return parameter_dict


def analyze_scaler_data(parameter_dict):
    try:
        # convert from microseconds to seconds
        total_duration = parameter_dict['period'] / 1e6 * \
            parameter_dict['n_runs']
    except KeyError:
        total_duration = parameter_dict['period'] / 1e6
    # convert from FPGA clock cycles to seconds
    deadtime = parameter_dict['deadtime'] * FPGA_CLOCK_TO_S

    scaler_count = parameter_dict['scaler_count']
    time = total_duration - (scaler_count * deadtime)

    rate = scaler_count / time
    error = np.sqrt(scaler_count / time)
    return rate, error, deadtime, time


def calc_quantiles(data, parameter_dict):
    low_probability = (1 - 0.6827) / 2.
    high_probability = 1 - low_probability

    total_duration = parameter_dict['period'] / 1e6
    deadtime = parameter_dict['deadtime'] * FPGA_CLOCK_TO_S

    time = total_duration - (data * deadtime)

    rate = data / time

    low_q = np.quantile(rate, low_probability)
    high_q = np.quantile(rate, high_probability)

    # if high_q < np.mean(rate):
    #     raise ValueError(f'Upper Quantile ({high_q}) is Lower than Mean ({np.mean(rate)})!')
    # if low_q > np.mean(rate):
    #     raise ValueError(f'Lower Quantile ({low_q}) is Higher than Mean ({np.mean(rate)})!')

    return rate, low_q, high_q


def make_scaler_darkrate_df(filenames,
                            use_quantiles=False,
                            get_time=False,
                            from_monitoring=False,
                            **kwargs):
    final_df = pd.DataFrame()

    if isinstance(filenames, str):
        filenames = [filenames]
    for filename in filenames:
        df = pd.DataFrame()

        if get_time == True:
            parameter_dict, scaler_counts, datetime_timestamp, measure_time, \
                temperature, high_voltage = read_scaler_data(
                        filename, return_indiv_counts=True, get_time=True)
            df['indv_cnt'] = scaler_counts
            df['meas_t'] = measure_time
            df['tempScaler'] = temperature
            df['highVoltage'] = high_voltage
        elif use_quantiles == False and get_time == False:
            parameter_dict = read_scaler_data(filename)
        else:
            parameter_dict, scaler_counts, datetime_timestamp = read_scaler_data(
                filename,
                return_indiv_counts=True)
            #df['indv_cnt'] = scaler_counts
            #df['meas_t'] = np.arange(len(scaler_counts))

        rate, error, deadtime, time = analyze_scaler_data(parameter_dict)
        print(rate, error, deadtime, time)
        if from_monitoring == True:
            volt_scaling = VOLT_SCALING['Rev4.1']
            try:
                df['threshold'] = pd.Series(float(parameter_dict['threshold_over_baseline']))
                df['useFIR'] = pd.Series(True)
            except KeyError:
                df['threshold'] = pd.Series(float(parameter_dict['threshold']))
                df['useFIR'] = pd.Series(False)

        if from_monitoring == False:
            pmt = parameter_dict[parameter_dict['pmt'] + '.SerialNumber']
            pmt_loc = parameter_dict['pmt']
            mainboard = parameter_dict.get('MainboardNumber', '')
            if mainboard.startswith('4.1') or mainboard.startswith('4A'):
                volt_scaling = VOLT_SCALING['Rev4.1']
            else:
                print('Using volt scaling for Rev3 mainboards!')
                volt_scaling = VOLT_SCALING['Rev3']
            spe_peak_height = SPE_PEAK_HEIGHT_DICT.get(pmt.lower(), None)
            if spe_peak_height is None:
                spe_peak_height = float(
                    parameter_dict[parameter_dict['pmt'] + '.SPEPeakHeight'])
            if get_time == True:
                df['pmt'] = pmt
                df['pmt_loc'] = pmt_loc
            else:
                df['pmt'] = pd.Series(pmt)
                df['pmt_loc'] = pd.Series(pmt_loc)
            try:
                df['adcThresh'] = parameter_dict['threshold_over_baseline']
                df['thresh'] = (float(parameter_dict['threshold_over_baseline']) *
                            volt_scaling / spe_peak_height)
            except KeyError:
                print('No Threshold Key! - Assuming 0.25 * SPE!')
                df['thresh'] = np.ceil(spe_peak_height * 0.25 / volt_scaling)

        ##stop strange pandas behaviour - pd.Series()
        df['darkrate'] = pd.Series(rate)
        df['darkrate_err'] = error
        df['deadtime'] = deadtime
        df['period'] = parameter_dict['period']
        df['filename'] = pd.Series(filename)
        df['time'] = time
        print(df)

        if use_quantiles == True:
            dr_list, dr_lower, dr_upper = calc_quantiles(scaler_counts, parameter_dict)
            df['darkrate_lower'] = dr_lower
            df['darkrate_upper'] = dr_upper
            df['darkrate_list']  = [dr_list]

        for key, val in kwargs.items():
            print(key, val)
            df[key] = val
        try:
            df['temp'] = parameter_dict['degg_temp']
        except KeyError:
            print("No temperature info! - Using default of nan")
            df['temp'] = np.nan

        print(df)

        final_df = final_df.append(df, ignore_index=True)
    return final_df


def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys


