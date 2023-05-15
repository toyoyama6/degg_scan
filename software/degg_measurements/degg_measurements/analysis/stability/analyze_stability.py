import os, sys
import numpy as np
import matplotlib.pyplot as plt
import click
from glob import glob
import pandas as pd
from tqdm import tqdm

from degg_measurements.utils import load_run_json
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import DEggLogBook

from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH

from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements.analysis.analysis_utils import get_run_json
from degg_measurements.analysis.gain.analyze_gain import run_fit
from degg_measurements.analysis.analysis_utils import get_measurement_numbers
from degg_measurements.analysis.darkrate.analyze_dt import read_timestamps
from degg_measurements.analysis.darkrate.analyze_dt import plot_dt_distribution
from degg_measurements.analysis.darkrate.analyze_dt import plot_charge_distribution
from degg_measurements.analysis.darkrate.loading import make_scaler_darkrate_df

from chiba_slackbot import send_warning

@click.command()
@click.argument('run_json')
@click.option('--offline', is_flag=True)
@click.option('--remote', is_flag=True)
@click.option('--skip_redo', is_flag=True)
def main(run_json, offline, remote, skip_redo):
    analysis_wrapper(run_json, offline, remote, skip_redo)

def analysis_wrapper(run_json, offline=False, remote=False, skip_redo=False):
    run_json, run_number = get_run_json(run_json)
    list_of_deggs = load_run_json(run_json)
    measurement_type = "AdvancedMonitoring"

    if offline != True:
        logbook = DEggLogBook()
    else:
        logbook = None

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    if skip_redo == False:
        print('Rerunning over all files, this will take some time!')
        redoData = True
    if skip_redo == True:
        print('Using processed cache!')
        redoData = False

    dfList = []
    for degg_file in tqdm(list_of_deggs, desc='DEggs'):
        unpackData(dfList, degg_file, measurement_type, run_number, redoData, cache_dir,
                   remote, logbook, offline)

    dfTotal = pd.concat(dfList)
    pErr = (dfTotal.GainPeakError.values/dfTotal.GainPeakPosition.values) * 100
    _mask = np.isfinite(pErr) == True
    pErr = pErr[_mask]
    ##total hist
    fig0, ax0 = plt.subplots()
    ax0.hist(pErr, 80, histtype='step', color='royalblue')

    fig1, ax1 = plt.subplots()
    for degg in dfTotal.DEgg.unique():
        _dfDEgg = dfTotal[dfTotal.DEgg == degg]
        for pmt in _dfDEgg.PMT:
            _df = _dfDEgg[_dfDEgg.PMT == pmt]
            pErr = (_df.GainPeakError.values/_df.GainPeakPosition.values) * 100
            _mask = np.isfinite(pErr) == True
            pErr = pErr[_mask]
            ax1.hist(pErr, 80, histtype='step', label=f'{degg}:{pmt}')

    ax0.set_xlabel('Gain Fit Error / Gain Fit Peak [%]')
    ax0.set_ylabel('Entries')
    fig0.savefig(os.path.join(
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs'),
                 f'total_peakErrorPercent_hist.pdf'))

    ax1.set_xlabel('Gain Fit Error / Gain Fit Peak [%]')
    ax1.set_ylabel('Entries')
    ax1.legend()
    fig1.savefig(os.path.join(
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs'),
                 f'each_peakErrorPercent_hist.pdf'))

def unpackData(dfList, degg_file, measurement_type, run_number, redoData, cache_dir,
               remote, logbook, offline):
    degg_dict = load_degg_dict(degg_file)
    degg_name = degg_dict['DEggSerialNumber']
    for pmt in ['LowerPmt', 'UpperPmt']:
        pmt_id = degg_dict[pmt]['SerialNumber']
        cache_file = f'{run_number}_{degg_name}_{pmt_id}.hdf5'

        if redoData == True:
            measurement_numbers = get_measurement_numbers(
                degg_dict, pmt, 'latest',
                measurement_type, returnAll=True)

            ##also gather cross-file info
            peakPosition = np.zeros(len(measurement_numbers))
            peakWidth    = np.zeros(len(measurement_numbers))
            peakError    = np.zeros(len(measurement_numbers))
            tempList     = np.zeros(len(measurement_numbers))
            hvStd        = np.zeros(len(measurement_numbers))

            deltaTs      = []
            dtTemp       = np.zeros(len(measurement_numbers))
            dtHighF      = np.zeros(len(measurement_numbers))
            dtAfterPulse = np.zeros(len(measurement_numbers))
            dtLowF       = np.zeros(len(measurement_numbers))

            drList   = np.zeros(len(measurement_numbers))
            drErr    = np.zeros(len(measurement_numbers))
            drTemp   = np.zeros(len(measurement_numbers))
            drThresh = np.zeros(len(measurement_numbers))
            drFIR    = np.zeros(len(measurement_numbers))

            mNumber      = np.zeros(len(measurement_numbers))

            for i, m_num in enumerate(measurement_numbers):
                run_plot_dir, run_data_dir, \
                  data_key, data_dir = collectMetaInfo(run_number, m_num,
                                                       degg_dict, pmt,
                                                       measurement_type, remote)
                if data_key == 'SKIP':
                    deltaTs.append([])
                    continue
                if data_dir == 'None' or data_dir == None:
                    print('data_dir is None, skipping measurement.')
                    deltaTs.append([])
                    continue

                ##do specific measurement operations
                unpackGainInfo(i, run_number, data_key, data_dir,
                               run_plot_dir, pmt, pmt_id, m_num,
                               peakPosition, peakWidth, peakError,
                               tempList, hvStd, mNumber)
                unpackDeltaT(i, run_number, data_key, data_dir,
                             run_plot_dir, pmt, pmt_id, m_num,
                             deltaTs, dtTemp, dtHighF, dtAfterPulse, dtLowF)
                unpackScaler(i, run_number, data_key, data_dir,
                             run_plot_dir, pmt, pmt_id, m_num,
                             drList, drErr, drTemp, drThresh, drFIR)

            ##save data to avoid looping again in the future
            data = {
                'DEgg': [degg_name]*len(mNumber),
                'PMT': [pmt_id]*len(mNumber),
                'MeasurementNumber': mNumber,
                'GainPeakPosition' : peakPosition,
                'GainPeakWidth': peakWidth,
                'GainPeakError': peakError,
                'GainTemperature': tempList,
                'GainHVStd': hvStd,
                'DeltaT': deltaTs,
                'DeltaTTemp': dtTemp,
                'DeltaTHighFreq': dtHighF,
                'DeltaTAfterPulse': dtAfterPulse,
                'DeltaTLowFreq': dtLowF,
                'DarkRate': drList,
                'DarkRateErr': drErr,
                'DarkRateTemp': drTemp,
                'DarkRateThreshold': drThresh,
                'DarkRateFIR': drFIR
            }
            df = pd.DataFrame(data=data)
            df.to_hdf(os.path.join(cache_dir, cache_file), 'df', 'w')

        ##try and find the cache
        if redoData == False:
            if not os.path.exists(os.path.join(cache_dir, cache_file)):
                raise IOError(f'Could not find {os.path.join(cache_dir, cache_file)}!' +
                              'Please run with --redo to make a new cache!')
            else:
                df = pd.read_hdf(os.path.join(cache_dir, cache_file))

        dfList.append(df)

        if len(df.index.values) == 0:
            print('Skipping DEgg since df is empty')
            continue
        if np.sum(df.MeasurementNumber.values) == 0:
            continue

        ##finished looping through files, make plots
        plot2d(run_number, df.DEgg.values[0],
               df.MeasurementNumber.values, df.DeltaTHighFreq.values,
               'Measurement Number', 'Trigger pairs where F < 2e-6', pmt_id, 'mNum_highF',
               'deltaT')
        plot2d(run_number, df.DEgg.values[0],
               df.MeasurementNumber.values, df.DeltaTAfterPulse.values,
               'Measurement Number', 'Trigger pairs (2e-5 > F >= 2e-6)', pmt_id, 'mNum_afterPulse',
               'deltaT')
        plot2d(run_number, df.DEgg.values[0],
               df.MeasurementNumber.values, df.DeltaTLowFreq.values,
               'Measurement Number', 'Trigger pairs where F >= 2e-5', pmt_id, 'mNum_lowF',
               'deltaT')
        plotDT(run_number, df.DEgg.values[0],
               df.DeltaT.values, r'$\Delta$T [s]', pmt_id, 'delta_t_summary')
        plotHist(run_number, df.DEgg.values[0],
                 df.GainPeakPosition.values, 'gain',
                 'SPE Peak Position [pC]', pmt_id, 'peakPos_hist')
        plotHist(run_number, df.DEgg.values[0],
                 df.GainPeakError.values, 'default',
                 'SPE Peak Error [pC]', pmt_id, 'peakError_hist')

        pErr = (df.GainPeakError.values * abs(1.6 - df.GainPeakPosition.values)) * 100
        _mask = np.isfinite(pErr) == True
        pErr = pErr[_mask]
        if len(pErr) == 0:
            pErr = [-1]
        try:
            plotHist(run_number, df.DEgg.values[0],
                 pErr, 'default',
                 'SPE Peak Error / (1.6 - Peak Position) [%]', pmt_id,
                 'peakErrorPercent_hist', draw_bound=0.15)
        except:
            print(df)
            print(pErr)
        plotHist(run_number, df.DEgg.values[0],
                 df.GainPeakWidth.values, 'default',
                 'SPE Peak Width [pC]', pmt_id, 'peakWidth_hist')
        plotHist(run_number, df.DEgg.values[0],
                 df.GainHVStd.values, 'default',
                 'HV Readback Std [V] (N=10)', pmt_id, 'hvStd_hist')

        darkrates, passDR, aveColdTemp = plotDR(run_number, df, pmt_id)


        plot2d(run_number, df.DEgg.values[0],
               df.GainPeakPosition.values, df.GainHVStd.values,
               'SPE Peak Position [pC]', 'HV Readback Std [V] (N=10)', pmt_id, 'peakPos_hvStd')
        plot2d(run_number, df.DEgg.values[0],
               df.GainPeakPosition.values, df.MeasurementNumber.values,
               'SPE Peak Position [pC]', 'Measurement Number', pmt_id, 'peakPos_mNum')
        plot2d(run_number, df.DEgg.values[0],
               df.GainPeakPosition.values, df.GainPeakWidth.values,
               'SPE Peak Position [pC]', 'SPE Peak Width [pC]', pmt_id, 'peakPos_peakWidth')
        plot2d(run_number, df.DEgg.values[0],
               df.GainPeakPosition.values, df.GainPeakError.values,
               'SPE Peak Position [pC]', 'SPE Peak Error [pC]', pmt_id, 'peakPos_peakError')

        if offline == False and logbook != None:
            measurement_numbers = get_measurement_numbers(
                degg_dict, pmt, 'latest',
                measurement_type, returnAll=True)
            m_num = np.max(measurement_numbers)
            run_plot_dir, run_data_dir, data_key, data_dir = collectMetaInfo(
                                                   run_number, m_num,
                                                   degg_dict, pmt,
                                                   measurement_type, remote)
            ##create json files
            result = Result(pmt_id, logbook=logbook, run_number=run_number,
                         remote_path=REMOTE_DATA_DIR)

            _m = (df.GainPeakPosition.values > 1.4) & (df.GainPeakPosition.values < 1.8)
            json_filenames = result.to_json(
                meas_group='monitoring',
                raw_files=os.path.join(cache_dir, cache_file),
                folder_name=DB_JSON_PATH,
                filename_add=data_key.replace('Folder', ''),
                constant=True,
                temperature=aveColdTemp,
                darkrates=darkrates,
                passDR=int(passDR),
                pPos=df.GainPeakPosition.values[_m],
                pErr=pErr,
                hvStd=df.GainHVStd.values
            )
            run_handler = RunHandler(filenames=json_filenames)
            run_handler.submit_based_on_meas_class()

def plotDR(run_number, df, pmt_id):
    ##separate fir and theshold events
    use_fir = df.DarkRateFIR == True
    plotHist(run_number, df.DEgg.values[0],
             df.DarkRate.values[use_fir], 'default',
             'Dark Rate (FIR) [Hz]', pmt_id, 'darkrateFIR_hist')
    plotHist(run_number, df.DEgg.values[0],
             df.DarkRate.values[~use_fir], 'default',
             'Dark Rate (Threshold) [Hz]', pmt_id, 'darkrateThres_hist')
    plot2d(run_number, df.DEgg.values[0],
           df.MeasurementNumber.values[use_fir],
           df.DarkRate.values[use_fir],
           'Measurement Number', 'Dark Rate (FIR) [Hz]', pmt_id, 'mNum_darkrateFIR')
    plot2d(run_number, df.DEgg.values[0],
           df.MeasurementNumber.values[~use_fir],
           df.DarkRate.values[~use_fir],
           'Measurement Number', 'Dark Rate (Threshold) [Hz]', pmt_id, 'mNum_darkrateThresh')
    plot2d(run_number, df.DEgg.values[0],
           df.DarkRateTemp.values[use_fir],
           df.DarkRate.values[use_fir],
           'Mainboard Temperature [C]', 'Dark Rate (FIR) [Hz]', pmt_id, 'temp_darkrateFIR')
    plot2d(run_number, df.DEgg.values[0],
           df.DarkRateTemp.values[~use_fir],
           df.DarkRate.values[~use_fir],
           'Mainboard Temperature [C]', 'Dark Rate (Threshold) [Hz]',
           pmt_id, 'temp_darkrateThresh')

    ##also slice for cold temperatures, so we can use goalposts
    ##only check when FIR == True
    cold_mask = df.DarkRateTemp.values < -15
    _cold_mask = cold_mask * use_fir
    passDR = df.DarkRate.values < 2600
    passDR = passDR * cold_mask * use_fir

    plotHist(run_number, df.DEgg.values[0],
             df.DarkRate.values[_cold_mask], 'default',
             'Dark Rate (FIR) [Hz] @ -40', pmt_id, 'darkrateColdFIR_hist')

    return df.DarkRate.values[_cold_mask], np.sum(passDR), np.mean(df.DarkRateTemp.values[passDR])

def unpackScaler(ind, run_number, data_key_to_use, data_dir, run_plot_dir,
                 pmt, pmt_id, m_num, drList, drErr, drTemp, drThresh, drFIR):
    filename = glob(os.path.join(data_dir, f'{pmt_id}_scaler_*.hdf5'))
    if len(filename) == 0:
        print(f'{filename} not found at {data_dir} for {pmt_id}!')
        return
    try:
        darkrate_df = make_scaler_darkrate_df(filename,
                    use_quantiles=False,
                    from_monitoring=True,
                    key=data_key_to_use,
                    run_number=run_number)
    except:
        print(f'Issue with {filename[0]}, skipping')
        return

    darkrate = darkrate_df['darkrate'].values[0]
    if not np.isfinite(darkrate):
        print(f'Dark rate had value of NAN for {run_number}:{data_key_to_use}')
    drList[ind]   = darkrate

    darkrate_err = darkrate_df['darkrate_err'].values[0]
    drErr[ind]    = darkrate_err

    temp = darkrate_df['temp'].values[0]
    drTemp[ind]   = temp

    threshold = darkrate_df['threshold'].values[0]
    drThresh[ind] = threshold

    drFIR[ind]    = darkrate_df['useFIR'].values[0]

def unpackGainInfo(ind, run_number, data_key_to_use, data_dir, run_plot_dir,
                   pmt, pmt_id, m_num,
                   peakPosition, peakWidth, peakError, tempList, hvStd, mNumber):
    filename = glob(os.path.join(data_dir, f'{pmt_id}_gain_*.hdf5'))
    if len(filename) == 0:
        print(f'{filename} not found at {data_dir} for {pmt_id}!')
        return
    fit_info = run_fit(filename[0], pmt, pmt_id, save_fig=True,
                    run_number=run_number, data_key=data_key_to_use,
                    ext_fig_path=run_plot_dir, chargeStamp=False, verbose=False)
    if fit_info == None:
        return

    q_peak     = fit_info['popt'][1]
    q_width    = fit_info['popt'][2]
    q_peak_err = np.sqrt(fit_info['pcov'][1, 1])
    temp = float(fit_info['temp'])
    hvRead = []
    for hv in fit_info['hv_mon'][1:-1].split(' '):
        if hv == '':
            continue
        hvRead.append(float(hv))
    for hv in fit_info['hv_mon_pre'][1:-1].split(' '):
        if hv == '':
            continue
        hvRead.append(float(hv))
    hv_std = np.std(hvRead)

    peakPosition[ind] = q_peak
    peakWidth[ind]    = q_width
    peakError[ind]    = q_peak_err
    tempList[ind]     = temp
    hvStd[ind]        = hv_std
    mNumber[ind]      = m_num

def unpackDeltaT(ind, run_number, data_key_to_use, data_dir, run_plot_dir,
                 pmt, pmt_id, m_num, deltaTs, dtTemp, dtHighF, dtAfterPulse, dtLowF):
    filename = glob(os.path.join(data_dir, f'{pmt_id}_delta_t_*.hdf5'))
    if len(filename) == 0:
        print(f'{filename} not found at {data_dir} for {pmt_id}!')
        deltaTs.append([])
        return
    if os.path.basename(filename[0]).split('_')[4] == 'withFIR':
        use_fir = True
    elif os.path.basename(filename[0]).split('_')[4] == 'noFIR':
        use_fir = False
    else:
        print(f'FIR not sure? Error in code!: {os.path.basename(filename[0]).split("_")}')
        exit(1)

    timestamps, chargestamps, dt_ts, temp  = read_timestamps(
         filename[0], temp_info=True)
    dt_hist, bins, darkrate = plot_dt_distribution(
         timestamps, pmt_id, run_plot_dir, use_fir)
    plot_charge_distribution(chargestamps, pmt_id, run_plot_dir, use_fir)

    delta_t = np.diff(timestamps)
    delta_t_in_s = delta_t / 240e6

    mask = delta_t_in_s < 2e-6
    highF = np.sum(mask)

    mask = (delta_t_in_s >= 2e-6) & (delta_t_in_s < 2e-5)
    afterPulse = np.sum(mask)

    mask = delta_t_in_s >= 2e-5
    lowF = np.sum(mask)

    ##save the dt, temp, and 3 contributions
    #deltaTs[ind]      = delta_t_in_s
    deltaTs.append(delta_t_in_s)
    dtTemp[ind]       = temp
    dtHighF[ind]      = highF
    dtAfterPulse[ind] = afterPulse
    dtLowF[ind]       = lowF

def plotDT(run_number, degg_name, deltaTList, xlabel, pmt_id, plt_name):
    DELTA_T_BINS = np.logspace(
             np.log10(3e-7 * 0.9),
             np.log10(2e-2 * 1.1),
             101)
    fig0, ax0 = plt.subplots()
    fig1, ax1 = plt.subplots()
    bins = DELTA_T_BINS
    linestyle = ['-', '--', ':', '-.']
    colors = ['blue', 'black', 'red', 'green', 'purple', 'goldenrod']
    lcounter = 0
    ccounter = 0
    dt_hist = []
    for i, delta_t in enumerate(deltaTList):
        lcounter += 1
        if lcounter == len(linestyle):
            lcounter = 0
            ccounter += 1
        if ccounter == (len(colors) - 1):
            ccounter = 0
        ax0.hist(delta_t, bins, histtype='step', linestyle=linestyle[lcounter],
                 color=colors[ccounter])

        vals, bin_edges = np.histogram(delta_t, bins)
        dt_hist.append(vals)

    dt_hist = np.array(dt_hist)
    binVals = np.zeros(len(dt_hist[0]))
    binErrs = np.zeros(len(dt_hist[0]))
    for i in range(len(dt_hist[0])):
        bin_l = dt_hist[:, i]
        binVals[i] = np.mean(bin_l)
        binErrs[i] = np.std(bin_l)

    ax1.stairs(binVals, bins, label='Mean', color='royalblue')
    ax1.stairs(binVals+binErrs, bins, label=r'+1$\sigma$', color='goldenrod', linestyle='--')
    ax1.stairs(binVals-binErrs, bins, label=r'-1$\sigma$', color='goldenrod', linestyle='--')
    ax1.set_xscale('log')
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel('Entries')
    ax1.legend()
    ax1.set_title(f'{degg_name}:{pmt_id}')
    pmt_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),
               'figs'), f'run_{run_number}_{degg_name}_{pmt_id}')
    if not os.path.exists(pmt_path):
        os.mkdir(pmt_path)
    fig1.savefig(os.path.join(pmt_path, f'{degg_name}_{pmt_id}_{plt_name}_mean.pdf'))
    plt.close(fig1)


    ax0.set_xscale('log')
    ax0.set_xlabel(xlabel)
    ax0.set_ylabel('Entries')
    ax0.set_title(f'{degg_name}:{pmt_id}')
    pmt_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),
               'figs'), f'run_{run_number}_{degg_name}_{pmt_id}')
    if not os.path.exists(pmt_path):
        os.mkdir(pmt_path)
    fig0.savefig(os.path.join(pmt_path, f'{degg_name}_{pmt_id}_{plt_name}.pdf'))
    plt.close(fig0)


def plot2d(run_number, degg_name, xvals, yvals, xlabel, ylabel, pmt_id, plt_name, key='None'):
    mask = np.isfinite(xvals) == 1
    xvals = xvals[mask]
    mask = np.isfinite(yvals) == 1
    yvals = yvals[mask]

    fig0, ax0 = plt.subplots()
    if key == 'None':
        ax0.plot(xvals, yvals, 'o', color='royalblue')
    elif key == 'deltaT':
        ax0.plot(xvals, yvals, 'o', linewidth=1, color='royalblue')
    ax0.set_xlabel(xlabel)
    ax0.set_ylabel(ylabel)
    ax0.set_title(f'{degg_name}:{pmt_id}')
    pmt_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),
               'figs'), f'run_{run_number}_{degg_name}_{pmt_id}')
    if not os.path.exists(pmt_path):
        os.mkdir(pmt_path)
    fig0.savefig(os.path.join(pmt_path, f'{degg_name}_{pmt_id}_{plt_name}.pdf'))
    plt.close(fig0)

def plotHist(run_number, degg_name, xvals, bins, xlabel, pmt_id,
             plt_name, draw_bound=False):
    mask = np.isfinite(xvals) == 1
    xvals = xvals[mask]

    fig0, ax0 = plt.subplots()
    if bins == 'gain':
        bins = np.linspace(1.4, 1.8, 40)
        _m = (xvals > 1.4) & (xvals < 1.8)
        ax0.hist(xvals, bins, color='royalblue', histtype='step',
                 label=f'{np.mean(xvals[_m]):.2f}+/-{np.std(xvals[_m]):.2f} pC')
    if bins == 'default':
        bins = np.linspace(np.min(xvals), np.max(xvals), 40)
        ax0.hist(xvals, bins, color='royalblue', histtype='step', label=f'N={len(xvals)}')
    ax0.set_xlabel(xlabel)
    ax0.set_ylabel('Entries')
    ax0.set_title(f'{degg_name}:{pmt_id}')
    ax0.legend()

    if draw_bound != False:
        ax0.axvline(draw_bound, linestyle='--', color='goldenrod', label=f'Gpost={draw_bound}')

    pmt_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),
               'figs'), f'run_{run_number}_{degg_name}_{pmt_id}')
    if not os.path.exists(pmt_path):
        os.mkdir(pmt_path)
    fig0.savefig(os.path.join(pmt_path, f'{degg_name}_{pmt_id}_{plt_name}.pdf'))
    plt.close(fig0)

def collectMetaInfo(run_number, m_num, degg_dict, pmt, measurement_type, remote):
    run_plot_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'figs', f'run_{run_number}_advanced_mon_{m_num}')
    run_data_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data', f'run_{run_number}_advanced_mon_{m_num}')
    if not os.path.isdir(run_plot_dir):
        os.makedirs(run_plot_dir)
    if not os.path.isdir(run_data_dir):
        os.makedirs(run_data_dir)
    data_key_to_use = measurement_type + f'_{m_num:02d}'
    if remote:
        try:
            data_dir = degg_dict[pmt][data_key_to_use]['RemoteFolder']
        except KeyError:
            data_dir = 'None'
            send_warning(f'{degg_dict["DEggSerialNumber"]}:{data_key_to_use} had no remote folder.'+
                         '\n - Skipping this device - ')
            data_key_to_use = 'SKIP'
    else:
        data_dir = degg_dict[pmt][data_key_to_use]['Folder']
    return run_plot_dir, run_data_dir, data_key_to_use, data_dir

if __name__ == "__main__":
    main()
##end
