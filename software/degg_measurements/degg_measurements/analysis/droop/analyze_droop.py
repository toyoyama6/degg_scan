import sys
import os
import click
from glob import glob
import numpy as np
import tables
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit
from scipy.optimize import least_squares
from scipy.optimize import brentq
from scipy.signal import find_peaks
from scipy.stats import norm
from scipy.ndimage import gaussian_filter1d

from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges, calc_charge
from degg_measurements.utils import get_spe_avg_waveform
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import DEggLogBook
from degg_measurements.analysis import Result
from degg_measurements.utils import extract_runnumber_from_path

from degg_measurements.utils.wfana import \
    get_highest_density_region_charge
from degg_measurements.analysis import calc_baseline


E_CONST = 1.60217662e-7
TIME_SCALING = 1 / 240e6
VOLT_SCALING = 0.075e-3


def fit_baseline(x, E):
    val = E * (1+x)
    return val


def gauss(x, norm, peak, width):
    val = norm * np.exp(-(x-peak)**2/(2 * width**2))
    return val


def fit_func(x, spe_norm, spe_peak, spe_width):
    x_vals = x[0]
    return gauss(x_vals, spe_norm, spe_peak, spe_width)


def plot_corrected_wf(x_value, y_values, num, pmt_id, min_y, max_y):
    baseline = get_baseline(pmt_id)
    Corrected_droop, Corrected_undershoot, Original_waveform, tau_droop, tau_undershoot = correct_droop_undershoot(x_value, y_values, baseline)
    Corrected_Original = Corrected_droop - (y_values - baseline)
    peaks, _ = find_peaks(Corrected_droop, height=18)
    index_start, index_stop = get_start_end(x_value, Corrected_Original)
    laser_charge = calc_charge(x_value*TIME_SCALING, Corrected_droop*VOLT_SCALING, index_start, index_stop)
    after_charge = calc_charge(x_value*TIME_SCALING, Corrected_droop*VOLT_SCALING, index_stop+1, int(x_value[-1]))

    fig, (ax1, ax2) = plt.subplots(1, 2)
    fig.suptitle(f'PMT {pmt_id}', fontsize=20)
    ax1.set_title('Corrected and Original wavefoms',fontsize=18)
    ax1.tick_params(axis='x', labelsize=16)
    ax1.tick_params(axis='y', labelsize=16)
    ax1.plot(x_value, Corrected_droop, '-', linewidth = 2, label=rf'Corrected $\tau$={tau_droop*1e6:.1f}$\mu$s')
    ax1.plot(x_value, (y_values-baseline), linestyle = '--', lw =2,  color='orangered', linewidth = 1, alpha = 0.8,  label='Original Waveform')
    ax1.set_xlabel('bins', fontsize = 18)
    ax1.set_ylabel('ADC counts', fontsize = 18)
    ax1.grid(linestyle='dotted')
    #ax1.set_xlim(490, 510)
    ax1.legend(loc='best', fontsize = 12)

    ax2.set_title(f'Corrected waveform - Original waveform',fontsize=18)
    ax2.tick_params(axis='x', labelsize=16)
    ax2.tick_params(axis='y', labelsize=16)
    ax2.plot(x_value, Corrected_Original, color='indigo', linewidth = 2, label=r'Corrected$-$Original')
    ax2.set_xlabel('bins', fontsize = 18)
    ax2.set_ylabel('Corrected Waveform - Original Waveform (ADC)', fontsize = 18)
    ax2.grid(linestyle='dotted')
    #ax2.set_xlim(490,510)
    ax3 = ax2.twinx()
    smooth = gaussian_filter1d(Corrected_Original, 10)
    #ax2.plot(x_value, smooth, color='k', linewidth = 1 , alpha = 0.8, linestyle = '--', label='Smoothed Curve')
    #ax2.legend(loc='best', fontsize = 14)

    m = np.diff(smooth)/np.diff(x_value)
    m_diff = np.diff(m)
    mask_start = m_diff == np.max(m_diff)
    mask_end = m_diff == np.min(m_diff)
    mask = peaks >= x_value[1:-1][mask_end]
    ax1.plot(x_value[peaks[mask]], Corrected_droop[peaks[mask]], 'rx', label='Afterpulse peaks')
    ax2.plot(x_value[peaks[mask]], Corrected_Original[peaks[mask]], 'rx', linewidth = 3, label='Afterpulse peaks')
    ax2.axvspan(x_value[1:-1][mask_start], x_value[1:-1][mask_end], facecolor='royalblue', alpha=0.2, label = f'Laser charge = {laser_charge:.1f} pC')
    ax2.axvspan(x_value[1:-1][mask_end], x_value[-1], facecolor='red', alpha=0.2, label = f'After laser charge = {after_charge:.1f} pC')

    ax3.plot(x_value[:-1], m, color='green', linewidth = 1, label='Slope')
    ax3.plot(x_value[1:-1], m_diff, color='orangered', linewidth = 1, label='diff_slope', linestyle = '--')
    ax3.tick_params(axis='y', labelsize=16)
    ax3.set_ylabel('Slope axis', fontsize=18)

    # ask matplotlib for the plotted objects and their labels
    lines, labels = ax2.get_legend_handles_labels()
    lines2, labels2 = ax3.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='center right', fontsize = 12)
    fig.set_size_inches(18.5, 8.5, forward=True)
    plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/random_wf/droop_measurement/charge_outliers/PMT{pmt_id}_correctedwf{num}_grad.png', bbox_inches='tight')
    #plt.show()
    plt.clf()
    plt.cla()
    plt.close()

def make_random_correction_plot(files, num, pmt_id):
    for j, file_name in enumerate(files):
        e_id, time, waveforms, ts, pc_t, params = read_data(file_name)
        for i in range(num):
            min_y = 7700#np.min(waveforms)
            max_y = 10600#np.max(waveforms)
            rd_num = np.random.randint(len(time))
            plot_corrected_wf(time[rd_num], waveforms[rd_num], i,  pmt_id, min_y, max_y)


def correction_algorithm(tau, dt, Y):
    A = (tau/dt) * (1-np.exp(-dt/tau))
    S = 0
    X0 = (1/A * Y[0])
    X = [X0]
    for j in range(1, len(Y)):
        sj = X[j-1] + S*np.exp(-dt/tau)
        xj = (1/A) * Y[j] + (A*dt)/tau * sj
        S = sj
        X.append(xj)
    return X


def correct_droop_undershoot(x_value, y_values, baseline):
    #mean values of the constants --update to take the values directly from the database!!!
    p0 = 4.536475587728131e-06
    p1 = 2.728386839836242e-05
    p2 = 29.50883205770401
    p3 = 4.246080961487583e-06
    p4 = 2.7143255325039317e-05
    p5 = 30.620432988018425
    temp = 25 #room temperature
    tau_droop = p0 + p1/(1+np.exp(-temp/p2))
    tau_undershoot = p3 + p4/(1+np.exp(-temp/p5))

    Y = y_values - baseline
    dt = TIME_SCALING
    Corrected_droop = correction_algorithm(tau_droop, dt, Y)
    Corrected_undershoot = correction_algorithm(tau_undershoot, dt, Y)
    return np.asarray(Corrected_droop), np.asarray(Corrected_undershoot), Y, tau_droop, tau_undershoot


def get_start_end(x_value, Corrected_Original):
    smooth = gaussian_filter1d(Corrected_Original, 10)
    m = np.diff(smooth)/np.diff(x_value)
    m_diff = np.diff(m)
    mask_start = m_diff == np.max(m_diff)
    mask_end = m_diff == np.min(m_diff)
    start = x_value[1:-1][mask_start]
    end = x_value[1:-1][mask_end]
    return int(start), int(end)


def get_baseline(pmt_id):
    filename = f'/home/scanbox/data/develop/baseline/20201007_06/{pmt_id}.hdf5'
    foo = tables.open_file(filename)
    data = foo.get_node('/data')
    baseline = data.col('waveform')
    median_value = np.median(baseline)
    foo.close()
    return median_value

def plot_baseline(pmt_id, first_bin):
    filename = f'/home/scanbox/data/develop/baseline/20201007_06/{pmt_id}.hdf5'
    foo = tables.open_file(filename)
    data = foo.get_node('/data')
    baseline = data.col('waveform')
    n = 20
    if pmt_id == 'SQ0328':
        mask = baseline < 7975
        mask_1st = first_bin > 7945
        mask_2nd = first_bin[mask_1st] < 7975
        xmin, xmax = np.min(baseline[mask]), np.max(baseline[mask])
        bins = np.linspace(start=xmin, stop=xmax, num=n+1, endpoint=True)
    if pmt_id == 'SQ0336':
        mask = baseline < 8085
        mask_1st = first_bin > 8050
        mask_2nd = first_bin[mask_1st] < 8100
        xmin, xmax = np.min(baseline[mask]), np.max(baseline[mask])
        bins = np.linspace(start=xmin, stop=xmax, num=n+1, endpoint=True)
    if pmt_id == 'SQ0425':
        mask = baseline < 7950
        mask_1st = first_bin > 7910
        mask_2nd = first_bin[mask_1st] < 7950
        xmin, xmax = np.min(baseline[mask]), np.max(baseline[mask])
        bins = np.linspace(start=xmin, stop=xmax, num=n+1, endpoint=True)
    if pmt_id == 'SQ0426':
        mask = baseline < 8030
        mask_1st = first_bin > 8000
        mask_2nd = first_bin[mask_1st] < 8030
        xmin, xmax = np.min(baseline[mask]), np.max(baseline[mask])
        bins = np.linspace(start=xmin, stop=xmax, num=n+1, endpoint=True)

    #delta_baseline = np.abs(first_bin[mask_1st][mask_2nd] - np.median(baseline))
    plt.title(f'PMT {pmt_id}', fontsize = 20)
    #plt.hist(delta_baseline, bins=12, alpha=0.85, label=r'$\Delta$Baseline')
    plt.hist(baseline[mask], density='True', bins=bins, alpha=0.35, label='baseline')
    plt.hist(first_bin[mask_1st][mask_2nd], density='True', bins =bins, alpha=0.35, label='first bin')
    plt.axvline(x=np.median(baseline), color='red', linestyle='--', label=f'median= {np.median(baseline):.1f}')
    plt.legend(loc='best', fontsize = 14)
    plt.xlabel('ACD value', fontsize = 18)
    plt.ylabel('Counts', fontsize = 18)
    plt.tick_params(axis='x', labelsize=14)
    plt.tick_params(axis='y', labelsize=14)
    plt.grid(linestyle='dotted')
    plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/hist_baseline_{pmt_id}.png', bbox_inches='tight')
    plt.clf()
    foo.close()


def run_analysis(data_key, degg_dict, run, pmt, logbook, aggregate_fig=None, aggregate_ax=None, cnt=None, max_cnt=None):
    folder = degg_dict[pmt][data_key]['Folder']
    pmt_id = degg_dict[pmt]['SerialNumber']
    files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
    print(f"PMT ID: {pmt_id}")
    baseline = get_baseline(pmt_id)
    #make n random corrected waveforms
    #make_random_correction_plot(files, 30, pmt_id)

    difference, inflection_point, start = [], [], []
    charge_laser, charge_after = [], []
    wf_weird = []
    for j, file_name in enumerate(files):
        e_id, time, waveforms, ts, pc_t, params = read_data(file_name)
        #plot_baseline(pmt_id, waveforms[:,0])

        for wf in range(len(waveforms)):
            Corrected_droop, Corrected_undershoot, Original_waveform, tau_droop, tau_undershoot = correct_droop_undershoot(time[wf], waveforms[wf], baseline)
            Corrected_Original = Corrected_droop - (waveforms[wf] - baseline)
            difference.append(np.max(Corrected_Original))
            index_start, index_stop = get_start_end(time[wf], Corrected_Original)
            inflection_point.append(index_stop)
            start.append(index_start)
            if  np.max(Corrected_Original) >= 100:
                Q_laser = calc_charge(time[wf]*TIME_SCALING, Corrected_droop*VOLT_SCALING, index_start, index_stop)
                charge_laser.append(Q_laser)
                Q_after = calc_charge(time[wf]*TIME_SCALING, Corrected_droop*VOLT_SCALING, index_stop+1, int(np.max(time[wf])))
                charge_after.append(Q_after)
                '''if pmt_id == 'SQ0328':
                    if Q_after < -50 or Q_after > 150:
                        min_y, max_y = 7700, 10600
                        plot_corrected_wf(time[wf], waveforms[wf], wf,  pmt_id, min_y, max_y)
                '''
    plt.title(f'PMT {pmt_id}', fontsize = 20)
    plt.hist2d(charge_laser, charge_after, bins=(50, 50), cmap='viridis')
    #plt.legend(loc='best', fontsize = 14)
    plt.xlabel('Charge of the laser', fontsize = 18)
    plt.ylabel('Charge after the laser', fontsize = 18)
    plt.tick_params(axis='x', labelsize=14)
    plt.tick_params(axis='y', labelsize=14)
    plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/2D_Charge_PMT{pmt_id}_charge.png', bbox_inches='tight')
    #plt.show()
    plt.clf()
    plt.cla()
    plt.close()


    '''
    n = 50 #slices for the histograms
    #Charge histograms
    x_generic_laser = [[4700, 4950], [4325, 4550], [4150, 4400], [np.min(charge_laser), np.max(charge_laser)]]
    x_generic_after = [[-100, 200], [-100, 100], [np.min(charge_after), np.max(charge_after)], [np.min(charge_after), np.max(charge_after)]]
    if pmt_id == 'SQ0328':
        a = 0
    if pmt_id == 'SQ0336':
        a = 1
    if pmt_id == 'SQ0425':
        a = 2
    if pmt_id == 'SQ0426':
        a = 3
    xmin_laser, xmax_laser = x_generic_laser[a][0], x_generic_laser[a][1]
    bins_laser = np.linspace(start=xmin_laser, stop=xmax_laser, num=n+1, endpoint=True)
    xmin_after, xmax_after = x_generic_after[a][0], x_generic_after[a][1]
    bins_after = np.linspace(start=xmin_after, stop=xmax_after, num=n+1, endpoint=True)

    fig, (ax0, ax1) = plt.subplots(1,2)
    fig.suptitle(f'PMT {pmt_id}', fontsize=20)
    ax0.hist(charge_laser[150:-150], bins=bins_laser, alpha=0.5, label=f'Laser = {len(charge_laser)}')
    ax0.tick_params(axis='x', labelsize=14)
    ax0.tick_params(axis='y', labelsize=14)
    ax0.set_title(f'Mean charge = {np.mean(charge_laser[150:-150]):.2f} [pC] $\sim$ {np.mean(charge_laser[150:-150])/1.60217662:.2f} PEs', fontsize = 18)
    ax0.set_xlabel('Laser Charge [pC]', fontsize = 18)
    ax0.set_ylabel('Counts', fontsize = 18)
    ax0.grid(linestyle='dotted')
    ax0.legend(loc=0, fontsize = 16)

    ax1.hist(charge_after[150:-150], bins=bins_after, alpha=0.5, label=f'After = {len(charge_after)}', color = 'red')
    ax1.tick_params(axis='x', labelsize=14)
    ax1.tick_params(axis='y', labelsize=14)
    ax1.set_title(f'Mean charge = {np.mean(charge_after[150:-150]):.2f} [pC] $\sim$ {np.mean(charge_after[50:-50])/1.60217662:.2f} PEs', fontsize = 18)
    ax1.set_xlabel('After Laser Charge [pC]', fontsize = 18)
    ax1.set_ylabel('Counts', fontsize = 18)
    ax1.grid(linestyle='dotted')
    ax1.legend(loc=0, fontsize = 16)

    fig.set_size_inches(18.5, 8.5, forward=True)
    fig.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/random_wf/droop_measurement/PMT{pmt_id}_charge.png', bbox_inches='tight')
    #plt.show()
    plt.clf()
    plt.cla()
    plt.close()


    difference = np.asarray(difference)
    mask_diff = difference >= 100
    print('Number of cut events for height (>= 100):', len(difference[mask_diff]))
    xmin, xmax = difference[mask_diff].min(), difference[mask_diff].max()
    bins = np.linspace(start=xmin, stop=xmax, num=n+1, endpoint=True)
    #mu, sigma = norm.fit(difference)
    #best_fit_line = norm.pdf(bins, mu, sigma)


    fig, (ax0, ax1) = plt.subplots(1, 2)
    ax0.tick_params(axis='x', labelsize=14)
    ax0.tick_params(axis='y', labelsize=14)
    ax0.set_title('Max. Amount of ADC Corrected per bin', fontsize = 18)
    hist, edges_bins, patches = ax0.hist(difference[mask_diff], bins=bins, alpha=0.5, label='ADC Histogram')
    #prop = np.max(hist)/best_fit_line.max()
    #ax0.plot(bins, best_fit_line*0.9*prop, label='Best fit')
    #ax0.set_title(r'PMT ID: {0}, Gaussian: $\sigma$ = {1:0.2f}, $\mu$ = {2:0.2f}'.format(pmt_id, sigma, mu))
    ax0.set_ylabel('Counts', fontsize = 16)
    ax0.set_xlabel('Inflection point height (ADC)', fontsize = 16)
    #ax0.set_ylim(0, 600)
    ax0.grid(linestyle='dotted')
    #ax0.set_xlim(xmin, xmax)
    ax0.legend(loc='best', fontsize = 14)

    inflection_point = np.asarray(inflection_point)
    xmin_ip, xmax_ip = inflection_point[mask_diff].min(), inflection_point[mask_diff].max()
    bins_ip = np.linspace(start=xmin_ip, stop=xmax_ip, num=10, endpoint=True)
    ax1.tick_params(axis='x', labelsize=14)
    ax1.tick_params(axis='y', labelsize=14)
    ax1.hist(inflection_point[mask_diff], bins=bins_ip, alpha=0.5, label='Time Histogram')
    #ax1.set_title(r'PMT ID: {0}'.format(pmt_id))
    ax1.set_ylabel('Counts', fontsize = 16)
    ax1.set_xlabel('Inflection point timing (bin number)', fontsize = 16)
    #ax1.set_ylim(0, 600)
    ax1.grid(linestyle='dotted')
    ax1.set_xlim(xmin_ip, xmax_ip)
    ax1.legend(loc='best', fontsize = 14)
    fig.set_size_inches(12.5, 5.5)
    plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/random_wf/droop_measurement/PMT{pmt_id}_droop_under.png', bbox_inches='tight')
    #plt.show()
    plt.clf()
    plt.cla()
    plt.close()
    '''

@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--measurement_number', '-n', default='latest')
def main(run_json, measurement_number):
    run_number = extract_runnumber_from_path(run_json)
    try:
        measurement_number = int(measurement_number)
    except ValueError:
        pass

    #if data_key is None:
    data_key = 'BurstMeasurement'
    #data_key = 'DroopMeasurement'

    logbook = DEggLogBook()

    fig0, ax0 = plt.subplots()
    fig1, ax1 = plt.subplots()
    aggregate_fig, aggregate_ax = [fig0, fig1], [ax0, ax1]


    list_of_deggs = load_run_json(run_json)
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

            #degg_dict =
            run_analysis(data_key_to_use, degg_dict,
                                     run_number, pmt, logbook, aggregate_fig, aggregate_ax, cnt, max_cnt)
            #update_json(degg_file, degg_dict)
            cnt += 1

if __name__ == '__main__':
    main()


'''
        mins = []
        bls = []
        droops = []
        for wf in waveforms:

            first_vals = wf[0]
            bl = np.median(first_vals)
            wf_min = (np.min(wf))

            bls.append(bl)
            mins.append(wf_min)

            droop = bl - wf_min
            droops.append(droop)

        fig0, ax0 = plt.subplots()
        ax0.set_xlim(0, 250)
        ax0.hist(droops, bins=50)
        plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/droop_hist_PMT{pmt_id}.png')
        #plt.show()
        plt.clf()
        plt.cla()
        plt.close()

        fig1, ax1 = plt.subplots()
        my_bins = np.linspace(np.min(mins), 8200, 50)
        ax1.hist(mins, bins=my_bins, color='royalblue', label='Min')
        ax1.hist(bls, bins=my_bins, color='goldenrod', label='Baseline')
        ax1.legend(loc=0)
        plt.savefig(f'/home/scanbox/software/degg_measurements/degg_measurements/analysis/droop/baseline_droop_hist_PMT{pmt_id}.png')
        #plt.show()
        plt.clf()
        plt.cla()
        plt.close()
'''


'''
def run_fit(charges, pmt, fw, run, data_key):
    print(f"Running fit at {fw} Filter")
    bins = np.linspace(-1, np.median(charges) * 4, 101)
    hist, edges = np.histogram(charges, bins=bins)
    center = (edges[1:] + edges[:-1]) * 0.5

    temp_charges = np.load(f'templates/{pmt}_{fw}.npy')
    temp_hist, _ = np.histogram(temp_charges, bins=bins)
    temp_hist = np.array(temp_hist, dtype=float)
    temp_hist *= (len(charges) / len(temp_charges))

    init_spe_norm = np.max(hist)
    init_spe_peak = center[np.argmax(hist)]
    init_spe_width = 0.35 * init_spe_peak
    init_temp_norm = 0.1

    p0 = [init_spe_norm, init_spe_peak, init_spe_width, init_temp_norm]

    #bounds = [(0.5 * init_spe_norm, 0.8 * init_spe_peak, 0.05, 0),
    #          (2. * init_spe_norm, 1.2 * init_spe_peak, 2. * init_spe_width, 1)]

    bounds = [(0.01 * init_spe_norm, 0., 0., 0),
              (10. * init_spe_norm, np.median(charges) * 2, 10. * init_spe_width, 1)]

    popt, pcov = curve_fit(fit_func, (center, temp_hist), hist, p0=p0, bounds=bounds)
    print(popt)
    fig, ax = plt.subplots()
    ax.errorbar(center, hist, xerr=np.diff(edges)*0.5, yerr=np.sqrt(hist), fmt='none')
    ax.plot(center, fit_func((center, temp_hist), *popt))
    ax.plot(center, gauss(center, *popt[:-1]))
    ax.set_yscale('log')
    ax.set_xlabel('Charge / pC')
    ax.set_ylabel('Entries')
    ax.set_ylim(1, np.max(hist)*1.2)
    fig.savefig(f'figs/charge_hist_{run}_{data_key}_{pmt}_{fw}_template.pdf')
    plt.close(fig)
    return popt, pcov


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
        fig.savefig(f'figs/linearity_{run}_{data_key}_{pmt}.pdf')

    if aggregate_fig is not None:
        aggregate_ax[0].errorbar(ideal_pe, observed_pe, fmt='o', label=pmt)
        aggregate_ax[1].errorbar(fw_settings_all, observed_pe_all, fmt='o',
                                 label=pmt, alpha=.7)
        if cnt == max_cnt:
            aggregate_ax[0].plot([1, 1e4], [1, 1e4], '--', color='grey')
            aggregate_ax[0].set_xscale('log')
            aggregate_ax[0].set_yscale('log')
            aggregate_ax[0].set_xlim(10, 1e3)
            aggregate_ax[0].set_ylim(10, 1e3)
            aggregate_ax[0].set_xlabel("Ideal NPE / pe")
            aggregate_ax[0].set_ylabel("Observed NPE / pe")
            aggregate_ax[0].legend()
            aggregate_fig[0].savefig(f'figs/linearity_{run}_{data_key}_aggregate.pdf')

            aggregate_ax[1].set_xscale('log')
            aggregate_ax[1].set_yscale('log')
            aggregate_ax[1].set_xlim(0.0009, 2)
            aggregate_ax[1].set_xlim(0.7, 400)
            aggregate_ax[1].set_xlabel("Filter strength")
            aggregate_ax[1].set_ylabel("Observed NPE / pe")
            aggregate_ax[1].legend()
            aggregate_fig[1].savefig(f'figs/output_{run}_{data_key}_aggregate.pdf')

        fw = params['strength']
        fw_settings.append(fw)
        print(fw)
        if float(fw) == 1.:
            for i in range(10):
                fifig, ax = plt.subplots()
                ax.plot(time[i]*TIME_SCALING*1e9,
                        waveforms[i]*VOLT_SCALING*1e3)
                ax.set_xlabel('t / ns')
                ax.set_ylabel('voltage / mV')
                fig.savefig(
                    f'figs_waveform/wf_{run}_{data_key}_{pmt_id}_{i}_max_intensity.pdf')
        # This baseline calculation probably doesnt work in this context...
        # Please check when running this script
        charges = get_charges(waveforms*VOLT_SCALING,
                              gate_start=13,
                              gate_width=15,
                              baseline=np.median(waveforms)*VOLT_SCALING)

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

        fig, ax = plt.subplots()
        bins = np.linspace(-1, np.median(high_density_charges) * 4, 101)
        hist, edges = np.histogram(high_density_charges, bins=bins)
        center = (edges[1:] + edges[:-1]) * 0.5

        ax.errorbar(center, hist, xerr=np.diff(edges)*0.5, yerr=np.sqrt(hist), fmt='none')
        ax.set_ylim(1, np.max(hist)*1.2)
        ax.set_yscale('log')
        ax.set_ylabel('Counts')
        ax.set_xlabel(f'Highest density charge in {n_bins} bins / pC')
        fig.savefig(f'figs/hd_charge_vs_strength_{pmt}_{fw}.pdf')
        plt.close(fig)


        #popt, pcov = run_fit(charges, pmt_id, fw, run, data_key)
        #popts.append(popt)
        #pcovs.append(pcov)
    spe_peak_pos = np.array([popt[1] for popt in popts])
    print(f"Gaussian Fit Peak Positions: {spe_peak_pos}")
    spe_peak_pos_err = np.array([pcov[1, 1] for pcov in pcovs])

    fig, ax = plt.subplots()
    ax.plot(np.array(fw_settings, dtype=float), spe_peak_pos/E_CONST/1e7)
    ax.set_xlabel('Filter wheel strength')
    ax.set_ylabel('Mean charge / PE')
    fig.savefig(f'figs/charge_vs_strength_{run}_{data_key}_{pmt}.pdf')

    ax.set_xscale('log')
    ax.set_yscale('log')
    fig.savefig(f'figs/charge_vs_strength_{run}_{data_key}_{pmt}_log.pdf')

    plot_linearity(fw_settings, spe_peak_pos, pmt_id, run, data_key)
    plot_linearity(fw_settings, spe_peak_pos, pmt_id, run, data_key, aggregate_fig, aggregate_ax, cnt, max_cnt)

    return degg_dict
'''
