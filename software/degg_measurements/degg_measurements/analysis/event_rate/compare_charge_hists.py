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
from plotting import plot_charge_histogram


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

    charges = get_charges(time * time_scaling,
                          waveforms * volt_scaling,
                          signal_start * time_scaling,
                          signal_width * time_scaling,
                          pedestal_start * time_scaling,
                          pedestal_width * time_scaling,
                          n_waveforms)

    total_time = pc_time[-1] - pc_time[0]
    print(int(pc_time[-1]), int(pc_time[0]))
    print(total_time / 60)

    print(f'Mean charge: {np.mean(charges)} pC')
    if output_file is not None:
        np.savetxt(output_file, charges)
    return charges


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



if __name__ == '__main__':
    # filename = '/home/scanbox/dvt/data/scalar/20200208_01/sq0286_500.hdf5'
    filenames = glob('/home/scanbox/dvt/data/mpe_13.4/20200210_00/*.hdf5')

    # 289 -- 290
    # 286 -- 331
    degg1 = ['289', '290']
    degg2 = ['286', '331']
    charges_degg1 = []
    names_degg1 = []
    charges_degg2 = []
    names_degg2 = []

    for filename in filenames:
        basename = os.path.basename(filename)
        print(f"Loaded {filename}")
        charges = calc_charge_and_rate(filename, display=False)
        if degg1[0] in basename or degg1[1] in basename:
            charges_degg1.append(charges)
            names_degg1.append(basename.replace('.hdf5', ''))
        if degg2[0] in basename or degg2[1] in basename:
            charges_degg2.append(charges)
            names_degg2.append(basename.replace('.hdf5', ''))

    plot_charge_histogram(charges_degg1, names_degg1, 'figs/charge_comparison_degg1.pdf')
    plot_charge_histogram(charges_degg2, names_degg2, 'figs/charge_comparison_degg2.pdf')

