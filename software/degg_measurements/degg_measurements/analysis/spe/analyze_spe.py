import sys
import os
import click
from glob import glob
import numpy as np
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit
from scipy.optimize import least_squares
from scipy.optimize import brentq
from scipy import stats as scs

from degg_measurements.utils import read_data
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.control_data_charge import read_data_charge
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from termcolor import colored

E_CONST = 1.60217662e-7
TIME_SCALING = 1 / 240e6
VOLT_SCALING = 0.075e-3

def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def fit_func(x, spe_norm, spe_peak, spe_width):
    return gauss(x, spe_norm, spe_peak, spe_width)

def normed_gauss(x, peak, width):
    val = 1 / (np.sqrt(2 * np.pi) * width) * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def fit_func_w_exp(x, ped_norm, ped_peak, ped_width, exp_norm, tau, spe_norm, spe_peak, spe_width):
    exp_term = exp_norm / tau * np.exp(-x/tau)
    gauss_term = spe_norm * normed_gauss(x, spe_peak, spe_width)
    pedestal_term = gauss(x, ped_norm, ped_peak, ped_width)
    return pedestal_term + exp_term + gauss_term

def fit_func_w_exp(x, exp_norm, tau, spe_norm, spe_peak, spe_width):
    exp_term = exp_norm / tau * np.exp(-x/tau)
    gauss_term = spe_norm * normed_gauss(x, spe_peak, spe_width)
    return exp_term + gauss_term

def run_fit(filename, pmt, pmt_id, degg_id, save_fig=False,
            run_number=None, data_key=None, icrc=False):
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    ret = {}
    if os.path.isfile(filename):
        charges, timestamps, params = read_data_charge(filename)
    else:
        print("No valid file when reading charge data - skipping...")
        return
    if icrc:
        print('Recalibrating charges to 50 Ohm. Charge stamp calc uses 36.96!')
        # STM32Workspace/xdom-processing/include/xdom-processing/degg/degg_constants.h
        charges = charges * 36.96 / 50.

    ret['charges'] = charges
    ret['timestamps'] = timestamps
    ret['temp'] = params['degg_temp']
    ret['hv_mon'] = params['hv_mon']
    ret['hv_mon_pre'] = params['hv_mon_pre']

    print(charges)
    hv = params['hv']
    ret['hv'] = hv

    fig1, ax1 = plt.subplots()
    if hv < 1701:
        ax1.hist(charges, np.linspace(-1, 7, 100), histtype='step')
    else:
        ax1.hist(charges, np.linspace(-1, 9, 100), histtype='step')
    ax1.set_xlabel('Charge [pC]')
    ax1.set_ylabel('Entries')
    fig1.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}.pdf'))
    ax1.set_yscale('log')
    fig1.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}_log.pdf'))

    fig2, ax2 = plt.subplots()
    ax2.hist(np.diff(timestamps)/240e6, np.logspace(-7, -2, 100), histtype='step')
    ax2.set_xlabel(r'$\Delta$T [s]')
    ax2.set_ylabel('Entries')
    ax2.set_xscale('log')
    fig2.savefig(os.path.join(folder, f'delta_t_{pmt_id}_{hv}.pdf'))
    ax2.set_yscale('log')
    fig2.savefig(os.path.join(folder, f'delta_t_{pmt_id}_{hv}_log.pdf'))

    return

    if save_fig:
        fig, ax = plt.subplots()
        ax.plot(np.arange(len(charges)), charges, 'o')
        ax.set_yscale('log')
        ax.set_xlabel('Waveform number')
        ax.set_ylabel('Charge via charge stamp / pC')
        fig.savefig(os.path.join(folder, f'charge_vs_time_{pmt_id}_{hv}_log.png'),
                bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots()
        sub_data = np.array_split(charges, 5)
        bins = np.linspace(0, 7, 7001)
        for i, d in enumerate(sub_data):
            h, _, _ = ax.hist(d, bins=bins, histtype='step', lw=2, label=f'Slice {i}')
        ax.set_yscale('log')
        ax.set_xlabel('Charge / pC')
        ax.set_ylabel('Entries / bin')
        ax.set_xlim(0, 3)
        ax.legend()
        fig.savefig(os.path.join(folder, f'spe_dist_slices_{pmt_id}_{hv}_log.pdf'),
                bbox_inches='tight')
        plt.close(fig)

    # charges, pmt, hv
    print(f"Running fit at {hv}V")
    bins = np.linspace(-1, 3, 71)
    hist, edges = np.histogram(charges, bins=bins)
    center = (edges[1:] + edges[:-1]) * 0.5

    init_ped_norm = np.max(hist)
    init_ped_peak = center[np.argmax(hist)]
    init_ped_width = 0.2
    init_spe_norm = hist[53]
    init_spe_peak = 1.6
    init_tau = 0.2 * init_spe_peak
    exp_norm = init_spe_norm
    init_spe_width = 0.3 * init_spe_peak

    ped_mask = np.logical_and(center >= -0.5, center <= 0.5)
    popt_ped, pcov_ped = curve_fit(
        gauss,
        center[ped_mask], hist[ped_mask],
        p0=[init_ped_norm, init_ped_peak, init_ped_width])
    print(f'popt_ped: {popt_ped}')

    #p0 = [init_ped_norm, init_ped_peak, init_ped_width, exp_norm,
    #       init_tau, init_spe_norm, init_spe_peak, init_spe_width]
    p0 = [exp_norm,
           init_tau, init_spe_norm, init_spe_peak, init_spe_width]
    #print(p0)

    bounds = [(0.5 * init_ped_norm, -0.5, 0.01, 0.01 * init_spe_norm, 0.01, 0.5 * init_spe_norm, 0.5 * init_spe_peak, 0.05),
               (2. * init_ped_norm, 0.5, 1., 10 * init_spe_norm, 10, 2. * init_spe_norm, 1.2 * init_spe_peak, 2. * init_spe_width)]
    #bounds = [(0.01 * init_spe_norm, 0.01, 0.5 * init_spe_norm, 0.5 * init_spe_peak, 0.05),
    #          ( 10 * init_spe_norm, 100, 2. * init_spe_norm, 1.2 * init_spe_peak, 2. * init_spe_width)]

    popt, pcov = curve_fit(fit_func_w_exp,
                           center[25:], hist[25:] - gauss(center[25:], *popt_ped),
                           p0=p0, bounds=bounds,
    #                       #sigma=np.sqrt(hist)/hist, absolute_sigma=True,
                           maxfev=10000)

    print(popt)

    ret['popt'] = popt
    ret['pcov'] = pcov

    print(hist)
    if save_fig:
        plotSetting(plt)
        fig, ax = plt.subplots()
        ax.errorbar(center, hist,
                    xerr=np.diff(edges)*0.5,
                    yerr=np.sqrt(hist),
                    fmt='none',
                    label='Data',
                    color='k')
        x = np.linspace(0.5, 2.5, 101)
        ax.plot(x, popt[2]  * normed_gauss(x, popt[3], popt[4]), label='Gaussian Fit', color='C1', ls='--')
        #x = np.linspace(-0.5, 0.5, 101)
        #ax.plot(x, gauss(x, popt[0], popt[1], popt[2]))
        x = np.linspace(0.4, 1.5, 101)
        # ax.plot(x, popt[0] / popt[1] * np.exp(-x/popt[1]))
        ax.plot(center[26:], fit_func_w_exp(center[26:], *popt), label='Gaussian + Exponential', color='C1')
        x = np.linspace(np.min(center[ped_mask]), np.max(center[ped_mask]), 101)
        ax.plot(x, gauss(x, *popt_ped),
                label='Pedestal Fit', ls='--', color='C0')
        if icrc:
            ax.set_xlabel('Charge / pC', fontsize=16)
        else:
            ax.set_xlabel('Charge Stamp Value [pC]')
            ax.set_title(f"{pmt_id} - ({degg_id}, {pmt})")
        ax.legend(fontsize=16)
        ax.set_ylabel('Entries / bin', fontsize=16)
        ax.set_ylim(1, 1e5)
        if icrc:
            ax.set_xlim(-0.5, bins[-1])
        else:
            ax.set_xlim(bins[0], bins[-1])
        if run_number is not None:
            folder = os.path.join(folder, f'run_{run_number}')
        if data_key is not None:
            folder = os.path.join(folder, f'key_{data_key}')
        if not os.path.isdir(folder):
            os.makedirs(folder)
        fig.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}.pdf'))
        if icrc:
            ax.set_ylim(3e3, np.max(hist)*1.5)
        else:
            ax.set_ylim(1, np.max(hist)*1.5)
        ax.set_yscale('log')
        fig.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}_log.pdf'))
        plt.close(fig)

    return ret, center, hist

def plotSetting(plt):
    plt.rcParams['font.sans-serif'] = ['Arial','Liberation Sans']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.labelsize'] = 14
    plt.rcParams['xtick.labelsize'] = 12
    plt.rcParams['ytick.labelsize'] = 12
    plt.rcParams['xtick.direction'] = 'in'
    plt.rcParams['ytick.direction'] = 'in'
    plt.rcParams['xtick.top'] = True
    plt.rcParams['xtick.bottom'] = True
    plt.rcParams['ytick.left'] = True
    plt.rcParams['ytick.right'] = True
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.color'] = 'black'
    plt.rcParams['grid.linewidth'] = 0.8
    plt.rcParams['grid.linestyle'] = ':'
    plt.rcParams['figure.subplot.right'] = 0.95
    plt.rcParams['figure.subplot.top'] = 0.95

def calculate_gain(high_voltages, spe_peak_pos,
                   spe_peak_pos_err):

    gain = spe_peak_pos / E_CONST
    gain_err = spe_peak_pos_err / E_CONST

    sys_err = gain * 0.02
    combined_err = np.sqrt(gain_err**2 + sys_err**2)

    return gain, combined_err


def run_analysis(data_key, degg_dict, pmt, logbook, run_number, icrc, hv_setting=''):
    try:
        folder = degg_dict[pmt][data_key]['Folder']
    except KeyError:
        print(f'Key not found, skipping PMT {pmt}')
        return degg_dict, None, None
    pmt_id = degg_dict[pmt]['SerialNumber']
    lower_upper = pmt
    degg_id = degg_dict['DEggSerialNumber']
    if hv_setting == '':
        file_name = os.path.join(folder, pmt_id + '.hdf5')
    else:
        file_name = os.path.join(folder, pmt_id + f'_{hv_setting}V.hdf5')

    print(f"PMT ID: {pmt_id}")

    if logbook is not None:
        remote_path = os.path.join(
            '/data/exp/IceCubeUpgrade/commissioning',
            'degg_test_files')
        result = Result(pmt_id,
                        logbook=logbook,
                        run_number=run_number,
                        remote_path=remote_path)
    else:
        print("Skipping Upload Step, run without --offline to enable")

    fit_info, center, hist = run_fit(file_name, pmt, pmt_id, degg_id, save_fig=True,
                           run_number=run_number,
                           data_key=data_key,
                           icrc=icrc)
    high_voltage = fit_info['hv']
    popt = fit_info['popt']
    pcov = fit_info['pcov']
    temp = fit_info['temp']
    hv_mon = fit_info['hv_mon']
    hv_mon_pre = fit_info['hv_mon_pre']

    spe_peak_pos = popt
    print(spe_peak_pos)
    spe_peak_pos_err = pcov
    gain, gain_err = calculate_gain(high_voltage, spe_peak_pos, spe_peak_pos_err)

    import degg_measurements
    db_path = os.path.join(degg_measurements.__path__[0],
                           'analysis',
                           'database_jsons')
    json_filenames = result.to_json(meas_group='charge',
                   raw_files=file_name,
                   folder_name=db_path,
                   filename_add=data_key.replace('Folder', ''),
                   high_voltage=high_voltage,
                   gain=gain,
                   gain_err=gain_err,
                   temperature=temp)

    run_handler = RunHandler(filenames=json_filenames)
    run_handler.submit_based_on_meas_class()
    return degg_dict, center, hist


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--measurement_number', '-n', default='latest')
@click.option('--offline', is_flag=True)
@click.option('--icrc', is_flag=True)
def main(run_json, measurement_number, offline, icrc):
    try:
        measurement_number = int(measurement_number)
    except ValueError:
        pass

    #data_key = 'GainMeasurement'
    #print("RUNNING WITH KEY = GainMeasurement!!!")
    data_key = 'SpeMeasurement'

    if offline == False:
        logbook = DEggLogBook()
    else:
        logbook = None

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)

    plotSetting(plt)
    fig = plt.figure()
    plt.rc('legend', fontsize=9)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)

        pmts = ['LowerPmt', 'UpperPmt']
        for pmt in pmts:
            if measurement_number == 'latest':
                eligible_keys = [key for key in degg_dict[pmt].keys()
                                 if key.startswith(data_key)]
                cts = [int(key.split('_')[1]) for key in eligible_keys]
                if len(cts) == 0:
                    print(f'No measurement found for '
                          f'{degg_dict[pmt]["SerialNumber"]} '
                          f'in DEgg {degg_dict["DEggSerialNumber"]}. '
                          f'Skipping it!')
                    continue
                measurement_number = np.max(cts)
            suffix = f'_{measurement_number:02d}'
            data_key_to_use = data_key + suffix
            for hv_setting in np.arange(1200, 1850, 50):
                degg_dict, center, hist = run_analysis(data_key_to_use, degg_dict,
                                     pmt, logbook, run_number, icrc, hv_setting)
            update_json(degg_file, degg_dict)
            center = None
            hist = None
            if center is not None and hist is not None:
                ax = fig.add_subplot()
                ax.step(center,hist,label=f"{degg_dict[pmt]['SerialNumber']}")
                ax.set_yscale('log')
                ax.legend(ncol=2)
                print("make plots")

    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if run_number is not None:
        folder = os.path.join(folder, f'run_{run_number}')
    if data_key_to_use is not None:
        folder = os.path.join(folder, f'key_{data_key_to_use}')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    fig.savefig(f'{folder}/conv_hists.pdf')

if __name__ == '__main__':
    main()

