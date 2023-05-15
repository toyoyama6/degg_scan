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
from degg_measurements.utils import get_spe_avg_waveform
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.control_data_charge import read_data_charge
from degg_measurements.analysis import Result
from termcolor import colored

E_CONST = 1.60217662e-7
TIME_SCALING = 1 / 240e6
VOLT_SCALING = 0.075e-3

def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def fit_func(x, spe_norm, spe_peak, spe_width):
    return gauss(x, spe_norm, spe_peak, spe_width)

def run_fit(filename, pmt, pmt_id, degg_id, save_fig=False,
            run_number=None, data_key=None):
    ret = {}
    charges, timestamps, params = read_data_charge(filename)

    ret['charges'] = charges
    ret['timestamps'] = timestamps
    ret['temp'] = params['degg_temp']
    ret['hv_mon'] = params['hv_mon']
    ret['hv_mon_pre'] = params['hv_mon_pre']

    #print(charges)
    hv = params['hv']
    ret['hv'] = hv
    # charges, pmt, hv
    print(f"Running fit at {hv}V")
    bins = np.linspace(-1, 9, 101)
    hist, edges = np.histogram(charges, bins=bins)
    center = (edges[1:] + edges[:-1]) * 0.5

    init_spe_norm = np.max(hist)
    init_spe_peak = center[np.argmax(hist)]
    print(f"peak/mean = {center[np.argmax(hist)]/np.mean(charges)}")
    if init_spe_peak/np.mean(charges) < 0.1: 
        init_spe_peak = np.mean(charges) * 0.3
    #init_spe_peak = np.mean(charges)
    init_spe_width = 0.35 * init_spe_peak

    p0 = [init_spe_norm, init_spe_peak, init_spe_width]

    #bounds = [(0.5 * init_spe_norm, 0.8 * init_spe_peak, 0.05),
    bounds = [(0.5 * init_spe_norm, 0.5 * init_spe_peak, 0.05),
              (2. * init_spe_norm, 1.2 * init_spe_peak, 2. * init_spe_width)]


    popt, pcov = curve_fit(fit_func,
                           center[center>1.], hist[center>1.],
                           p0=p0, bounds=bounds,
                           #sigma=np.sqrt(hist)/hist, absolute_sigma=True,
                           maxfev=1000)

    #popt = 1.6
    #pcov = 1
    print("--------")
    print(f"popt: {popt}")
    print(f"bounds: {bounds}")
    i = 0
    for info in popt:
        if (info*0.99) < bounds[0][i] or (info*1.1) > bounds[1][i]:
            print(f"{i}: WOAH, CHECK THIS OUT!")
        i += 1
    print("-------")
    
    ret['popt'] = popt[1]
    ret['pcov'] = np.sqrt(np.diag(pcov))[1]
    print(ret['pcov'])

    print(hist)
    plotSetting(plt)
    if save_fig:
        fig, ax = plt.subplots()
        ax.errorbar(center, hist,
                    xerr=np.diff(edges)*0.5,
                    yerr=np.sqrt(hist),
                    fmt='none')
        ax.plot(center, fit_func(center, *popt), color='r')
        ax.set_xlabel('Charge Stamp Value [pC]')
        ax.set_ylabel('Entries')
        ax.set_title(f"{pmt_id} - ({degg_id}, {pmt}) - {hv} V")
        ax.set_ylim(1, np.max(hist)*1.2)
        ax.set_yscale('log')
        ax.axvline(np.mean(charges), color="tomato", linestyle=":")
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
        if run_number is not None:
            folder = os.path.join(folder, f'run_{run_number}')
        if data_key is not None:
            folder = os.path.join(folder, f'key_{data_key}')
        if not os.path.isdir(folder):
            os.makedirs(folder)
        fig.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}.pdf'))
        plt.close(fig)

    return ret

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


def run_analysis(data_key, degg_dict, pmt, logbook, run_number):
    folder = degg_dict[pmt][data_key]['Folder']
    pmt_id = degg_dict[pmt]['SerialNumber']
    lower_upper = pmt
    degg_id = degg_dict['DEggSerialNumber']
    filenames = glob(os.path.join(folder, pmt_id + '*.hdf5'))

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

    hvs = []
    gains = []
    gerrs = []
    for file_name in filenames:
        fit_info = run_fit(file_name, pmt, pmt_id, degg_id, save_fig=True,
                           run_number=run_number,
                           data_key=data_key)
        high_voltage = fit_info['hv']
        popt = fit_info['popt']
        pcov = fit_info['pcov']
        temp = fit_info['temp']
        hv_mon = fit_info['hv_mon']
        hv_mon_pre = fit_info['hv_mon_pre']

        spe_peak_pos = popt
        print(spe_peak_pos)
        spe_peak_pos_err = pcov
        print(spe_peak_pos_err)

        gain, gain_err = calculate_gain(high_voltage, spe_peak_pos, spe_peak_pos_err)
        print(gain)
        hvs.append(high_voltage)
        gains.append(gain)
        gerrs.append(gain_err)

    #print(f'hvs: {hvs}\ngains:{gains}\ngerrs:{gerrs}')
    plotSetting(plt)
    #plt.rcParams['figure.subplot.left'] = 0.8
    fig, ax = plt.subplots()
    ax.errorbar(hvs, gains, gerrs, fmt='o')
    #ax.set_yscale('log')
    ax.set_xlabel('Applied High Voltage [V]')
    ax.set_ylabel(r'Observed Gain')
    ax.set_title(f'{pmt_id} - ({degg_id}, {pmt})')
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if run_number is not None:
        folder = os.path.join(folder, f'run_{run_number}')
    if data_key is not None:
        folder = os.path.join(folder, f'key_{data_key}')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    fig.savefig(os.path.join(folder, f'gain_{pmt_id}.pdf'))

    #result.to_json(meas_group='charge',
    #               raw_files=file_name,
    #               folder_name='../database_jsons',
    #               filename_add=data_key.replace('Folder', ''),
    #               high_voltage=high_voltage,
    #               gain=gain,
    #               gain_err=gain_err,
    #               temperature=temp)
    # result.to_database(dry_run=True)
    return degg_dict


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--measurement_number', '-n', default='latest')
@click.option('--offline', is_flag=True)
def main(run_json, measurement_number, offline):
    try:
        measurement_number = int(measurement_number)
    except ValueError:
        pass

    data_key = 'ChargeGainMeasurement'

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
            try:
                degg_dict = run_analysis(data_key_to_use, degg_dict,
                                         pmt, logbook, run_number)
            except KeyError:
                continue
            update_json(degg_file, degg_dict)


if __name__ == '__main__':
    main()

