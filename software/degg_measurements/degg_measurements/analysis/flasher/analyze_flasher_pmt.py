import numpy as np
import matplotlib.pyplot as plt
import os, sys
import pandas as pd
from glob import glob
import click
import tables

from degg_measurements.utils import read_data
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path

def signalPlots(df_off, df_on, degg_id, savedir, mode='all'):
    if mode == 'horizontal':
        label_list = ['0x0001', '0x0004', '0x0008', '0x0020', 
                      '0x0040', '0x0100', '0x0200', '0x0800']
        mode_list = [1, 4, 8, 32, 64, 256, 512, 2048]
        df_signal = df_on.loc[df_on['Dir'] == 'horizontal']
        df_bkg = df_off.loc[df_off['Dir'] =='horizontal']
    elif mode == 'vertical':
        label_list = ['0x0002', '0x0010', '0x0080', '0x0400']
        mode_list = [2, 16, 128, 1024]
        df_signal = df_on.loc[df_on['Dir'] == 'vertical']
        df_bkg = df_off.loc[df_off['Dir'] == 'vertical']
    else:
        df_signal = df_on
        df_bkg = df_off
        label_list = ['0x0001', '0x0002', '0x0004', '0x0008', '0x0010',
                      '0x0020', '0x0040', '0x0080', '0x0100', '0x0200',
                      '0x0400', '0x0800']
        c0 = 'royalblue'
        c1 = 'goldenrod'
        color_list = [c0, c1, c0, c0, c1, c0, c0, c1, c0, c0, c1, c0]

    low_hv = df_signal["HVLowGain"].values[0]

    fig1, ax1 = plt.subplots()
    ax1.set_title(f'Flasher Scaler Test, HV={low_hv} V')
    ax1.set_ylabel('Rate [Hz]')
    ax1.set_xlabel(f'LED Configuration {degg_id} - {mode}')
    if mode == 'horizontal' or mode == 'vertical':
        ax1.plot(np.arange(df_signal.index.size), df_signal['Rate'], 
                 marker='o', linewidth=0, color='royalblue', label=mode)
        ax1.legend()
    else:
        ax1.scatter(np.arange(df_signal.index.size), df_signal['Rate'], marker='o', 
                 linewidth=0, color=color_list)

    fig1.tight_layout()
    fig1.savefig(savedir + f'signal_{degg_id}_{mode}.pdf')

def baselinePlots(df_0, df_off, degg_id, savedir):
    off_rate = df_off['Rate'].values
    null_rate = df_0['Rate'].values[0]
    diff = abs(off_rate - null_rate)
    low_hv = df_off["HVLowGain"].values[0]
    fig1, ax1 = plt.subplots()
    ax1.plot(np.arange(len(diff)), diff, marker='o', linewidth=0)
    ax1.set_xlabel(f'LED Configuration {degg_id}')
    ax1.set_title(f'Null Measurements, HV={low_hv} V')
    ax1.set_ylabel('Off - Baseline [Hz]')
    fig1.savefig(savedir + f'null_{degg_id}.pdf')

def flasher_plot(df, degg_id, savedir):
    df_on = df.loc[df['FlasherStatus'] == True]
    df_off = df.loc[(df['FlasherStatus'] == False) & (df['Config'] != 0)]

    ## calculate difference in the on/off rates, use config 0 for baseline
    df_0 = df.loc[df['Config'] == 0]

    print(df_0)
    print(df_off)
    print(df_on)

    baselinePlots(df_0, df_off, degg_id, savedir)
    signalPlots(df_off, df_on, degg_id, savedir, mode='all')
    signalPlots(df_off, df_on, degg_id, savedir, mode='horizontal')
    signalPlots(df_off, df_on, degg_id, savedir, mode='vertical')

def read_scaler_data(filename, return_indiv_counts=False):
    with tables.open_file(filename) as open_file:
        if return_indiv_counts:
            data = open_file.get_node('/data')
            scaler_counts = data.col('scaler_count')
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
    if return_indiv_counts:
        return parameter_dict, scaler_counts
    else:
        return parameter_dict


def analyze_scaler_data(parameter_dict):
    try:
        # convert from microseconds to seconds
        total_duration = (parameter_dict['period'] / 1e6 *
            parameter_dict['n_runs'])
    except KeyError:
        total_duration = parameter_dict['period'] / 1e6 
    # convert from FPGA clock cycles to seconds
    deadtime = parameter_dict['deadtime'] / 240e6

    scaler_count = parameter_dict['scaler_count']
    time = total_duration - (scaler_count * deadtime)

    rate = scaler_count / time
    error = np.sqrt(scaler_count / time)
    return rate, error, deadtime, time

def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys

def flasher_ana(degg_dict):
    data_key = 'FlasherCheck'
    degg_id = degg_dict['DEggSerialNumber']
    pmt_id = degg_dict['LowerPmt']['SerialNumber']
    print(f"DEGG ID: {degg_id}, PMT ID: {pmt_id}")
    keys = find_keys(degg_dict['LowerPmt'], data_key)

    rate_l = []
    error_l = []
    deadtime_l = []
    time_l = []
    status_l = []
    config_l = []
    dir_l = []
    key_l = []
    low_hv_l = []

    for key in keys:
        folder = degg_dict['LowerPmt'][key]['Folder']
        low_hv = degg_dict['LowerPmt']['HVLowGain']
        files = glob(os.path.join(folder, pmt_id + '*.hdf5'))

        if len(files) != 25:
            raise ValueError("Please check that all files finished - should be 25")
        for i, file_name in enumerate(files):
            try:
                scaler_dict = read_scaler_data(file_name)
                rate, error, deadtime, time = analyze_scaler_data(scaler_dict)
            except UnboundLocalError:
                print(colored("Likely Error Opening File - Measurement was killed early?", 'red'))
                continue

            ##determine if flasher was On or Off from filename
            ##0 || negative value = Off
            b_file_name = os.path.basename(file_name)
            split = b_file_name.split("_")
            subsplit = split[1]
            config = subsplit.split(".")[0]
            if float(config) <= 0:
                status = False
            elif float(config) > 0:
                status = True
            else:
                raise ValueError("Could not determine flasher status from file")
            horizontal_list = [1, 4, 8, 32, 64, 256, 512, 2048]
            vertical_list = [2, 16, 128, 1024]
            direction = 'none'
            
            if abs(int(config)) in horizontal_list:
                direction = 'horizontal'
            
            if abs(int(config)) in vertical_list:
                direction = 'vertical'
            
            rate_l.append(rate)
            error_l.append(error)
            deadtime_l.append(deadtime)
            time_l.append(time)
            status_l.append(status)
            config_l.append(float(config))
            dir_l.append(direction)
            key_l.append(key)
            low_hv_l.append(low_hv)

    d = {'Rate': rate_l,
         'Error': error_l,
         'Deadtime': deadtime_l,
         'Time': time_l,
         'FlasherStatus': status_l,
         'Config': config_l,
         'Dir': dir_l,
         'Key': key_l,
         'HVLowGain': low_hv_l}
    df = pd.DataFrame(data=d)
    print(df)
    return df

@click.command()
@click.argument('run_json')
def main(run_json):
    list_of_deggs = load_run_json(run_json)
    savedir = '/home/scanbox/data/develop/flasher_baseline_scaler/plots/'
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        df = flasher_ana(degg_dict)
        degg_id = degg_dict['DEggSerialNumber']
        flasher_plot(df, degg_id, savedir)

if __name__ == "__main__":
    main()

##end
