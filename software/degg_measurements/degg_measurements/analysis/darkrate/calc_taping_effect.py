import tables
import numpy as np
from degg_measurements.utils import read_data
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
from IPython import embed

from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json

from loading import make_darkrate_df
from loading import make_scaler_darkrate_df


RUN_TO_LABEL = {
    5: "taped & bagged",
    19: "bagged",
    26: "bare"
}

PLOT_DIR_TAPE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_tape')
PLOT_DIR_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_json')

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
            filename = os.path.join(PLOT_DIR_JSON, f'scaler_darkrate_{u_name}.pdf')
        else:
            filename = os.path.join(PLOT_DIR_JSON, f'scaler_darkrate_{u_name}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_scaler_darkrates(df, run_number, temperature=-40, log_y=True, suffix=None):
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
        filename = os.path.join(PLOT_DIR_JSON, f'pmt_comparison_{temperature}_run_{run_number}.pdf')
    else:
        filename = os.path.join(PLOT_DIR_JSON, f'pmt_comparison_{temperature}_run_{run_number}_{suffix}.pdf')
    fig.savefig(filename,
                bbox_inches='tight')


def compare_different_temperatures(df, run_number, suffix=None):
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
            filename = os.path.join(PLOT_DIR_JSON, f'temperature_comparison_{u_name}_run_{run_number}.pdf')
        else:
            filename = os.path.join(PLOT_DIR_JSON, f'temperature_comparison_{u_name}_run_{run_number}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def compare_different_runs(df, temperature=-40, log_y=True,
                           ratio=None, suffix=None):
    corr_factors = []
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
            print(u_name, ratio_v[3], np.mean(ratio_v[3:11]), np.mean(ratio_v[3:]))
            corr_factors.append(ratio_v[3])
        else:
            ax.set_xlabel(xlabel)
        ax.set_ylabel('Dark rate / Hz')
        if log_y:
            ax.set_yscale('log')
        else:
            ax.set_ylim(5e1, 3e3)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(PLOT_DIR_TAPE, f'figs_tape/run_comparison_{u_name}_temp_{temperature}.pdf')
        else:
            filename = os.path.join(PLOT_DIR_TAPE, f'figs_tape/run_comparison_{u_name}_temp_{temperature}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')
    print(np.mean(corr_factors))


def compare_different_keys(df, suffix=None):
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

        for i, key in enumerate(np.unique(df['key'])):
            mask = pmt_df['key'] == key
            key_df = pmt_df.loc[mask]
            if (np.sum(np.isfinite(key_df['darkrate_lower'])) == key_df.shape[0] and
                    np.sum(np.isfinite(key_df['darkrate_upper'])) == key_df.shape[0]):
                yerr = np.vstack((
                    key_df['darkrate'].values -
                    key_df['darkrate_lower'].values,
                    key_df['darkrate_upper'].values -
                    key_df['darkrate'].values))
            elif np.sum(np.isfinite(key_df['darkrate_err'])) == key_df.shape[0]:
                yerr = key_df['darkrate_err']
            else:
                raise ValueError(
                    f'Found unexpected amount of nans, check dataframe! '
                    f'{key_df}')

            print(f'{key}: Temp: {key_df["temp"]}')

            ax.errorbar(key_df['thresh'],
                        key_df['darkrate'],
                        yerr=yerr,
                        fmt='o',
                        label=f'Key {key}',
                        markersize=5,
                        alpha=0.6,
                        color=f'C{i}')
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
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.98))
        if suffix is None:
            filename = os.path.join(PLOT_DIR_JSON, f'key_comparison_{u_name}.pdf')
        else:
            filename = os.path.join(PLOT_DIR_JSON, f'figs_json/key_comparison_{u_name}_{suffix}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')

def plot_histogram(df, key):
    mask = df['key'] == key
    values = df.loc[mask, 'darkrate']
    temp = np.array(df.loc[mask, 'temp'], dtype=float)

    u_runs = np.unique(df['run_number'])
    if len(u_runs) > 1:
        raise ValueError('This comparison is intended to be done within one run!')
    run_number = u_runs[0]

    label = fr'Average MB temperature: {np.mean(temp):.2f}$\,^{{\circ}}\mathrm{{C}}$'

    fig, ax = plt.subplots()
    ax.set_title(f'Run {run_number}')
    bins = np.linspace(np.min(values) * 0.95,
                       np.max(values) * 1.05,
                       11)
    ax.hist(values,
            bins=bins,
            histtype='step',
            lw=2,
            label=label)
    ax.set_xlabel('PMT dark rate / Hz')
    ax.set_ylabel('PMTs / bin')
    ax.legend(loc='best')

    filename = os.path.join(PLOT_DIR_JSON, f'key_darkrate_histogram_{key}.pdf')
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
    ax.set_ylabel('PMTs / bin')
    ax.legend(loc='best')

    filename = os.path.join(PLOT_DIR_JSON, f'key_temp_histogram_{key}.pdf')
    fig.savefig(filename,
                bbox_inches='tight')


def plot_baseline_comparison(df, temp=-40):
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
        filename = os.path.join(PLOT_DIR_JSON, f'baseline_comparison_{u_name}.pdf')
        fig.savefig(filename,
                    bbox_inches='tight')


def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys


@click.command()
@click.argument('run_json', nargs=-1, type=click.Path(exists=True))
@click.option('--compare_baselines', is_flag=True)
@click.option('--hist-key', default=None)
def main(run_json, compare_baselines, hist_key):

    if not os.path.exists(PLOT_DIR_TAPE):
        os.mkdir(PLOT_DIR_TAPE)
        print(f'Created directory: {PLOT_DIR_TAPE}')
    if not os.path.exists(PLOT_DIR_JSON):
        os.mkdir(PLOT_DIR_JSON)
        print(f'Created directory: {PLOT_DIR_JSON}')


    print(run_json)
    print(compare_baselines)
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
                dac_value = degg_dict['Constants']['DacValue']
                keys = find_keys(degg_dict[pmt], 'DarkrateWaveformMeasurement')
                for key in keys:
                    folder = folder = degg_dict[pmt][key]['Folder']
                    temp = degg_dict[pmt][key]['DEggSurfaceTemp']
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    darkrate_df = make_darkrate_df(files,
                                                   threshold=18,
                                                   deadtime=24,
                                                   DEggSurfaceTemp=temp,
                                                   key=key,
                                                   run_number=run_number,
                                                   dac_value=dac_value)
                    waveform_df = waveform_df.append(darkrate_df, ignore_index=True)
                keys = find_keys(degg_dict[pmt], 'DarkrateScalerMeasurement_')
                for key in keys:
                    folder = degg_dict[pmt][key]['Folder']
                    temp = degg_dict[pmt][key]['DEggSurfaceTemp']
                    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
                    scaler_df_i = make_scaler_darkrate_df(files,
                                                          use_quantiles=True,
                                                          DEggSurfaceTemp=temp,
                                                          key=key,
                                                          run_number=run_number,
                                                          dac_value=dac_value)
                    scaler_df = scaler_df.append(scaler_df_i, ignore_index=True)
        #compare_scaler_darkrates(scaler_df, run_number, temperature=-40)
        #compare_scaler_darkrates(scaler_df, run_number, temperature=-40,
        #                         log_y=False, suffix='lin')
        #compare_different_temperatures(scaler_df, run_number)
    print(waveform_df.shape, waveform_df.columns)
    print(scaler_df.shape, scaler_df.columns)
    total_df = scaler_df.append(waveform_df, ignore_index=True)
    print(total_df.shape, total_df.columns)

    if hist_key is not None:
        plot_histogram(total_df, hist_key)

    if len(run_json) == 1:
        if len(np.unique(total_df['key'])) > 1:
            compare_different_keys(total_df)
    if len(run_json) > 1:
        compare_different_runs(scaler_df, temperature=-40)
        compare_different_runs(scaler_df, temperature=-40,
                               log_y=False, suffix='lin')
        compare_different_runs(scaler_df, temperature=-40,
                               log_y=True, ratio=[19, 5], suffix='ratio')
        compare_different_runs(scaler_df, temperature=-20)
        compare_different_runs(scaler_df, temperature=-20,
                               log_y=False, suffix='lin')
        compare_different_runs(scaler_df, temperature=-20,
                               log_y=True, ratio=[19, 5], suffix='ratio')
    if compare_baselines:
        plot_baseline_comparison(scaler_df)
    return total_df, scaler_df


if __name__ == '__main__':
    main()

