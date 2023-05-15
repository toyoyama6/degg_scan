import sys
import os
from glob import glob
import numpy as np
from matplotlib import pyplot as plt

from degg_measurements.utils import read_data
from degg_measurements.utils import get_charges
from degg_measurements.utils import DEggLogBook
from degg_measurements.analysis import Result


if __name__ == '__main__':
    logbook = DEggLogBook()

    intensities = [8.3, 8.5, 8.8, 9.4, 13.4]
    file_names = []
    for intensity in intensities:
        folder_name = f'/home/scanbox/dvt/data/mpe_{intensity:.1f}/20200210_00/*.hdf5'
        file_names.extend(glob(folder_name))

    pmts = ['sq0286', 'sq0289', 'sq0290', 'sq0331']
    wf_list = [[], [], [], []]
    time_list = [[], [], [], []]
    for file_name in file_names:
        e_id, time, waveforms, ts, pc_t, params = read_data(file_name)
        for i, pmt in enumerate(pmts):
            if pmt in file_name:
                idx = i
        wf_list[idx].append(waveforms)
        time_list[idx].append(time)

    # Load calibration data
    calibration_data = np.loadtxt('half_degg_intensity_calib.tab')
    calibration_scaling_factors = calibration_data[:, 1] / calibration_data[0, 1]

    time_scaling = 1 / 240e6
    volt_scaling = 0.089e-3

    for i, pmt in enumerate(pmts):
        fig, ax = plt.subplots()
        obs_charge = []
        ideal_charge = []
        for j, intensity in enumerate(intensities):
            times = time_list[i][j]
            waveforms = wf_list[i][j]
            charges = get_charges(times*time_scaling, waveforms*volt_scaling,
                                  gate_start=14*time_scaling,
                                  gate_width=15*time_scaling,
                                  pede_gate_start=1*time_scaling,
                                  pede_gate_width=12*time_scaling,
                                  nevent=len(waveforms))
            obs_charge.append(np.mean(charges))
            ideal_charge.append(obs_charge[0] * calibration_scaling_factors[j])
            avg_waveform = np.mean(waveforms, axis=0)
            ax.plot(avg_waveform)
        ax.set_xlabel('Time bins')
        ax.set_ylabel('ADC counts')
        fig.savefig(f'figs/average_waveforms_{pmt}.pdf')

        print(obs_charge)
        print(ideal_charge)

        fig, ax = plt.subplots()
        ax.plot(ideal_charge, obs_charge, 'o')
        ax.plot([1, 1e5], [1, 1e5], '--', color='grey')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(2e1, 2e4)
        ax.set_ylim(2e1, 2e4)
        ax.set_xlabel('Ideal charge / pC')
        ax.set_ylabel('Observed charge / pC')
        fig.savefig(f'figs/linearity_{pmt}.pdf')

        result = Result(pmt_name=pmt, logbook=logbook,
                        test_type='dvt')
        result.to_json(test_name='linearity',
                       folder_name='../database_jsons',
                       ideal_charge=ideal_charge,
                       observed_charge=obs_charge)

