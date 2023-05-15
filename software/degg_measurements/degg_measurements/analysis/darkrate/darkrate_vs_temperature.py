##streamlined way to analyze dark rate vs temperature
import os, sys
import click
from glob import glob
import pandas as pd
import tables
import numpy as np
import matplotlib.pyplot as plt
from warnings import warn
from datetime import datetime

#####
from degg_measurements.daq_scripts.degg_cal import DEggCal
from degg_measurements.daq_scripts.degg_cal import PMTCal
from degg_measurements.utils import load_run_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.analysis import Result
##
from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis.gain.analyze_gain import run_fit
from degg_measurements.analysis.gain.analyze_gain import calc_avg_spe_peak_height
from degg_measurements.analysis.darkrate.analyze_dt import read_timestamps
from degg_measurements.analysis.darkrate.loading import analyze_scaler_data
from degg_measurements.analysis.darkrate.loading import read_scaler_data, calc_quantiles
from degg_measurements.utils.control_data_charge import read_data_charge
#from degg_measurements.analysis.spe.analyze_spe import run_fit as fit_charge_stamp_hist
##
#####
E_CONST = 1.60217662e-7

import ast
class PythonLiteralOption(click.Option):

    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)

def setup_classes(run_file, verbose, meas_num_list, meas_num):
    DEggCalList = []
    #load all degg files
    list_of_deggs = load_run_json(run_file)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)
    ##filepath for saving data
    dirname = "figs_darkrate_temperature"
    filepath = os.path.dirname(os.path.abspath(__file__))
    fullpath = os.path.join(filepath, dirname)

    if not os.path.isdir(fullpath):
        os.makedirs(fullpath)

    for degg_file in sorted_degg_files:
        if verbose:
            print(f'Loading: {degg_file}')
        degg = DEggCal(degg_file, gain_reference=0)
        DEggCalList.append(degg)
        meas_num_list.append(meas_num)

    return DEggCalList, fullpath

def get_files(deggCal, meas_num, prefix, verbose=False, ignore_missing_files=False):
    degg_dict = deggCal.degg_dict
    pmt_names = [degg_dict['LowerPmt']['SerialNumber'],
                 degg_dict['UpperPmt']['SerialNumber']]
    key = 'DarkrateTemperature' + '_' + f'{meas_num:02d}'
    dataDir = degg_dict['LowerPmt'][key]['Folder']
    dataFilesList = []
    channelsList = []

    max_scan = 0

    channels = [0, 1]
    for channel in channels:
        pmtCal = deggCal.get_pmt_cal(channel)
        pmtName = pmt_names[channel]
        dataFiles = glob(os.path.join(dataDir, f'{pmtName}_{prefix}_*.hdf5'))
        if len(dataFiles) == 0:
            if ignore_missing_files:
                if verbose:
                    print(f"Missing files for {pmtName} ignored!")
            else:
                raise FileNotFoundError(f'No files found for {pmtName}!')

        if prefix == 'chargeStamp':
            for dfile in dataFiles:
                f = os.path.basename(dfile)
                f = f.split('.')[0]
                s = f.split("_")
                i_scan = int(s[-1])
                if i_scan > max_scan:
                    max_scan = i_scan

        if verbose:
            print(dataFiles)
        dataFilesList.append(dataFiles)
        channelsList.append(channel)

    return dataFilesList, channelsList, int(max_scan)

class AnaTracker(object):
    def __init__(self):
        self.rows = []
        self.pmts = []
        self.channels = []
        self.prefixs = []
        self.filenames = []
        self.hvs = []
        self.temps = []
        self.iterations = []
        self.vals = []
        self.index = []
        self.unixTimes = []

    def addRow(self, row):
        self.rows.append(row)
        self.pmts.append(row.info()[0])
        self.channels.append(row.info()[1])
        self.prefixs.append(row.info()[2])
        self.filenames.append(row.info()[3])
        self.hvs.append(row.info()[4])
        self.temps.append(row.info()[5])
        self.iterations.append(row.info()[6])
        self.vals.append(row.info()[7])
        self.index.append(row.info()[8])
        self.unixTimes.append(row.info()[9])

    def getRow(self, ind):
        return self.rows[ind]

    def getRowInfo(self, ind):
        row = self.rows[ind]
        return row.info()

    def createDF(self):
        mult_index = pd.MultiIndex.from_tuples(self.index, names=['MeasOrder', 'Iter', 'Pmt'])
        df = pd.DataFrame(list(zip(self.pmts, self.channels, self.prefixs, self.filenames,
                        self.hvs, self.temps, self.unixTimes, self.iterations, self.vals)),
                        columns=['pmt', 'channel', 'prefix', 'filename', 'hv', 'temp', 'unixTime', 'iter', 'val'],
                        index=mult_index)
        return df

class AnaRow(object):
    def __init__(self, pmt, channel, prefix, filename, hv, temp, iteration, val, index):
        self.pmt = pmt
        self.channel = int(channel)
        self.prefix = prefix
        self.filename = filename
        self.hv = int(float(hv))
        self.temp = float(temp)
        self.iteration = iteration
        self.val = val
        self.index = index
        self.unixTime = 0

    def info(self):
        information =  [self.pmt, self.channel, self.prefix, self.filename, self.hv,
               self.temp, self.iteration, self.val, self.index, self.unixTime]
        return information

    @classmethod
    def fillRow(cls, prefix, f_path, channel, max_scan=0, figs_dir=None):
        f = os.path.basename(f_path)
        temp = 0
        val = 0
        split = f.split("_")
        ith = split[3]

        if prefix == 'baseline':
            baseline_d = calc_baseline(f_path)
            baseline = baseline_d['baseline'].values[0]
            temp = baseline_d['temp'].values[0]
            datetime_timestamp = baseline_d['datetime_timestamp'].values[0]
            ##initial baseline measurement
            if split[4][0] == '0':
                this_index = (0, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, split[1], f, split[2], float(temp), ith, baseline, this_index)
            ##check baseline at new hv
            if split[4][0] == '1':
                this_index = (2, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, f'{split[1]}Update', f, split[2], float(temp), ith, baseline, this_index)
            row.unixTime = datetime_timestamp

        ##charge stamp files are a large collection
        elif prefix == 'chargeStamp':
            if figs_dir == None:
                fit_info = run_fit(f_path, pmt=channel, pmt_id=split[0],
                               save_fig=False, chargeStamp=True)
            else:
                try:
                    fit_info = run_fit(f_path, pmt=channel, pmt_id=split[0],
                               save_fig=True, chargeStamp=True, ext_fig_path=figs_dir)
                except ValueError:
                    print(f"Problem fitting! {channel}, {split[0]}")
                    fit_info = {'popt':[0, 0], 'temp':-999}
            measured_gain = fit_info['popt'][1] / E_CONST
            temp = float(fit_info['temp'])
            hv_step = split[-1]
            hv_step = hv_step.split(".")[0]
            hv_step = int(hv_step)
            if hv_step == max_scan:
                this_index = (1, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, f'{split[1]}Last', f, split[2], float(temp), ith, measured_gain, this_index)
            else:
                this_index = (100+hv_step, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, split[1], f, split[2], float(temp), ith, measured_gain, this_index)
            row.unixTime = fit_info['datetime_timestamp']

        ##essentially replaced by chargeStamp for index 0 - keeping for legacy cases
        ##index 3 is still used to extract the gain/peak height *see below*
        ##currently only this measurement adds unixTime to the params
        elif prefix == 'gain':
            try:
                spe_fit_info = run_fit(f_path, pmt=channel, pmt_id=split[0], save_fig=True)
                measured_gain = spe_fit_info['popt'][1] / E_CONST
                temp = float(spe_fit_info['temp'])
            except OSError:
                measured_gain = -1
                temp = -9999
            except ValueError:
                measured_gain = -1
                temp = -9999
                print("x0 infeasible - using filler values")
            ##initial gain measurement
            if split[4][0] == '0':
                this_index = (1, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, split[1], f, split[2], temp, ith, measured_gain, this_index)
            ##gain check at new hv
            if split[4][0] == '1':
                this_index = (3, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, f'{split[1]}Update', f, split[2], temp, ith,
                             measured_gain, this_index)
            row.unixTime = spe_fit_info['datetime_timestamp']

        elif prefix == 'peak_height':
            try:
                spe_fit_info = run_fit(f_path, pmt=channel, pmt_id=split[0], save_fig=False)
                spe_peak_height = calc_avg_spe_peak_height(
                    spe_fit_info['time']*CALIBRATION_FACTORS.fpga_clock_to_s,
                    spe_fit_info['waveforms']*CALIBRATION_FACTORS.adc_to_volts,
                    spe_fit_info['charges'],
                    spe_fit_info['hv'],
                    spe_fit_info['popt'][1],
                    bl_start=50,
                    bl_end=120)
                temp = float(spe_fit_info['temp'])
            except OSError:
                spe_peak_height = -1
                temp = -9999
            except ValueError:
                measured_gain = -1
                temp = -9999
                print("x0 infeasible - using filler values")
            ##initial gain measurement
            if split[4][0] == '0':
                this_index = (7, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, 'peakHeight', f, split[2], temp, ith, spe_peak_height / CALIBRATION_FACTORS.adc_to_volts, this_index)
            ##gain check at new hv
            if split[4][0] == '1':
                this_index = (8, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, 'peakHeightUpdate', f, split[2], temp, ith, spe_peak_height / CALIBRATION_FACTORS.adc_to_volts, this_index)
            row.unixTime = spe_fit_info['datetime_timestamp']

        elif prefix == 'delta_t':
            t, c, datetime_timestamp, temp = read_timestamps(f_path, True)
            delta_t = np.diff(t) / 240e6
            ith = split[4]
            ith = ith.split('.')[0]
            this_index = (6, int(ith[:-1]), split[0])
            row = AnaRow(split[0], channel, f'{split[1]}_{split[2]}', f, split[3], float(temp), ith, delta_t, this_index)
            row.unixTime = datetime_timestamp

        elif prefix == 'scaler':
            ith = split[4]
            ith = ith.split('.')[0]
            try:
                parameter_dict, scaler_counts, datetime_timestamp, measure_time, \
                temperature, high_voltage = read_scaler_data(f_path, return_indiv_counts=True, get_time=True)
            except:
                ##catch bad files from crash or early exit
                if split[3] == '0.25':
                    this_index = (4, int(ith[:-1]), split[0])
                    row = AnaRow(split[0], channel, f'{split[1]}_25', f, split[2], -999, ith, [0, 0, 0, 0, 0], this_index)
                    row.unixTime = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
                    return row
                if split[3] == '0.3':
                    this_index = (5, int(ith[:-1]), split[0])
                    row = AnaRow(split[0], channel, f'{split[1]}_30', f, split[2], -999, ith, [0, 0, 0, 0, 0], this_index)
                    row.unixTime = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
                    return row

            try:
                rate, error, deadtime, time = analyze_scaler_data(parameter_dict)
            except:
                print("Analyze Scaler: TEMPORARY SOLUTION!")
                rate = -1
                time = -1
                #lq = -1
                #uq = -1
            lq, uq = calc_quantiles(scaler_counts, parameter_dict)
            temp = parameter_dict['degg_temp']
            if split[3] == '0.25':
                this_index = (4, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, f'{split[1]}_25', f, split[2], float(temp), ith, [rate, time, lq, uq, scaler_counts], this_index)
                row.unixTime = datetime_timestamp
            if split[3] == '0.3':
                this_index = (5, int(ith[:-1]), split[0])
                row = AnaRow(split[0], channel, f'{split[1]}_30', f, split[2], float(temp), ith, [rate, time, lq, uq, scaler_counts], this_index)
                row.unixTime = datetime_timestamp
        else:
            raise KeyError(f'Prefix: {prefix} not valid for filling AnaRow')

        return row

def tag_vs_temp(pmt_df, tag, ylabel, fig_x, ax_x, fig_dir):
    pmt_df = pmt_df[pmt_df.prefix == tag]
    if pmt_df.size == 0:
        return
    pmt_name = pmt_df.pmt.values[0]

    fig, ax = plt.subplots()
    if tag == 'scaler_25' or tag == 'scaler_30':
        rates = []
        for _v in pmt_df.val.values:
            rates.append(_v[0])
        rates = np.array(rates)
        mask = rates > 0
        rates = rates[mask]
        temps = pmt_df.temp.values
        if len(temps) > len(rates):
            temps = temps[:len(rates)]
        ax.plot(temps, rates, 'o')
        ax_x.plot(temps, rates, 'o', label=f'{pmt_name}')
    else:
        temps = pmt_df.temp.values
        if len(temps) > len(pmt_df.val.values):
            temps = temps[:len(pmt_df.val.values)]
        ax.plot(temps, pmt_df.val.values, 'o')
        ax_x.plot(temps, pmt_df.val.values, 'o', label=f'{pmt_name}')
    ax.set_xlabel('Temperature [C]')
    ax.set_ylabel(ylabel)
    ax.set_title(pmt_name)
    fig.tight_layout()
    save = os.path.join(fig_dir, f'{pmt_name}_{tag}_vs_temp.pdf')
    fig.savefig(save)
    plt.close(fig)


def temp_time(fig_temp, ax_temp, pmt_df, fig_dir):

    pmt_name = pmt_df.pmt.values[0]
    ##duplicates delta T point, un-needed peakHeight rows
    cond = ~pmt_df['prefix'].isin(['chargeStamp', 'AveDeltaT', 'peakHeight', 'peakHeightUpdate']).values
    temp_df = pmt_df[cond]
    temp_df = temp_df.sort_index(level=1)

    #separation between sets of points is about 1 hour
    fig, ax = plt.subplots()
    ax.plot(np.arange(len(temp_df.temp.values)), temp_df.temp.values, 'o')
    ax.set_xlabel('Measurement Number')
    ax.set_ylabel('Temperature [C]')
    ax.set_title(pmt_name)
    ax.grid(which='both')
    fig.tight_layout()
    save = os.path.join(fig_dir, f'{pmt_name}_temp_vs_time.pdf')
    fig.savefig(save)
    plt.close(fig)

    fig_s, ax_s = plt.subplots()
    fig_s2, ax_s2 = plt.subplots()
    for i in temp_df.iter.values:
        _df = temp_df[temp_df.iter.values == i]
        start = int(i[:-1]) * 7
        ax_s.plot(np.arange(start, start+len(_df.temp.values)), _df.temp.values, 'o')
        ax_s2.plot(np.arange(start, start+len(_df.hv.values)), _df.hv.values, 'o')

    ax_s.grid(which='both')
    ax_s.set_xlabel('Measurement Number')
    ax_s.set_ylabel('Temperature [C]')
    ax_s.set_title(pmt_name)
    fig_s.tight_layout()
    save = os.path.join(fig_dir, f'{pmt_name}_temp_vs_time_slice.pdf')
    fig_s.savefig(save)
    plt.close(fig_s)

    ax_s2.grid(which='both')
    ax_s2.set_xlabel('Measurement Number')
    ax_s2.set_ylabel('PMT High Voltage [V] (SET)')
    ax_s2.set_title(pmt_name)
    fig_s2.tight_layout()
    save2 = os.path.join(fig_dir, f'{pmt_name}_hv_vs_time_slice.pdf')
    fig_s2.savefig(save2)
    plt.close(fig_s2)

    #ax_temp.plot(np.arange(len(temp_df.temp.values)), temp_df.temp.values, 'o', label=f'{pmt_name}')

    if temp_df.channel.values[0] == 0:
        ax_temp.plot(np.arange(len(temp_df.temp.values)), temp_df.temp.values, 'o', markerfacecolor='none', label=f'{pmt_name}')
    if temp_df.channel.values[0] == 1:
        ax_temp.plot(np.arange(len(temp_df.temp.values)), temp_df.temp.values, 'x', label=f'{pmt_name}')

def double_tags(pmt_df, tag1, tag2, label1, label2, fig_dir):
    pmt_name = pmt_df.pmt.values[0]
    df1 = pmt_df[pmt_df.prefix == tag1]
    df2 = pmt_df[pmt_df.prefix == tag2]

    fig1, ax1 = plt.subplots()
    h = ax1.scatter(df1.val.values, df2.val.values, c=df2.temp.values)
    ax1.set_xlabel(label1)
    ax1.set_ylabel(label2)
    ax1.set_title(f'{pmt_name}')
    fig1.colorbar(h, ax=ax1, label='Temperature [C]')
    fig1.tight_layout()
    save = os.path.join(fig_dir, f'{pmt_name}_{tag1}_vs_{tag2}.pdf')
    fig1.savefig(save)
    plt.close(fig1)

def hist_plots(df, tag, label, fig_dir):
    df_tag = df[df.prefix == tag]
    if len(df_tag) == 0:
        if tag != 'gain' or tag != 'peakHeight':
            print(f"No data found for {tag}!")
        return 1


    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()
    if tag == 'scaler_25' or tag == 'scaler_30':
        v = df_tag.val.values
        rates = []
        for _v in v:
            rates.append(_v[0])
        rates = np.array(rates)
        mask = rates > 0
        rates = rates[mask]
        ax1.hist(rates, histtype='step')
        temps = df_tag.temp.values
        if len(temps) > len(rates):
            temps = temps[:len(rates)]
        h = ax2.hist2d(temps, rates, cmin=1)
    else:
        ax1.hist(df_tag.val.values, histtype='step')
        temps = df_tag.temp.values
        if len(temps) > len(df_tag.val.values):
            temps = temps[:len(df_tag.val.values)]
        h = ax2.hist2d(temps, df_tag.val.values, cmin=1)

    ax1.set_xlabel(label)
    ax1.set_ylabel('Entries')
    fig1.tight_layout()
    save1 = os.path.join(fig_dir, f'{tag}_hist.pdf')
    fig1.savefig(save1)
    plt.close(fig1)

    ax2.set_xlabel('Temperature [C]')
    ax2.set_ylabel(label)
    fig2.colorbar(h[3], ax=ax2, label='Entries')
    fig2.tight_layout()
    save2 = os.path.join(fig_dir, f'{tag}_hist2d.pdf')
    fig2.savefig(save2)
    plt.close(fig2)

    if tag == 'scaler_25' or tag == 'scaler_30':
        fig2b, ax2b = plt.subplots()
        x_binning = np.linspace(np.min(df_tag.temp.values), np.max(df_tag.temp.values), num=20, endpoint=True)
        y_binning = np.logspace(np.log10(np.min(rates)), np.log10(np.max(rates)), num=20, endpoint=True)
        temps = df_tag.temp.values
        if len(temps) > len(rates):
            temps = temps[:len(rates)]
        h = ax2b.hist2d(temps, rates, bins=[x_binning, y_binning], cmin=1)
        ax2b.set_xlabel('Temperature [C]')
        ax2b.set_ylabel(label)
        ax2b.set_yscale('log')
        fig2b.colorbar(h[3], ax=ax2b, label='Entries')
        fig2b.tight_layout()
        save2b = os.path.join(fig_dir, f'{tag}_hist2d_logy.pdf')
        fig2b.savefig(save2b)
        plt.close(fig2b)

    return 0

def delta_t_dists(pmt_df, fig_dir):
    alt_df = pmt_df[pmt_df.prefix == 'peakHeightUpdate']
    pmt_df = pmt_df[pmt_df.prefix == 'delta_t']
    iter_vals = pd.unique(pmt_df.iter)
    pmt_name = pmt_df.pmt.values[0]

    binning = np.logspace(-7, -2, 100)

    dark_rates = []

    fig1, ax1 = plt.subplots()
    for its in iter_vals:
        df_i = pmt_df[pmt_df.iter == its]
        df_j = alt_df[alt_df.iter == its]
        approx_dark_rate = len(df_i.val.values[0]) / np.sum(df_i.val.values[0])
        dark_rates.append(approx_dark_rate)
        ax1.hist(df_i.val.values, bins=binning, histtype='step', label=f'{df_i.temp.values[0]:.01f},    {df_i.hv.values[0]},  \
         {approx_dark_rate:.01f},  \
         {int(df_j.val.values[0])}')
        figA, axA = plt.subplots()
        axA.hist(df_i.val.values, bins=binning, histtype='step')
        axA.set_xscale('log')
        axA.set_title(f'{pmt_name} - PeakHeight={int(df_j.val.values[0])}')
        axA.set_xlabel('Delta T [s]')
        axA.set_ylabel('Entries')
        figA.tight_layout()
        saveA = os.path.join(fig_dir, f'{pmt_name}_delta_t_{its}_hist.pdf')
        figA.savefig(saveA)

    ax1.set_xscale('log')
    ax1.set_title(pmt_name)
    ax1.set_xlabel('Delta T [s]')
    ax1.set_ylabel('Entries')
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.17), title='Temp[C], HV[V],  DarkRate[Hz],  PeakHeight[ADC]')
    fig1.tight_layout()
    save = os.path.join(fig_dir, f'{pmt_name}_delta_t_multi_hist.pdf')
    fig1.savefig(save)

    return dark_rates

def charge_stamps(pmt_df, figs_dir):
    pmt_dfL = pmt_df[pmt_df.prefix == 'chargeStampLast']
    pmt_df = pmt_df[pmt_df.prefix == 'chargeStamp']
    iter_vals = pd.unique(pmt_df.iter)
    pmt_name = pmt_df.pmt.values[0]

    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()
    for its in iter_vals:
        df_i = pmt_df[pmt_df.iter == its]
        df_j = pmt_dfL[pmt_dfL.iter == its]
        order = df_i.index.get_level_values(0).values - 99 ##all chargeStamp orders were padded with 100
        #np.append(order, np.max(order) + 1)
        gains = df_i.val.values
        #np.append(gains, df_j.val.values[0])
        ax1.plot(order, gains, 'o')
        ax2.plot(df_i.hv.values, gains, 'o')

    ax1.set_title(f'Charge Stamp: {pmt_name}')
    ax1.set_xlabel('HV Scan Step Number')
    ax1.set_ylabel('Gain')
    fig1.tight_layout()
    save1 = os.path.join(figs_dir, f'{pmt_name}_charge_stamp_gains.pdf')
    fig1.savefig(save1)

    ax2.set_title(f'Charge Stamp: {pmt_name}')
    ax2.set_xlabel('High Voltage [V]')
    ax2.set_ylabel('Gain')
    fig2.tight_layout()
    save2 = os.path.join(figs_dir, f'{pmt_name}_charge_stamp_gain_curve.pdf')
    fig2.savefig(save2)

def analysis(deggCal, meas_num, anaTracker, verbose, ignore_missing_files, figs_dir):
    prefixList = ['baseline', 'chargeStamp', 'gain', 'peak_height', 'delta_t', 'scaler']
    for prefix in prefixList:
        ##repeat for peakHeight - no separate file
        if prefix == 'peak_height':
            fileList, channelsList, max_scan = get_files(deggCal, meas_num, 'gain', verbose, ignore_missing_files)
        else:
            fileList, channelsList, max_scan = get_files(deggCal, meas_num, prefix, verbose, ignore_missing_files)
        ##list contains lower, upper PMT
        for files, channel in zip(fileList, channelsList):
            for f in files:
                row = AnaRow.fillRow(prefix, f, channel, max_scan, figs_dir)
                if row == None:
                    continue
                anaTracker.addRow(row)
                ##also do the average dT
                if prefix == 'delta_t':
                    row_b = row
                    row_b.val = np.mean(row.val)
                    row_b.prefix = 'AveDeltaT'
                    ia, ib, ic = row_b.index
                    row_b.index = (9, ib, ic)
                    anaTracker.addRow(row_b)

    return anaTracker

def analysisWrapper(run_file, meas_num, verbose, ignore_missing_files, cache, outfile):
    anaTracker = AnaTracker()
    deggCalList = []
    meas_num_list = []
    for r, n in zip(run_file, meas_num):
        print(r, n)
        _deggCalList, dirname = setup_classes(r, verbose, meas_num_list, int(n))
        deggCalList.append(_deggCalList)
    deggCalList = np.array(deggCalList)
    deggCalList = deggCalList.flatten()
    print(deggCalList)
    infile_name = os.path.basename(run_file[0]).split('.')[0]
    dir_name = f'{infile_name}_{meas_num[0]}'
    fig_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f'figs_darkrate_temperature/{dir_name}')
    if not os.path.isdir(fig_dir):
        os.makedirs(fig_dir)
    for deggCal, n in zip(deggCalList, meas_num_list):
        anaTracker = analysis(deggCal, n, anaTracker, verbose, ignore_missing_files, fig_dir)
    df = anaTracker.createDF()
    print(df)
    if cache == True:
        df.to_hdf(outfile, key='df', mode='w')

def analysis_per_pmt(pmt, logbook, run_number, pmt_df, tags, labels, figs_list, axs_list, fig_temp, ax_temp, fig_dir, data_key, abs_fpath):
    ##plotting functions
    #temp_time(fig_temp, ax_temp, pmt_df, fig_dir)
    for tag, label, fig_x, ax_x in zip(tags, labels, figs_list, axs_list):
        tag_vs_temp(pmt_df, tag, label, fig_x, ax_x, fig_dir)
    charge_stamp_dark_rates = delta_t_dists(pmt_df, fig_dir)
    double_tags(pmt_df, 'gainUpdate', 'peakHeightUpdate', 'Gain Updated', 'Peak Height Updated [ADC]', fig_dir)
    charge_stamps(pmt_df, fig_dir)

    ##database insertions
    _pmt_df1 = pmt_df[pmt_df.prefix == 'gainUpdate']
    _pmt_df2 = pmt_df[pmt_df.prefix == 'scaler_25']
    baselineValues = pmt_df[pmt_df.prefix == 'baselineUpdate'].val.values
    gainValues = pmt_df[pmt_df.prefix == 'gainUpdate'].val.values
    peakHeightValues = pmt_df[pmt_df.prefix == 'peakHeightUpdate'].val.values
    scalerRateValues = pmt_df[pmt_df.prefix == 'scaler_25'].val.values

    result = Result(pmt,
                    logbook=logbook,
                    run_number=run_number,
                    remote_path=REMOTE_DATA_DIR)


    jsonBaselines = []
    for b in baselineValues:
        jsonBaselines.append(float(b))
    jsonScalerRates = []
    for s in scalerRateValues:
        jsonScalerRates.append(float(s[0]))

    jsonTimes = []
    for t in _pmt_df1.unixTime.values:
        if t.any() == -1 or t.any() == 0:
            print("warning you are filling the time with a default value!")
            t = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
            jsonTimes.append(t)
        ##times are valid! But only need the first one
        else:
            jsonTimes.append(np.min(t))

    result.to_json(meas_group='monitoring',
                   raw_files          = abs_fpath,
                   folder_name        = DB_JSON_PATH,
                   filename_add       = data_key.replace('Folder', ''),
                   times              = jsonTimes,
                   temperatures       = _pmt_df2.temp.values.tolist(),
                   high_voltages      = _pmt_df1.hv.values.tolist(),
                   baselines          = jsonBaselines,
                   gains              = gainValues.tolist(),
                   peak_heights       = peakHeightValues.tolist(),
                   scaler_rates       = jsonScalerRates,
                   charge_stamp_rates = charge_stamp_dark_rates
                   )
    del result

def postAnalysisWrapper(infile, run_number):
    df = pd.read_hdf(infile)
    infile_name = os.path.basename(infile).split('.')[0]
    fig_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f'figs_darkrate_temperature/{infile_name}')
    if not os.path.isdir(fig_dir):
        os.makedirs(fig_dir)

    pmts = pd.unique(df.pmt)
    ##'gain' tag now deprecated! (gainUpdate still used)
    ##scaler_30 tag will also be deprecated!
    tags = ['scaler_25', 'AveDeltaT',
            'peakHeight', 'peakHeightUpdate',
            'gainUpdate', 'baseline', 'baselineUpdate']
    labels = ['Dark Rate [Hz] (25%)', 'Average Delta T [s]',
            'Peak Height [ADC]', 'Peak Height Updated [ADC]',
            'Gain Updated', 'Baseline [ADC]', 'Baseline Updated [ADC]']

    logbook = DEggLogBook()

    figs_list = []
    axs_list = []

    for tag, label in zip(tags, labels):
        r = hist_plots(df, tag, label, fig_dir)
        ##No entires for given tag found
        fig_x, ax_x = plt.subplots()
        figs_list.append(fig_x)
        axs_list.append(ax_x)

    fig_temp, ax_temp = plt.subplots()
    data_key = 'Monitoring'
    abs_fpath = os.path.abspath(infile)

    fig_hvg, ax_hvg = plt.subplots()

    ##slice by PMTs
    for pmt in pmts:
        pmt_df = df[df.pmt == pmt]
        print(f'PMT: {pmt}')
        analysis_per_pmt(pmt, logbook, run_number, pmt_df, tags, labels, figs_list, axs_list, fig_temp, ax_temp, fig_dir, data_key, abs_fpath)

        _val_df = pmt_df[pmt_df.prefix == 'gainUpdate']
        hv = _val_df.hv.values
        gain = _val_df.val.values

        ax_hvg.plot(hv, gain, 'o')

    ax_hvg.set_xlabel('HV@1e7 Gain (From Charge Stamp Gain Scan)')
    ax_hvg.set_ylabel('Gain (From WF Gain Check at Shown HV)')
    fig_hvg.tight_layout()
    fig_hvg.savefig(os.path.join(fig_dir, f'gainUpdate_vs_hv.pdf'))

    print("Plotting")
    for tag, label, fig_x, ax_x in zip(tags, labels, figs_list, axs_list):
        ax_x.set_xlabel('Temperature [C]')
        ax_x.set_ylabel(label)
        #ax_x.legend()
        save = os.path.join(fig_dir, f'{tag}_vs_temp.pdf')
        fig_x.tight_layout()
        fig_x.savefig(save)
        if tag == 'gainUpdate':
            ax_x.set_ylim(0.9*1e7, 1.1*1e7)
            fig_x.tight_layout()
            alt_save = os.path.join(fig_dir, f'{tag}_vs_temp_ylim.pdf')
            fig_x.savefig(alt_save)
        if tag == 'scaler_25':
            ax_x.set_ylim(1000, 5000)
            fig_x.tight_layout()
            alt_save = os.path.join(fig_dir, f'{tag}_vs_temp_ylim.pdf')
            fig_x.savefig(alt_save)

    plt.close(fig_x)

    ax_temp.set_xlabel('Measurement Number')
    ax_temp.set_ylabel('Temperature [C]')
    fig_temp.savefig(os.path.join(fig_dir, 'temp_vs_time_no_legend.pdf'))
    ax_temp.legend(loc='upper center', bbox_to_anchor=(1.55, 1.05), ncol=2)
    fig_temp.tight_layout()
    fig_temp.savefig(os.path.join(fig_dir, 'temp_vs_time.pdf'))
    plt.close(fig_temp)
    #aggregate_plots(df)

def do_stack(stackfile, outfile):
    df_l = []
    max_iter = 1
    for i, f in enumerate(stackfile):
        df = pd.read_hdf(f)
        iters = df.iter.values
        vals = [int(v[:-1]) for v in iters]
        max_val = np.max(vals)
        if i == 0:
            print('First df added as normal')
        if i > 0:
            new_vals = vals + max_iter
            new_iters = [str(v)+'i' for v in new_vals]
            _tup = (df.index.get_level_values(0), new_iters, df.index.get_level_values(2))
            mult_index = pd.MultiIndex.from_arrays(_tup, names=('MeasOrder', 'Iter', 'Pmt'))
            df.reindex(mult_index)
            print(f'Added another df with max: {max_iter}')

        df_l.append(df)
        max_iter += max_val

    df_full = pd.concat(df_l)
    print(df_full)
    print(df_full.prefix.unique())

    df_full.to_hdf(outfile, key='df', mode='w')
    print(f'--- Finished new dataframe: {outfile} ---')

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('run_file', type=click.Path(exists=True))
@click.option('--meas_num', '-n', cls=PythonLiteralOption, default='[]')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--ignore_missing_files', '-i', is_flag=True)
@click.option('--cache', is_flag=True)
@click.option('--outfile', '-o', default=None)
@click.option('--infile', '-in', default=None)
@click.option('--stackfile', '-s', multiple=True)
def main(run_file, meas_num, verbose, ignore_missing_files, cache, outfile, infile, stackfile):

    if len(stackfile) >= 2:
        if outfile == None:
            raise IOError('Must specify outfile name to use stacking')
        do_stack(stackfile, outfile)
        exit(0)

    if infile is not None:
        print("Running cached analysis file!")
        print("Making plots then exiting!")
        run_number = extract_runnumber_from_path(run_file)
        postAnalysisWrapper(infile, run_number)
        return

    else:
        if cache == False:
            raise Error('Run with --cache and give an outfile name with -o !')

    _run_file = [run_file]
    if len(_run_file) != len(meas_num):
        if len(_run_file) != 1:
            raise NotImplementedError('Number of run files and measurement numbers must be equal!')
        else:
            print("Assuming all measurements are from this same run!")
            run_file = [run_file] * len(meas_num)

    else:
        run_file = [run_file]

    if cache == True and outfile is None:
        raise NotImplementedError('If caching the dataframe, provide an output file name with -o')
    analysisWrapper(run_file, meas_num, verbose, ignore_missing_files, cache, outfile)

if __name__ == "__main__":
    main()

##end
