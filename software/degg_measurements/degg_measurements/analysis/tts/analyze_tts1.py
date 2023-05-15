import os, sys
import shutil
import tables
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
from datetime import datetime
import click
from tqdm import tqdm
from scipy.optimize import curve_fit
from scipy.stats import chisquare

from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.analysis.analysis_utils import get_measurement_numbers



def checkTabletop(df, plot_dir, rate):
    df = df[df.type == 'tabletop']
    diff = np.diff(df.mfhTime.values)
    fig, ax = plt.subplots()
    if rate == 100:
        binning = np.linspace(9.999995e12, 1.0000006e13, 200)
    elif rate == 1000:
        binning = np.linspace(9.999995e11, 1.0000009e12, 200)
    elif rate == 5000:
        binning = np.linspace(9.999995e11/5, 1.0000009e12/5, 200)
    elif rate == 500:
        binning = np.linspace(0.0019*1e15, 0.0021*1e15, 200)
    else:
        raise ValueError(f'Rate of {rate} is not yet supported - implement manually!')
    ax.hist(diff, histtype='step', bins=binning, color='royalblue')
    ax.set_xlabel('Time Between Tabletop Triggers [ps]')
    ax.set_ylabel('Entries')
    fig.savefig(os.path.join(plot_dir, 'tabletop_diff.pdf'))
    ax.set_yscale('log')
    fig.savefig(os.path.join(plot_dir, 'tabletop_diff_log.pdf'))
    plt.close(fig)

    print(binning[1] -binning[0])

    ##control for bad triggers - usually at the start of a block
    ##simply remove them
    ##tuned for 100 Hz
    if rate == 100:
        mask = (diff  >= 9.9e12) & (diff <= 1.1e13)
    ##tuned for 1000 Hz
    elif rate == 1000:
        mask = (diff  >= 9.9e11) & (diff <= 1.1e12)
    elif rate == 5000:
        mask = (diff  >= 9.9e11/5) & (diff <= 1.1e12/5)
    elif rate == 500:
        mask = (diff >= 0.0019*1e15)  & (diff <= 0.0021*1e15)
    else:
        raise ValueError(f'Rate of {rate} is not yet supported - implement manually!')

    df['validRef'] = [True]*len(df.index)
    df.validRef[1:] = mask

    print(f'Number of reference triggers: {len(df.index)}')
    print(f'Number of valid reference triggers: {np.sum(mask)}')

    if np.sum(mask) == 0:
        raise ValueError('None of your reference triggers are valid! Do validation checks! (or laser frequency is changed)')

    return df

def compareTimes(df_total, df_ref, plot_dir, cache_dir, rate=100,
                 spe=False, run_number='00000', data_key_to_use='tts_00'):

    df_ref  = df_ref[df_ref.validRef == True]
    df_degg = df_total[df_total.type == 'degg']

    ref_time = df_ref.mfhTime.values/1e15 + df_ref.delta.values[0]
    min_time = np.min(ref_time)

    fig, ax = plt.subplots()
    fig2, ax2 = plt.subplots()

    for port in df_degg.port.unique():
        for channel in [1]:
            _df = df_degg[(df_degg.port == port) & (df_degg.channel == channel)]

            mfhTime = _df.mfhTime.values/1e15 + _df.delta.values[0] - min_time
            slice_ind = 100
            if len(mfhTime) == 0:
                continue
            plt_port0 = [port - 4999] * len(mfhTime)
            plt_port1 = [port - 4999 + 0.5] * len(mfhTime)
            if plt_port1[0] == 7.5 or plt_port1[0] == 15.5:
                continue
            if channel == 0:
                ax.plot(mfhTime, plt_port0, 'o', linewidth=0)
                ax2.plot(mfhTime[:slice_ind], plt_port0[:slice_ind], 'o', linewidth=0)
            if channel == 1:
                ax.plot(mfhTime, plt_port1, 'o', linewidth=0)
                ax2.plot(mfhTime[:slice_ind], plt_port1[:slice_ind], 'o', linewidth=0)


    ax.plot(ref_time - min_time, [0]*len(df_ref.index.values), 'o', linewidth=0)
    ax2.plot(ref_time[:slice_ind] - min_time, [0]*len(df_ref.index.values[:slice_ind]), 'o', linewidth=0)

    ax.set_ylabel('D-Egg Number')
    ax.set_xlabel('Trigger Time [s]')
    fig.savefig(os.path.join(plot_dir, 'sampled_time.png'), dpi=300)
    plt.close(fig)

    ax2.set_ylabel('D-Egg Number')
    ax2.set_xlabel('Trigger Time [s]')
    fig2.savefig(os.path.join(plot_dir, 'sampled_time_trim.png'), dpi=300)
    plt.close(fig2)

    diff = np.diff(df_degg.mfhTime.values)
    diff = np.append(diff, 1e25)
    df_degg['dt'] = diff
    ##for 100 Hz MPE
    #if rate == 100:
    #    mask = (diff > 0.0092e15) & (diff < 0.0111e15)
    ##for 1kHz
    #if rate == 1000:
    #    mask = (diff > 0.00092e15) & (diff < 0.00111e15)
    #df_degg.loc[~mask, 'dt'] = np.nan
    #df_dt_slice = df_degg.loc[mask]

    for it0, port in enumerate(df_degg.port.unique()):
        for it1, channel in enumerate([1]):
            _df = df_degg[(df_degg.port == port) & (df_degg.channel == channel)]
            print('-'*20)
            port = int(port)
            channel = int(channel)
            if channel == 0:
                pmt_name = _df.lowerPMT.values[0]
            if channel == 1:
                pmt_name = _df.upperPMT.values[0]
            print(f'DEgg:{port}:{channel}')
            if spe == True:
                new_mask = make_laser_freq_mask_spe(_df.timestamp.values, rate)
            else:
                new_mask = make_laser_freq_mask_spe(_df.timestamp.values, rate)

            _df_dt_slice = _df.loc[new_mask]
            if it0 == 0 and it1 == 0:
                df_dt_slice = _df_dt_slice
            else:
                df_dt_slice = pd.concat([df_dt_slice, _df_dt_slice])
            print(f'Events remaining after deltaT cut: {(np.sum(new_mask)/len(new_mask))*100}%')

            ##plotting
            _fig, _ax = plt.subplots()
            _ax.plot(np.arange(len(_df.charge.values)), _df.charge.values, 'o', color='royalblue')
            _ax.set_yscale('log')
            _fig.tight_layout()
            _fig.savefig(f'{plot_dir}/charge_time_{port}_{channel}.png', dpi=300)
            plt.close(_fig)
            _fig2, _ax2 = plt.subplots()
            binning = np.linspace(0, 10, 200)
            _ax2.hist(_df.charge.values, bins=binning, histtype='step', color='royalblue', label='Before Cut')
            _ax2.hist(df_dt_slice.charge.values, bins=binning, histtype='step', color='goldenrod', label='After Cut')
            _ax2.legend()
            _ax2.set_yscale('log')
            _fig2.tight_layout()
            _fig2.savefig(f'{plot_dir}/charge_hist_{port}_{channel}.pdf')
            plt.close(_fig2)
            _fig2b, _ax2b = plt.subplots()
            binning = np.linspace(0, 250, 2500)
            _ax2b.hist(_df.charge.values, bins=binning, histtype='step', color='royalblue', label='Before Cut')
            _ax2b.hist(df_dt_slice.charge.values, bins=binning, histtype='step', color='goldenrod', label='After Cut')
            _ax2b.legend()
            _ax2b.set_yscale('log')
            _fig2b.tight_layout()
            _fig2b.savefig(f'{plot_dir}/charge_hist_wide_{port}_{channel}.pdf')
            plt.close(_fig2b)
            _fig3, _ax3 = plt.subplots()
            _ax3.plot(np.arange(len(new_mask)), np.cumsum(new_mask)/np.sum(new_mask), 'o', color='royalblue')
            _ax3.set_ylabel('Mask Cumulative Sum')
            _ax3.set_xlabel('Index')
            _ax3t = _ax3.twinx()
            _ax3t.plot(np.arange(len(new_mask))[500:-500], (np.cumsum(new_mask)[1000:]-np.cumsum(new_mask)[:-1000])/1000, color='goldenrod')
            #_ax3t.plot(np.arange(len(new_mask)), new_mask, color='goldenrod')
            _ax3t.set_xlabel('Cut Mask Rolling Average')
            _fig3.tight_layout()
            _fig3.savefig(f'{plot_dir}/pass_time_{port}_{channel}.png', dpi=300)
            plt.close(_fig3)


    print(df_dt_slice.channel.unique())

    ##Matching is performed here!!!
    df_matched, ERROR_FLAG = findValidTriggers(df_dt_slice, df_ref)

    ##computation is expensive, so cache the df
    print("Created updated dataframe with matched trigger information")
    if spe == False:
        cache_name = f'timing_{run_number}_{data_key_to_use}_matched_triggers.hdf5'
    if spe == True:
        cache_name = f'timing_{run_number}_{data_key_to_use}_matched_triggers_spe.hdf5'
    df_matched.to_hdf(os.path.join(cache_dir, cache_name), key='df', mode='w')
    print(f'File cached at {cache_dir}/{cache_name}.hdf5')
    return df_matched, ERROR_FLAG

def make_laser_freq_mask_spe(timestamps, rate=5000, tolerance=5e-5,
                             smallOffset=5, pairRange=1000):
    laser_freq_in_hz = rate
    timestamps_per_second = 240e6
    dt_in_timestamps = timestamps_per_second / laser_freq_in_hz
    ##try to find laser triggers by checking delta-T
    starting_idx = -1
    num_pairs = 0
    starting_inds = []
    for i, t in enumerate(timestamps):
        for j in range(pairRange):
            if (i+j) >= len(timestamps):
                break
            delta = timestamps[i+j] - t
            if delta >= dt_in_timestamps - smallOffset and delta <= dt_in_timestamps + smallOffset:
                #print(i, j)
                #print(delta, delta/timestamps_per_second)
                num_pairs += 1
                starting_inds.append(i)
                if starting_idx == -1:
                    starting_idx = i
                    #break
        #if starting_idx != -1:
        #    break

    if starting_idx == -1:
        print('No valid index match for laser!')
        #raise ValueError('No starting index could be found!')
        return np.zeros_like(timestamps, dtype=bool)

    mask_list = []
    valid_range = 1000
    print(f'Number of starting pts: {len(starting_inds)}')
    for ind in tqdm(starting_inds):
        timestamps_shifted = timestamps - timestamps[ind]
        timestamps_in_dt = timestamps_shifted / dt_in_timestamps
        rounded_timestamps = np.round(timestamps_in_dt)
        mask_i = np.isclose(timestamps_in_dt, rounded_timestamps,
                       atol=tolerance, rtol=0)
        min_pt = ind-valid_range
        if min_pt < 0:
            min_pt = 0
        max_pt = ind+valid_range
        if max_pt > len(mask_i):
            max_pt = len(mask_i)-1
        mask_i[:min_pt] = 0
        mask_i[max_pt:] = 0
        mask_list.append(mask_i)

    master_mask = [False] * len(mask_list[0])
    for m in mask_list:
        master_mask = np.logical_or(master_mask, m)
    return master_mask

    ########
    new_mask = np.isclose(timestamps_in_dt, rounded_timestamps,
                       atol=tolerance, rtol=0)
    print(timestamps_in_dt)
    print(num_pairs, np.sum(new_mask))
    print(np.sum(new_mask)/len(timestamps))
    return new_mask

def make_laser_freq_mask(timestamps, rate):
    diffs = np.diff(timestamps)
    laser_freq_in_hz = rate
    timestamps_per_second = 240e6
    dt_in_timestamps = timestamps_per_second / laser_freq_in_hz
    mask = np.logical_and(diffs > dt_in_timestamps - 10,
                       diffs < dt_in_timestamps + 10)
    if np.sum(mask) == 0:
        print('Mask is all False!')
        return np.zeros_like(timestamps, dtype=bool)

    # Find one index where a neighboring trigger is the laser freq away
    starting_idx = np.where(mask)[0][0]

    timestamps_shifted = timestamps - timestamps[starting_idx]
    timestamps_in_dt = timestamps_shifted / dt_in_timestamps
    rounded_timestamps = np.round(timestamps_in_dt)
    new_mask = np.isclose(timestamps_in_dt, rounded_timestamps,
                       atol=1e-3, rtol=0)
    print(f'Mask Info ({len(mask)}): {np.sum(mask)}, {np.sum(new_mask)}')
    return new_mask

def findValidTriggers(df_degg, df_ref):
    ERROR_FLAG = ''

    t_max_degg = np.max(df_degg.mfhTime.values)
    t_min_degg = np.min(df_degg.mfhTime.values)
    t_ref = df_ref.mfhTime.values
    t_ind = df_ref.triggerNum.values
    drift_ref  = df_ref.clockDrift.values
    delay_ref = df_ref.cableDelay.values
    ref_delta = df_ref.delta.values[0]

    ##NOTE: for now ignoring the batching effect
    ##but anyway - batching just means some D-Egg triggers get thrown away, less than 1 in 200

    ##t_ref is already sorted
    ##sort dataframe based on mfhTime
    df_degg.sort_values(by='mfhTime', inplace=True)

    valid_row = [False] * len(df_degg.index)
    df_degg['t_match']          = np.zeros(len(df_degg.index))
    df_degg['matchInd']         = np.zeros(len(df_degg.index))
    df_degg['matchClockDrift']  = np.zeros(len(df_degg.index))
    df_degg['matchCableDelay1'] = np.zeros(len(df_degg.index))
    df_degg['matchCableDelay2'] = np.zeros(len(df_degg.index))
    df_degg['refDelta']         = np.zeros(len(df_degg.index))
    ##then do comparison
    ##looks like some of them need more than 100 ns -- due to the startup time?
    t_tolerance = 20000e-9

    '''
    i = 0
    for tr, drift, delay in tqdm(zip(t_ref, drift_ref, delay_ref), desc='Matching D-Egg and tabletop Times'):
        ttList = (df_degg.mfhTime.values - tr)/1e15 + (df_degg.delta.values - df_ref.delta.values[0])
        ##this number appears to be constant!
        #print( np.max(ttList) - np.min(ttList) )
        mask = np.abs(ttList) <= t_tolerance
        valid_row = np.logical_or(valid_row, mask)
        df_degg.loc[mask, 't_match'] = tr
        df_degg.loc[mask, 'matchClockDrift']  = drift
        delay1, delay2 = delay
        df_degg.loc[mask, 'matchCableDelay1'] = delay1
        df_degg.loc[mask, 'matchCableDelay2'] = delay2
        df_degg.loc[mask, 'refDelta'] = ref_delta
        i += 1

    df_degg['valid'] = valid_row
    print(f'Valid Triggers: {np.sum(valid_row)}')
    if np.sum(valid_row) == 0:
        raise ValueError('No matches found!')

    return df_degg
    '''
    print('Matching Triggers')
    pmt_num = 0
    for port in df_degg.port.unique():
        print(port)
        for channel in [1]:
            print(channel)
            _df_s = df_degg[(df_degg.port == port) & (df_degg.channel == channel)]
            if len(_df_s.index.values) == 0:
                print(f'Port {port} and channel {channel} are empty?')
                continue
            ##loop over each element in the dataframe
            i = 0
            matchList   = np.zeros(len(_df_s.delta.values))
            matchInd    = np.zeros(len(_df_s.delta.values))
            matchDrift  = np.zeros(len(_df_s.delta.values))
            matchDelay1 = np.zeros(len(_df_s.delta.values))
            matchDelay2 = np.zeros(len(_df_s.delta.values))
            validRow    = [False] * len(_df_s.delta.values)
            deltaList   = np.zeros(len(_df_s.delta.values))

            dummy_mask = [False] * len(_df_s.delta.values)

            ##only match within blocks
            for block in _df_s.blockNum.unique():
                _df_ref = df_ref[df_ref.blockNum == block]
                t_ref = _df_ref.mfhTime.values
                drift_ref  = _df_ref.clockDrift.values
                delay_ref = _df_ref.cableDelay.values
                ref_delta = _df_ref.delta.values[0]
                _df = _df_s[_df_s.blockNum == block]

                for td, delta in tqdm(zip(_df.mfhTime.values, _df.delta.values)):
                    valid_row = False
                    ttList = (td - t_ref)/1e15 + (delta - df_ref.delta.values[0])
                    print("delta = ", (delta - df_ref.delta.values[0]))
                    print("ttList = ", ttList)
                    ##this is now a mask over the reference df!
                    mask = np.abs(ttList) <= t_tolerance
                    itrue = np.argwhere(mask > 0)
                    #print(np.abs(ttList))
                    if np.sum(mask) == 1:
                        #print(td, t_ref, (td-t_ref), (td-t_ref)/1e15)
                        validRow[i]    = True
                        # matchList[i]   = t_ref[mask][0]
                        # matchInd[i]    = t_ind[mask][0]
                        # matchDrift[i]  = drift_ref[mask][0]
                        # matchDelay1[i] = delay_ref[mask][0][0]
                        # matchDelay2[i] = delay_ref[mask][0][1]
                        itrue = itrue[0][0]
                        matchList[i]   = t_ref[itrue]
                        matchInd[i]    = t_ind[itrue]
                        matchDrift[i]  = drift_ref[itrue]
                        matchDelay1[i] = delay_ref[itrue][0]
                        matchDelay2[i] = delay_ref[itrue][1]
                        deltaList[i]   = ref_delta
                    elif np.sum(mask) == 0:
                        pass
                    else:
                        print(f'Sum: {np.sum(mask)} was greater than 1!')
                    i += 1

            if np.sum(validRow) == 0:
                warn_msg = f'No matches found in TTS analysis for {port}:{channel}! \n'
                warn_msg = warn_msg + 'Is the linearity data OK? If not, the fiber'
                warn_msg = warn_msg + ' transmission may be bad. New data may need to be collected.'
                warn_msg = warn_msg + ' Contact an expert immediately!'
                #if silence == False:
                #    print(warn_msg)
                #print(warn_msg)
                #ERROR_FLAG = ERROR_FLAG + 'warn_msg'
                #continue
                ##this error is preventing the analysis from finishing
                #raise ValueError(f'No matches at all!')

            _df_s['t_match'] = matchList
            _df_s['matchInd'] = matchInd
            _df_s['matchClockDrift'] = matchDrift
            _df_s['matchCableDelay1'] = matchDelay1
            _df_s['matchCableDelay2'] = matchDelay2
            _df_s['refDelta'] = deltaList
            _df_s['valid'] = validRow
            if pmt_num == 0:
                if len(_df_s.index.values) == 0:
                    raise ValueError(f'Size of _df_s is 0! ({_df_s.channel})')
                new_df = _df_s
            else:
                new_df = pd.concat([new_df, _df_s])
            pmt_num += 1

    return new_df, ERROR_FLAG

##in ns - and other tests
def ks_test(tt_pmt, tt_bins, fit_x, fit_y, centered_tt_pmt,
            degg_name, pmt_name, port, channel, plot_dir):
    ##standard
    h, b_edges = np.histogram(tt_pmt, bins=tt_bins)
    ##centered hist
    c_bins = np.linspace(-6.8, 6.8, 88)
    c_h, c_b_edges = np.histogram(centered_tt_pmt*1e9, c_bins)
    c_h = np.array(c_h, dtype=float)
    p0 = [np.max(c_h), np.median(centered_tt_pmt*1e9), 1]
    p0 = np.array(p0, dtype=float)
    center_m = (c_b_edges[1:] + c_b_edges[:-1]) * 0.5
    center_m = np.array(center_m, dtype=float)
    popt_m, pcov_m = curve_fit(fit_func, center_m, c_h, p0=p0, maxfev=10000)
    c_fit_y = fit_func(center_m, *popt_m)

    cdf = []
    total = 0
    for _h in h:
       total += _h
       cdf.append(total)
    ##normalise the cdf
    cdf = np.array(cdf)/np.max(cdf)

    fcdf = []
    ftotal = 0
    for _y in fit_y:
        ftotal += _y
        fcdf.append(ftotal)
    fcdf = np.array(fcdf)/np.max(fcdf)

    ##find the difference
    m_diff = np.max(abs(cdf - fcdf))

    fig, ax = plt.subplots()
    ax.plot(range(len(cdf)), cdf, color='royalblue', label='Data')
    ax.plot(range(len(fcdf)), fcdf, color='goldenrod', label='Fit')
    ax.set_xlabel('Bin #')
    ax.set_ylabel('CDF')
    ax.legend()
    ax.set_title(f'{port}:{channel}')
    fig.savefig(os.path.join(plot_dir, f'{degg_name}_{pmt_name}_{port}_{channel}_tt_cdf.pdf'))
    plt.close(fig)

    mask = h > 2
    error = np.sqrt(h)
    chi2 = np.nansum(((fit_y[mask] - h[mask]) / error[mask])**2) / (len(h[mask]) - 3)
    pval = 0

    c_mask = c_h > 2
    c_error = np.sqrt(c_h)
    c_chi2 = np.nansum(((c_fit_y[c_mask] - c_h[c_mask]) /
                        c_error[c_mask])**2) / (len(c_h[c_mask]) - 3)

    fig2, ax2 = plt.subplots()
    ax2.plot(range(len(h[mask])), ((fit_y[mask] - h[mask]) / error[mask])**2)
    fig2.savefig(os.path.join(plot_dir, f'{degg_name}_{pmt_name}_{port}_{channel}_chi2.pdf'))

    return m_diff, chi2, pval, c_chi2

def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val

def fit_func(x, spe_norm, spe_peak, spe_width):
    return gauss(x, spe_norm, spe_peak, spe_width)

def calculateTTS(df, plot_dir, laser_freq, silence=False, names_dict={}):
    df_t = df[df.valid == True]
    t_degg = df_t.mfhTime.values
    t_ref = df_t.t_match.values
    ref_delta = df_t.refDelta.values[0]
    print(df_t)
    tt = (t_degg - t_ref) /1e15 + (df_t.delta.values - ref_delta)

    print("Making Plots")

    fig01, ax01 = plt.subplots()
    ax01.plot(range(len(t_ref)), t_ref/1e15, 'o', color='royalblue')
    ax01.set_ylabel('Matched Reference Times [s]')
    ax01.set_xlabel('Index')
    fig01.savefig(os.path.join(plot_dir, 'ref_times.png'), dpi=300)
    plt.close(fig01)

    fig, ax = plt.subplots()
    ax.hist(tt, bins=200, histtype='step', color='royalblue')
    ax.set_xlabel('Transit Time [s]')
    ax.set_ylabel('Entries')
    fig.savefig(os.path.join(plot_dir, 'all_tt.pdf'))
    ax.set_yscale('log')
    fig.savefig(os.path.join(plot_dir, 'all_tt_log.pdf'))
    plt.close(fig)

    portList = []
    channelList = []
    normList = []
    peakList = []
    widthList = []
    ttData = []
    ttBins = []
    fitCenter = []
    fitVals = []
    funcStr = []
    effList = []
    tempList = []
    ksList = []
    chi2List = []
    centeredChi2List = []

    lowEfficiency = 0
    highTTS = 0
    highKS = 0
    highChi2 = 0

    ##separate out between PMTs
    for port in sorted(df_t.port.unique()):
        port = int(port)
        print(f'--- {port} ---')
        for channel in [1]:
            df_pmt = df_t[(df_t.port == port) & (df_t.channel == channel)]
            tt_pmt = (df_pmt.mfhTime.values - df_pmt.t_match.values) /1e15 + (df_pmt.delta.values - ref_delta)
            if len(df_pmt.index.values) == 0:
                print(f'No matched data, skipping {port}')
                continue
            temperature = df_pmt.temperature.values[0]
            try:
                degg_name = df_pmt.deggName.values[0]
            except:
                print('Legacy data without deggName in dataframe. Grabbing from jsons')
                degg_name = names_dict[port]
            if channel == 0:
                pmt_name = df_pmt.lowerPMT.values[0]
            if channel == 1:
                pmt_name = df_pmt.upperPMT.values[0]

            if len(df_pmt) == 0:
                continue

            modStr = f'{degg_name}_{pmt_name}_{port}_{channel}'

            centered_tt = np.zeros([len(df_pmt.blockNum.unique()), 1000])

            eff = 0
            ##loop over blocks
            i = 0
            for block in df_pmt.blockNum.unique():
                _df = df_pmt[df_pmt.blockNum == block]
                _tt = (_df.mfhTime.values - _df.t_match.values) /1e15 + (_df.delta.values - ref_delta)
                mean_tt = np.mean(_tt)
                centering = _tt - mean_tt
                centered_tt[i, :len(centering)] = centering
                i += 1

                num_missed_trigs = np.sum(np.diff(_df.matchInd.values) - 1)
                _eff = (1 - (num_missed_trigs/laser_freq)) * 100
                eff += _eff

            eff = eff / len(df_pmt.blockNum.unique())
            effList.append(eff)
            if eff <= 50:
                lowEfficiency += 1

            centered_tt = centered_tt.flatten()
            mask = centered_tt != 0
            centered_tt = centered_tt[mask]

            bins = np.linspace(np.min(tt_pmt), np.max(tt_pmt), 200)
            hist, edges = np.histogram(tt_pmt, bins=bins)
            p0 = [np.max(hist), np.median(tt_pmt), 0.35 * np.median(tt_pmt)]
            center = (edges[1:] + edges[:-1]) * 0.5

            center = np.array(center, dtype=float)
            hist = np.array(hist, dtype=float)
            p0 = np.array(p0, dtype=float)
            popt, pcov = curve_fit(fit_func, center, hist, p0=p0, maxfev=10000)

            bins = np.linspace(np.min(centered_tt*1e9), np.max(centered_tt*1e9), 200)
            hist, edges = np.histogram(centered_tt*1e9, bins=bins)
            hist = np.array(hist, dtype=float)
            p0 = [np.max(hist), np.median(centered_tt*1e9), 1]
            p0 = np.array(p0, dtype=float)
            center_m = (edges[1:] + edges[:-1]) * 0.5
            center_m = np.array(center_m, dtype=float)
            popt_m, pcov_m = curve_fit(fit_func, center_m, hist, p0=p0, maxfev=10000)

            fig2, ax2 = plt.subplots()
            tt_bins = np.linspace((popt[1]-(np.abs(popt[2])*5))*1e9,
                                  (popt[1]+(np.abs(popt[2])*5))*1e9,
                                  100)
            _hist, _edges = np.histogram(tt_pmt*1e9, bins=tt_bins)
            _p0 = [np.max(_hist), np.median(tt_pmt*1e9), 0.35 * np.median(tt_pmt*1e9)]
            _center = (_edges[1:] + _edges[:-1]) * 0.5
            _center = np.array(_center, dtype=float)
            _hist = np.array(_hist, dtype=float)
            _p0 = np.array(_p0, dtype=float)
            _popt, _pcov = curve_fit(fit_func, _center, _hist, p0=_p0)

            if np.abs(_popt[2]) >= 3.1:
                highTTS += 1

            ax2.hist(tt_pmt*1e9, bins=tt_bins, histtype='step', color='royalblue')
            ax2.set_xlabel(r'Transit Time [ns]')
            ax2.set_ylabel('Entries')
            ax2.set_title(f'D-Egg {port}-{channel}')
            ax2.plot(_center, fit_func(_center, *_popt), color='goldenrod',
                        label=f'{np.abs(_popt[2]):.2f}')
            ax2.legend(title='TTS [ns]')
            fig2.savefig(os.path.join(plot_dir, f'{modStr}_tt.pdf'))
            ax2.set_yscale('log')
            fig2.savefig(os.path.join(plot_dir, f'{modStr}_tt_log.pdf'))
            plt.close(fig2)

            if silence == False:
                print(os.path.join(plot_dir, f'{modStr}_tt.pdf'), f'{modStr}_tt')

            fig2z, ax2z = plt.subplots()
            for blkNum in df_pmt.blockNum.unique():
                df_blk = df_pmt[df_pmt.blockNum == blkNum]
                tt_blk = (df_blk.mfhTime.values - df_blk.t_match.values) /1e15 + (df_blk.delta.values - ref_delta)
                ax2z.hist(tt_blk*1e9, bins=tt_bins, histtype='step', alpha=0.4)
                if blkNum == 10:
                    break
            ax2z.set_xlabel(r'Transit Time [ns]')
            ax2z.set_ylabel('Entries')
            ax2z.set_title(f'D-Egg {port}-{channel}')
            fig2z.savefig(os.path.join(plot_dir, f'{modStr}_tt_blk.pdf'))


            fig2a, ax2a = plt.subplots()
            ax2a.scatter(tt_pmt, df_pmt.charge.values, s=3)
            ax2a.set_xlabel('Transit Time [s]')
            ax2a.set_ylabel('Charge [pC]')
            ax2a.set_title(f'D-Egg {port}-{channel}')
            fig2a.tight_layout()
            fig2a.savefig(os.path.join(plot_dir, f'{modStr}_tt_vs_charge.png'), dpi=300)
            ax2a.set_yscale('log')
            ax2a.set_ylim(1, 250)
            ax2a.set_xlim(5.5e-8, 8.5e-8)
            fig2a.tight_layout()
            fig2a.savefig(os.path.join(plot_dir, f'{modStr}_tt_vs_charge_log.png'), dpi=300)
            plt.close(fig2a)

            fig2aa, ax2aa = plt.subplots()
            xbins = np.linspace(5.5e-8, 8.5e-8, 200)
            ybins = np.logspace(0, 1, 200)
            p2aa = ax2aa.hist2d(tt_pmt, df_pmt.charge.values, bins=[xbins, ybins], cmin=0.01)
            ax2aa.set_xlabel('Transit Time [s]')
            ax2aa.set_ylabel('Charge [pC]')
            ax2aa.set_title(f'D-Egg {port}-{channel}')
            ax2aa.set_yscale('log')
            cbar = fig2aa.colorbar(p2aa[3], ax=ax2aa)
            cbar.set_label('Transit Time [s]')
            fig2aa.tight_layout()
            fig2aa.savefig(os.path.join(plot_dir, f'{modStr}_tt_vs_charge_hist.png'), dpi=300)
            fig2aa.tight_layout()
            plt.close(fig2aa)

            fig2b, ax2b = plt.subplots()
            ax2b.hist(centered_tt*1e9, bins=200, histtype='step', color='royalblue')
            ax2b.set_xlabel(r'Mean Corrected Transit Time [ns]')
            ax2b.set_ylabel('Entries')
            ax2b.set_title(f'D-Egg {port}-{channel}')
            ax2b.plot(center_m, fit_func(center_m, *popt_m),
            color='goldenrod', label=f'{np.abs(popt_m[2]/1e-9):.2f}')
            ax2b.legend(title='TTS [ns]')
            fig2b.savefig(os.path.join(plot_dir, f'{modStr}_tt_mean.pdf'))
            ax2b.set_yscale('log')
            fig2b.savefig(os.path.join(plot_dir, f'{modStr}_tt_mean_log.pdf'))
            plt.close(fig2b)

            print(f'TT Fit Results: {channel}')
            print(f'Efficiency: {eff:.1f} %')
            print('Standard Deviation (Hist), Fit width - [ns]')
            print(np.std(tt_pmt)/1e-9, abs(popt[2])/1e-9)

            ##perform a K-S test for the hist & fit
            ks_stat, chi2, pval, c_chi2 = ks_test(tt_pmt*1e9, tt_bins, _center,
                    fit_func(_center, *_popt), centered_tt,
                    degg_name, pmt_name, port, channel, plot_dir)
            ksList.append(ks_stat)
            chi2List.append(chi2)
            centeredChi2List.append(c_chi2)

            if ks_stat >= 1000:
                highKS += 1
            if c_chi2 >= 3.5:
                highChi2 += 1

            ##save fitting info
            portList.append(port)
            tempList.append(temperature)
            channelList.append(channel)
            normList.append(popt[0])
            peakList.append(popt[1]/1e-9)
            widthList.append(abs(popt[2])/1e-9)
            ttData.append(tt_pmt)
            ttBins.append(tt_bins)
            fitCenter.append(_center)
            fitVals.append(fit_func(_center, *_popt))
            funcStr.append('norm * np.exp(-(x-peak)**2/(2 * width**2))')

            fig3, ax3 = plt.subplots()
            t_ref_plotting = df_pmt.t_match.values - df_pmt.t_match.values[0]
            ax3.plot(t_ref_plotting, tt_pmt, 'o', color='royalblue', linewidth=0)
            ax3.set_xlabel(r'$T_{0}$ [s]')
            ax3.set_ylabel(r'Transit Time [s]')
            ax3.set_title(f'D-Egg {port}-{channel}')
            ax3.set_ylim(np.median(tt_pmt)*0.9, np.median(tt_pmt)*1.1)
            fig3.savefig(os.path.join(plot_dir, f'{modStr}_tt_time.png'), dpi=300)
            plt.close(fig3)


            ##plot block number vs trigger number to see temporal trends
            fig4, ax4 = plt.subplots()
            p4 = ax4.scatter(df_pmt.blockNum, df_pmt.triggerNum, c=tt_pmt)
            ax4.set_xlabel('Block Number')
            ax4.set_ylabel('Block Trigger Number')
            ax4.set_title(f'D-Egg {port}-{channel}')
            cbar = fig4.colorbar(p4, ax=ax4)
            cbar.set_label('Transit Time [s]')
            fig4.tight_layout()
            fig4.savefig(os.path.join(plot_dir, f'{modStr}_block_trigger_num.png'), dpi=350)
            plt.close(fig4)

            fig5, ax5 = plt.subplots()
            ax5.plot(df_pmt.triggerNum, tt_pmt, marker='o', linewidth=0, color='royalblue')
            ax5.set_xlabel('Block Trigger Number')
            ax5.set_ylabel('Transit Time [s]')
            ax5.set_title(f'D-Egg {port}-{channel}')
            fig5.tight_layout()
            fig5.savefig(os.path.join(plot_dir, f'{modStr}_trigger_num_tt.png'), dpi=300)
            plt.close(fig5)

            fig4b, ax4b = plt.subplots()
            p4b = ax4b.scatter(df_pmt.blockNum, df_pmt.triggerNum, c=df_pmt.clockDrift.values)
            ax4b.set_xlabel('Block Number')
            ax4b.set_ylabel('Block Trigger Number')
            ax4b.set_title(f'D-Egg {port}-{channel}')
            cbar = fig4b.colorbar(p4b, ax=ax4b)
            cbar.set_label('Clock Drift')
            fig4b.tight_layout()
            fig4b.savefig(os.path.join(plot_dir, f'{modStr}_block_trigger_num_drift.png'), dpi=350)
            plt.close(fig4b)

            delay1 = []
            delay2 = []
            delay_diff = []
            for delays in df_pmt.cableDelay.values:
                delay1.append(delays[0])
                delay2.append(delays[1])
                delay_diff.append(np.abs(delays[1] - delays[0]))

            fig4c, ax4c = plt.subplots()
            p4c = ax4c.scatter(df_pmt.blockNum, df_pmt.triggerNum, c=delay_diff)
            ax4c.set_xlabel('Block Number')
            ax4c.set_ylabel('Block Trigger Number')
            ax4c.set_title(f'D-Egg {port}-{channel}')
            cbar = fig4c.colorbar(p4c, ax=ax4c)
            cbar.set_label(r'$\Delta$ Cable Delay [s]')
            fig4c.tight_layout()
            fig4c.savefig(os.path.join(plot_dir,
          f'{modStr}_block_trigger_num_delta_delay.png'), dpi=350)
            plt.close(fig4c)

            fig5b, ax5b = plt.subplots()
            ax5b.plot(df_pmt.triggerNum, df_pmt.clockDrift.values,
          marker='o', linewidth=0, color='royalblue')
            ax5b.set_xlabel('Block Trigger Number')
            ax5b.set_ylabel('Clock Drift')
            ax5b.set_title(f'D-Egg {port}-{channel}')
            fig5b.tight_layout()
            fig5b.savefig(os.path.join(plot_dir, f'{modStr}_trigger_num_drift.png'), dpi=300)
            plt.close(fig5b)

            fig6, ax6 = plt.subplots()
            ax6.plot(df_pmt.clockDrift.values, tt_pmt, marker='o', linewidth=0, color='royalblue')
            ax6.set_xlabel('Clock Drift')
            ax6.set_ylabel('Transit Time [s]')
            ax6.set_title(f'D-Egg {port}-{channel}')
            fig6.tight_layout()
            fig6.savefig(os.path.join(plot_dir, f'{modStr}_drift_tt.png'), dpi=300)
            plt.close(fig6)

            fig7, ax7 = plt.subplots()
            ax7.plot(delay_diff, tt_pmt, marker='o', linewidth=0, color='royalblue')
            ax7.set_xlabel(r'$\Delta$ Cable Delay')
            ax7.set_ylabel('Transit Time [s]')
            ax7.set_title(f'D-Egg {port}-{channel}')
            fig7.tight_layout()
            fig7.savefig(os.path.join(plot_dir, f'{modStr}_delta_delay_tt.png'), dpi=300)
            plt.close(fig7)

            #look at clock drift and cable delays for the matched events
            fig8, ax8 = plt.subplots()
            p8 = ax8.scatter(df_pmt.clockDrift.values, df_pmt.matchClockDrift.values, c=tt_pmt)
            ax8.set_xlabel('D-Egg Clock Drift')
            ax8.set_ylabel('Tabletop Clock Drift')
            ax8.set_title(f'D-Egg {port}-{channel}')
            cbar = fig8.colorbar(p8, ax=ax8)
            cbar.set_label(r'Transit Time [s]')
            fig8.tight_layout()
            fig8.savefig(os.path.join(plot_dir, f'{modStr}_clock_drift_correlation.png'), dpi=350)
            plt.close(fig8)

            fig9, ax9 = plt.subplots()
            p9 = ax9.scatter(delay1, df_pmt.matchCableDelay1.values, c=tt_pmt)
            ax9.set_xlabel('D-Egg Cable Delay [s]')
            ax9.set_ylabel('Tabletop Cable Delay [s]')
            ax9.set_title(f'D-Egg {port}-{channel}')
            cbar = fig9.colorbar(p9, ax=ax9)
            cbar.set_label(r'Transit Time [s]')
            fig9.tight_layout()
            fig9.savefig(os.path.join(plot_dir,
          f'{modStr}_cable_delay_1_correlation.png'), dpi=350)
            plt.close(fig9)

            fig10, ax10 = plt.subplots()
            p10 = ax10.scatter(delay2, df_pmt.matchCableDelay2.values, c=tt_pmt)
            ax10.set_xlabel('D-Egg Cable Delay [s]')
            ax10.set_ylabel('Tabletop Cable Delay [s]')
            ax10.set_title(f'D-Egg {port}-{channel}')
            cbar = fig10.colorbar(p10, ax=ax10)
            cbar.set_label(r'Transit Time [s]')
            fig10.tight_layout()
            fig10.savefig(os.path.join(plot_dir,
          f'{modStr}_cable_delay_2_correlation.png'), dpi=350)
            plt.close(fig10)

    data = {'Port': portList, 'Channel': channelList, 'Norm': normList,
            'Peak': peakList, 'Width': widthList, 'Efficiency': effList,
            'ttData': ttData, 'ttBins': ttBins, 'plottingCenter': fitCenter,
            'fitVals': fitVals, 'funcStr': funcStr, 'chi2': chi2List,
            'Centeredchi2': centeredChi2List, 'temperature': tempList}
    new_df = pd.DataFrame(data=data)

    ##report some info to slack about analysis
    msg = 'TTS Analysis Results'
    ##format the values to be legible
    seffList = []
    swidthList = []
    schi2List = []
    c_schi2List = []
    for e, w, c, cc in zip(effList, widthList, chi2List, centeredChi2List):
        seffList.append(f'{e:.1f}')
        swidthList.append(f'{w:.2f}')
        schi2List.append(f'{c:.2f}')
        c_schi2List.append(f'{cc:.2f}')

    _size = len(seffList)
    if silence == False:
        if lowEfficiency != 0:
            print(f'{msg} FAIL {lowEfficiency}/{_size}: Efficiency [%] {seffList}')
        else:
            print(f'{msg} ALL PASS: Efficiency [%] {seffList}')

        if highTTS != 0:
            print(f'{msg} FAIL {highTTS}/{_size}: TTS [ns] {swidthList}')
        else:
            print(f'{msg} ALL PASS: TTS [ns] {swidthList}')

        if highChi2 != 0:
            print(f'{msg} FAIL {highChi2}/{_size}: chi2 Stat {c_schi2List}')
        else:
            print(f'{msg} ALL PASS: chi2 test {schi2List}')

        if highTTS != 0 or lowEfficiency != 0 or highChi2 != 0:
            print(f'Failure Detected in TTS analysis!')
        else:
            print(f'TTS Analysis - All Pass')

        print('Shifter, please record any results which are out of the expected bounds.')

    return new_df

def plot_total_info(df, plot_dir):
    fig1, ax1 = plt.subplots()
    ax1.plot(np.arange(len(df.Port.values)), df.Peak.values, 'o', color='royalblue')
    ax1.set_xlabel('PMT No.')
    ax1.set_ylabel('Peak Position [ns]')
    fig1.savefig(os.path.join(plot_dir, 'all_peak_pos.pdf'))
    plt.close(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot(np.arange(len(df.Port.values)), df.Width.values, 'o', color='royalblue')
    ax2.set_xlabel('PMT No.')
    ax2.set_ylabel('Width [ns]')
    fig2.savefig(os.path.join(plot_dir, 'all_widths.pdf'))
    plt.close(fig2)

    fig3, ax3 = plt.subplots()
    ax3.plot(np.arange(len(df.Port.values)), df.Efficiency.values, 'o', color='royalblue')
    ax3.set_xlabel('PMT No.')
    ax3.set_ylabel('Efficiency %')
    fig3.savefig(os.path.join(plot_dir, 'all_efficiencies.pdf'))
    plt.close(fig3)

    fig4, ax4 = plt.subplots()
    ax4.plot(np.arange(len(df.Port.values)), df.chi2.values, 'o', color='royalblue')
    ax4.set_xlabel('PMT No.')
    ax4.set_ylabel(r'Reduced $\chi^{2}$')
    fig4.savefig(os.path.join(plot_dir, 'all_chi2.pdf'))
    plt.close(fig4)

def openDEggs(file_folder, run_number, cached=False):
    if cached == True:
        df = pd.read_hdf(file_folder)
        return df

    in_file = os.path.join(file_folder, f'total_{run_number:05d}_charge_stamp.hdf5')
    try:
        df = pd.read_hdf(in_file)
    except:
        print(f'File could not be opened, check it exists: {in_file}')
        exit(1)
    return df

def create_database_jsons(df, fit_df, run_number, file_folder=None,
                          remote=False, data_key_to_use='tts_key'):
    known_ports = np.arange(5000, 5016)

    logbook = DEggLogBook()
    print("-- Create database json files --")
    #for port in df.port.unique():
    for port in known_ports:
        for channel in [1]:
            _df = df[(df.port == port) & (df.channel == channel)]
            _df_fit = fit_df[(fit_df.Port == port) & (fit_df.Channel == channel)]
            if len(_df.index) == 0:
                print(f"Skipping Port {port} Channel {channel}")
                continue
            if channel == 0:
                pmt_name = _df.lowerPMT.unique()[0]
                raw_files = _df.files0.unique()[0]
            if channel == 1:
                pmt_name = _df.upperPMT.unique()[0]
                raw_files = _df.files1.unique()[0]
            if remote == True:
                _raw_files = os.path.basename(raw_files)
                raw_files = os.path.join(file_folder, _raw_files)

            result = Result(pmt_name, logbook=logbook,
                            run_number=run_number,
                            remote_path=REMOTE_DATA_DIR)

            try:
                temperature = _df_fit.temperature.values[0]
            except:
                print('WARN! Temperature not set')
                temperature = -999

            json_filenames = result.to_json(
                meas_group='timing',
                raw_files=raw_files,
                folder_name=DB_JSON_PATH,
                efficiency=_df_fit.Efficiency.values[0],
                norm=_df_fit.Norm.values[0],
                peak=_df_fit.Peak.values[0],
                tts=_df_fit.Width.values[0],
                ttData=_df_fit.ttData.values[0],
                ttBins=_df_fit.ttBins.values[0],
                plotC=_df_fit.plottingCenter.values[0],
                fitVals=_df_fit.fitVals.values[0],
                funcStr=_df_fit.funcStr.values[0],
                chi2=_df_fit.Centeredchi2.values[0],
                temperature=temperature,
                filename_add=data_key_to_use)

            run_handler = RunHandler(filenames=json_filenames)
            run_handler.submit_based_on_meas_class()


def analysis_wrapper(run_file, measurement_number="latest", verbose=False, cache_file=None,
                     input_file=None, spe=False,
                     rate=None, remote=False, offline=False,
                     silence=False):

    if offline == True:
        print("Running without creating output database json files")

    list_of_deggs = load_run_json(run_file)
    degg_dict = load_degg_dict(list_of_deggs[0])

    names_dict = {}
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        degg_name = degg_dict['DEggSerialNumber']
        degg_port = degg_dict['Port']
        _d = {degg_port: degg_name}
        names_dict.update(_d)

    pmt = 'LowerPmt'
    data_key = 'TransitTimeSpread'
    run_number = extract_runnumber_from_path(run_file)

    measurement_numbers = get_measurement_numbers(degg_dict, pmt, measurement_number, data_key)
    # if measurement_number == 'latest':
    #     eligible_keys = [key for key in degg_dict[pmt].keys()
    #                      if key.startswith(data_key)]
    #     cts = [int(key.split('_')[1]) for key in eligible_keys]
    #     if len(cts) == 0:
    #         print(f'No measurement found for '
    #               f'{degg_dict[pmt]["SerialNumber"]} '
    #               f'in DEgg {degg_dict["DEggSerialNumber"]}. '
    #               f'Exiting!')
    #         exit(1)
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
        #if audit_ignore_list(list_of_deggs[0], degg_dict, data_key_to_use) == True:
            #continue
    if rate == None:
        # try to get the rate from the DEgg json
        try:
            rate = degg_dict[pmt][data_key_to_use]["LaserFreq"]
        except:
            print('Please specify the rate of the laser with --rate!')
            exit(1)
    rate = int(rate)
    if remote:
        file_folder = degg_dict[pmt][data_key_to_use]['RemoteFolder']
    else:
        file_folder = degg_dict[pmt][data_key_to_use]['Folder']

    if spe == True:
        plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_spe')
    else:
        plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)
        print(f'Created directory: {cache_dir}')
    if cache_file == None:
        ##just give the 'total' file in most cases
        #df_degg, run_number = openDEggs(input_file)
        df_degg = openDEggs(file_folder, run_number)
    if cache_file != None:
        df_matched = openDEggs(cache_file, run_number, cached=True)

    plot_dir = os.path.join(plot_dir, f'{run_number}_{data_key_to_use.split("_")[-1]}')
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)
        print(f'Created directory: {plot_dir}')

    if verbose:
        ##simple checks
        i = 0
        for t in df_ref_data.Time.values:
            print(t, datetime.fromtimestamp(t), datetime.fromtimestamp(t+tabletop_offset))
            if i == 10:
                break
            i += 1
        i = 0
        for t in df_degg.mfhTime.values:
            print(t, datetime.fromtimestamp(t))
            if i == 10:
                break
            i+=1

    if cache_file == None:
        df_ref = checkTabletop(df_degg, plot_dir, rate)
        df_matched, ERROR_FLAG = compareTimes(df_degg, df_ref, plot_dir, cache_dir,
                                  rate, spe, run_number, data_key_to_use)

    fit_df = calculateTTS(df_matched, plot_dir, rate, silence, names_dict)
    plot_total_info(fit_df, plot_dir)

    ##create database json files
    if offline == False:
        create_database_jsons(df_matched, fit_df, run_number, file_folder, remote,
                              data_key_to_use)

    if cache_file == None:
        if ERROR_FLAG != '':
            print(ERROR_FLAG)
    print("Done")

@click.command()
@click.argument('run_file')
@click.option('--measurement_number', '-n', default='latest')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--cache_file', '-c', default=None)
@click.option('--input_file', '-in', default=None)
@click.option('--spe', is_flag=True)
@click.option('--rate', default=None)
@click.option('--remote', is_flag=True)
@click.option('--offline', is_flag=True)
@click.option('--silence', '-s', is_flag=True)
def main(run_file, measurement_number, verbose, cache_file, input_file,
         spe, rate, remote, offline, silence):
    analysis_wrapper(run_file, measurement_number, verbose, cache_file, input_file,
                     spe, rate, remote, offline, silence)

if __name__ == "__main__":
    main()

##end
