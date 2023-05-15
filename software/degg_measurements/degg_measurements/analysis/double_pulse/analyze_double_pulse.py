import numpy as np
import tables
import matplotlib.pyplot as plt
import pandas as pd
import click
from glob import glob
import os, sys
from scipy import signal
import time

from chiba_slackbot import send_message, send_warning, push_slow_mon

##################################################
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import read_data
from degg_measurements.utils import load_run_json
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.analysis import Analysis
from degg_measurements.analysis import RunHandler
from degg_measurements.analysis.analysis_utils import get_measurement_numbers
from degg_measurements.analysis import Result
##################################################
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')


def extract_info(filename, pmt_id):
    e_id, time, waveforms, ts, pc_t, datetime_timestamp, params = read_data(filename)
    baselines = []
    for wf in waveforms:
        baseline = np.mean(wf[:8])
        baselines.append(baseline)
    d = {
        'X': time,
        'Y': waveforms,
        'DEgg': params['DEggSerialNumber'],
        'Port': params['Port'],
        'Temp': params['degg_temp'],
        'PMT': pmt_id,
        'Baseline': baselines
    }
    return d

##check if pulses are separated in time
def process_pulses(info, run_number, data_key, pdf=None, detailed_pdf=False, num_key=None,
                   icrc=False, every_wf=True):
    run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key}')
    wf = info['Y']
    n_wfs = len(wf)
    wf_ave = np.sum(wf, axis=0) / n_wfs
    bl_ave = np.sum(info['Baseline'], axis=0) / n_wfs
    degg = info['DEgg']
    pmt = info['PMT']
    peaks = info['Peaks']
    peaks_ind = info['PeaksInd']

    if icrc == True and degg == 'DEgg2020-1-006' and pmt.lower() == 'sq0414':
        print(f"Creating ICRC plot: {degg}, {pmt}")
        volt_scaling = 0.075e-3
        ##we collected 5001 wfs, only want to take 5000
        wf_ave_icrc = np.sum(wf[1:-1], axis=0) / (len(wf)-1)
        fig_icrc, ax_icrc = plt.subplots()
        ax_icrc.plot(info['X'][0][:70] * 4.2,
                     (wf_ave_icrc[:70] - bl_ave) * volt_scaling * 1e3,
                     label=f'N={len(wf)-1}')
        ax_icrc.plot(peaks_ind*4.2, (wf_ave[peaks_ind]-bl_ave) * volt_scaling * 1e3,
                     marker='x',
                     linewidth=0, color='goldenrod',
                     label=r'$\Delta$T~'+f'{np.diff(peaks_ind)[0]*4.2} ns')

        ax_icrc.legend()
        ax_icrc.set_xlabel('Time / ns')
        ax_icrc.set_ylabel('Response / mV')
        save_icrc = os.path.join(run_plot_dir, f'icrc_{degg}_{pmt}.pdf')
        fig_icrc.savefig(save_icrc)
        plt.close(fig_icrc)

        import matplotlib
        font = {'family' : 'normal',
        'weight' : 'bold',
        'size'   : 22}

        matplotlib.rc('font', **font)

    fig00, ax00 = plt.subplots()
    for i in range(10):
        ax00.plot(info['X'][0][:70] * 4.2,
                  wf[i][:70]-bl_ave)
        ax00.set_xlabel('Time [ns]')
        ax00.set_ylabel('ADC')
        #ax00.set_title(f'25 Waveforms - {degg}: {pmt}')
        save = os.path.join(run_plot_dir, f'wf_lineup_{i}_{degg}_{pmt}.pdf')
        fig00.savefig(save)
        plt.close(fig00)

    fig0, ax0 = plt.subplots()
    for i in range(25):
        ax0.plot(info['X'][0][:180], wf[i][:180])
    ax0.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax0.set_ylabel('ADC')
    ax0.set_title(f'25 Waveforms - {degg}: {pmt} ({num_key})')
    save = os.path.join(run_plot_dir, f'wf_lineup_{degg}_{pmt}.pdf')
    fig0.savefig(save)
    if pdf != None and detailed_pdf == True:
        pdf.attach_note(f'wf_lineup_{degg}_{pmt}')
        pdf.savefig(fig0)
    plt.close(fig0)

    fig1, ax1 = plt.subplots()
    ax1.plot(info['X'][0][:100], wf_ave[:100], label=f'N={n_wfs}')
    ax1.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax1.set_ylabel('ADC')
    ax1.set_title(f'{degg}: {pmt}')
    ax1.legend()
    save = os.path.join(run_plot_dir, f'ave_wf_{degg}_{pmt}.pdf')
    fig1.savefig(save)
    plt.close(fig1)

    ##baseline subtracted
    fig1b, ax1b = plt.subplots()
    ax1b.plot(info['X'][0][:100], wf_ave[:100]-bl_ave, label=f'N={n_wfs}')
    ax1b.plot(peaks_ind, wf_ave[peaks_ind]-bl_ave, marker='x',
              linewidth=0, color='goldenrod')
    #ax1b.hlines(*info['Widths'][1:], color='firebrick')
    ax1b.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax1b.set_ylabel('ADC')
    ax1b.set_title(f'{degg}: {pmt}')
    ax1b.legend()
    save = os.path.join(run_plot_dir, f'ave_wf_bl_sub_{degg}_{pmt}.pdf')
    fig1b.savefig(save)
    plt.close(fig1b)

    ##baseline subtracted, timing corrected
    fig1c, ax1c = plt.subplots()
    ax1c.plot(info['X'][0][:100]*4.2, wf_ave[:100]-bl_ave, label=f'N={n_wfs}')
    if len(peaks_ind) >= 2:
        ax1c.plot(peaks_ind*4.2, wf_ave[peaks_ind]-bl_ave, marker='x',
              linewidth=0, color='goldenrod',
              label=r'$\Delta$T~'+f'{np.diff(peaks_ind)[0]*4.2} ns')
    else:
        ax1c.plot(peaks_ind*4.2, wf_ave[peaks_ind]-bl_ave, marker='x',
              linewidth=0, color='goldenrod',
              label='No double peak')
    #ax1b.hlines(*info['Widths'][1:], color='firebrick')
    ax1c.set_xlabel('Mainboard Time [ns]')
    ax1c.set_ylabel('ADC')
    ax1c.set_title(f'{degg}: {pmt} ({num_key})')
    ax1c.legend()
    save = os.path.join(run_plot_dir, f'ave_wf_bl_sub_time_{degg}_{pmt}.pdf')
    if pdf != None:
        pdf.attach_note(f'Average WF, BL Sub {degg}:{pmt}')
        pdf.savefig(fig1c)
    fig1c.savefig(save)
    plt.close(fig1c)

    fig2, ax2 = plt.subplots()
    ax2.plot(info['X'][0], wf_ave, label=f'N={n_wfs}')
    ax2.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax2.set_ylabel('ADC')
    ax2.set_title(f'{degg}: {pmt}')
    ax2.legend()
    save = os.path.join(run_plot_dir, f'full_ave_wf_{degg}_{pmt}.pdf')
    fig2.savefig(save)
    plt.close(fig2)

    plot_y_vals = 0

    ##also take results from the wf by wf case if enabled
    ###this is the STANDARD configuration from now on!
    if every_wf == True:
        volt_scaling = 0.075e-3
        peaks_l = info['PeaksList']
        peaks_ind_l = info['PeaksIndList']
        double_peaks_ind = info['DoublePeaksInd']
        print(double_peaks_ind)
        int_dp_ind = [int(np.round(double_peaks_ind[0])), int(np.round(double_peaks_ind[1]))]
        if len(peaks_l) == 0:
            warn_msg = f'No double peak structure found for {degg} - {pmt} \n'
            warn_msg = warn_msg + 'Check if problems have been observed in linearity/TTS analyses \n'
            warn_msg = warn_msg + 'If so, this indicates a likely problem with the fibre.'
            warn_msg = warn_msg + 'Log this issue and inform an expert.'
            send_warning(warn_msg)
            print(f"No double peaks for {degg} - {pmt}")
            return

        ##get the list of valley Y values
        valley_y = info['ValleyList']
        peak_to_valley_l = []
        min_ptv = 1000
        max_ptv = 0
        ##calculate peak to valley for both peaks
        for _peak_y, _valley_y in zip(peaks_l, valley_y):
            these_ptv = np.zeros(2)
            for pnum, _py in enumerate(_peak_y):
                if _valley_y[0] <= 0:
                    these_ptv[pnum] = -1
                    continue
                peak_to_valley = _py / _valley_y[0]
                if peak_to_valley < min_ptv:
                    min_ptv = peak_to_valley
                if peak_to_valley > max_ptv:
                    max_ptv = peak_to_valley

                these_ptv[pnum] = peak_to_valley
            peak_to_valley_l.append(these_ptv)

        peak_to_valley_l = np.array(peak_to_valley_l)
        ##plot the distribution of the 1st and 2nd peak to valleys
        #binning = np.linspace(min_ptv, max_ptv, 40)
        binning = np.linspace(1, 5, 50)
        peak1 = peak_to_valley_l[:,0]
        peak2 = peak_to_valley_l[:,1]
        mask1 = (peak1 >= 0.5) & (peak1 <= 5)
        mask2 = (peak2 >= 0.5) & (peak2 <= 5)

        m1_ptv = np.mean(peak1[mask1])
        m2_ptv = np.mean(peak2[mask2])

        fig_ptv1, ax_ptv1 = plt.subplots()
        ax_ptv1.hist(peak_to_valley_l[:,0], binning, histtype='step', color='royalblue', label=f'Peak1:{m1_ptv:.2f}')
        ax_ptv1.hist(peak_to_valley_l[:,1], binning, histtype='step', color='goldenrod', label=f'Peak2:{m2_ptv:.2f}')
        ax_ptv1.set_xlabel('Peak to Valley Ratio')
        ax_ptv1.set_ylabel('Entries')
        ax_ptv1.legend()
        ax_ptv1.set_label(f'{degg} - {pmt}')
        fig_ptv1.savefig(os.path.join(run_plot_dir, f'peak_to_valley_hist_{degg}_{pmt}.pdf'))
        plt.close(fig_ptv1)

        double_x = info['X']
        double_y = info['Y']
        double_bl = info['Baseline']
        n_2wfs = len(double_y)
        wf_ave = np.sum(double_y, axis=0) / n_2wfs
        bl_ave = np.sum(double_bl, axis=0) / n_2wfs
        fig3, ax3 = plt.subplots()
        ax3.plot(double_x[0][:70]*4.2,
                 (wf_ave-bl_ave)[:70], color='royalblue', label=f'Average Waveform')
        ax3.plot(np.array(double_peaks_ind)*4.2, (wf_ave-bl_ave)[int_dp_ind],
                 marker='x',linewidth=0, color='goldenrod',
                 label='Average Peak Position')
        ax3.set_title(r'<$\Delta$T>~'+f'{(np.diff(double_peaks_ind)[0]*4.2):0.2f} ns')
        ax3.legend(title=f'N={n_2wfs}')
        ax3.set_xlabel('Time / ns')
        ax3.set_ylabel('Response / ADC')
        save = os.path.join(run_plot_dir,
            f'ave_wf_bl_sub_every_wf_{degg}_{pmt}.pdf')
        fig3.savefig(save)
        plt.close(fig3)
        plot_y_vals = (wf_ave - bl_ave)[:70] * volt_scaling * 1e3

        push_slow_mon(save, f'{degg}_{pmt}_double_pulse')

        sm1_ptv = np.std(peak_to_valley_l[:,0][mask1])
        sm2_ptv = np.std(peak_to_valley_l[:,1][mask2])
        return plot_y_vals, double_peaks_ind, [m1_ptv, sm1_ptv], [m2_ptv, sm2_ptv]


    return plot_y_vals

def find_valley(p_i, wz):
    ##only look between the two peaks
    wf = wz[p_i[0]:p_i[1]]
    #print(f'Searching size: {len(wf)}')

    ##need to find min so invert wf
    n_wf = -1 * wf
    #print(n_wf)

    m_i, _ = signal.find_peaks(n_wf)
    #print(m_i)
    if len(m_i) == 0:
        return [0]

    ##return the value of the waveform at the valley
    else:
        return wf[m_i]

def double_pulse_ana(info, threshold, every_wf=False):
    wf = info['Y']
    n_wfs = len(wf)
    wf_ave = np.sum(wf, axis=0) / n_wfs
    bl_ave = np.sum(info['Baseline'], axis=0) / n_wfs
    wf_zeroed = wf_ave - bl_ave

    ##set some threshold for the peak finder
    mask = (wf_zeroed >= threshold)
    peaks_to_find = wf_zeroed[mask]

    #peaks_ind, _  = signal.find_peaks(peaks_to_find)
    peaks_ind, _  = signal.find_peaks(wf_zeroed, height=threshold)

    peaks = wf_zeroed[peaks_ind]
    info['Peaks'] = peaks
    info['PeaksInd'] = peaks_ind

    peaks_width = signal.peak_widths(wf_zeroed, peaks_ind, rel_height=0.5)
    info['Widths'] = peaks_width

    ##also do wf by wf
    double_peaks = 0
    single_peaks = 0
    peak1_ind = 0
    peak2_ind = 0
    if every_wf == True:
        peaks_list = []
        peaks_ind_list = []
        valley_list = []
        valid_double = [False] * len(wf)
        for i, w in enumerate(wf):
            wz = w - bl_ave
            p_i, _ = signal.find_peaks(wz, height=threshold)
            p = wz[p_i]

            if len(p) == 2:
                peaks_list.append(p)
                peaks_ind_list.append(p_i)
                double_peaks += 1
                valid_double[i] = True
                peak1_ind += p_i[0]
                peak2_ind += p_i[1]
                min_y = find_valley(p_i, wz)
                valley_list.append(min_y)

            if len(p) == 1:
                single_peaks += 1

        info['X'] = info['X'][valid_double]
        info['Y'] = info['Y'][valid_double]

        info['PeaksList'] = peaks_list
        info['PeaksIndList'] = peaks_ind_list
        info['DoublePeaksInd'] = [peak1_ind/double_peaks, peak2_ind/double_peaks]
        #info['Peaks'] = np.array(info['Peaks'])[valid_double]
        #info['PeaksInd'] = info['PeaksInd'][valid_double]
        #info['Widths'] = info['Widths'][valid_double]
        info['Baseline'] = np.array(info['Baseline'])[valid_double]
        info['ValleyList'] = valley_list

    print(f'Single: {single_peaks}')
    print(f'Double: {double_peaks}')

    return info

def run_analysis(data_key, degg_dict, logbook, pmt, run_number, info_list,
                 threshold, this_filter, this_burstFreq,
                 pdf, detailed_pdf, num_key, icrc, ewf, remote=False):

    pmt_id = degg_dict[pmt]['SerialNumber']
    degg_id = degg_dict['DEggSerialNumber']
    if remote == True:
        folder = degg_dict[pmt][data_key]['RemoteFolder']
    else:
        folder = degg_dict[pmt][data_key]['Folder']
    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
    if len(files) == 0:
        raise FileNotFoundError(f'No files found for {pmt_id} at {folder}')
    print('-'*20)
    print(f"PMT ID: {pmt_id}")

    ptv1_list = []
    ptv2_list = []

    for j, filename in enumerate(files):
        info = extract_info(filename, pmt_id)
        info = double_pulse_ana(info, threshold, every_wf=ewf)
        plot_y_vals, double_peaks_ind, ptv1, ptv2 = process_pulses(info, run_number, data_key,
                                                        pdf, detailed_pdf, num_key, icrc, ewf)
        info_list.append(info)
        ptv1_list.append(ptv1)
        ptv2_list.append(ptv2)

        if ewf == True and logbook != None:
            result = Result(pmt_id,
                            logbook=logbook,
                            run_number=run_number,
                            remote_path=REMOTE_DATA_DIR)

            avg_peak_sep = np.diff(double_peaks_ind)[0] * \
                CALIBRATION_FACTORS.fpga_clock_to_s * 1e9
            aveT = info['X'][0][:70] * \
                CALIBRATION_FACTORS.fpga_clock_to_s * 1e9

            if logbook != None:
                json_filenames = result.to_json(
                    meas_group='sensitivity',
                    raw_files=filename,
                    folder_name=DB_JSON_PATH,
                    filename_add=data_key,
                    average_peak_separation=avg_peak_sep,
                    average_peak_to_valley1=ptv1,
                    average_peak_to_valley2=ptv2,
                    ndFilter=this_filter,
                    burstFrequency=this_burstFreq,
                    aveT=aveT,
                    aveV=plot_y_vals,
                    temperature=float(info['Temp'])
                )

                run_handler = RunHandler(filenames=json_filenames)
                run_handler.submit_based_on_meas_class()


        diff = np.diff(info['PeaksInd']) * 4.2
        if len(diff) == 1:
            print('Found exactly 2 peaks')
            if diff[0] > 16.7 and diff[0] < 21.5:
                return 1, ptv1_list, ptv2_list
            else:
                print(f'But time was wrong: {diff[0]}')
                return 0, [[0, 0]], [[0, 0]]
        else:
            print(f'Number of peaks was found to be: {len(diff)+1}!')
            return 0, [[0, 0]], [[0, 0]]

def summary_wfs(info_list, run_number, data_key):
    run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key}')
    if not os.path.exists(run_plot_dir):
        os.mkdir(run_plot_dir)
        print(f"Created directory: {run_plot_dir}")

    n_pmts = len(info_list)
    fig_ave, ax_ave = plt.subplots()
    fig_ave_full, ax_ave_full = plt.subplots()

    pulses_found = 0
    peak_bin_diff_l = []

    for info in info_list:
        wf = info['Y']
        n_wfs = len(wf)
        wf_ave = np.sum(wf, axis=0) / n_wfs
        bl_ave = np.sum(info['Baseline'], axis=0) / n_wfs
        degg = info['DEgg']
        pmt = info['PMT']
        peaks_ind = info['PeaksInd']
        if len(peaks_ind) >= 2:
            peak_bin_diff = np.diff(peaks_ind)
            pulses_found += 1
            peak_bin_diff_l.append(peak_bin_diff[0])

        ax_ave.plot(info['X'][0][:75], wf_ave[:75]-bl_ave, label=f'{pmt}')
        ax_ave_full.plot(info['X'][0], wf_ave-bl_ave, label=f'{pmt}')

    diff_bins = np.arange(8)
    fig_diff, ax_diff = plt.subplots()
    ax_diff.hist(peak_bin_diff_l, bins=diff_bins,
                 label=f'{len(peak_bin_diff_l)}/{len(info_list)}')
    ax_diff.set_xlabel('# Bins Between Double Pulse')
    ax_diff.set_ylabel('PMTs')
    ax_diff.legend(title='PMTs w/ double pulse')
    save = os.path.join(run_plot_dir, f'double_pulse_diff_hist.pdf')
    fig_diff.savefig(save)
    plt.close(fig_diff)

    ax_ave.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax_ave.set_ylabel('ADC')
    ax_ave.set_title(f'N PMTs: {n_pmts}')
    #ax_ave.legend()
    save = os.path.join(run_plot_dir, f'ave_double_pulse_wf.pdf')
    fig_ave.savefig(save)
    plt.close(fig_ave)

    ax_ave_full.set_xlabel('Mainboard Bins (~4 ns / bin)')
    ax_ave_full.set_ylabel('ADC')
    ax_ave_full.set_title(f'N PMTs: {n_pmts}')
    #ax_ave_full.legend()
    save = os.path.join(run_plot_dir, f'ave_double_pulse_wf_full.pdf')
    fig_ave_full.savefig(save)
    plt.close(fig_ave_full)

    ##plot difference between double pulse in time

def analysis_wrapper(run_json, pdf=None, detailed_pdf=False, measurement_number='latest',
                     icrc=False, remote=False, offline=False):

    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f"Created directory: {PLOT_DIR}")

    remote = bool(remote)
    if remote == True:
        print('Running in remote mode!')
    icrc = bool(icrc)
    ##legacy flag
    ewf = True

    if not os.path.isfile(run_json):
        raise IOError(f'Could not find list of'
                     ' measurements: {run_json}!')

    # if measurement_number != 'latest':
    #     nums = measurement_number.split(',')
    #     if len(nums) == 1:
    #         measurement_number = int(measurement_number)
    #     else:
    #         measurement_number = nums

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)

    #data_key = 'BurstMeasurement' #legacy key name
    data_key = 'DoublePulse'
    mode = 'double'
    ##filter baseline for peak finding
    info_list = []
    analysis_list = []

    ##instantiate the logbook
    if not offline:
        logbook = DEggLogBook()
    else:
        logbook = None

    ptv1_list = []
    ptv2_list = []
    sptv1_list = []
    sptv2_list = []

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
            # if type(measurement_number) == np.int64 or type(measurement_number) == int:
            #     measurement_number = [measurement_number]
            print(f'Measurement Number: {measurement_numbers}')
            #loop over all configured measurements
            verbose = True
            for num in measurement_numbers:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                if verbose == True:
                    print(data_key_to_use)
                    verbose = False
                try:
                    this_dict = degg_dict[pmt][data_key_to_use]
                    this_filter = this_dict['Filter']
                    this_burstFreq = this_dict['BurstFrequency']
                except KeyError:
                    print(f'KeyError: {data_key_to_use} - {degg_dict["DEggSerialNumber"]}, {pmt}')
                    print(degg_dict[pmt])
                    continue
                if float(this_filter) < 0.2 and float(this_filter) > 0.06:
                    threshold = 800 #ADC
                elif float(this_filter) < 0.06:
                    #threshold = 100
                    ##tuned for new laser alignment
                    threshold = 550
                else:
                    threshold = 1000
                print(f'Running with Peak Finder Threshold = {threshold}')

                run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key_to_use}')
                if not os.path.isdir(run_plot_dir):
                    os.mkdir(run_plot_dir)
                if audit_ignore_list(degg_file, degg_dict, data_key_to_use) == True:
                    continue
                verdict, ptv1, ptv2 = run_analysis(data_key=data_key_to_use,
                         degg_dict=degg_dict, logbook=logbook,
                         pmt=pmt, run_number=run_number, info_list=info_list,
                         threshold=threshold, this_filter=this_filter,
                         this_burstFreq=this_burstFreq, pdf=pdf, detailed_pdf=detailed_pdf,
                         num_key=data_key_to_use, icrc=icrc, ewf=ewf, remote=remote)

                ptv1_list.append(ptv1[0][0])
                ptv2_list.append(ptv2[0][0])
                sptv1_list.append(ptv1[0][1])
                sptv2_list.append(ptv2[0][1])

                ##if PMT passed, increment by  1
                if pmt == 'LowerPmt':
                    l_verdict += verdict
                if pmt == 'UpperPmt':
                    u_verdict += verdict

        #after looping PMTs and all measurements, create summary
        analysis = Analysis(f"DoublePulse (N={len(measurement_numbers)})",
                            degg_dict['DEggSerialNumber'], u_verdict, l_verdict,
                            len(measurement_numbers))
        analysis_list.append(analysis)


    fig1, ax1 = plt.subplots()
    ax1.errorbar(np.arange(len(ptv1_list)), ptv1_list, yerr=sptv1_list, marker='o', linewidth=0, elinewidth=3, color='royalblue', label='1st Peak')
    ax1.errorbar(np.arange(len(ptv2_list)), ptv2_list, yerr=sptv2_list, marker='o', linewidth=0, elinewidth=3,
                 color='goldenrod', label='2nd Peak', alpha=0.6)
    ax1.set_xlabel('PMT')
    ax1.set_ylabel('Peak to Valley Ratio')
    ax1.legend()
    save = os.path.join(run_plot_dir,'peak_to_valley_all.pdf')
    fig1.savefig(save)
    plt.close(fig1)

    push_slow_mon(save, f'double_pulse_peak_to_valley_summary')

    fig2, ax2 = plt.subplots()
    ax2.plot(np.arange(len(ptv1_list)), sptv1_list, marker='o', linewidth=0, color='royalblue', label='1st Peak')
    ax2.plot(np.arange(len(ptv2_list)), sptv2_list, marker='o', linewidth=0,
                 color='goldenrod', label='2nd Peak')
    ax2.set_xlabel('PMT')
    ax2.set_ylabel('Peak to Valley Ratio Std')
    ax2.legend()
    fig2.savefig(os.path.join(run_plot_dir,'peak_to_valley_widths_all.pdf'))
    plt.close(fig2)

    summary_wfs(info_list, run_number, data_key_to_use)
    total_ave_peak_height = []
    for info in info_list:
        ave_peak_height = np.sum(info['Peaks'])/2
        total_ave_peak_height.append(ave_peak_height)

    print("Done")
    msg = '--- double_pulse analysis is finished --- \n'
    msg = msg + f'Shifters should examine the new plots in {run_plot_dir}'

    return analysis_list

##input file is pair of run number & measurement number
@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--pdf', default=None)
@click.option('--detailed_pdf', default=False)
@click.option('--measurement_number', '-n', default='latest')
@click.option('--icrc', is_flag=True)
@click.option('--remote', is_flag=True)
@click.option('--offline', is_flag=True)
def main(run_json, pdf, detailed_pdf, measurement_number, icrc, remote, offline):
    analysis_wrapper(run_json, pdf, detailed_pdf, measurement_number, icrc,
                     remote, offline)

if __name__ == "__main__":
    main()

##end
