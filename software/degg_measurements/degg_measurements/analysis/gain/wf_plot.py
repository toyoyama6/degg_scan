import tables
import numpy as np
import matplotlib.pyplot as plt
import sys, os
from termcolor import colored

def plot_wf(average_wf, title):
    fig1, ax1 = plt.subplots()
    ax1.set_title(title)
    ax1.set_xlabel("Time Bins")
    ax1.set_ylabel("ADC Counts")

    ax1.plot(np.arange(len(average_wf)), average_wf)
    fig1.savefig(f"/home/scanbox/software/degg_measurements/degg_measurements/analysis/gain/figs/wf_{title}.pdf")

def average_wf(wf_list, n_wfs = 100):
    wf_for_ave = []
    i = 0
    for wf in wf_list:
        wf_for_ave.append(wf)
        if i == n_wfs:
            break
        i += 1
    average_wf = np.sum(wf_for_ave, axis=0) / float(len(wf_for_ave))
    return average_wf

def plot_ave_wf(data_file, n_wfs, title):
    f = tables.open_file(data_file)
    data = f.get_node("/data")
    wf_list = data.col("waveform")
    ave_wf = average_wf(wf_list, n_wfs)
    plot_wf(ave_wf, title)

if __name__ == "__main__":
    data_file = sys.argv[1]
    n_wfs = 1
    title = sys.argv[2]

    print(f"Making average waveform for: {data_file} with {n_wfs} WFs")
    plot_ave_wf(data_file, n_wfs, title)

##end
