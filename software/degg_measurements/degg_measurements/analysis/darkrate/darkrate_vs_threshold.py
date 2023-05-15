import numpy as np
import tables
import pandas as pd
from glob import glob
import os
from matplotlib import pyplot as plt
from degg_measurements.utils import read_data
from degg_measurements.utils import DEggLogBook
from degg_measurements.analysis import Result
from scipy.interpolate import interp1d

# Average SPE peak heights for 
# SQ0286, 0289, 0290, 0331 copied from ratafia jsonfiles
# SPE_PEAK_HEIGHTS = [0.0151776, 0.0166259,
#                     0.0092614, 0.0135131]

# Average SPE peak heights for
# SQ0286, 0289, 0290, 0331 calculated from digital measurements
SPE_PEAK_HEIGHTS = [0.00515506, 0.00464652,
                    0.00523450, 0.00477576]
SPE_PEAK_HEIGHT_DICT = {
    'sq0286': 0.00515506,
    'sq0289': 0.00464652,
    'sq0290': 0.00523450,
    'sq0331': 0.00477576
}
VOLT_SCALING = 0.089e-3


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


def plot_scaler_darkrates(dfs, labels, suffix=None):
    for u_name in np.unique(dfs[0]['pmt']):
        
        fig, ax = plt.subplots()
        for df, label in zip(dfs, labels):
            mask = df['pmt'] == u_name
            ax.errorbar(df.loc[mask, 'thresh'],
                        df.loc[mask, 'darkrate'],
                        yerr=df.loc[mask, 'darkrate_err'],
                        fmt='o',
                        label=label)
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_title(u_name.upper())
        ax.set_yscale('log')
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = f'figs/scaler_darkrate_{u_name}.pdf'
        else:
            filename = f'figs/scaler_darkrate_{u_name}_{suffix}.pdf'
        fig.savefig(filename,
                    bbox_inches='tight')


def make_darkrate_df(filenames):
    final_df = pd.DataFrame()

    for filename in filenames:
        event_id, time, waveforms, timestamp, pc_time, parameter_dict = read_data(filename)
        pmt = parameter_dict['name']
        thresh = int(os.path.basename(filename).split('.')[0].split('_')[-1])
        time = pc_time[-1] - pc_time[0] 
        livetime = time - len(event_id) * parameter_dict['samples'] / 240e6
        plot_time_diffs(pc_time, pmt, thresh)
        rate = len(event_id) / livetime 
        df = pd.DataFrame()
        df['pmt'] = pd.Series(pmt)
        df['thresh'] = thresh * VOLT_SCALING / SPE_PEAK_HEIGHT_DICT[pmt]
        df['time'] = time
        df['darkrate'] = rate
        df['darkrate_err'] = np.sqrt(len(event_id)) / livetime
        final_df = final_df.append(df, ignore_index=True)
    return final_df

def plot_time_diffs(pc_time, pmt, threshold):
    fig, ax = plt.subplots()
    time_diffs = np.diff(pc_time)
    ax.hist(time_diffs, bins=51)
    ax.set_yscale('log')
    fig.savefig(f'figs/prev_time_diffs_{pmt}_{threshold}.pdf')
    plt.close()


def make_scaler_darkrate_df(filenames):
    final_df = pd.DataFrame()
    for filename in filenames:
        parameter_dict = read_scaler_data(filename)
        rate, error, deadtime = analyze_scaler_data(parameter_dict)
        df = pd.DataFrame()
        pmt = parameter_dict['name']
        df['pmt'] = pd.Series(pmt)
        df['thresh'] = (parameter_dict['threshold_over_baseline'] *
                        VOLT_SCALING / SPE_PEAK_HEIGHT_DICT[pmt])
        df['darkrate'] = rate
        df['darkrate_err'] = error
        df['deadtime'] = deadtime
        final_df = final_df.append(df, ignore_index=True)
    return final_df


def load_analogue_data_as_df(filename):
    analogue_data = np.load(filename)
    analogue_df = pd.DataFrame()

    for key in analogue_data.keys():
        df = pd.DataFrame()
        data = analogue_data[key]
        df['pmt'] = pd.Series(np.tile(key.lower(), data.shape[0]))
        df['thresh'] = data[:, 0]
        df['darkrate'] = data[:, 1]
        df['darkrate_err'] = data[:, 2]
        analogue_df = analogue_df.append(df, ignore_index=True)
    return analogue_df
    

def analyze_darkrates(df, analogue_data):
    for i, u_name in enumerate(np.unique(df['pmt'])):
        print(u_name)
        fig, ax = plt.subplots()
        mask = df['pmt'] == u_name
        ax.set_title(u_name.upper())
        ax.errorbar(*(analogue_data[u_name.upper()].T), fmt='o',
                    label=r'Analogue measurement @ $-35^{\circ}$C')
        ax.plot(df.loc[mask, 'thresh']*VOLT_SCALING/SPE_PEAK_HEIGHTS[i],
                df.loc[mask, 'darkrate'], 'o',
                label='Full D-Egg measurement @ $-50^{\circ}$C')
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Darkrate / Hz')
        ax.legend()
        fig.savefig(f'figs/darkrate_{u_name}.pdf', bbox_inches='tight')


def extract_darkrate_values_from_df(df, pmt_name, pe_threshold):
    mask = df['pmt'] == pmt_name
    df = df.loc[mask]
    interp_darkrates = interp1d(df['thresh'], df['darkrate'])
    interp_darkrate_errors = interp1d(df['thresh'],
                                      df['darkrate_err'])
    dr = interp_darkrates(pe_threshold)
    dr_error = interp_darkrate_errors(pe_threshold)
    # Check if all the deadtimes are the same
    deadtimes = df['deadtime'].values
    if len(np.unique(deadtimes)) == 1:
        deadtime = deadtimes[0]
    else:
        raise NotImplementedError('Not all deadtimes are the same '
                                  'over the course of this measurement!')
    return dr, dr_error, deadtime


if __name__ == '__main__':
    filenames = glob('/home/scanbox/dvt/data/scalar/waveforms_-50/*.hdf5')
    waveform_df = make_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/taped_-20/*.hdf5')
    waveform_df_taped_20 = make_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-20/*.hdf5')
    waveform_df_bagged_20 = make_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-40/*.hdf5')
    waveform_df_bagged_40 = make_darkrate_df(filenames)

    analogue_data = np.load('darkrates_pre_dvt.npz')
    print(waveform_df)
    analyze_darkrates(waveform_df, analogue_data)

    filenames = glob('/home/scanbox/dvt/data/scaler/untaped_-50_fine_scan/*.hdf5')
    scaler_df = make_scaler_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/scaler/taped_-20_fine_scan/*.hdf5')
    scaler_df_taped_20 = make_scaler_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/scaler/20200305_00/*.hdf5')
    scaler_df_taped_40 = make_scaler_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/scaler/bagged_-40_fine_scan/*.hdf5')
    scaler_df_bagged_40 = make_scaler_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/scaler/bagged_-20_fine_scan/*.hdf5')
    scaler_df_bagged_20 = make_scaler_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/scaler/taped_-40_fine_scan/*.hdf5')
    scaler_df_taped = make_scaler_darkrate_df(filenames)

    analogue_df = load_analogue_data_as_df('darkrates_pre_dvt.npz')

    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-20_different_baseline/*.hdf5')
    df_baseline = make_darkrate_df(filenames)

    dfs = [analogue_df, scaler_df, waveform_df,
           scaler_df_taped_20, scaler_df_taped_40,
           waveform_df_taped_20, scaler_df_bagged_40, scaler_df_bagged_20,
           waveform_df_bagged_20, waveform_df_bagged_40, df_baseline]
    labels = ['Analogue measurement @ $-40^{\circ}$C (Waveforms)',
              'D-Egg measurement @ $-50^{\circ}$C (Scaler)',
              'D-Egg measurement @ $-50^{\circ}$C (Waveforms)',
              'Taped D-Egg measurement @ $-20^{\circ}$C (Scaler)',
              'Taped D-Egg measurement @ $-40^{\circ}$C (Scaler)',
              'Taped D-Egg measurement @ $-20^{\circ}$C (Waveforms)',
              'Bagged D-Egg measurement @ $-40^{\circ}$C (Scaler)',
              'Bagged D-Egg measurement @ $-20^{\circ}$C (Scaler)',
              'Bagged D-Egg measurement @ $-20^{\circ}$C (Waveforms)',
              'Bagged D-Egg measurement @ $-40^{\circ}$C (Waveforms)',
              'Bagged D-Egg measurement @ $-20^{\circ}$C (Waveforms) BL']

    plot_scaler_darkrates(dfs, labels)

    
    logbook = DEggLogBook()
    df = scaler_df_taped_40
    pe_threshold = 0.25
    for pmt_name in np.unique(df['pmt']):
        darkrate, darkrate_error, deadtime = \
            extract_darkrate_values_from_df(df, pmt_name, pe_threshold)
        temp = -40
        result = Result(pmt_name, logbook=logbook,
                        test_type='dvt')
        result.to_json(test_name='darknoise',
                       folder_name='../database_jsons',
                       darkrate=float(darkrate),
                       darkrate_error=float(darkrate_error),
                       deadtime=float(deadtime),
                       temp=temp,
                       pe_threshold=pe_threshold)
    result.to_database()


    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-20_unresetted/*.hdf5')
    df_unresetted = make_darkrate_df(filenames)

    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-20_resetted/*.hdf5')
    df_resetted = make_darkrate_df(filenames)
    
    filenames = glob('/home/scanbox/dvt/data/dark_waveforms/bagged_-20_different_baseline/*.hdf5')
    df_baseline = make_darkrate_df(filenames)

    plot_scaler_darkrates(
        [df_unresetted, df_resetted, df_baseline], 
        ['unresetted', 'resetted', 'changed baseline'],
        suffix='test')

