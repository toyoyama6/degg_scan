import tables
import numpy as np
from degg_measurements.utils import read_data
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt

from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json

# Average SPE peak heights for
# SQ0286, 0289, 0290, 0331 calculated from digital measurements
SPE_PEAK_HEIGHT_DICT = {
    'sq0286': 0.00515506,
    'sq0289': 0.00464652,
    'sq0290': 0.00523450,
    'sq0331': 0.00477576
}
VOLT_SCALING = 0.089e-3

PLOT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
PLOT_DIR_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_json')

def make_darkrate_df(filenames):
    final_df = pd.DataFrame()

    for filename in filenames:
        event_id, time, waveforms, timestamp, pc_time, parameter_dict = read_data(filename)
        pmt = parameter_dict[parameter_dict['pmt'] + '.SerialNumber']
        thresh = parameter_dict['threshold_over_baseline']
        time = pc_time[-1] - pc_time[0]

        print(filename)
        plot_name = os.path.basename(filename).replace('.hdf5', '.pdf')
        fig, ax = plt.subplots()
        ax.plot((timestamp-timestamp[0])/240e6, 'o--')
        fig.savefig(os.path.join(PLOT_DIR, plot_name)
        plt.close(fig)


        timestamp_time = (timestamp[-1] - timestamp[0]) / 240e6
        livetime = time - len(event_id) * parameter_dict['Constants.Samples'] / 240e6
        rate = len(event_id) / livetime
        df = pd.DataFrame()
        df['pmt'] = pd.Series(pmt)
        df['thresh'] = thresh * VOLT_SCALING / SPE_PEAK_HEIGHT_DICT[pmt.lower()]
        df['time'] = time
        df['timestamp_time'] = timestamp_time
        df['darkrate'] = rate
        df['darkrate_err'] = np.sqrt(len(event_id)) / livetime
        final_df = final_df.append(df, ignore_index=True)
    return final_df


def read_scaler_data(filename):
    with tables.open_file(filename) as open_file:
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
    return parameter_dict


def analyze_scaler_data(parameter_dict):
    try:
        # convert from microseconds to seconds
        total_duration = parameter_dict['period'] / 1e6 * \
            parameter_dict['n_runs']
    except KeyError:
        total_duration = parameter_dict['period'] / 1e6
    # convert from FPGA clock cycles to seconds
    deadtime = parameter_dict['deadtime'] / 240e6

    scaler_count = parameter_dict['scaler_count']
    time = total_duration - (scaler_count * deadtime)

    rate = scaler_count / time
    error = np.sqrt(scaler_count) / time
    return rate, error, deadtime


def make_scaler_darkrate_df(filenames, **kwargs):
    final_df = pd.DataFrame()
    for filename in filenames:
        parameter_dict = read_scaler_data(filename)
        rate, error, deadtime = analyze_scaler_data(parameter_dict)
        df = pd.DataFrame()
        pmt = parameter_dict[parameter_dict['pmt'] + '.SerialNumber']
        df['pmt'] = pd.Series(pmt)
        df['thresh'] = (parameter_dict['threshold_over_baseline'] *
                        VOLT_SCALING / SPE_PEAK_HEIGHT_DICT[pmt.lower()])
        df['darkrate'] = rate
        df['darkrate_err'] = error
        df['deadtime'] = deadtime
        for key, val in kwargs.items():
            df[key] = val
        final_df = final_df.append(df, ignore_index=True)
    return final_df


def plot_scaler_darkrates(df, suffix=None):
    for u_name in np.unique(df['pmt']):
        fig, ax = plt.subplots()
        mask = df['pmt'] == u_name
        temp_df = df.loc[mask]
        temperatures = [-40]
        for temperature in temperatures:
            mask = np.logical_and(
                temp_df['DEggSurfaceTemp'] > temperature - 10,
                temp_df['DEggSurfaceTemp'] < temperature + 10)
            ax.errorbar(temp_df.loc[mask, 'thresh'],
                        temp_df.loc[mask, 'darkrate'],
                        yerr=temp_df.loc[mask, 'darkrate_err'],
                        fmt='o',
                        label=temperature)
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_title(u_name.upper())
        ax.set_yscale('log')
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(PLOT_DIR_JSON, f'scaler_darkrate_{u_name}.pdf')
        else:
            filename = os.path.join(PLOT_DIR_JSON, f'scaler_darkrate_{u_name}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_scaler_darkrates(df, suffix=None):
    fig, ax = plt.subplots()
    for u_name in np.unique(df['pmt']):
        mask = df['pmt'] == u_name
        temp_mask = np.logical_and(
            df['DEggSurfaceTemp'] > -50,
            df['DEggSurfaceTemp'] < -30)
        mask = np.logical_and(mask, temp_mask)
        ax.errorbar(df.loc[mask, 'thresh'],
                    df.loc[mask, 'darkrate'],
                    yerr=df.loc[mask, 'darkrate_err'],
                    fmt='o',
                    label=u_name.upper())
    ax.set_xlabel('Threshold / PE')
    ax.set_ylabel('Dark rate / Hz')
    ax.set_yscale('log')
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
    if suffix is None:
        filename = os.path.join(PLOT_DIR_JSON, 'scaler_darkrate_comparison.pdf')
    else:
        filename = os.path.join(PLOT_DIR_JSON, f'scaler_darkrate_comparison_{suffix}.pdf')
    fig.savefig(filename,
                bbox_inches='tight')


def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys


@click.command()
@click.argument('run_json', nargs=-1, type=click.Path(exists=True))
def main(run_json):

    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f'Created directory: {PLOT_DIR}')
    if not os.path.exists(PLOT_DIR_JSON):
        os.mkdir(PLOT_DIR_JSON)
        print(f'Created directory: {PLOT_DIR_JSON}')

    total_df = pd.DataFrame()
    scaler_df = pd.DataFrame()

    for run_json_i in run_json:
        list_of_deggs = load_run_json(run_json)
        for degg_file in list_of_deggs:
            degg_dict = load_degg_dict(degg_file)

            pmts = ['LowerPmt', 'UpperPmt']

            for pmt in pmts:
                pmt_id = degg_dict[pmt]['SerialNumber']
                try:
                    folder = degg_dict[pmt]['DarkrateWaveformsFolder']
                except KeyError:
                    print('Waveform darkrate measurement not found!')
                else:
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    darkrate_df = make_darkrate_df(files)
                    total_df = total_df.append(darkrate_df, ignore_index=True)
                keys = find_keys(degg_dict[pmt], 'DarkrateScalerMeasurement')
                for key in keys:
                    folder = degg_dict[pmt][key]['Folder']
                    temp = degg_dict[pmt][key]['DEggSurfaceTemp']
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    scaler_df_i = make_scaler_darkrate_df(files,
                                                          DEggSurfaceTemp=temp,
                                                          key=key)
                    scaler_df = scaler_df.append(scaler_df_i, ignore_index=True)
    print(total_df)
    print(scaler_df)
    plot_scaler_darkrates(scaler_df)
    compare_scaler_darkrates(scaler_df)
    return total_df, scaler_df


if __name__ == '__main__':
    main()

