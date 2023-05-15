import tables
import numpy as np
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy import signal

##################################################
from load_dict import load_degg_dict, load_run_json
from read_data import read_data
##################################################
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots')

def intraDEggAnalysis(df, num):
    if len(num) == 3:
        ##special run where gain was varied
        if int(num[2]) == 6 or int(num[2]) >= 7:
            PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')
    if len(num) == 4:
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
        plt.close(figrb)

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
        plt.close(figqr)

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
        if int(num[2]) == 6 or int(num[2]) >= 7:
            PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')
    elif len(num) == 4:
        PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots_gain_change')
    else:
        PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots')


    pmts = df.PMT.unique()
    fig1, ax1 = plt.subplots()
    fig1z, ax1z = plt.subplots()
    fig1t, ax1t = plt.subplots()
    fig1r, ax1r = plt.subplots()

    figdrtt, axdrtt = plt.subplots()
    figdrttd, axdrttd = plt.subplots()

    figpbr, axpbr = plt.subplots()

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
            plt.close(figdrt)
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
        plt.close(figrb)

        ##what is the time between these spikes? is it consistent?
        peaks, prop = signal.find_peaks(rate_list, height=24000, distance=20)
        figrbp, axrbp = plt.subplots()
        axrbp.plot(np.arange(len(rate_list)), rate_list, 'o', linewidth=0, color='royalblue')
        rate_list = np.array(rate_list)
        axrbp.plot(peaks, rate_list[peaks], 'x', label=f'N Peaks={len(peaks)}', color='goldenrod')
        axrbp.set_xlabel('Charge Block')
        axrbp.set_ylabel('Dark Rate [Hz]')
        axrbp.grid(True)
        axrbp.legend()
        figrbp.savefig(os.path.join(PLOT_DIR, f'{pmt}_block_rate_peaks_{num}.png'), dpi=300)
        plt.close(figrbp)

        if len(peaks) != 0:
            axpbr.plot(peaks, rate_list[peaks], marker='o', markersize=1.7, linewidth=0)

        figpdif, axpdif = plt.subplots()
        plotting_times = np.array(plotting_times)
        axpdif.hist(np.diff(plotting_times[peaks]), histtype='step', color='royalblue')
        axpdif.set_xlabel('Time Between Dark Rate Peaks [s]')
        axpdif.set_ylabel('Entries')
        figpdif.savefig(os.path.join(PLOT_DIR, f'{pmt}_peak_time_diff_{num}.pdf'))
        plt.close(figpdif)

        figqr, axqr = plt.subplots()
        axqr.plot(rate_list, charge_list, 'o', linewidth=0)
        axqr.set_xlabel('Dark Rate [Hz]')
        axqr.set_ylabel('Total Charge per block')
        figqr.savefig(os.path.join(PLOT_DIR, f'{pmt}_total_charge_rate_{num}.png'), dpi=300)
        axqr.set_xscale('log')
        figqr.savefig(os.path.join(PLOT_DIR, f'{pmt}_total_charge_rate_log_{num}.png'), dpi=300)
        plt.close(figqr)

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
        plt.close(figq)

        figqz, axqz = plt.subplots()
        axqz.hist(charge, bins=small_qbinning, histtype='step', color='royalblue')
        axqz.set_xlabel('Waveform Charge [pC]')
        axqz.set_ylabel('Entries')
        axqz.set_yscale('log')
        figqz.savefig(os.path.join(PLOT_DIR, f'{pmt}_charge_zoom_{num}.pdf'))
        plt.close(figqz)

        figq2, axq2 = plt.subplots()
        axq2.plot(mfh_t, charge, 'o', linewidth=0)
        axq2.set_xlabel('Trigger Time [ns]')
        axq2.set_ylabel('Waveform Charge [pC]')
        figq2.savefig(os.path.join(PLOT_DIR, f'{pmt}_time_charge_{num}.png'), dpi=300)
        plt.close(figq2)

    ##end looping PMTs

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
    plt.close(figdrtt)

    axdrttd.set_xlabel('Trigger Time [s]')
    axdrttd.set_ylabel(r'$\Delta$ Dark Rate [Hz]')
    axdrttd.set_ylim(10, total_max)
    #axdrttd.set_yscale('log')
    figdrttd.savefig(os.path.join(PLOT_DIR, f'all_delta_dark_rate_time_{num}.png'), dpi=300)
    axdrttd.set_xlim(0, 250)
    figdrttd.savefig(os.path.join(PLOT_DIR, f'all_delta_dark_rate_time_zoom_{num}.png'), dpi=300)
    plt.close(figdrttd)

    axpbr.set_xlabel('Readout Block')
    axpbr.set_ylabel('Block Dark Rate [Hz]')
    figpbr.savefig(os.path.join(PLOT_DIR, f'all_peak_block_rate_{num}.png'), dpi=300)
    plt.close(figpbr)

    ##start checking correlations within D-Eggs?

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

def getFiles(filedir, num, altThreshold=False):
    if altThreshold == True:
        all_files = glob(filedir + f'/*_{num}_30.hdf5')
    #elif subrun != None:
    #    all_files = glob(filedir + f'/*_{subrun}_{num}.hdf5')
    else:
        all_files = glob(filedir + f'/*_{num}.hdf5')
    if len(all_files) == 0:
        raise IOError('No files found!')
    ##separate different 'runs'
    return all_files

def getFileNameInfo(filename):
    f = os.path.basename(filename)
    split = f.split('_')
    name = split[0]
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

def buildDataFrames(filename, minimum, deggList):
    name, hv = getFileNameInfo(filename)
    if hv == -1:
        return
    timestamps, charges, channels, mfhTimes, offsets, blockNums = readData(filename)
    mfhTimes = np.array((mfhTimes - minimum) * 1e9, dtype=float)
    degg = getDEgg(name, channels[0], deggList)
    data = {'PMT':[name]*len(timestamps), 'DEgg': [degg]*len(timestamps),
            'HV':[hv]*len(timestamps), 'Charge':charges,
            'Channel':channels, 'mfhTime':mfhTimes, 'blockNum':blockNums}
    df = pd.DataFrame(data=data)
    return df

def buildTotalDataFrame(fileList, deggList):
    dfList = []
    ##first get global minimum
    minimum = 0
    valid = [True] * len(fileList)
    for i, f in enumerate(fileList):
        _, _, _, mfhTimes, _, _ = readData(f)
        if len(mfhTimes) != 0:
            this_min = np.min(mfhTimes)
        else:
            valid[i] = False
            continue
        if i == 0:
            minimum = this_min
        else:
            if this_min < minimum:
                minimum = this_min

    for v, f in zip(valid, fileList):
        if v == False:
            continue
        df = buildDataFrames(f, minimum, deggList)
        dfList.append(df)
    dfTotal = pd.concat(dfList)
    return dfTotal

def analysis_wrapper(filepath, run_json, num, infile, altThreshold=False):
    read_dir = os.path.dirname(os.path.abspath(__file__))
    if not infile:
        deggList = load_run_json(run_json)
        files = getFiles(filepath, num, altThreshold)
        df = buildTotalDataFrame(files, deggList)
        df.to_hdf(f'cache{num}.hdf5', key='df', mode='w')
    if infile:
        df = pd.read_hdf(os.path.join(read_dir, f'cache{num}.hdf5'))

    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f"Created directory: {PLOT_DIR}")

    print(f'Analyse df{num}')
    separateAnalysis(df, num)
    intraDEggAnalysis(df, num)
    del df
    print('Done')

@click.command()
@click.argument('filepath', type=click.Path(exists=True))
@click.argument('run_json', type=click.Path(exists=True))
@click.argument('num')
@click.option('--altthreshold', '-at', is_flag=True)
@click.option('--infile', '-in', is_flag=True)
def main(filepath, run_json, num, altthreshold, infile):
    print("WARNING - THESE FILES ARE REALLY BIG, YOU MIGHT CRASH THE COMPUTER")
    analysis_wrapper(filepath, run_json, num, infile, altthreshold)

if __name__ == '__main__':
    main()

