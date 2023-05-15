import tables
import numpy as np
from degg_measurements.utils import read_data
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec

##################################################
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils.analysis import Analysis
from degg_measurements.analysis import Result
from degg_measurements.analysis.gain.analyze_gain import calc_avg_spe_peak_height
from degg_measurements.analysis.gain.analyze_gain import run_fit as fit_charge_hist
from degg_measurements.utils import CALIBRATION_FACTORS
##################################################
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')

def intraDEggAnalysis(df, num):
    if len(num) == 3:
        ##special run where gain was varied
        if int(num[2]) == 6:
            PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')
    deggs = df.DEgg.unique()
    for i, degg in enumerate(deggs):
        print(i, degg)
        _df = df[df.DEgg == degg]
        tbinning = np.linspace(0, np.max(_df.mfhTime.values), 1000)
        width = (tbinning[1] - tbinning[0]) / 1e9
        df_b = _df[_df.Channel == 0]
        df_t = _df[_df.Channel == 1]
        t_b = df_b.mfhTime.values
        q_b = df_b.Charge.values
        t_t = df_t.mfhTime.values
        q_t = df_t.Charge.values
        pmt_b = df_b.PMT.values[0]
        pmt_t = df_t.PMT.values[0]

        blockNums_b = df_b.blockNum.unique()
        blockNums_t = df_t.blockNum.unique()
        not_matched = False
        total_blocks = 0
        if blockNums_b.all() != blockNums_t.all():
            print("Blocks not equal!")
            print(blockNums_b, blockNums_t)
            not_matched == True

        if not_matched == True:
            ##try to match blocks and make them the same length
            b_max = np.max(blockNums_b)
            t_max = np.max(blockNums_t)
            if b_max >= t_max:
                total_blocks = b_max
            if b_max < t_max:
                total_blocks = t_max
        else:
            total_blocks = np.max(blockNums_b)

        rate_list_b   = [0] * total_blocks
        charge_list_b = [0] * total_blocks
        rate_list_t   = [0] * total_blocks
        charge_list_t = [0] * total_blocks
        for j, block in enumerate(range(total_blocks)):
            df_n_b = df_b[df_b.blockNum == block]
            df_n_t = df_t[df_t.blockNum == block]
            charge_list_b[j] = np.sum(df_n_b.Charge.values)
            charge_list_t[j] = np.sum(df_n_t.Charge.values)
            ##correct for deadtime of 500 ns
            if len(df_n_b.index) <= 1:
                rate_list_b[j] = 0
            else:
                total_time = (np.max(df_n_b.mfhTime.values) - np.min(df_n_b.mfhTime.values)) - (len(df_n_b.index) * 500)
                rate = len(df_n_b.index) / total_time
                rate = rate / 1e-9 ##convert into Hz
                rate_list_b[j] = rate

            if len(df_n_t.index) <= 1:
                rate_list_t[j] = 0
            else:
                total_time = (np.max(df_n_t.mfhTime.values) - np.min(df_n_t.mfhTime.values)) - (len(df_n_t.index) * 500)
                rate = len(df_n_t.index) / total_time
                rate = rate / 1e-9 ##convert into Hz
                rate_list_t[j] = rate

        figrb, axrb = plt.subplots()
        axrb.plot(np.arange(len(rate_list_b)), rate_list_b, 'o', linewidth=0, color='royalblue', alpha=0.5, label=f'{pmt_b} (0)')
        axrb.plot(np.arange(len(rate_list_t)), rate_list_t, 'o', linewidth=0, color='goldenrod', alpha=0.5, label=f'{pmt_t} (1)')
        axrb.set_xlabel('Charge Block')
        axrb.set_ylabel('Dark Rate [Hz]')
        axrb.grid(True)
        axrb.legend()
        figrb.tight_layout()
        figrb.savefig(os.path.join(PLOT_DIR, f'{degg}_block_rate_{num}.png'), dpi=300)
        axrb.set_yscale('log')
        figrb.savefig(os.path.join(PLOT_DIR, f'{degg}_block_rate_log_{num}.png'), dpi=300)

        figqr, axqr = plt.subplots()
        axqr.plot(rate_list_b, charge_list_b, 'o', linewidth=0, color='royalblue', alpha=0.5, label=f'{pmt_b} (0)')
        axqr.plot(rate_list_t, charge_list_t, 'o', linewidth=0, color='goldenrod', alpha=0.5, label=f'{pmt_t} (1)')
        axqr.set_xlabel('Dark Rate [Hz]')
        axqr.set_ylabel('Total Charge per block')
        axqr.legend()
        figqr.tight_layout()
        figqr.savefig(os.path.join(PLOT_DIR, f'{degg}_total_charge_rate_{num}.png'), dpi=300)
        axqr.set_xscale('log')
        figqr.savefig(os.path.join(PLOT_DIR, f'{degg}_total_charge_rate_log_{num}.png'), dpi=300)

        del _df
        del df_b
        del df_t

        fig1, ax1 = plt.subplots()
        ax1.plot(t_b[:1000], [0]*len(t_b[:1000]), 'o', linewidth=0, label=pmt_b, color='royalblue')
        ax1.plot(t_t[:1000], [1]*len(t_t[:1000]), 'o', linewidth=0, label=pmt_t, color='goldenrod')
        ax1.legend()
        ax1.set_xlabel('Trigger Time [ns]')
        ax1.set_ylabel('PMT Channel')
        fig1.savefig(os.path.join(PLOT_DIR, f'{degg}_trigger_times_{num}.png'), dpi=300)
        plt.close(fig1)

        ##calculate some rates
        ##since we care about correlation, start from shared point (0)
        t_hist_b, edges = np.histogram(t_b, bins=tbinning)
        t_hist_t, edges = np.histogram(t_t, bins=tbinning)
        ##correct for deadtime of 500 ns
        total_time_b = width - (t_hist_b * 500e-9)
        total_time_t = width - (t_hist_t * 500e-9)
        rate_b = t_hist_b / total_time_b
        rate_t = t_hist_t / total_time_t
        fig1r, ax1r = plt.subplots()
        ax1r.plot(np.arange(len(t_hist_b)), rate_b, 'o', linewidth=0, label=f'{pmt_b} (0)', color='royalblue')
        ax1r.plot(np.arange(len(t_hist_t)), rate_t, 'o', linewidth=0, label=f'{pmt_t} (1)', color='goldenrod')
        ax1r.legend()
        ax1r.set_ylabel(f'Trigger Rate [Hz]')
        ax1r.set_xlabel(f'Integration Bin ({width:.2f} [s])')
        fig1r.savefig(os.path.join(PLOT_DIR, f'{degg}_rates_{num}.png'), dpi=300)
        ax1r.set_xlim(0, 99)
        fig1r.savefig(os.path.join(PLOT_DIR, f'{degg}_rates_zoom_{num}.png'), dpi=300)
        plt.close(fig1r)

def separateAnalysis(df, num):
    if len(num) == 3:
        ##special run where gain was varied
        if int(num[2]) == 6:
            PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')

    pmts = df.PMT.unique()
    fig1, ax1 = plt.subplots()
    fig1z, ax1z = plt.subplots()
    fig1t, ax1t = plt.subplots()
    fig1r, ax1r = plt.subplots()

    figdrtt, axdrtt = plt.subplots()
    figdrttd, axdrttd = plt.subplots()

    tbinning = np.linspace(0, np.max(df.mfhTime.values), 10000)
    width = (tbinning[1] - tbinning[0]) / 1e9
    binning = np.logspace(2, 7, 200)
    total_max = 0
    #binning=200
    for i, pmt in enumerate(pmts):
        print(i, pmt)
        _df = df[df.PMT == pmt]
        mfh_t = _df.mfhTime.values
        charge = _df.Charge.values
        blockNums = _df.blockNum.unique()
        small_qbinning = np.linspace(-2, 5, 700)
        figqb, axqb = plt.subplots()
        rate_list = [0] * len(blockNums)
        charge_list = [0] * len(blockNums)
        block_times = [0] * len(blockNums)
        plotting_times = [0] * len(blockNums)
        for j, blockNum in enumerate(blockNums):
            _df_n = _df[_df.blockNum == blockNum]
            if j <= 4 or j > (len(blockNums) - 4):
                axqb.hist(_df_n.Charge.values, bins=small_qbinning, histtype='step')
            charge_list[j] = np.sum(_df_n.Charge.values)
            plotting_times[j] = ((np.max(_df_n.mfhTime.values) - np.min(_df_n.mfhTime.values))/2 + np.min(_df_n.mfhTime.values)) * 1e-9
            block_times[j] = (np.max(_df_n.mfhTime.values))*1e-9 - plotting_times[j]
            ##correct for deadtime of 500 ns
            if len(_df_n.index) <= 1:
                rate_list[j] = 0
                continue
            total_time = (np.max(_df_n.mfhTime.values) - np.min(_df_n.mfhTime.values)) - (len(_df_n.index) * 500)
            rate = len(_df_n.index) / total_time
            rate = rate / 1e-9 ##convert into Hz
            #print(f'{pmt} {j}: R = {len(_df_n.index)} / {total_time} * 5e-9 = {rate}')
            rate_list[j] = rate

        ##I know SQ0558 has a few big and frequent spikes
        if pmt == 'SQ0558':
            figdrt, axdrt = plt.subplots()
            axdrt.errorbar(plotting_times, rate_list, xerr=block_times, marker='o', linewidth=0, elinewidth=4, color='royalblue')
            axdrt.set_xlabel('Trigger Time [s]')
            axdrt.set_ylabel('Dark Rate [Hz]')
            figdrt.savefig(os.path.join(PLOT_DIR, f'{pmt}_rate_time_{num}.png'), dpi=300)
            axdrt.set_xlim(plotting_times[0], plotting_times[50])
            figdrt.savefig(os.path.join(PLOT_DIR, f'{pmt}_rate_time_zoom_{num}.png'), dpi=300)
            axdrt.set_xlim(plotting_times[16], plotting_times[26])
            figdrt.savefig(os.path.join(PLOT_DIR, f'{pmt}_rate_time_peak_zoom_{num}.png'), dpi=300)
        del _df

        axdrtt.plot(plotting_times, rate_list, marker='o', markersize=1.7, linewidth=0)
        axdrttd.plot(plotting_times[1:], np.diff(rate_list), marker='o', markersize=1.7, linewidth=0)
        if np.max(rate_list) > total_max:
            total_max = np.max(rate_list)

        axqb.set_xlabel('Waveform Charge [pC]')
        axqb.set_ylabel('Entries')
        #axqb.set_yscale('log')
        figqb.savefig(os.path.join(PLOT_DIR, f'{pmt}_block_charge_zoom_{num}.png'), dpi=300)
        plt.close(figqb)

        figrb, axrb = plt.subplots()
        axrb.plot(np.arange(len(rate_list)), rate_list, 'o', linewidth=0, color='royalblue')
        axrb.set_xlabel('Charge Block')
        axrb.set_ylabel('Dark Rate [Hz]')
        axrb.grid(True)
        figrb.savefig(os.path.join(PLOT_DIR, f'{pmt}_block_rate_{num}.png'), dpi=300)

        figqr, axqr = plt.subplots()
        axqr.plot(rate_list, charge_list, 'o', linewidth=0)
        axqr.set_xlabel('Dark Rate [Hz]')
        axqr.set_ylabel('Total Charge per block')
        figqr.savefig(os.path.join(PLOT_DIR, f'{pmt}_total_charge_rate_{num}.png'), dpi=300)
        axqr.set_xscale('log')
        figqr.savefig(os.path.join(PLOT_DIR, f'{pmt}_total_charge_rate_log_{num}.png'), dpi=300)

        ax1.plot(mfh_t, [i]*len(mfh_t), 'o', linewidth=0)
        ax1z.plot(mfh_t, [i]*len(mfh_t), 'o', linewidth=0)

        fig2, ax2 = plt.subplots()
        ax2.hist(np.diff(mfh_t), bins=binning, histtype='step', color='royalblue')
        ax2.set_ylabel('Entries')
        ax2.set_xlabel('Time Between Triggers [ns]')
        ax2.set_xscale('log')
        fig2.savefig(os.path.join(PLOT_DIR, f'{pmt}_dt_{num}.pdf'))
        ax2.set_yscale('log')
        fig2.savefig(os.path.join(PLOT_DIR, f'{pmt}_dt_log_{num}.pdf'))
        plt.close(fig2)

        ##calculate some rates
        ##since we care about correlation, start from shared point (0)
        t_hist, edges = np.histogram(mfh_t, bins=tbinning)
        ##correct for deadtime of 500 ns
        total_time = width - (t_hist * 500e-9)
        rate = t_hist / total_time
        ax1t.plot(np.arange(len(t_hist)), t_hist, 'o', linewidth=0)
        ax1r.plot(np.arange(len(t_hist)), rate, 'o', linewidth=0)

        qbinning = np.linspace(np.min(charge), np.max(charge), 200)
        figq, axq = plt.subplots()
        axq.hist(charge, bins=qbinning, histtype='step', color='royalblue')
        axq.set_xlabel('Waveform Charge [pC]')
        axq.set_ylabel('Entries')
        axq.set_yscale('log')
        figq.savefig(os.path.join(PLOT_DIR, f'{pmt}_charge_{num}.pdf'))

        figqz, axqz = plt.subplots()
        axqz.hist(charge, bins=small_qbinning, histtype='step', color='royalblue')
        axqz.set_xlabel('Waveform Charge [pC]')
        axqz.set_ylabel('Entries')
        axqz.set_yscale('log')
        figqz.savefig(os.path.join(PLOT_DIR, f'{pmt}_charge_zoom_{num}.pdf'))

        figq2, axq2 = plt.subplots()
        axq2.plot(mfh_t, charge, 'o', linewidth=0)
        axq2.set_xlabel('Trigger Time [ns]')
        axq2.set_ylabel('Waveform Charge [pC]')
        figq2.savefig(os.path.join(PLOT_DIR, f'{pmt}_time_charge_{num}.png'), dpi=300)

    ax1.set_ylabel('PMT #')
    ax1.set_xlabel('Trigger Time [ns]')
    fig1.savefig(os.path.join(PLOT_DIR, f'all_trigger_times_{num}.png'), dpi=300)
    plt.close(fig1)

    ax1z.set_xlim(5e3, 1e4)
    ax1z.set_ylabel('PMT #')
    ax1z.set_xlabel('Trigger Time [ns]')
    fig1z.savefig(os.path.join(PLOT_DIR, f'all_trigger_times_zoom_{num}.png'), dpi=300)
    plt.close(fig1z)

    ax1t.set_ylabel(f'Triggers per {width:.2f} [s]')
    ax1t.set_xlabel(f'Integration Bin ({width:.2f} [s])')
    fig1t.savefig(os.path.join(PLOT_DIR, f'all_integrated_triggers_{num}.png'), dpi=300)
    plt.close(fig1t)

    ax1r.set_ylabel(f'Trigger Rate [Hz]')
    ax1r.set_xlabel(f'Integration Bin ({width:.2f} [s])')
    fig1r.savefig(os.path.join(PLOT_DIR, f'all_rates_{num}.png'), dpi=300)
    ax1r.set_xlim(0, 99)
    fig1r.savefig(os.path.join(PLOT_DIR, f'all_rates_zoom_{num}.png'), dpi=300)
    plt.close(fig1r)

    axdrtt.set_xlabel('Trigger Time [s]')
    axdrtt.set_ylabel('Dark Rate [Hz]')
    axdrtt.set_ylim(10, total_max)
    axdrtt.set_yscale('log')
    figdrtt.savefig(os.path.join(PLOT_DIR, f'all_dark_rate_time_{num}.png'), dpi=300)
    axdrtt.set_xlim(0, 250)
    figdrtt.savefig(os.path.join(PLOT_DIR, f'all_dark_rate_time_zoom_{num}.png'), dpi=300)

    axdrttd.set_xlabel('Trigger Time [s]')
    axdrttd.set_ylabel(r'$\Delta$ Dark Rate [Hz]')
    axdrttd.set_ylim(10, total_max)
    #axdrttd.set_yscale('log')
    figdrttd.savefig(os.path.join(PLOT_DIR, f'all_delta_dark_rate_time_{num}.png'), dpi=300)
    axdrttd.set_xlim(0, 250)
    figdrttd.savefig(os.path.join(PLOT_DIR, f'all_delta_dark_rate_time_zoom_{num}.png'), dpi=300)

    ##start checking correlations within D-Eggs?

##per PMT analysis
def gainInfoPlots(dfFileList, pmt_name, num, figList):
    loop_vals = [0.9, 1.0, 1.1, 1.2, 1.3]
    small_qbinning = np.linspace(-2, 5, 700)
    binning = np.logspace(2, 7, 200)
    figq, axq   = plt.subplots()
    fig2, ax2   = plt.subplots()
    figph, axph = plt.subplots()
    fighr, axhr = plt.subplots()
    figmr, axmr = plt.subplots()
    gainList          = [0] * len(dfFileList)
    highRateCounter   = [0] * len(dfFileList)
    medianRateCounter = [0] * len(dfFileList)
    stdRateCounter    = [0] * len(dfFileList)
    peakHeightList    = [0] * len(dfFileList)
    for i, f in enumerate(dfFileList):
        df = pd.read_hdf(f)
        #loop = loop_vals[df.Num.values[0][0]]
        hv = int(df.HV.values[0])
        gain = df.Gain.values[0]
        if gain <= 0:
            continue
        charges = df.Charge.values
        mfh_t   = df.mfhTime.values
        peakHeight = df.PeakHeight.values[0]
        axq.hist(charges, bins=small_qbinning, histtype='step', label=f'{gain/1e7:.2f}')
        ax2.hist(np.diff(mfh_t), bins=binning, histtype='step', label=f'{gain/1e7:.2f}')

        blockNums = df.blockNum.unique()
        rate_list = [0] * len(blockNums)
        charge_list = [0] * len(blockNums)
        block_times = [0] * len(blockNums)
        plotting_times = [0] * len(blockNums)
        highRate = 0
        for j, blockNum in enumerate(blockNums):
            _df_n = df[df.blockNum == blockNum]
            charge_list[j] = np.sum(_df_n.Charge.values)
            plotting_times[j] = ((np.max(_df_n.mfhTime.values) - np.min(_df_n.mfhTime.values))/2 + np.min(_df_n.mfhTime.values)) * 1e-9
            block_times[j] = (np.max(_df_n.mfhTime.values))*1e-9 - plotting_times[j]
            ##correct for deadtime of 500 ns
            if len(_df_n.index) <= 1:
                rate_list[j] = 0
                continue
            total_time = (np.max(_df_n.mfhTime.values) - np.min(_df_n.mfhTime.values)) - (len(_df_n.index) * 500)
            rate = len(_df_n.index) / total_time
            rate = rate / 1e-9 ##convert into Hz
            rate_list[j] = rate
            if rate >= 4000:
                highRate += 1
        gainList[i]          = gain
        highRateCounter[i]   = highRate
        medianRateCounter[i] = np.median(rate_list)
        stdRateCounter[i]    = np.std(rate_list)
        peakHeightList[i]    = int(peakHeight/CALIBRATION_FACTORS.adc_to_volts)

    axq.legend(title='Gain (1e7)')
    axq.set_xlabel('Charge [pC]')
    axq.set_ylabel('Entries')
    axq.set_yscale('log')
    figq.tight_layout()
    figq.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_charge_hist_gain_{num}.pdf'))
    plt.close(figq)

    ax2.set_ylabel('Entries')
    ax2.set_xlabel('Time Between Triggers [ns]')
    ax2.set_xscale('log')
    ax2.legend(title='Gain (1e7)')
    fig2.tight_layout()
    fig2.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_dt_gain_{num}.pdf'))
    ax2.set_yscale('log')
    fig2.tight_layout()
    fig2.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_dt_gain_log_{num}.pdf'))
    plt.close(fig2)

    axph.plot(gainList, peakHeightList, 'o', linewidth=0, color='royalblue')
    axph.set_xlabel('PMT Gain')
    axph.set_ylabel('SPE Peak Height [ADC]')
    axph.set_title(pmt_name)
    figph.tight_layout()
    figph.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_peak_height_gain_{num}.pdf'))
    plt.close(figph)

    axhr.plot(gainList, highRateCounter, 'o', linewidth=0, color='royalblue')
    axhr.set_xlabel('PMT Gain')
    axhr.set_ylabel('# Charge Blocks w/ Dark Rate > 4,000 Hz')
    axhr.set_title(pmt_name)
    fighr.tight_layout()
    fighr.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_high_rate_gain_{num}.pdf'))
    plt.close(fighr)

    axmr.errorbar(gainList, medianRateCounter, yerr=stdRateCounter, linewidth=0, elinewidth=2, marker='o', color='royalblue')
    axmr.set_xlabel('PMT Gain')
    axmr.set_ylabel('Median Dark Rate [Hz]')
    axmr.set_title(pmt_name)
    figmr.tight_layout()
    figmr.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_median_rate_gain_{num}.pdf'))
    plt.close(figmr)

    figrph, axrph = plt.subplots()
    axrpht = axrph.twinx()
    axrph.plot(gainList, peakHeightList, 'o', linewidth=0, color='royalblue')
    axrpht.plot(gainList, highRateCounter, 'o', linewidth=0, color='goldenrod')
    axrph.set_xlabel('PMT Gain')
    axrph.set_ylabel('SPE Peak Height [ADC]')
    axrpht.set_ylabel('# Charge Blocks w/ Dark Rate > 4,000 Hz')
    axrph.set_title(pmt_name)
    figrph.tight_layout()
    figrph.savefig(os.path.join(PLOT_DIR, f'{pmt_name}_peak_height_high_rate_gain_{num}.pdf'))
    plt.close(figrph)

    ##aggregate plots for all PMTs
    figList[0].plot(gainList, highRateCounter, 'o', linewidth=0)
    figList[1].errorbar(gainList, medianRateCounter, yerr=stdRateCounter, linewidth=0, elinewidth=2, marker='o')
    figList[2].plot(gainList, peakHeightList, 'o', linewidth=0)

def readData(filename):
    if not os.path.isfile(filename):
        raise IOError(f'File {filename} does not exist!')
    with tables.open_file(filename) as open_file:
        data = open_file.get_node('/data/')
        timestamps = data.col('timestamp')
        charges    = data.col('charge')
        channels   = data.col('channel')
        mfhTimes   = data.col('mfhTime')
        offsets    = data.col('offset')
        blockNums  = data.col('blockNum')

    return timestamps, charges, channels, mfhTimes, offsets, blockNums

def getFiles(deggList, filedir, gfiledir, num, altThreshold=False):
    valid_names = []
    for degg in deggList:
        degg_dict = load_degg_dict(degg)
        for pmt in ['LowerPmt', 'UpperPmt']:
            pmt_name = degg_dict[pmt]['SerialNumber']
            if pmt_name in ['SQ0626', 'SQ0556', 'SQ0580']:
                continue
            valid_names.append(pmt_name)

    all_files = []
    gain_files = []
    for pmt_name in valid_names:
        ##get timing information
        if altThreshold == True:
            info_file = sorted(glob(filedir + f'/*_{num}_30.hdf5'))
        else:
            info_file = sorted(glob(filedir + f'/{pmt_name}*_{num}.hdf5'))
        all_files.append(info_file[0])

        ##get waveform files
        gain_file = sorted(glob(gfiledir + f'/{pmt_name}*chargeStamp*_{num[0]}_1.hdf5'))
        gain_files.append(gain_file[0])

        if len(gain_file) != 1 or len(info_file) != 1:
            raise IOError(f'Duplicates in finding files! {gain_file}, {info_file}')

    if len(all_files) != len(gain_files):
        raise IOError('Something went wrong, files not same length!')

    ##separate different 'runs'
    return all_files, gain_files

def getFileNameInfo(filename, name_only=False):
    f = os.path.basename(filename)
    split = f.split('_')
    name = split[0]
    if name_only == True:
        return name, -1
    hv = split[3]
    ##remove the 'v'
    hv = int(float(hv[:-1]))
    return name, hv

def getDEgg(pmtName, channel, deggList):
    channelName = ['LowerPmt', 'UpperPmt']
    for degg in deggList:
        degg_dict = load_degg_dict(degg)
        if pmtName == degg_dict[channelName[channel]]['SerialNumber']:
            return degg_dict['DEggSerialNumber']
    raise NameError(f'Could not locate PMT name {pmtName} in dictionary')

def buildDataFrames(filename, gfilename, minimum, deggList, num):
    name, hv = getFileNameInfo(filename)
    gname, _ = getFileNameInfo(gfilename, name_only=True)
    if name != gname:
        raise NameError(f'Files {name} and {gname} are not the same PMT!')
    if hv == -1 or hv == 2000:
        return
    print(f'Creating Dataframe for {name}, {num}')
    timestamps, charges, channels, mfhTimes, offsets, blockNums = readData(filename)
    mfhTimes = np.array((mfhTimes - minimum) * 1e9, dtype=float)
    degg = getDEgg(name, channels[0], deggList)

    E_CONST = 1.60217662e-7
    try:
        fit_info = fit_charge_hist(gfilename, pmt=None, pmt_id=None, save_fig=False, chargeStamp=False)
        gain = fit_info['popt'][1] / E_CONST
        spe_peak_height = calc_avg_spe_peak_height(
                fit_info['time']*CALIBRATION_FACTORS.fpga_clock_to_s,
                fit_info['waveforms']*CALIBRATION_FACTORS.adc_to_volts,
                fit_info['charges'],
                fit_info['hv'],
                fit_info['popt'][1],
                bl_start=50,
                bl_end=120)
        valid = True
    except ValueError:
        print(f'- Error calculating gain for {name}, {num} -')
        gain = -1
        spe_peak_height = -1
        valid = False
    except IOError:
        print(f'- Error with file for {name}, {num} (likely due to timeout) -')
        gain = -1
        spe_peak_height = -1
        valid = False

    data = {'PMT':[name]*len(timestamps), 'DEgg': [degg]*len(timestamps),
            'HV':[hv]*len(timestamps), 'Charge':charges, 'Num': [num]*len(timestamps),
            'Channel':channels, 'mfhTime':mfhTimes, 'blockNum':blockNums,
            'Gain':[gain]*len(timestamps), 'PeakHeight': [spe_peak_height]*len(timestamps),
            'Valid': [valid]*len(timestamps)}
    df = pd.DataFrame(data=data)
    df.to_hdf(f'caches/cache_{name}_{degg}_{num}.hdf5', key='df', mode='w')
    print(f'Created cache for cache_{name}_{degg}_{num}.hdf5')
    print('-'*20)

def buildTotalDataFrame(fileList, gfileList, deggList, num):
    dfList = []
    ##first get global minimum
    minimum = 0
    for i, f in enumerate(fileList):
        _, _, _, mfhTimes, _, _ = readData(f)
        this_min = np.min(mfhTimes)
        if i == 0:
            minimum = this_min
        else:
            if this_min < minimum:
                minimum = this_min

    for f, g in zip(fileList, gfileList):
        buildDataFrames(f, g, minimum, deggList, num)

def analysis_wrapper(filepath, gfilepath, run_json, num, use_cache, altThreshold=False):
    read_dir = os.path.dirname(os.path.abspath(__file__))
    deggList = load_run_json(run_json)
    if not use_cache:
        files, gfiles = getFiles(deggList, filepath, gfilepath, num, altThreshold)
        print(files, gfiles)
        buildTotalDataFrame(files, gfiles, deggList, num)
        return
    if use_cache:
        ##plots to include all PMTs
        figHR, axHR = plt.subplots()
        figMR, axMR = plt.subplots()
        figPH, axPH = plt.subplots()
        figList = [axHR, axMR, axPH]

        ##go pmt by pmt
        for degg in deggList:
            degg_dict = load_degg_dict(degg)
            for pmt in ['LowerPmt', 'UpperPmt']:
                pmt_name = degg_dict[pmt]['SerialNumber']
                pmt_caches = sorted(glob(f'caches/cache_{pmt_name}*7.hdf5'))
                gainInfoPlots(pmt_caches, pmt_name, num[2], figList)


        axHR.set_xlabel('PMT Gain')
        axHR.set_ylabel('# Charge Blocks w/ Dark Rate > 4,000 Hz')
        figHR.tight_layout()
        figHR.savefig(os.path.join(PLOT_DIR, f'all_high_rate_gain.png'), dpi=300)

        axMR.set_xlabel('PMT Gain')
        axMR.set_ylabel('Median Dark Rate [Hz]')
        figMR.tight_layout()
        figMR.savefig(os.path.join(PLOT_DIR, f'all_median_rate_gain.png'), dpi=300)

        axPH.set_xlabel('PMT Gain')
        axPH.set_ylabel('SPE Peak Height [ADC]')
        figPH.tight_layout()
        figPH.savefig(os.path.join(PLOT_DIR, f'all_peak_height_gain.png'), dpi=300)

    print('Done')

@click.command()
@click.argument('filepath', type=click.Path(exists=True))
@click.argument('gfilepath', type=click.Path(exists=True))
@click.argument('run_json', type=click.Path(exists=True))
@click.argument('num')
@click.option('--auto', is_flag=True)
@click.option('--altthreshold', '-at', is_flag=True)
@click.option('--use_cache', '-c', is_flag=True)
def main(filepath, gfilepath, run_json, num, auto, altthreshold, use_cache):

    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f"Created directory: {PLOT_DIR}")
    if auto == False:
        analysis_wrapper(filepath, gfilepath, run_json, num, use_cache, altthreshold)
    if auto == True:
        for n in ['0_7', '1_7', '2_7', '3_7', '4_7']:
            analysis_wrapper(filepath, gfilepath, run_json, n, use_cache, altthreshold)

if __name__ == '__main__':
    main()


