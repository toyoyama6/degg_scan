# FAT linearity data read & create average NPE and Peak current list for each filter/PMT
# Show averaged waveform and histgram of NPE & Peak Current for each filter & PMT
# Rreference point is 0.1 because 0.05 is weak
from cProfile import label
import os
import wave
import click
from glob import glob
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import cm
from scipy.optimize import curve_fit

from degg_measurements import RUN_DIR
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH
from degg_measurements.utils import DEggLogBook
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements.utils import load_run_json
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.analysis.analysis_utils import get_run_json
from degg_measurements.analysis.analysis_utils import get_measurement_numbers

from degg_measurements.analysis.linearity.linearity_fit_functions import linearity_current_curve_func
from degg_measurements.analysis.linearity.linearity_fit_functions import linearity_current_curve_func2
from degg_measurements.analysis.linearity.linearity_fit_functions import linearity_current_curve_func3

from chiba_slackbot import send_message
from chiba_slackbot import send_warning, push_slow_mon
from tempfile import NamedTemporaryFile

E_CONST = 1.60217662e-7


def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val


def make_laser_freq_mask(timestamps, fw):
    fw = float(fw)
    timestamps_per_second = 240e6
    diffs = np.diff(timestamps)
    laser_freq_in_hz = 100.
    dt_in_timestamps = timestamps_per_second / laser_freq_in_hz
    mask = np.logical_and(diffs > dt_in_timestamps - 10,
                          diffs < dt_in_timestamps + 10)

    pulses = diffs / timestamps_per_second * laser_freq_in_hz
    _mask = (pulses > 0.0999) & (pulses < 1.0001)
    if np.sum(_mask) > np.sum(mask):
        mask = _mask

    if np.sum(mask) == 0:
        print('<make_laser_freq_mask>: no valid mask')
        if fw == 0.1:
            print('No valid triggers found for the 10% filter. Exiting')
            exit(1)
        return np.zeros_like(timestamps, dtype=bool)

    #This part was to verify that the filter above is actually working
    #But because it was done on bad data it lead to bad results.
    #It's not needed anymore.
    #Find one index where a neighboring trigger is the laser freq away
    # starting_idx = np.where(mask)[0][0]

    # timestamps_shifted = timestamps - timestamps[starting_idx]
    # timestamps_in_dt = timestamps_shifted / dt_in_timestamps
    # rounded_timestamps = np.round(timestamps_in_dt)
    # new_mask = np.isclose(timestamps_in_dt, rounded_timestamps,
    #                       atol=1e-3, rtol=0)

    # print(f'Mask Info - sum: {np.sum(mask)}, {np.sum(new_mask)}')
    # return new_mask
    return np.append(mask, mask[-1])


def fit_charge_and_peak_current(PMT, data_folder, plot_dir, data_dir):
    print('---' * 20)
    print(PMT)
    npe_ide_list = []
    ip_ide_list = []
    fit_mean_list =[]
    fit_std_list = []
    fit_ipk_list = []
    fit_ipk_std_list = []
    files = sorted(glob(os.path.join(data_folder, PMT + '*.hdf5')))

    fw_settings = []
    temperatures = []
    warn_status = False
    for file_i in files:
        print(f' --- File: {file_i} --- ')
        # 5001X128 data 5001 waveforms
        try:
            e_id, time, waveforms, ts, pc_t, datetime_timestamp, params = read_data(file_i)
        except OSError:
            print(f'Problem reading {file_i}')
            continue

        temperatures.append(float(params['degg_temp']))
        fw = params['strength']
        fw_settings.append(fw)

        nevent = len(e_id)
        print(f'nEvents: {nevent}')
        npe_main_mean_list=[]
        npe_main_std_list=[]
        ip_main_mean_list=[]
        ip_main_std_list =[]

        mask = make_laser_freq_mask(ts, fw)
        if np.sum(mask)/len(mask) <= 0.78 and float(fw) > 0.01:
            send_warning(f'Linearity Analysis: data has low efficiency! {file_i} - ({np.sum(mask)}/{len(mask)})')
            warn_status = True
        elif np.sum(mask)/len(mask) < 0.3 and float(fw) <= 0.01:
            send_warning(f'Linearity Analysis: data has low efficiency! {file_i} - ({np.sum(mask)}/{len(mask)})')
            warn_status = True
        if np.sum(mask) == 0:
            print(f'No laser triggers found for {PMT} {fw}. Skipping it!')
            continue
        waveforms = waveforms[mask]

        x_l1_list = time[0, 0:128] * CALIBRATION_FACTORS.fpga_clock_to_s
        yy = np.zeros(128)
        # Get the base line
        pre_trigger_wf = waveforms[:, :10]
        baselines = np.mean(pre_trigger_wf, axis=1)

        # charge pC
        charges = get_charges(waveforms*CALIBRATION_FACTORS.adc_to_volts,
                              gate_start=13,
                              gate_width=15,
                              baseline=baselines*CALIBRATION_FACTORS.adc_to_volts)

        npes = charges / 1.602 # PE
        #print(npes)
        # if fw in ["0.05", "0.1"]:
        #     # skip abnormal
        #     npes = npes[npes <= 80]

        #Peak current
        waveforms = (waveforms - baselines[:, np.newaxis]) * \
            CALIBRATION_FACTORS.adc_to_volts
        ip = np.max(waveforms, axis=1) / 50 * 1000 #mA
        # if fw in ["0.05", "0.1"]:
        #     ip = ip[ip <= 8]

        min_wf = 0
        max_wf = 0
        for i, wf in enumerate(waveforms):
            if np.max(wf) > np.max(waveforms[max_wf]):
                max_wf = i
            if np.max(wf) < np.max(waveforms[min_wf]):
                min_wf = i

        # average waveform
        ym = np.mean(waveforms, axis=0)
        fig = plt.figure(figsize=(15,3))
        ax1 = fig.add_subplot(1,3,1)
        ax2 = fig.add_subplot(1,3,2)
        ax3 = fig.add_subplot(1,3,3)
        ax1.set_title(f"averaged waveform [{len(waveforms)} waveforms]")
        ax1.set_ylim(-0.1, 1.4)
        ax1.set_xlim(0E-9, 500E-9)
        ax1.grid(linewidth=1)
        #ax1.tick_params(labelsize=16)
        ax1.plot(x_l1_list, ym, label="average waveform", color="tab:blue")
        ax1.plot(x_l1_list, waveforms[min_wf], label="smallest waveform", color="tab:blue", alpha=0.5)
        ax1.plot(x_l1_list, waveforms[max_wf], label="largest waveform", color="tab:blue", alpha=0.5)
        ax1.legend()

        # Mean & Error(simple)
        npe0_mean = np.mean(npes)
        npe0_std = np.std(npes)
        ip_mean= np.mean(ip)
        ip_std = np.std(ip)

        #histogram fit for NPE
        # Use different binning for the two lowest filter settings
        # For these settings we are in the PE range
        max_lim_0010 = 25
        max_lim_0025 = 100
        if fw == "0.01":
            bins = np.linspace(0, max_lim_0010, 101)

        elif fw == "0.025":
            bins = np.linspace(0, max_lim_0025, 101)
        else:
            bins = np.linspace(np.min(npes), np.max(npes), 101)

        hist, edges = np.histogram(npes, bins=bins)
        center = (edges[1:] + edges[:-1]) * 0.5
        init_norm = np.max(hist)
        # init_peak = np.abs(center[np.argmax(hist)])
        init_peak = npe0_mean
        init_width = 0.25 * init_peak
        p0 = [init_norm, init_peak, init_width]
        bounds = [(0.01 * init_norm, init_peak * 0.2, 0.),
                  (10. * init_norm, init_peak * 2, 3. * init_width)]
        # try to limit the histogram around the mean to make fitting with lots of
        # darknoise easier
        if fw == "0.01":
            # special limits for fitting for the lowest setting, because it's so close to 0.
            fit_min = 0.
            fit_max = init_peak * 2.5
        else:
            fit_min = init_peak * 0.4
            fit_max = init_peak * 2.5
        fit_mask = np.logical_and(center > fit_min,
                                  center < fit_max)
        try:
            popt, pcov = curve_fit(gauss, center[fit_mask], hist[fit_mask], p0=p0, bounds=bounds)
        except RuntimeError:
            popt = np.zeros_like(p0)
            pcov = np.zeros(9).reshape(len(p0), len(p0))
        except ValueError:
            popt = np.zeros_like(p0)
            pcov = np.zeros(9).reshape(len(p0), len(p0))
        # mean and std by gauss fit
        fit_mean = popt[1]
        fit_std = popt[2] / np.sqrt(np.sum(mask))
        fit_mean_list.append(fit_mean)
        fit_std_list.append(fit_std)

        # histogram of chage distribution for each section
        ax2.set_title("# NPE distribution ")
        ax2.set_xlabel("NPE (PE)")
        ax2.set_ylabel("# of count")
        # Indicate the fit reagion in the plot
        # if fit_max is higher that max(center), only plot till there
        if fit_max > center[-1]:
            fit_max = center[-1]
        ax2.axvspan(fit_min, fit_max, color="tab:orange", alpha=0.2,
                        label="Fit range")
        ax2.errorbar(center, hist,
                     xerr=np.diff(edges)*0.5,
                     yerr=np.sqrt(hist),
                     fmt='none',
                     label="Data")
        ax2.plot(center, gauss(center, *popt),
                     label=f"Gaussian fit (m={fit_mean:.2f})")
        ax2.legend()

        #histgrm fit for Ip
        # Use different binning for the two lowest filter settings
        # For these settings we are in the PE range
        if fw == "0.01":
            bins = np.linspace(0, max_lim_0010/10, 101)
        elif fw == "0.025":
            bins = np.linspace(0, max_lim_0025/10, 101)
        else:
            bins = np.linspace(np.min(ip), np.max(ip), 101)

        hist2, edges2 = np.histogram(ip, bins=bins)
        center2 = (edges2[1:] + edges2[:-1]) * 0.5
        init_norm = np.max(hist2)
        # init_peak = center2[np.argmax(hist2)]
        init_peak = ip_mean
        init_width = 0.35 * init_peak
        p0 = [init_norm, init_peak, init_width]

        bounds2 = [(0.01 * init_norm, init_peak * 0.2, 0.),
                  (10. * init_norm, init_peak * 2, 3. * init_width)]

        # try to limit the histogram around the mean to make fitting with lots of
        # darknoise easier
        if fw == "0.01":
            # special limits for fitting for the lowest setting, because it's so close to 0.
            fit_min2 = 0.
            fit_max2 = init_peak * 2.5
        else:
            fit_min2 = init_peak * 0.4
            fit_max2 = init_peak * 2.5
        fit_mask2 = np.logical_and(center2 > fit_min2,
                                   center2 < fit_max2)
        try:
            popt2, pcov = curve_fit(gauss, center2[fit_mask2], hist2[fit_mask2], p0=p0, bounds=bounds2)
        except RuntimeError:
            popt2 = np.zeros_like(p0)
        except ValueError:
            popt2 = np.zeros_like(p0)
        fit_ipk = popt2[1]
        fit_ipk_std = popt2[2]/np.sqrt(np.sum(mask))
        # fit_ipk_std = np.sqrt(pcov[1, 1])
        fit_ipk_list.append(fit_ipk)
        fit_ipk_std_list.append(fit_ipk_std)

        # histogram of chage distribution for each section
        ax3.set_title("# Peak current distribution ")
        ax3.set_xlabel("Peak current (mA)")
        ax3.set_ylabel("# of count")
        # Indicate the fit reagion in the plot
        # if fit_max is higher that max(center), only plot till there
        if fit_max2 > center2[-1]:
            fit_max2 = center2[-1]
        ax3.axvspan(fit_min2, fit_max2, color="tab:orange", alpha=0.2,
                    label="Fit range")
        ax3.errorbar(center2, hist2,
                     xerr=np.diff(edges2)*0.5,
                     yerr=np.sqrt(hist2),
                     fmt='none',
                     label="Data")
        ax3.plot(center2, gauss(center2, *popt2),
                 label=f"Gaussian fit (m={fit_ipk:.2f})")
        ax3.legend()
        fig.savefig(os.path.join(plot_dir, f'pmt_{PMT}_fw_{fw}.pdf'),
                    bbox_inches='tight')

        print(f"Filter %= {fw}")
        print(f"NPE mean(Observed) = {npe0_mean:.3f}",
              f" NPE_fit = {fit_mean:.3f}",
              f" STD NPE mean = {npe0_std:.3f}",
              f"STD NPE fit = {fit_std:.3f}")
        print(f"peak current mean = {ip_mean:.5f}",
              f"Ip_fit = {fit_ipk:.3f}",
              f"STD Ipeak mean = {ip_std:.5f}",
              f"STD Ip fit= {fit_ipk_std:.3f}")

        # create ideal PE
        ref_fw = 0.05
        if fw == str(ref_fw):  # 5% ideal = 5% observe
            npe_ref = fit_mean
            npe_ide = fit_mean
            ip_ref = fit_ipk
            ip_ide = fit_ipk
        # elif fw == "0.05":  # reference because 0.05 is too weak
        #     npe_ide = fit_mean
        #     ip_ide = fit_ipk
        elif float(fw) < 0.1:
            npe_ide = fit_mean
            ip_ide = fit_ipk
        else:
            npe_ide = (npe_ref * float(fw) / ref_fw)
            ip_ide  = (ip_ref * float(fw) / ref_fw)

        npe_ide_list.append(npe_ide)
        ip_ide_list.append(ip_ide)

    # save PMT linearity data for each PMT
    dat = np.vstack(
        (npe_ide_list, fit_mean_list,
         fit_std_list, ip_ide_list,
         fit_ipk_list, fit_ipk_std_list))
    sflname = os.path.join(data_dir, PMT + "FAT_ide_obs_r01")
    np.save(sflname, dat)

    if warn_status == True:
        warn_msg = f'{PMT} had at least 1 setting with a very low efficiency. \n'
        warn_msg = 'The current shifter should log this incident & contact the expert shifter. \n'
        warn_msg = warn_msg + 'If available, refer to the TTS data - does it show a similar issue? \n'
        warn_msg = warn_msg + 'If so, this may be a problem with the optical fibre. \n'
        warn_msg = warn_msg + f'See {plot_dir}'
        send_warning(warn_msg)

    return files, dat, fw_settings, temperatures


def plot_individual_linearity_curve(PMT,
                                    run_number,
                                    plot_dir,
                                    data_key,
                                    files,
                                    data,
                                    fw_settings,
                                    temperatures,
                                    logbook):
    if len(data[0]) < 3:
        print('Found less than 3 valid linearity points. Skipping PMT!')
        return None, None
    # divide each list
    npe_ide = data[0][0:] # ideal NPE
    npe_obs = data[1][0:] # observed NPE
    npe_std = data[2][0:] # observed NPE std
    ipk_ide = data[3][0:] # ideal Peak Current
    ipk_obs = data[4][0:] # Observe Peak Current
    ipk_std = data[5][0:] # Observed Peak Current Std
    corrected_ipk_ide = (ipk_ide /
        CALIBRATION_FACTORS.mainboard_peak_compression_factor)
    # plot NPE and Ip
    fig, ax = plt.subplots()
    fig_i, ax_i = plt.subplots()
    fig_ic, ax_ic = plt.subplots()
    ax.scatter(npe_ide, npe_obs, marker='o', label=PMT)
    ax_i.scatter(ipk_ide, ipk_obs,  marker='o', label=PMT)
    ax_ic.scatter(corrected_ipk_ide, ipk_obs,
                  marker='o', label=PMT)

    min_num = 2
    # fitting NPE
    npe_min = 1
    npe_max = 5e3
    xnew_npe = np.logspace(np.log10(npe_min), np.log10(npe_max) ,100)
    #mask = np.logical_and(npe_ide >= 0.5, npe_obs >= 0.5)
    mask = np.logical_and(npe_ide >= 0.5, npe_obs >= 0.5)
    if np.sum(mask) <= min_num:
        print(f'Skipping {PMT}. Fitted NPE are all below 0.5!')
        return None, None
    try:
        p0_charge=[3000 , 77 , 290]
        popt_charge, pcov_charge = curve_fit(
            linearity_current_curve_func,
            npe_ide[mask],
            npe_obs[mask],
            p0=p0_charge,
            maxfev=100000)
    except RuntimeError:
        popt_charge = np.zeros_like(p0_charge)
        pcov_charge = np.zeros_like(p0_charge)
    except ValueError:
        popt_charge = np.zeros_like(p0_charge)
        pcov_charge = np.zeros_like(p0_charge)
    print(popt_charge)
    print(pcov_charge)

    # plot y=x
    ax.plot([npe_min,npe_max], [npe_min,npe_max], '--', color='grey')
    # plot fitting curve for NPE
    ax.plot(xnew_npe,
            linearity_current_curve_func(xnew_npe, *popt_charge),
            ':', c='k')
    ax.set_xlabel("Ideal NPE / pe",
                  fontsize=16)
    ax.set_ylabel("Observed NPE / pe",
                  fontsize=16)
    ax.set_xlim(npe_min, npe_max)
    ax.set_ylim(npe_min, npe_max)
    ax.set_yscale('log')
    ax.set_xscale('log')
    ax.tick_params(labelsize=16)
    ax.grid(which='minor', alpha=0.2)
    ax.grid(which='major')

    fpath = os.path.join(plot_dir,f'{PMT}_NPE_ideal_vs_observed.pdf')
    fig.savefig(fpath,bbox_inches='tight')

    if logbook != None:
        # we also save a png and send that over slackbot
        # but only do this when we're _not_ in offline mode (ie logbook!=None)
        fpath_png = os.path.join(plot_dir,f'{PMT}_NPE_ideal_vs_observed.png')
        fig.savefig(fpath_png, bbox_inches='tight')
        push_slow_mon(fpath_png, "{}_NPE ideal vs obs".format(PMT))
        os.remove(fpath_png)


    # fitting Ip
    i_min = 0.05
    i_max = 200
    xnew_ipk = np.logspace(np.log10(i_min), np.log10(i_max) ,100)
    mask = np.logical_and(ipk_ide >= 0.05, ipk_obs >= 0.05)
    if np.sum(mask) <= min_num:
        print(f'Skipping {PMT}. Fitted Currents are all below 0.5!')
        return None, None
    try:
        p0_current=[60 , 4 , 3]
        popt_current, pcov_current = curve_fit(
            linearity_current_curve_func,
            ipk_ide[mask],
            ipk_obs[mask],
            p0=p0_current,
            maxfev=100000)
    except RuntimeError:
        popt_current = np.zeros_like(p0_current)
        pcov_current = np.zeros_like(p0_current)
    except ValueError:
        popt_current = np.zeros_like(p0_current)
        pcov_current = np.zeros_like(p0_current)
    print(popt_current)
    print(pcov_current)

    #plot y=x
    ax_i.plot([i_min,i_max], [i_min,i_max], '--', color='grey')
    # plot fitting curve for Peak Current
    ax_i.plot(xnew_ipk,
              linearity_current_curve_func(xnew_ipk, *popt_current),
              ':', c='r')
    ax_i.set_xlabel("Ideal Peak Current / mA",
                    fontsize=16)
    ax_i.set_ylabel("Observed Peak Current / mA",
                    fontsize=16)
    ax_i.set_xlim(i_min, i_max)
    ax_i.set_ylim(i_min, i_max)
    ax_i.set_yscale('log')
    ax_i.set_xscale('log')
    ax_i.tick_params(labelsize=16)
    ax_i.grid(which='minor', alpha=0.2)
    ax_i.grid(which='major')
    fig_i.savefig(os.path.join(plot_dir,
                               f'{PMT}_current_ideal_vs_observed.pdf'),
                  bbox_inches='tight')

    # Calc chi2/ndf
    def chi2(obs, exp, unc, n_fitparams):
        chi2 = np.sum((obs - exp)**2 / unc**2)
        ndof = len(obs) - n_fitparams
        return chi2 / ndof

    unc = np.sqrt(npe_obs) / npe_obs * ipk_obs

    chi2_val = chi2(
        ipk_obs,
        linearity_current_curve_func(ipk_ide, *popt_current),
        unc,
        len(popt_current))

    # fitting corrected Ip
    xnew_ipk = np.logspace(np.log10(1), np.log10(100) ,100)
    mask = np.logical_and(corrected_ipk_ide >= 0.5, ipk_obs >= 0.5)
    if np.sum(mask) <= min_num:
        print(f'Skipping {PMT}. Fitted Currents are all below 0.5!')
        return
    try:
        popt, pcov = curve_fit(linearity_current_curve_func3,
                           corrected_ipk_ide[mask],
                           ipk_obs[mask],
                           p0=[50, 2, 1, 0.6],
                           maxfev=100000)
    except:
        print('Fitting Failed!')
        popt = None
        pcov = None
    print(popt)
    print(pcov)
    # return None, None

    #plot y=x
    ax_ic.plot([1,100], [1,100], '--', color='grey')
    # plot fitting curve for Peak Current
    ax_ic.plot(xnew_ipk,
               linearity_current_curve_func3(xnew_ipk, *popt),
               ':', c='r')
    ax_ic.set_xlabel("Ideal Peak Current / mA",
                     fontsize=16)
    ax_ic.set_ylabel("Observed Peak Current / mA",
                     fontsize=16)
    ax_ic.set_xlim(1, 100)
    ax_ic.set_ylim(1, 100)
    ax_ic.set_yscale('log')
    ax_ic.set_xscale('log')
    ax_ic.tick_params(labelsize=16)
    ax_ic.grid(which='minor', alpha=0.2)
    ax_ic.grid(which='major')
    fig_ic.savefig(
        os.path.join(plot_dir,
                     f'{PMT}_current_ideal_vs_observed_corrected.pdf'),
        bbox_inches='tight')

    charge_true_val = 200 # PE
    charge_fitted_val = linearity_current_curve_func(
        charge_true_val, *popt_charge)

    current_true_val = 10 # mA
    current_fitted_val = linearity_current_curve_func(
        current_true_val, *popt_current
    )

    ##offline support
    if logbook == None:
        return chi2_val, popt_current

    result = Result(PMT,
                    logbook=logbook,
                    run_number=run_number,
                    remote_path=REMOTE_DATA_DIR)
    json_filenames = result.to_json(
        meas_group='linearity',
        raw_files=files,
        folder_name=DB_JSON_PATH,
        filename_add=data_key,
        ideal_charge=npe_ide.tolist(),
        observed_charge=npe_obs.tolist(),
        ideal_current=ipk_ide.tolist(),
        observed_current=ipk_obs.tolist(),
        used_filters=fw_settings,
        temperatures=temperatures,
        temperature=np.mean(temperatures),
        ratio_at_200pe=charge_fitted_val/charge_true_val,
        ratio_at_10mA=current_fitted_val/current_true_val
    )

    run_handler = RunHandler(filenames=json_filenames)
    run_handler.submit_based_on_meas_class()
    return chi2_val, popt_current


def npe_comparison(data, fw_settings, plot_dir):
    font_size = 10
    cmap = cm.get_cmap('magma')
    colors = iter(cmap(np.arange(len(data))/(len(data)-1)))
    # All points in one plot
    fig, ax = plt.subplots()
    for pmt, obs_npes in data.items():
        ax.plot(fw_settings, obs_npes, 'o', alpha=0.5, label=f"{pmt}", color=next(colors))

    ax.set_xlabel("Filterwheel setting",
                fontsize=font_size)
    ax.set_ylabel("Observed NPE / pe",
                fontsize=font_size)
    y_limits = ax.get_ylim()
    y_min = y_limits[0]
    y_max = y_limits[1]
    y_min = y_max - ((y_max - y_min)/3)*4
    ax.legend(bbox_to_anchor=(0, 0, 1, 0), loc="lower left", mode="expand", ncol=4, handletextpad=0.05)
    ax.set_ylim((y_min, y_max))
    #ax.set_xlim(0.05, 1.05)
    #ax.set_ylim(10, 1e3)
    ax.tick_params(labelsize=font_size)

    fig.savefig(os.path.join(plot_dir,
                            f'combined_npe_observed.pdf'),
                bbox_inches='tight')


def analysis_wrapper(run_json, measurement_number="latest", remote=False, offline=False):
    run_json, run_number = get_run_json(run_json)
    list_of_deggs = load_run_json(run_json)
    measurement_type = "LinearityMeasurement"

    if offline != True:
        logbook = DEggLogBook()
    else:
        logbook = None
    chi2_vals = []
    current_popts = []
    observed_npe = {}

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        for pmt in ['LowerPmt', 'UpperPmt']:
            pmt_id = degg_dict[pmt]['SerialNumber']
            measurement_numbers = get_measurement_numbers(
                degg_dict, pmt, measurement_number,
                measurement_type)


            for m_num in measurement_numbers:
                run_plot_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'figs', f'run_{run_number}_linearity_{m_num}')
                run_data_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'data', f'run_{run_number}_linearity_{m_num}')
                if not os.path.isdir(run_plot_dir):
                    os.makedirs(run_plot_dir)
                if not os.path.isdir(run_data_dir):
                    os.makedirs(run_data_dir)

                data_key_to_use = measurement_type + f'_{m_num:02d}'
                if audit_ignore_list(degg_file, degg_dict, data_key_to_use) == True:
                    continue
                if remote:
                   data_dir = degg_dict[pmt][data_key_to_use]['RemoteFolder']
                else:
                   data_dir = degg_dict[pmt][data_key_to_use]['Folder']
                if data_dir == 'None':
                    print('data_dir is None, skipping measurement.')
                    continue
                files, data, fw_settings, temps = fit_charge_and_peak_current(
                    pmt_id,
                    data_dir,
                    run_plot_dir,
                    run_data_dir
                )
                chi2_v, popt_current = plot_individual_linearity_curve(
                    pmt_id,
                    run_number,
                    run_plot_dir,
                    data_key_to_use,
                    files,
                    data,
                    fw_settings,
                    temps,
                    logbook
                )
                chi2_vals.append(chi2_v)
                current_popts.append(popt_current)
                observed_npe[pmt_id] = data[1][0:]
                send_message(f'Linearity Analysis Finished for {pmt_id}')

    npe_comparison(observed_npe, fw_settings, run_plot_dir)
    print(chi2_vals)
    np.save('linearity_pmt_fit_params.npy', current_popts)
    fatcat_link = 'https://hercules.icecube.wisc.edu/upgrade/fatcat/devices'
    send_message(f'Linearity Analysis Finished - please check {fatcat_link}')

@click.command()
@click.argument('run_json')
@click.option('--measurement_number', '-n', default='latest')
@click.option('--remote', is_flag=True)
@click.option('--offline', is_flag=True)
def main(run_json, measurement_number, remote, offline):
    analysis_wrapper(run_json, measurement_number, remote, offline)


if __name__ == '__main__':
    main()

