import numpy as np
import tables
import pandas as pd
from glob import glob
import os
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit


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
    return rate, error


def plot_scaler_darkrates(dfs, labels):
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
        ax.set_yscale('log')
        ax.set_title(u_name.upper())
        ax.legend()
        fig.savefig(f'figs/scaler_darkrate_{u_name}.pdf',
                    bbox_inches='tight')


def make_scaler_darkrate_df(filenames):
    final_df = pd.DataFrame()
    for filename in filenames:
        parameter_dict = read_scaler_data(filename)
        rate, error = analyze_scaler_data(parameter_dict)
        event_id = int(filename.split('_')[-1][:-5])
        time = os.path.getmtime(filename)
        df = pd.DataFrame()
        pmt = parameter_dict['name']
        df['pmt'] = pd.Series(pmt)
        df['event_id'] = event_id
        df['time'] = time
        df['thresh'] = (parameter_dict['threshold_over_baseline'] *
                        VOLT_SCALING / SPE_PEAK_HEIGHT_DICT[pmt])
        df['darkrate'] = rate
        df['darkrate_err'] = error
        final_df = final_df.append(df, ignore_index=True)
    return final_df


def exp_decay(t, N, lmd, N0):
    return N * np.exp(-lmd * t) + N0


def plot_darkrate_vs_time(dfs, labels):
    fig, ax = plt.subplots()
    pmt = dfs[0]['pmt'][0].upper()
    thresh = dfs[0]['thresh'][0]
    print([df['thresh'][0] for df in dfs])
    ax.set_title(f'{pmt}: {thresh:.2f}PE threshold')

    fit_df = dfs[-1]
    x_fit = (fit_df['time'] - np.min(fit_df['time'])) / 60
    dr_fit = fit_df['darkrate'].values
    popt, pcov = curve_fit(
        exp_decay, x_fit, dr_fit,
        p0=[dr_fit[0], 0.5, dr_fit[-1]])
    print(popt)


    # Mean time between 2 datapoints is 21.72s
    for df, label in zip(dfs, labels):
        ax.errorbar((df['time'] - np.min(df['time'])) / 60,
                    df['darkrate'],
                    yerr=df['darkrate_err'],
                    fmt='o',
                    label=label)
        ax.set_xlabel('Time / min')
        ax.set_ylabel('Darkrate / Hz')

    ax.plot(x_fit, exp_decay(x_fit, *popt), color='grey', ls='--',
            zorder=30)
    ax.set_xlim(0, 100)
    ax.legend()
    fig.savefig(f'figs/darkrate_vs_time_{pmt}.pdf',
                bbox_inches='tight')


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


if __name__ == '__main__':
    '''
    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0286_after_led/*.hdf5')
    df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([df], ['After LED illumination'])
    print(df.iloc[-100:].mean())

    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0289_after_led/*.hdf5')
    df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([df], ['After LED illumination'])
    print(df.iloc[-100:].mean())
    '''

    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0286_before_led_0.25pe/*.hdf5')
    before_df = make_scaler_darkrate_df(filenames)
    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0286_after_led_0.25pe/*.hdf5')
    after_df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([before_df, after_df], ['Before LED illumination', 'After LED illumination'])

    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0289_before_led_0.25pe/*.hdf5')
    before_df = make_scaler_darkrate_df(filenames)
    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0289_after_led_0.25pe/*.hdf5')
    after_df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([before_df, after_df], ['Before LED illumination', 'After LED illumination'])

    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0290_after_led_0.25pe/*.hdf5')
    after_df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([after_df], ['After LED illumination'])

    filenames = glob('/home/scanbox/dvt/data/scaler_vs_time/sq0331_after_led_0.25pe/*.hdf5')
    after_df = make_scaler_darkrate_df(filenames)
    plot_darkrate_vs_time([after_df], ['After LED illumination'])
