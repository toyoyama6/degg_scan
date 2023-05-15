import numpy as np
import tables
import pandas as pd
from glob import glob
import os
import sys
from matplotlib import pyplot as plt
from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
import click


def show_wf(time, waveforms, n_wf):
    if n_wf >= 10:
        n_wf = 10
    for i in range(n_wf):
        time_i, waveform_i = time[i], waveforms[i]
        plt.plot(time_i, waveform_i)
        plt.show()
        plt.clf()


def calc_charge_and_rate(input_file, signal_start=14, signal_width=15, 
        pedestal_start=1, pedestal_width=12, output_file=None, display=False):
    
    event_id, time, waveforms, timestamp, pc_time, parameter_dict = read_data(filename)
    
    n_waveforms = len(event_id)
    print(f'Loaded {n_waveforms} waveforms!')

    time_scaling = 1 / 240e6
    volt_scaling = 0.089e-3

    if display is True:
        show_wf(time, waveforms, n_waveforms)

    charges = get_charges(time*time_scaling,
                          waveforms*volt_scaling,
                          signal_start*time_scaling,
                          signal_width*time_scaling,
                          pedestal_start*time_scaling,
                          pedestal_width*time_scaling,
                          n_waveforms)

    print(f'Mean charge: {np.mean(charges)} pC')
    if output_file is not None:
        np.savetxt(output_file, charges)
    return charges, pc_time


def plot_charge_dist(charges, plot_name=None):
    fig1, ax1 = plt.subplots()
    ax1.set_xlabel("Charge [pC]")
    ax1.set_ylabel("Entries")
    ax1.set_yscale('log')

    ax1.hist(charges, bins=50)
    if plot_name is None:
        plt.show()
    else:
        fig1.savefig(plot_name, bbox_inches='tight')
    plt.close(fig1)


def plot_charge_time(charges, times, plot_name=None):
    fig1, ax1 = plt.subplots()
    ax1.scatter(times, charges, color="royalblue", linewidth=0)
    ax1.axhline(np.median(charges), ls='--', color='k')
    plot_max = np.max(charges)
    plot_min = np.min(charges)
    ax1.set_ylim(plot_min * 0.95, plot_max * 1.05)
    ax1.set_xlabel("Time / s")
    ax1.set_ylabel("Charge / pC")
    if plot_name is None:
        plt.show()
    else:
        fig1.savefig(plot_name, bbox_inches='tight')
    plt.close(fig1)


def plot_across_rate(charges_list_100hz, times_list_100hz, 
        charges_list_500hz, times_list_500hz, basename_list):
    fig2, ax2 = plt.subplots()
    ax2.set_xlabel("Module ID")
    ax2.set_ylabel("Median Charge / pC")

    fig3, ax3 = plt.subplots()
    ax3.set_xlabel("Module ID")
    ax3.set_ylabel(r"$\Delta$ Median Charge (500 Hz - 100 Hz)/ pC")
    
    fig4, ax4 = plt.subplots()
    ax4.set_xlabel("Module ID")
    ax4.set_ylabel(r"% Diff. / pC")

    for cntr in range(0,4):
        charges_100hz = charges_list_100hz[cntr]
        charges_500hz = charges_list_500hz[cntr]
        times_100hz = times_list_100hz[cntr]
        times_500hz = times_list_500hz[cntr]
        basename = basename_list[cntr]

        fig1, ax1 = plt.subplots()
        ax1.plot(times_100hz, charges_100hz, label='100 Hz', linewidth=0, marker='o', 
                color='royalblue', alpha=0.6)
        ax1.axhline(np.median(charges_100hz), ls='--', color='teal', label='100 Hz Median')
        ax1.plot(times_500hz, charges_500hz, label='500 Hz', linewidth=0, marker='o',
                color='goldenrod', alpha=0.6)
        ax1.axhline(np.median(charges_500hz), ls='--', color='khaki', label='500 Hz Median')
        ax1.legend(loc=0, framealpha=1.0)
        ax1.set_xlabel('Waveform Number')
        ax1.set_ylabel('Charge / pC')
        ax1.set_title(basename)
        fig1.savefig(f'figs/charge_vs_time_vs_rate_{basename}.pdf')
        plt.close(fig1)

        delta = np.median(charges_500hz) - np.median(charges_100hz)
        delta_sig = np.sqrt((np.std(charges_500hz) / np.median(charges_500hz))**2 
                    + (np.std(charges_100hz) / np.median(charges_100hz))**2)

        percent_diff = delta / np.median(charges_500hz)

        if cntr == 0:
            ax2.errorbar(cntr, np.median(charges_100hz), yerr=np.std(charges_100hz),
                    color='royalblue', marker='o', elinewidth=2, linewidth=0, alpha=0.6,
                    label='100 Hz')
            ax2.errorbar(cntr, np.median(charges_500hz), yerr=np.std(charges_500hz),
                    color='goldenrod', marker='o', elinewidth=2, linewidth=0, alpha=0.6,
                    label='500 Hz')
            ax3.errorbar(cntr, delta, yerr=delta_sig,
                    color='firebrick', marker='o', elinewidth=2, linewidth=0)
            ax4.errorbar(cntr, percent_diff, yerr=0,
                    color='firebrick', marker='o', elinewidth=2, linewidth=0)
        if cntr != 0:
            ax2.errorbar(cntr, np.median(charges_100hz), yerr=np.std(charges_100hz),
                    color='royalblue', marker='o', elinewidth=2, linewidth=0, alpha=0.6)
            ax2.errorbar(cntr, np.median(charges_500hz), yerr=np.std(charges_500hz),
                    color='goldenrod', marker='o', elinewidth=2, linewidth=0, alpha=0.6)
            ax3.errorbar(cntr, delta, yerr=delta_sig,
                    color='firebrick', marker='o', elinewidth=2, linewidth=0)
            ax4.errorbar(cntr, percent_diff, yerr=0,
                    color='firebrick', marker='o', elinewidth=2, linewidth=0)
    
    label_loc = np.arange(4)
    ax2.legend(loc=0, framealpha=1.0)
    labels = [item.get_text() for item in ax2.get_xticklabels()]
    evens = [1, 3, 5, 7]
    counter = 0
    for num in evens:
        labels[num] = basename_list[counter]
        counter = counter + 1

    ax2.set_xticklabels(labels)
    fig2.savefig(f'figs/charge_median_combo.pdf')
    plt.close(fig2)

    ax3.set_xticklabels(labels)
    fig3.savefig(f'figs/charge_median_delta_combo.pdf')
    plt.close(fig3)

    ax4.set_xticklabels(labels)
    fig4.savefig(f'figs/charge_median_percent_delta_combo.pdf')
    plt.close(fig4)


if __name__ == '__main__':
    filenames_100hz = sorted(glob('/home/scanbox/dvt/data/mpe/20200208_00/*.hdf5'))
    filenames_500hz = sorted(glob('/home/scanbox/dvt/data/mpe/20200208_01/*.hdf5'))

    _timing_info=False

    print("Timing info is enabled?... ", _timing_info)

    charges_list_100hz = []
    charges_list_500hz = []
    times_list_100hz = []
    times_list_500hz = []
    basename_list = []

    wf_num_list = []

    for filename in filenames_100hz:
        basename = os.path.basename(filename)
        print(f"Loaded {filename}")
        charges, times = calc_charge_and_rate(filename, display=False)
        wf_num = np.arange(len(charges))
        basename = basename.replace('.hdf5', '')
        plot_charge_dist(charges,
                         plot_name=f'figs/charge_dist_100hz_{basename}.pdf')
        if _timing_info is True:
            plot_charge_time(charges, times,
                         plot_name=f'figs/charge_vs_time_100hz_{basename}.pdf')
        if _timing_info is False:
            plot_charge_time(charges, wf_num,
                         plot_name=f'figs/charge_vs_time_100hz_{basename}.pdf')

        charges_list_100hz.append(charges)
        times_list_100hz.append(times)
        basename_list.append(basename)
        wf_num_list.append(wf_num)

    for filename in filenames_500hz:
        basename = os.path.basename(filename)
        print(f"Loaded {filename}")
        charges, times = calc_charge_and_rate(filename, display=False)
        basename = basename.replace('.hdf5', '')
        plot_charge_dist(charges,
                         plot_name=f'figs/charge_dist_500hz_{basename}.pdf')
        if _timing_info is True:
            plot_charge_time(charges, times,
                         plot_name=f'figs/charge_vs_time_500hz_{basename}.pdf')
        if _timing_info is False:
            plot_charge_time(charges, wf_num,
                         plot_name=f'figs/charge_vs_time_500hz_{basename}.pdf')

        charges_list_500hz.append(charges)
        times_list_500hz.append(times)


    if _timing_info is True:
        plot_across_rate(charges_list_100hz, times_list_100hz, 
                     charges_list_500hz, times_list_500hz, basename_list)
    if _timing_info is False:
        plot_across_rate(charges_list_100hz, wf_num_list, charges_list_500hz, wf_num_list, basename_list)
##end
