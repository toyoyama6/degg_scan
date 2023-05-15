import shutil
import os
import click
import tables
import numpy as np
import pandas as pd
from glob import glob
from tqdm import tqdm
from datetime import datetime
from warnings import warn

from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import LogNorm

##################################################
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.analysis import Analysis
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements.analysis.darkrate.loading import make_darkrate_df
from degg_measurements.analysis.darkrate.loading import make_scaler_darkrate_df
from degg_measurements.analysis.analysis_utils import get_measurement_numbers
##################################################
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_dt')
from decimal import Decimal

from chiba_slackbot import send_warning

def format_sci(value:float)->str:
    return "{:.5E}".format(value)

TAPING_CORR_FACTOR = 2.375


def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys


def read_timestamps(filename, temp_info=False):
    with tables.open_file(filename) as f:
        data = f.get_node('/data')
        timestamps = data.col('timestamp')
        chargestamps = data.col('chargestamp')
        try:
            datetime_timestamp = data.col('datetime_timestamp')
        except:
            warning_str = filename + " does not include datetime timing information (file is probably older than 2022/05/11)."
            warn(warning_str)
            ##this was the start of FAT
            datetime_timestamp = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
        if temp_info:
            parameters = f.get_node('/parameters')
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
            return timestamps[0], chargestamps[0], datetime_timestamp, parameter_dict['degg_temp']

        else:
            return timestamps[0], chargestamps[0], datetime_timestamp

from scipy.stats import poisson
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d, UnivariateSpline
from math import log10, sqrt, pi
rootoo = sqrt(2)

def plot_dt_distribution(timestamps, pmt_id, plot_dir, use_fir, degg_name="None"):
    """
    Plots the 1D histogram of the \Delta t distributions for a given pmt

    Performs fits to quantify contributions from the uncorrelated, correlated, and afterpulses
    """
    # if FALSE then it makes the fits, otherwise it does not
    DEBUG = True
    if DEBUG == False:
        _bump = np.transpose(np.loadtxt(
            os.path.join(os.path.dirname(__file__), "bump.dat"),
            delimiter=","
        ))
        # _bump = np.transpose(np.loadtxt("bump.dat",delimiter=","))
        #_bump[1][_bump[1]<1e-20] = 1e-20

        _iterp = interp1d(_bump[0],
                            _bump[1],
                            bounds_error = False,
                            fill_value = 0)

        def bump(log_xs,bumpsize):
            return bumpsize*_iterp(log_xs)


    def uncorrelated_noise(xs, ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center):
        """
        Params
        --------------
            p_norm      - normalization for poissonian distribution
            p_center    - thermal noise rate (Hz)
        """
        pdf_ensemble = poisson(p_center*xs)
        return p_norm*pdf_ensemble.pmf(1)

    def afterpulses(xs, ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center):
        """
        Params
        --------------
            a_mean  - mean of afterpulses Gaussian
            a_sigma - width of afterpulses Gaussian
            a_height  - normalization for afterpulses
        """
        a_mean = 10**a_mean
        #a_sigma = 10**a_sigma
        return a_height*np.exp(-0.5*((xs - a_mean)/a_sigma)**2)


    def correlated(xs, ln_height, ln_sigma, ln_mean, p_norm, a_mean, a_sigma, a_height, p_center):
        """
        Params
        --------------
            ln_height   - log normal distribution normalization
            ln_sigma    - width of log normal distribution
            ln_mean     - "mu" for log normal distribution
        """
        #return  (ln_height/(xs*ln_sigma*pi*rootoo))*np.exp(-((np.log(xs) - ln_mean)**2)/(2*ln_sigma*ln_sigma))
        ln_mean     = ln_mean
        ln_sigma    = ln_sigma
        return (ln_height/xs)*np.exp(-0.5*((np.log10(xs)-ln_mean)/ln_sigma)**2)

    def dt_funcy(log_xs, ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center, flatit=True):
        """
        Fit is done in log-x space

        p_peak - poisson peak time
        p_norm - normialzation for poisson contribution

        a_mean - central peak
        a_sigma - central width
        a_height - central norm

        ln_sigma - exponential dropoff rate
        ln_height - exponential dropoff norm
        """

        # Dt's
        xs = 10**log_xs

        #pdf_ensemble = poisson(central_frequency*xs)

        res =  uncorrelated_noise(xs, ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center) \
                    + afterpulses(xs, ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center) \
                    + correlated(xs, ln_height, ln_sigma, ln_mean, p_norm, a_mean, a_sigma, a_height, p_center)
                    #+ bump(log_xs, bumpsize)
                    #+ ln_height*np.exp(-1*xs/ln_sigma)

        if flatit:
            fitmask = xs >1.0e-5
            fitmask = np.logical_and(fitmask, xs<5e-4)

            res[fitmask] = 0.0
        return res

        # these can be simplified when expressed in logform
        return p_norm*pdf_ensemble.pmf(1) \
                        + a_height*np.exp(-0.5*((xs - a_mean)/a_sigma)**2)  \
                        + ln_height*np.exp(-1*xs/ln_sigma)

    delta_t = np.diff(timestamps)
    if np.sum(delta_t < 0) > 0:
        print(f'Found negative delta t! - N={np.sum(delta_t < 0)}')
    mask = delta_t > 0
    ##cut away high T for difference in files if files were merged
    delta_t_in_s = delta_t / 240e6
    mask2 = delta_t_in_s < 2e-2
    mask = mask * mask2

    delta_t_in_s = delta_t[mask] / 240e6


    bins = np.logspace(
        np.log10(np.min(delta_t_in_s) * 0.9),
        np.log10(np.max(delta_t_in_s) * 1.1),
        101)

    fitmask = bins[:-1] >1.0e-5
    fitmask = np.logical_and(fitmask, bins[:-1]<5e-4)

    darkrate = len(timestamps) / np.sum(delta_t_in_s)

    values, edges = np.histogram(delta_t_in_s, bins=bins)


    values[fitmask] = 0.0

    centers = 0.5*(edges[1:]+edges[:-1])
    names = "ln_height, ln_sigma,ln_mean, p_norm, a_mean, a_sigma, a_height, p_center".split(",")
    p0 =      (   20,        2,      4,      300,    -5,      1e-6,      80,    1000)#, 0.01)
    bounds = (  (  0,       0.5,     0,      100,    -6,      1e-7,       0,     800), #, 0.0),
                (500,         5,    10,     1000,    -4,      1e-5,      300,    1050)) # , 0.03))
    for i,value in enumerate(p0):
        if value<=bounds[0][i] or value>=bounds[1][i]:
            print("Illegal {}".format(names[i]))

    small = 1e-15
    # redo this so we get it all back
    values, edges = np.histogram(delta_t_in_s, bins=bins)



    fig, ax = plt.subplots()
    ax.set_title(f'Darkrate: {darkrate:.1f} (FIR = {use_fir})')
    ax.stairs(values, edges, lw=2)

    eval_at = np.logspace(log10(np.min(delta_t_in_s*0.9)), log10(np.max(delta_t_in_s*1.1)), 1000)

    if not DEBUG:
        failed = False
        try:
            popt,pcov = curve_fit(
                dt_funcy,
                np.log10(centers),
                values,
                p0     =  p0,
                bounds = bounds,
                maxfev = 250*len(p0)
                )
        except RuntimeError:
            popt = p0
            failed = True
        for i, entry in enumerate(popt):
            if abs(entry-bounds[0][i])<small:
                print("Fit {} to its minimum".format(names[i]))
            elif abs(entry-bounds[1][i])<small:
                print("Fit {} to its maximum".format(names[i]))
        ax.plot(eval_at, dt_funcy(np.log10(eval_at), *popt, False),label="Fit")

        ax.plot(eval_at, uncorrelated_noise(eval_at, *popt),label="Uncorrelated")
        ax.plot(eval_at, afterpulses(eval_at, *popt),label="Afterpulses")
        ax.plot(eval_at, correlated(eval_at, *popt),label="Correlated")
        #ax.plot(eval_at, bump(np.log10(eval_at), popt[-1]), label="Mystery Bump")

    ax.set_xscale('log')
    #ax.set_yscale('log')

    ax.set_xlabel(r'$\Delta t$ / s')
    ax.set_ylabel('Entries / bin')
    if not DEBUG:
        ax.legend(loc='upper left')

    if degg_name != "None":
        plot_name = os.path.join(
            plot_dir,
            f'delta_t_{degg_name}_{pmt_id}.pdf')
    else:
        plot_name = os.path.join(
            plot_dir,
            f'delta_t_{pmt_id}.pdf')
    fig.savefig(plot_name)
    return values, bins, darkrate


def plot_charge_distribution(chargestamps, pmt_id, plot_dir, use_fir):
    bins = np.linspace(
        -1,
        10,
        111)

    fig, ax = plt.subplots()
    ax.hist(chargestamps,
            bins=bins,
            histtype='step',
            lw=2)

    ax.set_yscale('log')

    ax.set_xlabel('Charge / pC')
    ax.set_ylabel('Entries / bin')
    ax.set_title(f'FIR = {use_fir}')

    plot_name = os.path.join(
        plot_dir,
        f'charge_dist_{pmt_id}.pdf')
    fig.savefig(plot_name)


def plot_dt_charge_scatter(timestamps,
                           chargestamps,
                           pmt_id,
                           plot_dir,
                           use_fir):
    delta_t = np.diff(timestamps)
    if np.sum(delta_t < 0) > 0:
        print(f'Found negative delta t! - N={np.sum(delta_t < 0)}')
    mask = delta_t > 0

    delta_t_in_s = delta_t[mask] / 240e6

    fig, ax = plt.subplots()
    im = ax.scatter(delta_t_in_s,
                    chargestamps[:-1],
                    c=chargestamps[1:],
                    norm=LogNorm())
    fig.colorbar(im, label='subsequent charge / pe')

    ax.set_xscale('log')

    ax.set_xlabel(r'$\Delta t$ / s')
    ax.set_ylabel('Charge / pC')
    ax.set_title(f'FIR = {use_fir}')
    plot_name = os.path.join(
        plot_dir,
        f'dt_charge_scatter_{pmt_id}.png')
    fig.savefig(plot_name,
                dpi=300)
    plt.close(fig)

    delta_t_bins = np.logspace(
        np.log10(np.min(delta_t_in_s) * 0.9),
        np.log10(np.max(delta_t_in_s) * 1.1),
        101)
    charge_bins = np.linspace(-1, 10, 111)

    fig, ax = plt.subplots()
    h, _, _, im = ax.hist2d(
        delta_t_in_s,
        chargestamps[:-1],
        bins=[delta_t_bins,
              charge_bins])
    ax.set_title(f'Events: {np.sum(h)}, FIR = {use_fir}')
    fig.colorbar(im, label='events / bin')
    ax.set_xscale('log')

    ax.set_xlabel(r'$\Delta t$ / s')
    ax.set_ylabel('Charge / pC')
    plot_name = os.path.join(
        plot_dir,
        f'dt_charge_hist_{pmt_id}.png')
    fig.savefig(plot_name,
                dpi=300)
    plt.close(fig)


def run_analysis(degg_dict, pmt, key, plot_dir, logbook, run_number, remote):
    if remote:
        folder = degg_dict[pmt][key]['RemoteFolder']
    else:
        folder = degg_dict[pmt][key]['Folder']
    #folder = degg_dict[pmt][key]['Folder']
    degg_name = degg_dict['DEggSerialNumber']
    pmt_id = degg_dict[pmt]['SerialNumber']
    #temp = degg_dict[pmt][key]['DEggSurfaceTemp']
    filename = os.path.join(folder, pmt_id + '.hdf5')
    if not os.path.exists(filename):
        print(f'File {filename} does not exist! - Skipping')
        return

    try:
        use_fir = degg_dict[pmt][key]['use_fir']
    except KeyError:
        print(f'This older measurement ({key}) does not have the use_fir key!')
        use_fir = 'Unknown'

    if key.split('_')[0] == 'DarkrateTemperature':
        use_fir = True

    try:
        timestamps, chargestamps, dt_ts, temp  = read_timestamps(
            filename, temp_info=True)
    except:
        print('Error in reading timestamps - Skipping')
        send_warning(f'Error reading timestamps for {filename}')
        return

    dt_hist, bins, darkrate = plot_dt_distribution(
        timestamps, pmt_id, plot_dir, use_fir, degg_name)
    plot_charge_distribution(chargestamps, pmt_id, plot_dir, use_fir)
    plot_dt_charge_scatter(timestamps, chargestamps,
                           pmt_id, plot_dir, use_fir)

    if logbook != None:
        result = Result(
            pmt_id,
            logbook=logbook,
            run_number=run_number,
            remote_path=REMOTE_DATA_DIR
        )

        json_filenames = result.to_json(
            meas_group='darknoise',
            raw_files=filename,
            folder_name=DB_JSON_PATH,
            filename_add=key,
            bins=bins,
            delta_t_hist=dt_hist,
            darkrate=darkrate,
            temperature=float(temp),
            lin_bins=False
        )

        run_handler = RunHandler(filenames=json_filenames)
        run_handler.submit_based_on_meas_class()


def analysis_wrapper(run_json, measurement_number="latest", remote=False, offline=False):
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
    if offline == False:
        logbook = DEggLogBook()
    if offline == True:
        logbook = None

    data_key = 'DeltaTMeasurement'

    for degg_file in tqdm(list_of_deggs):
        degg_dict = load_degg_dict(degg_file)
        pmts = ['LowerPmt', 'UpperPmt']
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
            # print(measurement_number)
            #loop over all configured measurements
            for num in measurement_numbers:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                # print(data_key_to_use)

                run_plot_dir = os.path.join(
                    PLOT_DIR,
                    f'{run_number}_{data_key_to_use}')

                if not os.path.isdir(run_plot_dir):
                    os.makedirs(run_plot_dir)
                    print(f'Created {run_plot_dir}')

                if audit_ignore_list(degg_file, degg_dict, data_key_to_use) == True:
                    continue

                run_analysis(degg_dict, pmt, data_key_to_use,
                             run_plot_dir, logbook, run_number, remote)


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--measurement_number', '-n', default='latest')
@click.option("--remote", is_flag=True)
@click.option('--offline', is_flag=True)
def main(run_json, measurement_number, remote, offline):
    analysis_wrapper(run_json, measurement_number, remote, offline)


if __name__ == '__main__':
    main()

