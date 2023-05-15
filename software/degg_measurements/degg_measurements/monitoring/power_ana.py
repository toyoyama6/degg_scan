import sys, os
import pandas as pd
import click
import numpy as np
import matplotlib.pyplot as plt

from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path

def plot_all_ports(df, savedir):
    ##i mon
    fig1, ax1 = plt.subplots()
    ibinning = np.linspace(0, 1200, 600)
    for key in df.keys():
        if key in ['powerIsValid', 'port', 'degg_name', 'n_reads']:
            continue
        fig2, ax2 = plt.subplots()
        vals = df[f'{key}'].values
        if key[0] == 'i':
            ax1.hist(vals, ibinning, histtype='step', label=key)
        if key[0] == 'v':
            ax2.hist(vals, histtype='step')
            ax2.set_title(key)
            ax2.set_xlabel('Voltage Mon [V]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'v_mon_{key}_total.pdf'))
        if key == 'power':
            ax2.hist(vals, histtype='step')
            ax2.set_title(key)
            ax2.set_xlabel('Power [W]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'power_mon_total.pdf'))
        if key == 'hv0':
            hv_std = np.append(df.hv_std0.unique(), df.hv_std1.unique())
            ax2.hist(hv_std, 200, histtype='step', color='royalblue')
            ax2.axvline(0.02, color='salmon', label='Upper Limit')
            ax2.legend()
            ax2.set_title('HV Read-back')
            ax2.set_xlabel('HV Read-back Std [V]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'hv_std_total.pdf'))

            hv_diffs = np.append(df.hv_diff0.unique(), df.hv_diff1.unique())
            fig3, ax3 = plt.subplots()
            ax3.hist(hv_diffs, 200, histtype='step', color='royalblue')
            ax3.axvline(150, color='salmon', label='Upper Limit')
            ax3.legend()
            ax3.set_title('HV Read-back')
            ax3.set_xlabel('HV Read-back - HV @ 1e7 Gain [V]')
            ax3.set_ylabel('Entries')
            fig3.savefig(os.path.join(savedir, f'hv_diff_total.pdf'))
            plt.close(fig3)

        plt.close(fig2)

    ax1.set_title('I_Mon')
    ax1.set_xlabel('Current [mA]')
    ax1.set_ylabel('Entries')
    ax1.legend()
    fig1.savefig(os.path.join(savedir, f'i_mon_total.pdf'))
    plt.close(fig1)

def plot_single_port(df, savedir):
    ##i mon
    fig1, ax1 = plt.subplots()
    ibinning = np.linspace(0, 1200, 600)
    for key in df.keys():
        fig2, ax2 = plt.subplots()
        if key in ['powerIsValid', 'port', 'degg_name', 'n_reads']:
            continue
        vals = df[f'{key}'].values
        if key[0] == 'i':
            ax1.hist(vals, ibinning, histtype='step', label=key)
        if key[0] == 'v':
            ax2.hist(vals, histtype='step')
            ax2.set_title(key)
            ax2.set_xlabel('Voltage Mon [V]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'v_mon_{key}_{df.port.values[0]}.pdf'))
        if key == 'power':
            ax2.hist(vals, histtype='step')
            ax2.set_title(key)
            ax2.set_xlabel('Power [W]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'power_mon_{df.port.values[0]}.pdf'))
        if key == 'hv0' or key == 'hv1':
            ax2.hist(vals, histtype='step')
            ax2.set_title(key)
            ax2.set_xlabel('Voltage Read-back [V]')
            ax2.set_ylabel('Entries')
            fig2.savefig(os.path.join(savedir, f'{key}_mon_{df.port.values[0]}.pdf'))

            fig3, ax3 = plt.subplots()
            ax3.plot(np.arange(len(vals)), vals, 'o', color='royalblue')
            ax3.set_title(key)
            ax3.set_xlabel('Measurement Number')
            ax3.set_ylabel('Voltage Read-back [V]')
            fig3.savefig(os.path.join(savedir, f'{key}_mon_t_{df.port.values[0]}.pdf'))
            plt.close(fig3)
        ##check the deltaT between measurements - should be constant?
        if key == 'start_time':
            deltaT = np.diff(vals)
            ax2.plot(np.arange(len(deltaT)), deltaT, 'o', color='royalblue')
            ax2.set_title('Time Info')
            ax2.set_ylabel(r'$\Delta$T [s]')
            ax2.set_xlabel('Sample No.')
            fig2.savefig(os.path.join(savedir, f'time_diff_{df.port.values[0]}.pdf'))

        plt.close(fig2)

    ax1.set_title('I_Mon')
    ax1.set_xlabel('Current [mA]')
    ax1.set_ylabel('Entries')
    ax1.legend()
    fig1.savefig(os.path.join(savedir, f'i_mon_{df.port.values[0]}.pdf'))
    plt.close(fig1)

def get_measurement_number(measurement_number, degg_dict):
    data_key = 'OnlineMon'
    if measurement_number == 'latest':
        eligible_keys = [key for key in degg_dict.keys() if key.startswith(data_key)]
        cts = [int(key.split('_')[1]) for key in eligible_keys]
        if len(cts) == 0:
            print(f'No measurement found for '
                  f'in DEgg {degg_dict["DEggSerialNumber"]}. '
                  f'Skipping it!')
            return None
        measurement_number = np.max(cts)
    else:
        measurement_number = int(measurement_number)

    suffix = f'_{measurement_number:02d}'
    data_key_to_use = data_key + suffix
    print(data_key_to_use)
    try:
        this_dict = degg_dict[data_key_to_use]
    except KeyError:
        print(f'KeyError: {data_key_to_use} - {degg_dict["DEggSerialNumber"]}')
        exit(1)

    return data_key_to_use

@click.command()
@click.argument('run_json')
@click.option('--measurement_number', '-n', default='latest')
def main(run_json, measurement_number):

    proto_savedir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if not os.path.exists(proto_savedir):
        os.mkdir(proto_savedir)

    dfList = []

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        data_key = get_measurement_number(measurement_number, degg_dict)
        if data_key == None:
            raise KeyError(f'No valid keys found!')

        savedir = os.path.join(proto_savedir, data_key)
        if not os.path.exists(savedir):
            os.mkdir(savedir)

        filepath = degg_dict[data_key]['Folder']
        if filepath == "None":
            print(f'No data for {degg_dict["DEggSerialNumber"]}, {degg_dict["Port"]}')
            continue
        else:
            filepath = os.path.join(filepath, f'mon_{degg_dict["Port"]}.hdf5')


        df = pd.read_hdf(filepath)
        start_time = np.min(df.start_time.values)
        stop_time = np.max(df.start_time.values)
        print(f'{df.port.values[0]}: {stop_time - start_time}')

        df['hv_ave0']  = np.mean(df.hv0.values)
        df['hv_std0']  = np.std(df.hv0.values)
        df['hv_diff0'] = abs(np.mean(df.hv0.values) - df.hv1e7gain0.values[0])
        df['hv_ave1']  = np.mean(df.hv1.values)
        df['hv_std1']  = np.std(df.hv1.values)
        df['hv_diff1'] = abs(np.mean(df.hv1.values) - df.hv1e7gain1.values[0])
        plot_single_port(df, savedir)
        dfList.append(df)

    if len(dfList) != 0:
        df_total = pd.concat(dfList)
        plot_all_ports(df_total, savedir)
    else:
        print('No data from this run!')

if __name__ == "__main__":
    main()
##end
