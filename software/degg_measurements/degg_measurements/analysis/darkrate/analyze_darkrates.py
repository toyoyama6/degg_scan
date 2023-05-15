import shutil
import tables
import numpy as np
from degg_measurements.utils import read_data
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec

from chiba_slackbot import send_message, send_warning
from chiba_slackbot import push_slow_mon

##################################################
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.analysis import Analysis
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements.analysis.darkrate.loading import make_darkrate_df
from degg_measurements.analysis.darkrate.loading import make_scaler_darkrate_df
from degg_measurements.analysis.analysis_utils import get_measurement_numbers
##################################################
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')

TAPING_CORR_FACTOR = 2.375


RUN_TO_LABEL = {
    5: "taped & bagged",
    19: "bagged",
    26: "bare"
}


def plot_scaler_darkrates(df, suffix=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    for u_name in np.unique(df['pmt']):
        fig, ax = plt.subplots()
        mask = df['pmt'] == u_name
        temp_df = df.loc[mask]
        temperatures = [-40]
        for temperature in temperatures:
            mask = np.logical_and(
                temp_df['DEggSurfaceTemp'] > temperature - 10,
                temp_df['DEggSurfaceTemp'] < temperature + 10)
            yerr=np.vstack((
                temp_df.loc[mask, 'darkrate'].values - temp_df.loc[mask, 'darkrate_lower'].values,
                temp_df.loc[mask, 'darkrate_upper'].values - temp_df.loc[mask, 'darkrate'].values))
            ax.errorbar(temp_df.loc[mask, 'thresh'],
                        temp_df.loc[mask, 'darkrate'],
                        yerr=yerr,
                        # yerr=temp_df.loc[mask, 'darkrate_err'],
                        fmt='o',
                        label=temperature)
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_title(u_name.upper())
        ax.set_yscale('log')
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(plot_dir, f'scaler_darkrate_{u_name}.pdf')
        else:
            filename = os.path.join(plot_dir, f'scaler_darkrate_{u_name}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_scaler_darkrates(df, run_number, temperature=-40, log_y=True, suffix=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    fig, ax = plt.subplots()
    ax.set_title(f'Freezer temperature set to {temperature} degrees')
    df = df.loc[df['run_number'] == run_number]

    for u_name in np.unique(df['pmt']):
        mask = df['pmt'] == u_name
        temp_mask = np.logical_and(
            df['DEggSurfaceTemp'] > temperature - 10,
            df['DEggSurfaceTemp'] < temperature + 10)
        mask = np.logical_and(mask, temp_mask)
        yerr=np.vstack((
            df.loc[mask, 'darkrate'].values - df.loc[mask, 'darkrate_lower'].values,
            df.loc[mask, 'darkrate_upper'].values - df.loc[mask, 'darkrate'].values))
        ax.errorbar(df.loc[mask, 'thresh'],
                    df.loc[mask, 'darkrate'],
                    # yerr=df.loc[mask, 'darkrate_err'],
                    yerr=yerr,
                    fmt='o',
                    label=u_name.upper())
    ax.set_xlabel('Threshold / PE')
    ax.set_ylabel('Dark rate / Hz')
    if log_y:
        ax.set_yscale('log')
    else:
        ax.set_ylim(5e1, 3e3)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
    if suffix is None:
        filename = os.path.join(plot_dir, f'pmt_comparison_{temperature}_run_{run_number}.pdf')
    else:
        filename = os.path.join(plot_dir, f'pmt_comparison_{temperature}_run_{run_number}_{suffix}.pdf')
    fig.savefig(filename,
                bbox_inches='tight')


def compare_different_temperatures(df, run_number, suffix=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    temperatures = [-20, -40, np.nan]
    for u_name in np.unique(df['pmt']):
        mask = df['pmt'] == u_name

        fig, ax = plt.subplots()
        title = RUN_TO_LABEL.get(run_number, f'Run {run_number}')
        ax.set_title(u_name.upper() + ', '+ title)
        pmt_df = df.loc[mask]

        pmt_df = pmt_df.loc[pmt_df['run_number'] == run_number]

        for temperature in temperatures:
            if np.isfinite(temperature):
                temp_mask = np.logical_and(
                    pmt_df['DEggSurfaceTemp'] > temperature - 10,
                    pmt_df['DEggSurfaceTemp'] < temperature + 10)
            else:
                temp_mask = pmt_df['DEggSurfaceTemp'].isnull()

            yerr=np.vstack((
                pmt_df.loc[temp_mask, 'darkrate'].values - pmt_df.loc[temp_mask, 'darkrate_lower'].values,
                pmt_df.loc[temp_mask, 'darkrate_upper'].values - pmt_df.loc[temp_mask, 'darkrate'].values))
            ax.errorbar(pmt_df.loc[temp_mask, 'thresh'],
                        pmt_df.loc[temp_mask, 'darkrate'],
                        # yerr=pmt_df.loc[temp_mask, 'darkrate_err'],
                        yerr=yerr,
                        fmt='o',
                        label=f'{temperature}' + r'$^{\circ}\mathrm{C}$')
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_yscale('log')
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(plot_dir, f'temperature_comparison_{u_name}_run_{run_number}.pdf')
        else:
            filename = os.path.join(plot_dir, f'temperature_comparison_{u_name}_run_{run_number}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_different_runs(df, temperature=-40, log_y=True,
                           ratio=None, suffix=None, run_plot_dir=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    for u_name in np.unique(df['pmt']):
        mask = df['pmt'] == u_name

        if ratio is not None:
            fig = plt.figure()
            gs = GridSpec(2, 1,
                          height_ratios=[4, 1])
            ax = plt.subplot(gs[0, :])
            ax_ratio = plt.subplot(gs[1, :])
        else:
            fig, ax = plt.subplots()

        ax.set_title(u_name.upper() +
                     f', Temperature={temperature}' +
                     r'$^{\circ}\mathrm{C}$')
        pmt_df = df.loc[mask]

        temp_mask = np.logical_and(
            pmt_df['DEggSurfaceTemp'] > temperature - 10,
            pmt_df['DEggSurfaceTemp'] < temperature + 10)

        temp_df = pmt_df.loc[temp_mask]

        for run in np.unique(df['run_number']):
            mask = temp_df['run_number'] == run
            yerr=np.vstack((
                temp_df.loc[mask, 'darkrate'].values - temp_df.loc[mask, 'darkrate_lower'].values,
                temp_df.loc[mask, 'darkrate_upper'].values - temp_df.loc[mask, 'darkrate'].values))
            if ratio is not None:
                if run == ratio[0]:
                    nominator = temp_df.loc[mask, 'darkrate'].values
                    yerr_a = yerr
                if run == ratio[1]:
                    denominator = temp_df.loc[mask, 'darkrate'].values
                    yerr_b = yerr

            label = RUN_TO_LABEL.get(run, f'Run {run}')
            ax.errorbar(temp_df.loc[mask, 'thresh'],
                        temp_df.loc[mask, 'darkrate'],
                        # yerr=temp_df.loc[mask, 'darkrate_err'],
                        yerr=yerr,
                        fmt='o',
                        label=label)


        xlabel = 'Threshold / PE'

        if ratio is not None:
            l_nom = RUN_TO_LABEL.get(ratio[0], f'Run {ratio[0]}')
            l_denom = RUN_TO_LABEL.get(ratio[1], f'Run {ratio[1]}')
            label = f'{l_nom} / {l_denom}'
            ratio_v = nominator / denominator
            ratio_err = ratio_v * np.sqrt(yerr_a**2 / nominator**2 + yerr_b**2 / denominator**2)
            neg_mask = (ratio_v - ratio_err[0, :]) < 0
            ratio_err[0, neg_mask] = ratio_v[neg_mask]
            ax_ratio.errorbar(
                temp_df.loc[mask, 'thresh'].values,
                ratio_v,
                yerr=ratio_err,
                fmt='o',
                label=label)
            ax_ratio.legend()
            ax_ratio.set_xlabel(xlabel)
            ax_ratio.set_ylim(0, 4.)
        else:
            ax.set_xlabel(xlabel)
        ax.set_ylabel('Dark rate / Hz')
        if log_y:
            ax.set_yscale('log')
        else:
            ax.set_ylim(5e1, 3e3)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(plot_dir, f'run_comparison_{u_name}_temp_{temperature}.pdf')
        else:
            filename = os.path.join(plot_dir, f'run_comparison_{u_name}_temp_{temperature}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_different_keys(df, pdf=None, suffix=None, verbose=True, run_plot_dir=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    for u_name in np.unique(df['pmt']):
        mask = df['pmt'] == u_name

        fig, ax = plt.subplots()
        u_runs = np.unique(df['run_number'])
        if len(u_runs) > 1:
            raise ValueError('This comparison is intended to be done within one run!')
        run_number = u_runs[0]
        title = RUN_TO_LABEL.get(run_number, f'Run {run_number}')
        ax.set_title(u_name.upper() + ', ' + title)
        pmt_df = df.loc[mask]

        print(f'PMT: {u_name}')
        for i, key in enumerate(np.unique(df['key'])):
            mask = pmt_df['key'] == key
            key_df = pmt_df.loc[mask]
            degg_name = key_df.DEggName.values[0]
            if (np.sum(np.isfinite(key_df['darkrate_lower'])) == key_df.shape[0] and
                    np.sum(np.isfinite(key_df['darkrate_upper'])) == key_df.shape[0]):
                yerr = np.vstack((
                    np.median(key_df['darkrate_list'].values[0]) - key_df['darkrate_lower'].values,
                    key_df['darkrate_upper'].values - np.median(key_df['darkrate_list'].values[0])))
            elif np.sum(np.isfinite(key_df['darkrate_err'])) == key_df.shape[0]:
                yerr = abs(key_df['darkrate_err'])
            else:
                raise ValueError(
                    f'Found unexpected amount of nans, check dataframe! '
                    f'{key_df}')

            if verbose == True:
                print(f'{key}: Temp: {key_df["temp"]}')


            ax.errorbar(key_df['thresh'],
                        key_df['darkrate'],
                        yerr=yerr,
                        fmt='o',
                        label=f'Key {key}',
                        markersize=5,
                        alpha=0.6,
                        color=f'C{i}')

            fig0, ax0 = plt.subplots()
            ax0.hist(key_df['darkrate_list'].values[0], 100, histtype='step')
            ax0.set_xlabel('Dark Rate [Hz]')
            ax0.set_ylabel('Entries')
            ax0.set_title(f'{degg_name}:{key_df.pmt.values[0]}')
            fig0.savefig(os.path.join(run_plot_dir,
                                      f'dark_rate_{degg_name}_{key_df.pmt.values[0]}.pdf'))
            plt.close(fig0)
            push_slow_mon(os.path.join(run_plot_dir,
                                       f'dark_rate_{degg_name}_{key_df.pmt.values[0]}.pdf'),
                          f'{degg_name}_{key_df.pmt.values[0]} dark rate')

            mask = key_df['darkrate_list'].values[0] <= 8000
            binning = np.linspace(800, 8000, 120)
            fig1, ax1 = plt.subplots()
            ax1.hist(key_df['darkrate_list'].values[0][mask], binning, histtype='step')
            ax1.set_xlabel('Dark Rate [Hz]')
            ax1.set_ylabel('Entries')
            ax1.set_title(f'{degg_name}:{key_df.pmt.values[0]}')
            fig1.savefig(os.path.join(run_plot_dir,
                                      f'dark_rate_zoom_{degg_name}_{key_df.pmt.values[0]}.pdf'))
            plt.close(fig1)

            for x, y, temp in zip(key_df['thresh'], key_df['darkrate'], key_df['temp']):
                ax.annotate(f'{float(temp):.1f}', (x,y), fontsize=8)
            '''
            if np.sum(np.isfinite(key_df['darkrate_tw'])) > 0:
                ax.errorbar(
                    key_df['thresh'],
                    key_df['darkrate_tw'],
                    yerr=key_df['darkrate_tw_err'],
                    fmt='o',
                    label=f'TW Key {key}',
                    markersize=5,
                    alpha=0.6)
             '''
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_yscale('log')
        ax.set_title(f'{degg_name}:{pmt_df.pmt.values[0]} - {key}')
        if suffix is None:
            filename = os.path.join(plot_dir, f'key_comparison_{u_name}.pdf')
        else:
            filename = os.path.join(plot_dir, f'key_comparison_{u_name}_{suffix}.pdf')
        if pdf != None:
            ax.legend()
            pdf.savefig(fig)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        fig.savefig(filename,
                    bbox_inches='tight')

def plot_histogram(df, key, pdf=None, correct_for_not_taping=False, run_plot_dir=None):
    if run_plot_dir == None:
        raise ValueError(f'run_plot_dir must not be None!')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mask = df['key'] == key
    values = df.loc[mask, 'darkrate']
    temp = np.array(df.loc[mask, 'temp'], dtype=float)

    u_runs = np.unique(df['run_number'])
    if len(u_runs) > 1:
        raise ValueError('This comparison is intended to be done within one run!')
    run_number = u_runs[0]

    label = fr'Average MB temperature: {np.mean(temp):.1f}$\,^{{\circ}}\mathrm{{C}}$'

    fig, ax = plt.subplots()
    # ax.set_title(f'Run {run_number}')
    # ax.set_title(label, fontsize=16)
    bins = np.linspace(np.min(values) * 0.95,
                       np.max(values) * 1.05,
                       11)
    #ax.hist(values,
    #        bins=bins,
    #        histtype='step',
    #        lw=2,
    #        label=label)
    if correct_for_not_taping:
        values_corr = values / TAPING_CORR_FACTOR
        bins = np.linspace(np.min(values_corr) * 0.95,
                           np.max(values_corr) * 1.05,
                           11)
        ax.hist(values_corr,
                bins=bins,
                histtype='step',
                lw=2,
                label=label)
        print(f'Mean DR: {np.mean(values_corr)}, median DR: {np.median(values_corr)}')
    ax.set_xlabel('Dark Rate per (D-Egg) Hemisphere / Hz', fontsize=16)
    ax.set_ylabel('PMTs / bin', fontsize=16)
    # ax.legend(loc='best')
    # ax.set_title(f'{key}')

    print(f'Darkrates: {values}')

    filename = os.path.join(run_plot_dir, f'darkrate_histogram_{key}.pdf')
    if pdf != None:
        pdf.savefig(fig)
    fig.savefig(filename,
                bbox_inches='tight')

    print('Plotting Upper/Lower historgram')
    fig, ax = plt.subplots()
    bins = np.linspace(np.min(values) * 0.95,
                       np.max(values) * 1.05,
                       11)
    if correct_for_not_taping:
        values_corr = values / TAPING_CORR_FACTOR
        up_mask = df['pmt_loc'] == 'UpperPmt'
        masks = [up_mask, ~up_mask]
        labels = ['Upper PMTs', 'Lower PMTs']
        bins = np.linspace(np.min(values_corr) * 0.95,
                           np.max(values_corr) * 1.05,
                           11)
        for mask, label in zip(masks, labels):
            ax.hist(values_corr[mask].values,
                    bins=bins,
                    histtype='step',
                    lw=2,
                    label=label)
        ax.legend(loc='best')
        print(f'Mean DR: {np.mean(values_corr[mask])}, median DR: {np.median(values_corr[mask])}')
    ax.set_xlabel('Dark Rate per (D-Egg) Hemisphere / Hz', fontsize=16)
    ax.set_ylabel('Entries / bin', fontsize=16)
    # ax.set_title(f'{key}')
    # ax.legend(loc='best')

    filename = os.path.join(run_plot_dir, f'darkrate_histogram_upper_lower_{key}.pdf')
    if pdf != None:
        pdf.savefig(fig)
    fig.savefig(filename,
                bbox_inches='tight')


    label = f'Average PMT dark rate: {np.mean(values):.1f} Hz'

    fig, ax = plt.subplots()
    ax.set_title(f'Run {run_number}')
    bins = np.linspace(np.min(temp) * 0.95,
                       np.max(temp) * 1.05,
                       11)
    ax.hist(temp,
            bins=bins,
            histtype='step',
            lw=2,
            label=label)
    ax.set_xlabel(r'Mainboard temperature / $^{\circ}\mathrm{C}$')
    ax.set_ylabel('Entries / bin')
    ax.legend(loc='best')

    filename = os.path.join(run_plot_dir, f'temp_histogram_{key}.pdf')
    fig.savefig(filename,
                bbox_inches='tight')


def plot_baseline_comparison(df, temp=-40):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plot_dir = os.path.join(script_dir, "fig_json")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    tested_baselines = np.unique(df['dac_value'])

    for u_name in np.unique(df['pmt']):
        fig, ax = plt.subplots()
        ax.set_title(u_name.upper())
        # Find all values for a specific PMT
        mask = df['pmt'] == u_name
        # Find all measurements in the allowed temperature range
        temp_mask = np.logical_and(
            df['DEggSurfaceTemp'] > temp - 10,
            df['DEggSurfaceTemp'] < temp + 10)
        # Combine them
        mask = np.logical_and(mask, temp_mask)

        for tested_baseline in tested_baselines:
            bl_mask = df['dac_value'] == tested_baseline
            bl_mask = np.logical_and(bl_mask, mask)
            ax.errorbar(df.loc[bl_mask, 'thresh'],
                        df.loc[bl_mask, 'darkrate'],
                        yerr=df.loc[bl_mask, 'darkrate_err'],
                        fmt='o',
                        label=f'DAC value: {tested_baseline}')
        ax.set_xlabel('Threshold / PE')
        ax.set_ylabel('Dark rate / Hz')
        ax.set_yscale('log')
        ax.legend()
        filename = os.path.join(plot_dir, f'baseline_comparison_{u_name}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys

def run_analysis(key, degg_dict, pmt, run_number, pdf, mode, df, remote):

    if remote:
        folder = degg_dict[pmt][key]['RemoteFolder']
    else:
        folder = degg_dict[pmt][key]['Folder']
    degg_name = degg_dict['DEggSerialNumber']
    pmt_id = degg_dict[pmt]['SerialNumber']
    temp = degg_dict[pmt][key]['DEggSurfaceTemp']
    dac_value = degg_dict[pmt][key]['Constants']['DacValue']
    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))

    if mode.lower() == 'waveform':
        darkrate_df = make_darkrate_df(files,
                     adc_threshold=18,
                     pe_threshold=None,
                     deadtime=24,
                     DEggSurfaceTemp=temp,
                     key=key,
                     run_number=run_number,
                     dac_value=dac_value)

    if mode.lower() == 'scaler':
        darkrate_df = make_scaler_darkrate_df(files,
                         use_quantiles=True,
                         DEggSurfaceTemp=temp,
                         key=key,
                         run_number=run_number,
                         dac_value=dac_value)

    df = df.append(darkrate_df, ignore_index=True)
    df['DEggName'] = [degg_name] * len(df.index.values)

    darkrate = darkrate_df['darkrate'].values[0]

    if darkrate > 2600:
        warn_msg = f'Dark Rate of {darkrate} for {pmt_id} in dedicated measurement above 2600 Hz! \n'
        warn_msg = warn_msg + 'The shifter should log this instance. \n'
        warn_msg = warn_msg + 'Check previous dark rates (monitoring) for a possible pattern. \n'
        warn_msg = warn_msg + 'If the rate is > 4000 Hz, inform the expert shifter.'
        send_warning(warn_msg)

    if darkrate / TAPING_CORR_FACTOR > 1000:
        return df, 0
    if darkrate / TAPING_CORR_FACTOR <= 1000:
        return df, 1

##this is meant to be run with supreme_verdict via config file
##to compare different iterations of the measurement in the SAME run
def single_run_script_ana(run_json, pdf, measurement_number, mode, save_df, remote):
    print('Same Run Analysis Mode')
    run_json = run_json[0]

    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f'Created directory: {PLOT_DIR}')

    # if measurement_number != 'latest':
    #     nums = measurement_number.split(',')
    #     if len(nums) == 1:
    #         measurement_number = [int(measurement_number)]
    #     else:
    #         measurement_number = nums

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)

    if mode.lower() == 'waveform':
        data_key = 'DarkrateWaveformMeasurement'
    if mode.lower() == 'scaler':
        data_key = 'DarkrateScalerMeasurement'
    info_list = []
    analysis_list = []
    df = pd.DataFrame()
    keys_list = []

    print(measurement_number)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)


        pmts = ['LowerPmt', 'UpperPmt']
        u_verdict = 0
        l_verdict = 0
        for pmt in pmts:
            measurement_numbers = get_measurement_numbers(
                degg_dict, pmt, measurement_number,
                data_key)
            # if measurement_number == 'latest':
            #     eligible_keys = [key for key in degg_dict[pmt].keys()
            #                      if key.startswith(data_key)]
            #     cts = [int(key.split('_')[1]) for key in eligible_keys]
            #     if len(cts) == 0:
            #         print(f'No measurement found for '
            #               f'{degg_dict[pmt]["SerialNumber"]} '
            #               f'in DEgg {degg_dict["DEggSerialNumber"]}. '
            #               f'Skipping it!')
            #         continue
            #     measurement_number = np.max(cts)
            # if type(measurement_number) == np.int64:
            #     measurement_number = [measurement_number]
            #loop over all configured measurements
            for num in measurement_numbers:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                if data_key_to_use not in keys_list:
                    keys_list.append(data_key_to_use)
                run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key_to_use}')
                if not os.path.isdir(run_plot_dir):
                    os.mkdir(run_plot_dir)
                if audit_ignore_list(degg_file, degg_dict, data_key_to_use) == True:
                    continue
                df, verdict = run_analysis(data_key_to_use, degg_dict,
                         pmt, run_number, pdf, mode, df, remote)
                ##if PMT passed, increment by  1
                if pmt == 'LowerPmt':
                    l_verdict += verdict
                if pmt == 'UpperPmt':
                    u_verdict += verdict


        #after looping PMTs and all measurements, create summary
        analysis = Analysis(f"DarkRate {mode} (N={len(measurement_numbers)})",
                            degg_dict['DEggSerialNumber'], u_verdict, l_verdict,
                            len(measurement_numbers))
        analysis_list.append(analysis)

    #trim the string
    measurement_numbers = measurement_numbers[1:-1]
    if save_df:
        df.to_hdf(
            f'darkrate_df_run{run_number}_meas_num_{measurement_numbers}.hdf5',
            key='darkrate_df')

    ##after looping all D-Eggs and measurements
    for hist_key in keys_list:
        print(f'Making plots for {hist_key}')
        plot_histogram(df, hist_key, pdf, correct_for_not_taping=True, run_plot_dir=run_plot_dir)

    if len(df) == 0:
        raise IOError(f'No entries in df! Bad key?')
    compare_different_keys(df, pdf, verbose=False, run_plot_dir=run_plot_dir)
    create_database_jsons(df)
    return analysis_list


##this creates plots across several runs to compare dark rates
def multi_run_ana(run_json, compare_baselines, hist_key, remote):
    waveform_df = pd.DataFrame()
    scaler_df = pd.DataFrame()
    for run_json_i in run_json:
        run_base = os.path.basename(run_json_i)
        run_number = int(run_base.split('.')[0].split('_')[-1])
        print(run_number)
        list_of_deggs = load_run_json(run_json_i)
        for degg_file in list_of_deggs:
            degg_dict = load_degg_dict(degg_file)
            pmts = ['LowerPmt', 'UpperPmt']

            for pmt in pmts:
                pmt_id = degg_dict[pmt]['SerialNumber']
                keys = find_keys(degg_dict[pmt], 'DarkrateWaveformMeasurement')
                for key in keys:
                    if remote:
                        folder = degg_dict[pmt][key]['RemoteFolder']
                    else:
                        folder = degg_dict[pmt][key]['Folder']
                    temp = degg_dict[pmt][key]['DEggSurfaceTemp']
                    dac_value = degg_dict[pmt][key]['Constants']['DacValue']
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    darkrate_df = make_darkrate_df(files,
                                                   adc_threshold=18,
                                                   pe_threshold=None,
                                                   deadtime=24,
                                                   DEggSurfaceTemp=temp,
                                                   key=key,
                                                   run_number=run_number,
                                                   dac_value=dac_value)
                    waveform_df = waveform_df.append(darkrate_df, ignore_index=True)
                keys = find_keys(degg_dict[pmt], 'DarkrateScalerMeasurement_')
                for key in keys:
                    if remote:
                        folder = degg_dict[pmt][key]['RemoteFolder']
                    else:
                        folder = degg_dict[pmt][key]['Folder']
                    try:
                        temp = degg_dict[pmt][key]['DEggSurfaceTemp']
                    except KeyError:
                        temp = np.nan
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    scaler_df_i = make_scaler_darkrate_df(files,
                                                          use_quantiles=True,
                                                          DEggSurfaceTemp=temp,
                                                          key=key,
                                                          run_number=run_number,
                                                          dac_value=dac_value)
                    scaler_df = scaler_df.append(scaler_df_i, ignore_index=True)
        compare_scaler_darkrates(scaler_df, run_number, temperature=-40)
        compare_scaler_darkrates(scaler_df, run_number, temperature=-40,
                                 log_y=False, suffix='lin')
        compare_different_temperatures(scaler_df, run_number)
    total_df = scaler_df.append(waveform_df, ignore_index=True)
    print(total_df.shape, total_df.columns)

    if hist_key is not None:
        print(f'Making plots for {hist_key}')
        plot_histogram(total_df, hist_key, correct_for_not_taping=True)

    if len(run_json) == 1:
        if len(np.unique(total_df['key'])) > 1:
            compare_different_keys(total_df)
    if len(run_json) > 1:
        compare_different_runs(scaler_df, temperature=-40)
        compare_different_runs(scaler_df, temperature=-40,
                               log_y=False, suffix='lin')
        compare_different_runs(scaler_df, temperature=-40,
                               log_y=True, ratio=[26, 5], suffix='ratio')
        compare_different_runs(scaler_df, temperature=-20)
        compare_different_runs(scaler_df, temperature=-20,
                               log_y=False, suffix='lin')
        compare_different_runs(scaler_df, temperature=-20,
                               log_y=True, ratio=[26, 5], suffix='ratio')
    if compare_baselines:
        plot_baseline_comparison(scaler_df)

    create_database_jsons(total_df)
    return total_df, scaler_df


def create_database_jsons(df):
    # Make json files for database insertion
    # TODO: Add information about pmt location (?)
    run_number = np.unique(df['run_number'])[0]
    logbook = DEggLogBook()
    # Check each PMT
    for pmt_id in np.unique(df['pmt']):
        mask = df['pmt'] == pmt_id
        result = Result(pmt_id,
                        logbook=logbook,
                        run_number=run_number,
                        remote_path=REMOTE_DATA_DIR)
        # For each PMT find each darkrate measurement
        for key in np.unique(df.loc[mask, 'key']):
            key_mask = df.loc[mask, 'key'] == key
            key_df = df.loc[mask].loc[key_mask]
            # Find the threshold clostest to 0.25
            # This should be changed as soon as the DAQ script is "fixed"
            entry = key_df.iloc[np.argmin(np.abs(key_df['thresh'] - 0.25))]

            if 'waveform' in key.lower():
                daq_type = 'waveform'
            elif 'scaler' in key.lower():
                daq_type = 'scaler'
            else:
                raise ValueError(
                    f'Key has to either contain waveform or scaler '
                    f'but is {key} instead.')

            json_filenames = result.to_json(
                meas_group='darknoise',
                raw_files=entry['filename'],
                folder_name=DB_JSON_PATH,
                filename_add=key.replace('Folder', ''),
                darkrate=entry['darkrate'],
                darkrate_error=entry['darkrate_err'],
                deadtime=entry['deadtime'],
                temp=float(entry['temp']),
                pe_threshold=entry['thresh'],
                daq_type=daq_type)

            run_handler = RunHandler(filenames=json_filenames)
            run_handler.submit_based_on_meas_class()


def analysis_wrapper(run_json,
                     pdf=None,
                     measurement_number='latest',
                     mode='scaler',
                     compare_runs=False,
                     compare_baselines=True,
                     hist_key=None,
                     save_df=False,
                     remote=False,
                     offline=False):
    print('Analysis Wrapper')
    if remote == True:
        # triggering from remote only allowas for a single run_json to be transmitted
        run_json = [run_json]
    if compare_runs == False:
        analysis_info = single_run_script_ana(
            run_json, pdf, measurement_number, mode, save_df, remote)
        return analysis_info
    elif compare_runs == True:
        print("Traditional Analysis! (Comparing runs!)")
        multi_run_ana(run_json, compare_baselines, hist_key, remote)
    else:
        print('No measurement run...')

@click.command()
@click.argument('run_json', nargs=-1, type=click.Path(exists=True))
@click.option('--pdf', default=None)
@click.option('--measurement_number', '-n', default='latest')
@click.option('--mode', '-m', default='scaler')
@click.option('--compare_runs', is_flag=True)
@click.option('--compare_baselines', is_flag=True)
@click.option('--hist-key', default=None)
@click.option('--save_df', is_flag=True)
@click.option('--remote', is_flag=True)
@click.option('--offline', is_flag=True)
def main(run_json,
         pdf,
         measurement_number,
         mode,
         compare_runs,
         compare_baselines,
         hist_key,
         save_df,
         remote,
         offline):
    print(f'run_json: {run_json}')
    print(f'compare_baselines: {compare_baselines}')
    print(f'compare_runs: {compare_runs}')
    analysis_wrapper(
        run_json[0],
        pdf,
        measurement_number,
        mode,
        compare_runs,
        compare_baselines,
        hist_key,
        save_df,
        remote,
        offline
    )
    send_message(f'--- Dark rate analysis is finished --- ')
    print("Done")

if __name__ == '__main__':
    main()

