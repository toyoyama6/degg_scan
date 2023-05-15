import os, sys
import pandas as pd
import click
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

##################################
from degg_measurements.utils import DEggLogBook
from degg_measurements.utils import load_run_json
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.analysis import Result

def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def fit_func(x, spe_norm, spe_peak, spe_width):
    return gauss(x, spe_norm, spe_peak, spe_width)

def npe_ana(npes, nbins=100):
    bins = np.linspace(np.min(npes), np.max(npes), nbins)
    hist, edges = np.histogram(npes, bins=bins)
    center = (edges[1:] + edges[:-1]) * 0.5
    init_norm = np.max(npes)
    init_peak = np.median(npes)
    init_width =  0.6 * init_peak
    p0 = [init_norm, init_peak, init_width]
    popt, pcov = curve_fit(fit_func, center, hist, p0=p0, maxfev=1000)

    return popt, pcov, center

def print_info(degg, channel, port, hv, eff, npes):
    print(f'{degg}:{channel} - {port}, HV={hv}')
    print(f'Efficiency of laser freq cut: {eff}')
    print(f'Ave NPE: {np.mean(npes)}')

##not sure plotC is really doing anything....
def database_info(data_key, pmt_id, logbook, run_number, df_file, hv, hv1e7gain, temperature,
                  c_npes, npe_width, npeData, npeBins, plotC, fitVals,
                  funcStr, norm, peak, width):
        result = Result(pmt_id,
                 logbook=logbook,
                 run_number=run_number,
                 remote_path=REMOTE_DATA_DIR)

        result.to_json(meas_group='charge',
                    raw_files=[df_file],
                    folder_name=DB_JSON_PATH,
                    filename_add=data_key.replace('Folder', ''),
                    high_voltage=hv,
                    high_v_at_1e7_gain=hv1e7gain,
                    temperature=temperature,
                    c_npes=c_npes,
                    npe_width=npe_width,
                    npeData=npeData,
                    npeBins=npeBins,
                    plotC=plotC,
                    fitVals=fitVals,
                    funcStr=funcStr,
                    norm=norm,
                    peak=peak,
                    width=width
                   )

def degg_analysis(data_key, df, plot_dir, logbook, run_number, df_file, verbose):
    nbins = 50

    centers  = []
    widths   = []
    channels = []

    deggs = df.DEgg.unique()
    for degg in deggs:
        _df = df[df.DEgg == degg]
        if verbose:
            print('-'*20)
        for channel in _df.Channel.unique():
            df_pmt = _df[_df.Channel == channel]
            eff = df_pmt.Efficiency[0]
            pmt_id = df_pmt.PMT[0]
            port = df_pmt.Port[0]
            npes = df_pmt.NPEs
            hv = df_pmt.HV[0]
            hv1e7gain = df_pmt.HV1e7Gain[0]
            temperature = df_pmt.Temperature[0]
            if verbose:
                print_info(degg, channel, port, hv, eff, npes)

            popt, pcov, center = npe_ana(npes, nbins)

            centers.append(popt[1])
            widths.append(popt[2])
            channels.append(channel)


            if logbook is not None:
                database_info(data_key, pmt_id, logbook, run_number, df_file, hv, hv1e7gain, temperature,
                              popt[1], popt[2], npes, np.linspace(np.min(npes), np.max(npes), nbins),
                              fit_func(center, *popt), fit_func(center, *popt), 'norm * np.exp(-(x-peak)**2/(2 * width**2))',
                              popt[0], popt[1], popt[2])


            fig, ax = plt.subplots()
            ax.hist(npes, nbins, histtype='step', color='royalblue', label=f'N={len(npes)}')
            ax.plot(center, fit_func(center, *popt), color='goldenrod', label=f'{popt[1]:.1f}+/-{popt[2]:.1f}')
            ax.set_ylabel('Entries')
            ax.set_xlabel('Observed NPE')
            ax.set_title(f'{degg} - {channel}')
            ax.legend()
            fig.savefig(f'{plot_dir}/{degg}_{channel}_npe.pdf')
            plt.close(fig)

    fig1, ax1 = plt.subplots()
    ax1.errorbar(np.arange(len(deggs)*2), centers, yerr=widths, marker='o', linewidth=0, elinewidth=3, color='royalblue')
    ax1.set_ylabel('Observed NPE')
    ax1.set_xlabel('PMT')
    fig1.savefig(f'{plot_dir}/all_npe.pdf')
    plt.close(fig1)

    channels = np.array(channels)
    centers = np.array(centers)
    widths = np.array(widths)
    mask = channels == 0

    fig2, ax2 = plt.subplots()
    ax2.errorbar(np.arange(np.sum(mask)), centers[mask], yerr=widths[mask], marker='o', linewidth=0, elinewidth=3, color='royalblue', label='Channel 0')
    ax2.errorbar(np.arange(np.sum(mask)), centers[~mask], yerr=widths[~mask], marker='o', linewidth=0, elinewidth=3, color='goldenrod', label='Channel 1')
    ax2.set_ylabel('Observed NPE')
    ax2.set_xlabel('PMT')
    ax2.legend()
    fig2.savefig(f'{plot_dir}/all_npe_channels.pdf')
    plt.close(fig2)


@click.command()
@click.argument('run_json')
@click.option('--measurement_number', '-n', default='latest')
@click.option('--offline', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
def main(run_json, measurement_number, offline, verbose):
    list_of_deggs = load_run_json(run_json)
    measurement_type = "LaserVisibilityMeasurement"
    if offline == False:
        logbook = DEggLogBook()
    if offline == True:
        logbook = None

    ##just checking the pandas file for now, which is already all ports combined
    degg_dict = load_degg_dict(list_of_deggs[0])
    pmt_id = degg_dict['LowerPmt']['SerialNumber']
    if measurement_number == 'latest':
        eligible_keys = [key for key in degg_dict['LowerPmt'].keys() if key.startswith(measurement_type)]
        cts = [int(key.split('_')[1]) for key in eligible_keys]
        measurement_number = np.max(cts)

    num = int(measurement_number)
    suffix = f'_{num:02d}'
    data_key_to_use = measurement_type + suffix
    print(data_key_to_use)
    this_dict = degg_dict['LowerPmt'][data_key_to_use]
    if this_dict['Folder'] == "None":
        print("Measurement did not complete! Exiting")
        exit(1)
    else:
        df_file = this_dict['Output']

    run_number = extract_runnumber_from_path(run_json)
    run_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'plots/{run_number}')
    if not os.path.exists(run_dir):
        os.mkdir(run_dir)
    plot_dir = os.path.join(run_dir, f'{data_key_to_use}')
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)

    df = pd.read_hdf(df_file)
    degg_analysis(data_key_to_use, df, plot_dir, logbook, run_number, df_file, verbose)


if __name__ == "__main__":
    main()

##end
