import sys
import os
import click
from collections import defaultdict
from glob import glob
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit
from scipy.optimize import least_squares
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from scipy import stats as scs
from termcolor import colored
from datetime import datetime

import degg_measurements
from degg_measurements import DB_JSON_PATH
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import get_spe_avg_waveform
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements.utils.analysis import Analysis
from degg_measurements.utils.control_data_charge import read_data_charge
from degg_measurements.analysis.analysis_utils import get_measurement_numbers

E_CONST = 1.60217662e-7
TIME_SCALING = 1 / 240e6
VOLT_SCALING = 0.075e-3


def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val


def fit_func(x, spe_norm, spe_peak, spe_width):
    return gauss(x, spe_norm, spe_peak, spe_width)


def run_fit(filename, pmt, pmt_id, save_fig=False,
            run_number=None, data_key=None,
            ext_fig_path = None, chargeStamp=False,
            verbose=True, degg_name='None'):
    ret = {}
    if chargeStamp:
        charges, time, dt_ts, params = read_data_charge(filename)
    else:
        try:
            e_id, time, waveforms, ts, pc_t, dt_ts, params = read_data(filename)
        except IOError:
            msg_str = f'Error reading file {filename} - likely timed out during data-taking'
            msg_str += ' but file is not empty. Try re-running with -i'
            print(colored(msg_str, 'red'))
            return None
        ret['waveforms'] = waveforms
        #print('Temporary solution for baseline calc')
        #baseline = np.median(waveforms)
        baseline = np.median(waveforms[:,:10], axis=1)
        charges = get_charges(waveforms*VOLT_SCALING,
                              gate_start=13,
                              gate_width=15,
                              baseline=baseline*VOLT_SCALING)

    ret['time'] = time
    ret['temp'] = float(params['degg_temp'])
    ret['hv_mon'] = params['hv_mon']
    ret['hv_mon_pre'] = params['hv_mon_pre']
    hv = params['hv']
    ret['charges'] = charges
    ret['hv'] = float(hv)
    ret['datetime_timestamp'] = dt_ts
    # charges, pmt, hv
    if verbose == True:
        print(f"Running fit at {hv} V")
        print(f'Meidan Charge {np.median(charges)}')
    #bins = np.linspace(-1, 9, 101)
    #bins = np.linspace(0, 12, 80)
    bins = np.linspace(0, 6, 80)
    hist, edges = np.histogram(charges, bins=bins)
    center = (edges[1:] + edges[:-1]) * 0.5
    mask = (center > 0.7) & (center < 3)

    init_spe_norm = np.max(hist)
    #init_spe_peak = np.bincount(hist).argmax()
    init_spe_peak = np.median(charges)
    #init_spe_peak = center[np.argmax(hist)]
    init_spe_width = np.abs(0.35 * init_spe_peak)

    if init_spe_peak > 2.5 and init_spe_peak < 4:
        bins = np.linspace(0, 10, 80)
        hist, edges = np.histogram(charges, bins=bins)
        center = (edges[1:] + edges[:-1]) * 0.5
        mask = (center > 1) & (center < 7)
        init_spe_norm = np.max(hist)
        init_spe_width = np.abs(0.35 * init_spe_peak)
    if init_spe_peak >= 4:
        bins = np.linspace(0, 14, 80)
        hist, edges = np.histogram(charges, bins=bins)
        center = (edges[1:] + edges[:-1]) * 0.5
        mask = (center > 2.2) & (center < 14)
        init_spe_norm = np.max(hist)
        init_spe_width = np.abs(0.35 * init_spe_peak)

    p0 = [init_spe_norm, init_spe_peak, init_spe_width]
    bounds = [(0.5 * init_spe_norm, 0.5 * init_spe_peak, 0.1 * init_spe_width),
              (2. * init_spe_norm, 1.2 * init_spe_peak, 2. * init_spe_width)]

    popt, pcov = curve_fit(fit_func,
                           center[mask], hist[mask],
                           p0=p0, bounds=bounds,
                           #sigma=np.sqrt(hist)/hist, absolute_sigma=True,
                           maxfev=1000)

    mask = center > 0.8
    if verbose == True:
        print(f'<analyze_gain> Charge Histogram popt {popt}')

    i = 0
    for info in popt:
        if (info*0.99) < bounds[0][i]:
            print(f'Parameter {i} with value {info} close to '
                  f'lower bound {bounds[0][i]}')
        elif (info*1.1) > bounds[1][i]:
            print(f'Parameter {i} with value {info} close to '
                  f'upper bound {bounds[1][i]}')
        i += 1

    ret['popt'] = popt
    ret['pcov'] = pcov
    ret['center'] = center

    if save_fig:
        fig, ax = plt.subplots()
        ax.errorbar(center, hist,
                    xerr=np.diff(edges)*0.5,
                    yerr=np.sqrt(hist),
                    fmt='none')
        ax.plot(center, fit_func(center, *popt))
        ax.set_yscale('log')
        ax.set_xlabel('Charge / pC')
        ax.set_ylabel('Entries')
        if degg_name == 'None':
            ax.set_title(f"{pmt_id} - ({pmt})")
        else:
            ax.set_title(f'{degg_name}:{pmt_id} - ({pmt})')
        ax.set_ylim(1, np.max(hist)*1.2)
        if ext_fig_path != None:
            folder = ext_fig_path
        else:
            folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
        if run_number is not None:
            folder = os.path.join(folder, f'run_{run_number}')
        if data_key is not None:
            folder = os.path.join(folder, f'key_{data_key}')
        if not os.path.isdir(folder):
            os.makedirs(folder)
        fig.savefig(os.path.join(folder, f'charge_hist_{pmt_id}_{hv}.pdf'))
        plt.close(fig)

    if verbose == True:
        print("-------")
    return ret


def calculate_gain(high_voltages, spe_peak_pos,
                   spe_peak_pos_err):
    if len(high_voltages) != len(spe_peak_pos):
        raise ValueError('HV and SPE peak positions should have the same shape!')

    gain = spe_peak_pos / E_CONST
    gain_err = spe_peak_pos_err / E_CONST
    print(high_voltages, gain)

    sys_err = gain * 0.02
    combined_err = np.sqrt(gain_err**2 + sys_err**2)

    if len(gain) == 1:
        return gain, combined_err, None, None, None, None

    p0 = [1e-18, 7]
    popt, pcov = curve_fit(gain_func, high_voltages, gain,
                           p0=p0, sigma=combined_err, maxfev=10000)
    print(f"<calculate_gain> Gain popt {popt}")
    print(f"<calculate_gain> Gain pcov {pcov}")

    fitted_gain = gain_func(high_voltages, *popt)
    r_chi2 = np.sum(((fitted_gain - gain) / combined_err)**2) / (len(gain) - len(p0))


    min_voltage = np.maximum(1000, np.min(high_voltages) - 480)
    max_voltage = np.minimum(2000, np.max(high_voltages) + 480)
    try:
        ctrl_v_at_1e7_gain = brentq(shifted_gain_func,
                                    min_voltage,
                                    max_voltage,
                                    args=tuple(popt))
    except ValueError:
        print(colored(
            'Can not find a solution with brentq. Using min/max voltage!', 'red'))
        if (shifted_gain_func(min_voltage, *popt) <
                shifted_gain_func(max_voltage, *popt)):
            ctrl_v_at_1e7_gain = min_voltage
        else:
            ctrl_v_at_1e7_gain = max_voltage
    v_at_1e7_gain_str = f'Control voltage at 1e7 Gain: {ctrl_v_at_1e7_gain:.4f} V'
    if ctrl_v_at_1e7_gain < 1000 or ctrl_v_at_1e7_gain > 2000:
        raise ValueError(f'Control voltage should be around ~1500 V, not {ctrl_v_at_1e7_gain:.4f} V !')
    return gain, combined_err, popt, pcov, ctrl_v_at_1e7_gain, r_chi2


def estimate_next_point(hv_values, gain_values, gain_err_values,
                        nominal_gain):
    bounds = [1050, 1950]
    if len(gain_values) <= 4:
        volt_step = 40
        if gain_values[-1] < nominal_gain:
            new_hv = hv_values[-1] + volt_step
            while new_hv in hv_values:
                new_hv += volt_step
        else:
            new_hv = hv_values[-1] - volt_step
            while new_hv in hv_values:
                new_hv -= volt_step
    else:
        try:
            _, _, _, _, hv_at_1e7_gain, _ = calculate_gain(
                hv_values,
                np.asarray(gain_values)*E_CONST,
                np.asarray(gain_err_values)*E_CONST)
            new_hv = hv_at_1e7_gain
        except RuntimeError:
            print(f'<estimate_next_point> Could not find new hv! Trying interp1d!')
            min_gain_idx = np.argmin(gain_values)
            max_gain_idx = np.argmax(gain_values)
            gain_f = interp1d([hv_values[min_gain_idx], hv_values[max_gain_idx]],
                              np.log10([gain_values[min_gain_idx],
                                        gain_values[max_gain_idx]]) - 7,
                              fill_value='extrapolate')
            try:
                new_hv = brentq(gain_f,
                                bounds[0], bounds[1])
            except ValueError:
                return -1

    new_hv = np.maximum(new_hv, bounds[0])
    new_hv = np.minimum(new_hv, bounds[1])
    return new_hv


def log_gain_func(x, norm, exponent):
    norm = np.power(10, norm)
    exponent = np.power(10, exponent)
    val = norm * np.power(x, exponent)
    return np.log10(val)


def gain_func(x, norm, exponent):
    val = norm * np.power(x, exponent)
    return val


def shifted_gain_func(x, norm, exponent, shift=1e7):
    shifted_val = gain_func(x, norm, exponent) - shift
    return shifted_val


def plot_gain(high_voltages, gain, gain_err, popt, degg_id, pmt, lower_upper, pdf,
              run_number=None, data_key=None, temps=None, hv_mon=None,
              hv_mon_b4=None):
    fig, ax = plt.subplots()
    print(high_voltages, gain)
    ax.errorbar(high_voltages, gain, yerr=gain_err, fmt='o', zorder=0)
    #colors = np.arange(len(gain))
    #im = ax.scatter(high_voltages, gain, c=colors, zorder=3)
    #if temps is not None:
    #    for i, (x, y, temp) in enumerate(zip(high_voltages, gain, temps)):
    #        ax.annotate(f'{float(temp):.1f}', (x - 20 + i * 4,y), fontsize=8)
    new_v = np.linspace(np.min(high_voltages) - 40,
                        np.max(high_voltages) + 40,
                        201)
    ax.plot(new_v, gain_func(new_v, *popt))
    #fig.colorbar(im)
    ax.set_title(f'{pmt} ({degg_id}:{lower_upper})')
    ax.set_xlabel('Control voltage / V')
    ax.set_ylabel('Gain')
    ax.set_yscale('log')
    ax.grid()
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if run_number is not None:
        folder = os.path.join(folder, f'run_{run_number}')
    if data_key is not None:
        folder = os.path.join(folder, f'key_{data_key}')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    fig.savefig(os.path.join(folder, f'gain_curve_{pmt}.pdf'),
                bbox_inches='tight')
    if pdf != None and pdf != False:
        pdf.savefig(fig)
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.set_title(f'{pmt} ({degg_id}:{lower_upper})')
    ax.scatter(list(map(float, temps)), gain)
    ax.set_xlabel('Mainboard temperature / deg')
    ax.set_ylabel('Gain')
    ax.set_yscale('log')
    fig.savefig(os.path.join(folder, f'gain_vs_temp_{pmt}.pdf'),
                bbox_inches='tight')
    plt.close(fig)

    #have to do some string slicing...
    hv_ave_list = []
    for hv_s in hv_mon:
        hv_s = hv_s[1:-1]
        hv_s = hv_s.split(' ')
        hv_aves = []
        for hv in hv_s:
            try:
                val = float(hv)
            except ValueError:
                try:
                    val = int(hv)
                except ValueError:
                    continue
            hv_aves.append(val)
        hv_ave = np.mean(hv_aves)
        hv_ave_list.append(hv_ave)
    hv_ave_b4_list = []
    for hv_s in hv_mon_b4:
        hv_s = hv_s[1:-1]
        hv_s = hv_s.split(' ')
        hv_aves = []
        for hv in hv_s:
            try:
                val = float(hv)
            except ValueError:
                try:
                    val = int(hv)
                except ValueError:
                    continue
            hv_aves.append(val)
        hv_ave = np.mean(hv_aves)
        hv_ave_b4_list.append(hv_ave)

    fig3, ax3 = plt.subplots()
    ax3.set_title(f'{pmt} ({degg_id}:{lower_upper})')
    ax3.scatter(list(map(float, hv_ave_list)), gain)
    ax3.set_xlabel('Mainboard HV [V]')
    ax3.set_ylabel('Gain')
    ax3.set_yscale('log')
    fig3.savefig(os.path.join(folder, f'gain_vs_hv_{pmt}.pdf'), bbox_inches='tight')
    plt.close(fig3)

    fig4, ax4 = plt.subplots()
    ax4.set_title(f'{pmt} ({degg_id}:{lower_upper})')
    ax4.set_xlabel('Control Voltage [V]')
    ax4.set_ylabel('Read-back Voltage [V}')
    ax4.scatter(list(map(float, high_voltages)), list(map(float, hv_ave_list)))
    fig4.savefig(os.path.join(folder, f'hv_vs_hv_{pmt}.pdf'), bbox_inches='tight')
    plt.close(fig4)

    fig5, ax5 = plt.subplots()
    ax5.set_title(f'{pmt} ({degg_id}:{lower_upper})')
    ax5.set_xlabel('Control Voltage [V]')
    ax5.set_ylabel('Read-back Voltage [V]')
    h=ax5.scatter(list(map(float, high_voltages)), list(map(float, hv_ave_list)),
                  c=list(map(float, temps)), cmap='viridis')
    plt.colorbar(h, label='Temperature [C]')
    fig5.savefig(os.path.join(folder, f'hv_vs_hv_temp_{pmt}.pdf'),
                    bbox_inches='tight')
    plt.close(fig5)

    if hv_mon_b4 is not None and hv_mon is not None:
        fig6, ax6 = plt.subplots()
        ax6.set_title(f'{pmt} ({degg_id}:{lower_upper})')
        ax6.set_xlabel('Read-back Voltage Before Data-taking [V]')
        ax6.set_ylabel('Read-back Voltage After Data-taking [V]')
        h=ax6.scatter(list(map(float, hv_ave_b4_list)),
                      list(map(float, hv_ave_list)),
                      c=list(map(float,high_voltages)),
                      cmap='viridis')
        ax6.plot([1000, 2000],[1000, 2000], linestyle='dashed',
                    color='black', label='1:1')
        ax6.legend()
        ax6.set_xlim(np.min(hv_ave_b4_list)*0.98, np.max(hv_ave_b4_list)*1.02)
        ax6.set_ylim(np.min(hv_ave_list)*0.98, np.max(hv_ave_list)*1.02)
        plt.colorbar(h, label='Control Voltage [V]')
        fig6.savefig(os.path.join(folder, f'hv_vs_hv_hv_{pmt}.pdf'),
                      bbox_inches='tight')

##this is returned in units of Volts!
def calc_avg_spe_peak_height(times, waveforms, charges, hv, spe_means,
                             bl_start, bl_end, use_adc=False):
    _, avg_waveform, _ = get_spe_avg_waveform(times, waveforms,
                                              charges, spe_means)
    baseline = np.average(avg_waveform[bl_start:bl_end])
    peak_height = np.max(avg_waveform) - baseline
    if use_adc == True:
        return peak_height / VOLT_SCALING
    else:
        return peak_height


def linear_func(x, a, b):
    return a * x + b


##these peak_heights are also still in units of Volts!
def plot_peak_height_vs_control_voltage(ctrl_vs, peak_heights, gain,
                                        ctrl_v_at_1e7_gain, pmt,
                                        run_number=None, data_key=None):
    popt, pcov = curve_fit(linear_func, ctrl_vs, peak_heights)

    fig, ax = plt.subplots()
    ax.plot(ctrl_vs, peak_heights, 'o--')
    new_x = np.linspace(np.min(ctrl_vs) - 40,
                        np.max(ctrl_vs) + 40,
                        101)
    ax.plot(new_x, linear_func(new_x, *popt))
    ax.set_xlabel('Control voltage / V')
    ax.set_ylabel('SPE amplitude / V')
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if run_number is not None:
        folder = os.path.join(folder, f'run_{run_number}')
    if data_key is not None:
        folder = os.path.join(folder, f'key_{data_key}')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    fig.savefig(os.path.join(folder, f'peak_height_{pmt}.pdf'))
    plt.close(fig)

    fig2, ax2 = plt.subplots()
    ax2.plot(gain, peak_heights, 'o--')
    ax2.set_xlabel('Gain / 1e7')
    ax2.set_ylabel('SPE Amplitude / V')
    fig2.savefig(os.path.join(folder, f'peak_height_gain_{pmt}.pdf'))
    plt.close(fig2)

    ##if data is from "monitoring" linear fit may not work well
    if len(np.unique(ctrl_vs)) == 1:
        peak_height_1e7 = np.mean(peak_heights)

    ##find spe peak height at 1e7 gain
    else:
        peak_height_1e7 = linear_func(ctrl_v_at_1e7_gain, *popt)

    if peak_height_1e7 > 0.01 or peak_height_1e7 < 0.001:
        raise ValueError(f'SPE Peak Height should be around 0.003 V not {peak_height_1e7} V!')
    return peak_height_1e7

def plot_chi2(red_chi2_list, list_of_deggs, data_key, run_number, savedir):
    fig1, ax1 = plt.subplots()
    ax1.set_title(r'Gain Curve Reduced $\chi^{2}$')
    ax1.set_xlabel(r'Reduced $\chi^{2}$')
    ax1.set_ylabel('Num. PMTs')
    bins = 10
    ax1.hist(red_chi2_list, bins=bins)
    savedir = os.path.join(savedir, f'run_{run_number}')
    savedir = os.path.join(savedir, f'key_{data_key}')
    fig1.savefig(os.path.join(savedir, f'pmt_gain_reduced_chi2.pdf'))


def plot_delta_v(info_l, list_of_deggs, data_key, run_number, savedir):
    delta_v_l = []
    temp_l = []
    for info in info_l:
        delta_v, temp = info
        delta_v_l.append(delta_v)
        temp_l.append(temp)

    list_of_deggs[0]
    fig1, ax1 = plt.subplots()
    ax1.set_title('Delta V vs Temperature')
    ax1.set_xlabel('D-Egg Temperature [C]')
    ax1.set_ylabel(r'$V_{Cntl}$ - $V_{Read-back}$ [V]')
    ax1.plot(temp_l, delta_v_l, linewidth=0, marker='o')
    savedir = os.path.join(savedir, f'run_{run_number}')
    savedir = os.path.join(savedir, f'key_{data_key}')
    fig1.savefig(os.path.join(savedir, f'pmt_gain_delta_v_temp.pdf'))


def run_analysis(data_key, degg_dict, pmt, logbook, run_number,
                 pdf, offline, save_df, ignore_files=False, remote=False):
    result = None
    if remote:
        folder = degg_dict[pmt][data_key].get('RemoteFolder', 'None')
    else:
        folder = degg_dict[pmt][data_key]['Folder']
    pmt_id = degg_dict[pmt]['SerialNumber']
    lower_upper = pmt
    degg_id = degg_dict['DEggSerialNumber']
    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))

    print(f"PMT ID: {pmt_id}")
    if folder == 'None':
        return degg_dict, False, np.nan, (np.nan, np.nan)

    if logbook is not None:
        result = Result(pmt_id,
                        logbook=logbook,
                        run_number=run_number,
                        remote_path=REMOTE_DATA_DIR)
    else:
        print("Skipping Upload Step, run without --offline to enable")

    df = pd.DataFrame()
    info_dict = defaultdict(list)

    for j, file_name in enumerate(files):
        fit_info = run_fit(file_name, pmt, pmt_id, save_fig=True,
                           run_number=run_number,
                           data_key=data_key,
                           degg_name=degg_dict['DEggSerialNumber'])
        if fit_info == None and ignore_files == True:
            return degg_dict, None, None, (None, None)
        info_dict['high_voltages'].append(fit_info['hv'])
        info_dict['spe_peak_pos'].append(fit_info['popt'][1])
        info_dict['spe_peak_pos_err'].append(fit_info['pcov'][1, 1])
        info_dict['temps'].append(fit_info['temp'])
        info_dict['hv_mon'].append(fit_info['hv_mon'])
        info_dict['hv_mon_b4_wf'].append(fit_info['hv_mon_pre'])

        ##this value is in Volts!
        peak_height = calc_avg_spe_peak_height(
            fit_info['time']*TIME_SCALING,
            fit_info['waveforms']*VOLT_SCALING,
            fit_info['charges'],
            fit_info['hv'],
            fit_info['popt'][1],
            bl_start=50,
            bl_end=120)
        info_dict['peak_heights'].append(peak_height)

    df = pd.DataFrame(info_dict)
    print(df['spe_peak_pos'])
    df['gain'], df['gain_err'], popt, pcov, ctrl_v_at_1e7_gain, red_chi2 = calculate_gain(
            df['high_voltages'].values,
            df['spe_peak_pos'].values,
            df['spe_peak_pos_err'].values)

    # Remove points at small hv values where it looks like the gain is not
    # increasing monotonically with increasing HV
    min_gain_idx = np.argmin(df['gain'])
    mask = df['high_voltages'] >= df['high_voltages'].values[min_gain_idx]
    df = df.loc[mask]

    ##option to save dataframe
    if save_df == True:
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        df.to_hdf(os.path.join(cache_dir, f'{run_number}_{data_key}_gain_check_{pmt_id}.hdf5'), 'df')

    ##try to automatically detect 'check' mode runs
    if df.shape[0] == 1:
        if offline == False:
            print(df['gain'])
            json_filenames = result.to_json(
				meas_group='gain',
			    raw_files=files,
			    folder_name=DB_JSON_PATH,
			    filename_add=data_key.replace('Folder', ''),
			    high_voltage=df['high_voltages'].iloc[0],
			    gain=df['gain'].iloc[0],
			    temperature=df['temps'].iloc[0],
			    peak_height=df['peak_heights'].iloc[0])

            #run_handler = RunHandler(filenames=json_filenames)
            #run_handler.submit_based_on_meas_class()
        return degg_dict, None, None, None


    degg_dict[pmt]['HV1e7Gain'] = ctrl_v_at_1e7_gain

    degg_dict[pmt][data_key]['GainFitNorm'] = popt[0]
    degg_dict[pmt][data_key]['GainFitExp'] = popt[1]
    print(pmt, ctrl_v_at_1e7_gain)
    plot_gain(df['high_voltages'],
              df['gain'],
              df['gain_err'],
              popt,
              degg_id,
              pmt_id,
              lower_upper,
              pdf,
              run_number=run_number,
              data_key=data_key,
              temps=df['temps'],
              hv_mon=df['hv_mon'],
              hv_mon_b4=df['hv_mon_b4_wf'])

    spe_peak_height = plot_peak_height_vs_control_voltage(
        df['high_voltages'],
        df['peak_heights'],
        df['gain'],
        ctrl_v_at_1e7_gain,
        pmt_id,
        run_number=run_number,
        data_key=data_key)

    ##this is in units of V!
    degg_dict[pmt]['SPEPeakHeight'] = spe_peak_height

    if result is not None:
        json_filenames = result.to_json(
			meas_group='gain',
		    raw_files=files,
		    folder_name=DB_JSON_PATH,
		    filename_add=data_key.replace('Folder', ''),
		    high_voltage=df['high_voltages'].tolist(),
		    gain=df['gain'].tolist(),
		    temperature=df['temps'].tolist(),
		    gain_err=df['gain_err'].tolist(),
		    high_v_at_1e7_gain=ctrl_v_at_1e7_gain,
		    peak_height=spe_peak_height)

        #run_handler = RunHandler(filenames=json_filenames)
        #run_handler.submit_based_on_meas_class()

    hv_ave_list = []
    for hv_s in df['hv_mon']:
        hv_s = hv_s[1:-1]
        hv_s = hv_s.split(' ')
        hv_aves = []
        for hv in hv_s:
            try:
                val = float(hv)
            except ValueError:
                try:
                    val = int(hv)
                except ValueError:
                    continue
            hv_aves.append(val)
        hv_ave = np.mean(hv_aves)
        hv_ave_list.append(hv_ave)
    delta_v_l = df['high_voltages'] - hv_ave_list
    delta_v = np.mean(delta_v_l)
    ave_t = np.mean(df['temps'])

    print(delta_v)
    if delta_v < 20:
        verdict = 1
    else:
        verdict = 0

    return degg_dict, verdict, red_chi2, (delta_v, ave_t)

def analysis_wrapper(run_json, pdf=None, mode="gain_scan", measurement_number="latest", simple=False, save_df=False,
                     ignore_files=False, remote=False, offline=True):

    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if not os.path.exists(folder):
        os.mkdir(folder)
        print(f'Created directory: {folder}!')

    if mode not in ['gain_scan', 'gain_check']:
        print(mode)
        raise NotImplementedError('mode has to be either "gain_scan"'
                                  ' or "gain_check"!')
    # if measurement_number != 'latest':
    #     nums = measurement_number.split(',')
    #     if len(nums) == 1:
    #         measurement_number = int(measurement_number)
    #     else:
    #         measurement_number = nums

    if simple == True:
        data_key = 'GainMeasurementSimple'
    else:
        data_key = 'GainMeasurement'

    if offline:
        logbook = None
    else:
        logbook = DEggLogBook()

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)

    red_chi2_l = []
    info_l = []
    analysis_list = []
    l_verdict = 0
    u_verdict = 0

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)

        pmts = ['LowerPmt', 'UpperPmt']
        for pmt in pmts:
            measurement_numbers = get_measurement_numbers(degg_dict, pmt, measurement_number, data_key)
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
            # if type(measurement_number) == np.int64 or type(measurement_number) == int:
            #     measurement_number = [measurement_number]
            print(measurement_numbers)
            #loop over all configured measurements
            for num in measurement_numbers:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                print(data_key_to_use)
                try:
                    this_dict = degg_dict[pmt][data_key_to_use]
                except KeyError:
                    print(f'KeyError: {data_key_to_use} - {degg_dict["DEggSerialNumber"]}, {pmt}')
                    print(degg_dict[pmt])
                    exit(1)
                # if audit_ignore_list(degg_file, degg_dict, data_key_to_use) == True:
                #     continue

                degg_dict, verdict, red_chi2, info = run_analysis(data_key_to_use, degg_dict,
                                                                  pmt, logbook, run_number, pdf,
                                                                  offline, save_df,
                                                                  ignore_files, remote=remote)
                update_json(degg_file, degg_dict)

                if verdict == None:
                    continue

                if pmt == 'LowerPmt':
                    l_verdict += verdict
                if pmt == 'UpperPmt':
                    u_verdict += verdict

            red_chi2_l.append(red_chi2)
            info_l.append(info)

        analysis = Analysis(f'Gain (N={len(measurement_numbers)})',
                  degg_dict['DEggSerialNumber'],
                  u_verdict, l_verdict, len(measurement_numbers))
        analysis_list.append(analysis)

    if red_chi2_l[0] == None:
        return 0

    savedir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    if len(red_chi2_l) > 0:
        try:
            plot_chi2(red_chi2_l, list_of_deggs,
                  data_key_to_use, run_number, savedir)
            plot_delta_v(info_l, list_of_deggs,
                     data_key_to_use, run_number, savedir)
        except:
            print('Error in chi2 plotting script, likely the return chi2 was 0/None for a file')
            print('This is usually not a problem...')

    return analysis_list

@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--pdf', default=None)
@click.option('--mode', '-m', default='gain_scan')
@click.option('--measurement_number', '-n', default='latest')
@click.option('--simple', is_flag=True)
@click.option('--save_df', is_flag=True)
@click.option('--ignore_files', '-i', is_flag=True)
@click.option('--remote', is_flag=False)
@click.option('--offline', is_flag=True)
def main(run_json, pdf, mode, measurement_number, simple, save_df, ignore_files, remote, offline):

    analysis_wrapper(run_json, pdf, mode, measurement_number, simple, save_df,
                     ignore_files, remote, offline)

if __name__ == '__main__':
    main()

