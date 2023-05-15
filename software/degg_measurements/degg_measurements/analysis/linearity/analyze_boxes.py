import sys
import os
import click
from glob import glob
import numpy as np
from termcolor import colored
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit
from scipy.optimize import least_squares
from scipy.optimize import brentq

import pandas as pd

from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import get_spe_avg_waveform
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path

from degg_measurements.utils.wfana import \
    get_highest_density_region_charge
from degg_measurements.analysis import calc_baseline

from degg_measurements.analysis.linearity.analyze_linearity import run_fit

E_CONST = 1.60217662e-7
TIME_SCALING = 1 / 240e6
VOLT_SCALING = 0.075e-3


def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def plot_linearity(fw_settings, charge_peak_positions, pmt, run, 
                    data_key, aggregate_fig=None, aggregate_ax=None, cnt=None, max_cnt=None):
    charge_to_pe = 1 / (E_CONST * 1e7)
    
    # Make sure filter wheel settings are floats
    fw_settings = np.array(fw_settings, dtype=float)
    fw_settings_all = fw_settings
    observed_pe_all = charge_peak_positions * charge_to_pe

    # Remove filter settings where the laser is not visible
    mask = fw_settings > 0.01
    fw_settings = fw_settings[mask]
    charge_peak_positions = charge_peak_positions[mask]

    observed_pe = charge_peak_positions * charge_to_pe

    # Assume first data point is linear and the filter wheel
    # settings are the absolute truth
    ratios = fw_settings / fw_settings[0]
    ideal_pe = observed_pe[0] * ratios

    if aggregate_fig is None and aggregate_ax is None:
        fig, ax = plt.subplots()
        ax.errorbar(ideal_pe, observed_pe, fmt='o', label=pmt)
        ax.plot([1, 1e4], [1, 1e4], '--', color='grey')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(1, 1e4)
        ax.set_ylim(1, 1e4)
        ax.set_xlabel("Ideal NPE / pe")
        ax.set_ylabel("Observed NPE / pe")
        ax.legend()
        fig.savefig(f'figs_boxes/linearity_{run}_{data_key}_{pmt}.pdf')

    if aggregate_fig is not None:
        aggregate_ax[0].errorbar(ideal_pe, observed_pe, fmt='o', label=pmt)
        aggregate_ax[1].errorbar(fw_settings_all, observed_pe_all, fmt='o', label=pmt, alpha=0.7) 
        if cnt == max_cnt:
            aggregate_ax[0].plot([1, 1e4], [1, 1e4], '--', color='grey')
            aggregate_ax[0].set_xscale('log')
            aggregate_ax[0].set_yscale('log')
            aggregate_ax[0].set_xlim(10, 1e3)
            aggregate_ax[0].set_ylim(10, 1e3)
            aggregate_ax[0].set_xlabel("Ideal NPE / pe")
            aggregate_ax[0].set_ylabel("Observed NPE / pe")
            aggregate_ax[0].legend()
            aggregate_fig[0].savefig(f'figs_boxes/linearity_{run}_{data_key}_aggregate.pdf')
            
            aggregate_ax[1].set_xscale('log')
            aggregate_ax[1].set_yscale('log')
            aggregate_ax[1].set_xlim(0.0009, 2)
            aggregate_ax[1].set_ylim(0.7, 400)
            aggregate_ax[1].set_xlabel("Filter Strength")
            aggregate_ax[1].set_ylabel("Observed NPE / pe")
            aggregate_ax[1].legend()
            aggregate_fig[1].savefig(f'figs_boxes/output_{run}_{data_key}_aggregate.pdf')


def run_analysis(pmt_id, folder_list, run_list):
    i = 0
    pmt = pmt_id
    data_key = 'LinearityMeasurement'

    fig_all, ax_all = plt.subplots()

    charges_list = []

    print(f"PMT ID: {pmt_id}")
    for folder, run in zip(folder_list, run_list):
        files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
        print(colored(f"Folder: {folder} '\n' Run {run}", 'green'))

        fw_settings = []
        popts, pcovs = [], []
        peak_heights = []

        for j, file_name in enumerate(files):
            try:
                e_id, time, waveforms, ts, pc_t, params = read_data(file_name)
            except UnboundLocalError:
                print(colored("Likely Error Opening File - Measurement was killed early?", 'red'))
                continue

            fw = params['strength']
            fw_settings.append(fw)
            if float(fw) == 1.:
                for i in range(10):
                    fig, ax = plt.subplots()
                    ax.plot(time[i]*TIME_SCALING*1e9,
                            waveforms[i]*VOLT_SCALING*1e3)
                    ax.set_xlabel('t / ns')
                    ax.set_ylabel('voltage / mV')
                    fig.savefig(
                        f'figs_boxes/wf_{run}_{data_key}_{pmt_id}_{i}_max_intensity.pdf')

            charges = get_charges(waveforms*VOLT_SCALING,
                                  gate_start=13,
                                  gate_width=15,
                                  baseline=waveforms[:, 0]*VOLT_SCALING)

            if file_name == params['UpperPmt.filename']:
                baseline_filename = params['UpperPmt.BaselineFilename']
            elif file_name == params['LowerPmt.filename']:
                baseline_filename = params['LowerPmt.BaselineFilename']
            baseline = float(calc_baseline(baseline_filename)['baseline'].values[0])

            n_bins = 5
            high_density_charges = get_highest_density_region_charge(
                waveforms*VOLT_SCALING,
                TIME_SCALING,
                n_bins=n_bins,
                baseline=baseline*VOLT_SCALING)
            print(np.median(high_density_charges))
            print(np.median(high_density_charges) / (TIME_SCALING*n_bins) * 1e-8)

            popt, pcov = run_fit(charges, pmt_id, fw, run, data_key='LinearityMeasurement')
            popts.append(popt)
            pcovs.append(pcov)

        spe_peak_pos = np.array([popt[1] for popt in popts])
        print(f"Gaussian Fit Peak Positions: {spe_peak_pos}")
        spe_peak_pos_err = np.array([pcov[1, 1] for pcov in pcovs])

        fig, ax = plt.subplots()
        ax.plot(np.array(fw_settings, dtype=float), spe_peak_pos/E_CONST/1e7)
        ax.set_xlabel('Filter wheel strength')
        ax.set_ylabel('Mean charge / PE')
        fig.savefig(f'figs_boxes/charge_vs_strength_{run}_{data_key}_{pmt}.pdf')

        ax.set_xscale('log')
        ax.set_yscale('log')
        fig.savefig(f'figs_boxes/charge_vs_strength_{run}_{data_key}_{pmt}_log.pdf')

        ax_all.plot(np.array(fw_settings, dtype=float), spe_peak_pos/E_CONST/1e7, label=run)
        charges_list.append(spe_peak_pos/E_CONST/1e7)

        plot_linearity(fw_settings, spe_peak_pos, pmt_id, run, data_key)
        #plot_linearity(fw_settings, spe_peak_pos, pmt_id, run, data_key, aggregate_fig, aggregate_ax, cnt, max_cnt)

    ax_all.set_xlabel('Filter Wheel Strength')
    ax_all.set_ylabel('Mean Charge / PE')
    ax_all.set_title(pmt)
    ax_all.legend()
    fig_all.savefig(f'figs_boxes/pe_vs_strength_all_{pmt}.pdf')
    
    ax_all.set_yscale('log')
    ax_all.set_xscale('log')
    fig_all.savefig(f'figs_boxes/pe_vs_strength_all_{pmt}_log.pdf')

    return charges_list

def find_valid_files(pmt_id):
    ##default locataion for run files is: /home/scanbox/data/json/run/
    run_prefix = "/home/scanbox/data/json/run/"

    file_folder_list = []
    run_list = []

    ##calibration starts from run_00045
    calib_num_start = 45
    calib_num_end = 63
    run_files = glob(run_prefix + "*.json")
    for run in run_files:
        run_str = run.split("_")
        number = run_str[1]
        number = number.split(".")
        number = number[0]
        if int(number) < calib_num_start:
            continue
        if int(number) > calib_num_end:
            break
        list_of_deggs = load_run_json(run)
        for degg_file in list_of_deggs:
            degg_dict = load_degg_dict(degg_file)
            pmt_id_l = degg_dict['LowerPmt']['SerialNumber']
            pmt_id_u = degg_dict['UpperPmt']['SerialNumber']
            position = None
            if pmt_id == pmt_id_l:
                position = 'LowerPmt'
            if pmt_id == pmt_id_u:
                position = 'UpperPmt'
            if position == None:
                continue
            for key in degg_dict[position].keys():
                if "LinearityMeasurement" in key:
                    comment = degg_dict[position][key]['Comment']
                    if 'off' in comment or 'Off' in comment:
                        continue
                    if 'parallel' in comment:
                        continue
                    ##this measurement was bugged
                    if int(number) == 51 and key == 'LinearityMeasurement_00':
                        continue
                    if int(number) == 47 and pmt_id == 'SQ0328':
                        continue
                    file_folder = degg_dict[position][key]['Folder']
                    file_folder_list.append(file_folder)
                    run_list.append(int(number))

    return file_folder_list, run_list

def main():

    data_key = 'LinearityMeasurement'

    ###hard coding the lists
    box_map = {
        "SQ0426": {
            "45": "L-B-3-B",
            "46": "L-B-3-T",
            "47": "L-T-2-T",
            "48": "L-T-1-T",
            "50": "L-B-1-T",
            "51": "L-B-2-T",
            "52": "L-T-3-T",
            "53": "L-B-4-T",
            "55": "L-B-5-T",
            "56": "R-B-5-T",
            "57": "R-B-4-T",
            "58": "R-B-2-T",
            "59": "R-B-3-T",
            "60": "R-T-3-T",
            "61": "R-B-1-T",
            "62": "R-T-1-T",
            "63": "R-T-2-T"
        },
        "SQ0425": {
            "45": "L-B-3-T",
            "46": "L-B-3-B",
            "47": "L-T-2-B",
            "48": "L-T-1-B",
            "50": "L-B-1-B",
            "51": "L-B-2-B",
            "52": "L-T-3-B",
            "53": "L-B-4-B",
            "55": "L-B-5-B",
            "56": "R-B-5-B",
            "57": "R-B-4-B",
            "58": "R-B-2-B",
            "59": "R-B-3-B",
            "60": "R-T-3-B",
            "61": "R-B-1-B",
            "62": "R-T-1-B",
            "63": "R-T-2-B"
        },
        "SQ0328": {
            "45": "L-B-2-B",
            "46": "L-B-1-B",
            "47": "L-T-1-B",
            "48": "L-T-2-B",
            "50": "L-T-3-B",
            "52": "L-B-3-B",
            "53": "L-B-5-B",
            "55": "L-B-4-B",
            "56": "R-B-4-B",
            "57": "R-B-5-B",
            "58": "R-B-3-B",
            "59": "R-B-2-B",
            "60": "R-B-1-B",
            "61": "R-T-3-B",
            "62": "R-T-2-B",
            "63": "R-T-1-B"
        },
        "SQ0336": {
            "45": "L-B-2-T",
            "46": "L-B-1-T",
            "47": "L-T-1-T",
            "48": "L-T-2-T",
            "50": "L-T-3-T",
            "52": "L-B-3-T",
            "53": "L-B-5-T",
            "55": "L-B-4-T",
            "56": "R-B-4-T",
            "57": "R-B-5-T",
            "58": "R-B-3-T",
            "59": "R-B-2-T",
            "60": "R-B-1-T",
            "61": "R-T-3-T",
            "62": "R-T-2-T",
            "63": "R-T-1-T"
        }
    }



    logbook = DEggLogBook()

    aggregate_ax = []
    aggregate_fig = []
    aggregate_fig_0, aggregate_ax_0 = plt.subplots()
    aggregate_fig_1, aggregate_ax_1 = plt.subplots()
    aggregate_fig.append(aggregate_fig_0)
    aggregate_fig.append(aggregate_fig_1)
    aggregate_ax.append(aggregate_ax_0)
    aggregate_ax.append(aggregate_ax_1)

    pmt_list = []
    dir_list = []

    ##use sample calibration run: run_00045
    run_json = "/home/scanbox/data/json/run/run_00045.json"

    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        pmt_list.append(degg_dict['LowerPmt']['SerialNumber'])
        pmt_list.append(degg_dict['UpperPmt']['SerialNumber'])
        dir_list.append('upper')
        dir_list.append('lower')

    df = pd.DataFrame()
    fw_str = [0.001, 0.01, 0.05, 0.1, 0.5, 1.0]
    file_folder_lists = []
    i = 0
    for pmt in pmt_list:
        print(colored(pmt, 'yellow'))
        file_folder_list, run_list = find_valid_files(pmt)
        print(file_folder_list)
        print(run_list)
        #file_folder_lists.append((pmt, file_folder_list))
        charges_list = run_analysis(pmt, file_folder_list, run_list)

        #charges_list = np.array(charges_list)
        #charges_list = charges_list.flatten()
        
        run_index = 0
        for charges in charges_list:
            fw_index = 0
            for charge in charges:
                df_temp = pd.DataFrame(columns=['run', 'pmt', 'PE', 'fw_str', 'fibre'])
                df_temp['run'] = pd.Series(run_list[run_index])
                df_temp['pmt'] = pmt
                df_temp['PE'] = charge
                df_temp['fw_str'] = fw_str[fw_index]
                run = str(run_list[run_index])
                fibre = box_map[pmt][run]
                df_temp['fibre'] = fibre
                fw_index += 1
                print(df_temp)
                df = df.append(df_temp, ignore_index=True)
            run_index += 1
        '''
        full_fw_str = np.tile(fw_str, len(run_list))
        full_run_list = np.repeat(run_list, 6)
        full_pmt = np.repeat(pmt, 6 * len(run_list))
        full_dir_list = np.repeat(dir_list[i], 6)

        df_temp = pd.DataFrame()
        df_temp['pmt'] = full_pmt
        df_temp['run'] = full_run_list
        df_temp['fw_str'] = full_fw_str
        df_temp['PE'] = charges_list
        df_temp['Box'] = 
        df_temp['Dir'] = full_dir_list
        ##dir is reversed for run 45, SQ0425 and SQ0426
        

        df = df.append(df_temp, ignore_index=True)
        i += 1
        '''
    print(df)
    df.to_hdf('cached_fit.hdf5', 'charge')

    #from IPython import embed
    #embed()

    #print(file_folder_lists)
'''
    max_cnt = len(list_of_deggs) * 2 ##maximum number of PMTs
    cnt = 1
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        pmts = ['LowerPmt', 'UpperPmt']
        for pmt in pmts:
            if measurement_number == 'latest':
                eligible_keys = [key for key in degg_dict[pmt].keys()
                                 if key.startswith(data_key)]
                cts = [int(key.split('_')[1]) for key in eligible_keys]
                if len(cts) == 0:
                    print('No measurement found for '
                          f'{degg_dict[pmt]["SerialNumber"]} '
                          f'in DEgg {degg_dict["DEggSerialNumber"]}. '
                          'Skipping it!')
                    continue
                measurement_number = np.max(cts)
            suffix = f'_{measurement_number:02d}'
            data_key_to_use = data_key + suffix

            degg_dict = run_analysis(data_key_to_use, degg_dict,
                                     run_number, pmt, logbook, aggregate_fig, aggregate_ax, cnt, max_cnt)
            update_json(degg_file, degg_dict)
            cnt += 1
'''
if __name__ == '__main__':
    main()

