import pandas as pd
import matplotlib.pyplot as plt 
import glob
import numpy as np
from natsort import natsorted
from tqdm import tqdm



nbin = 250
file_list = glob.glob("./data/*")
for file in tqdm(natsorted(file_list)):
    r = file.split(".")[1].split("_")[-1]
    df = pd.read_hdf(file)
    df = df[df.triggerchannel==1]
    max_list = []
    for wf in df.wf:
        max = np.max(wf)
        max_list.append(max)
        plt.plot(wf)
    plt.ylabel('ADC', fontsize = 18)
    plt.xlabel('', fontsize = 18)
    plt.title(f'r = {r}', fontsize = 20)
    plt.tight_layout()
    plt.savefig(f'./figs/waveform_r_{r}.png')
    plt.close()
    #plt.show()


    density, bin_edges = np.histogram(max_list, bins = np.linspace(np.min(max_list), np.max(max_list), nbin))
    centres = (bin_edges[1:] + bin_edges[:-1]) / 2
    x = centres
    y = density
    # f = interp1d(centres, density)
    # x = np.linspace(centres.min(), centres.max(), nbin * 100, endpoint = False)
    # y = f(x)
    plt.figure()
    plt.hist(max_list, bins = np.linspace(np.min(max_list), np.max(max_list), nbin), histtype = 'step', color = "blue")
    #plt.scatter(x, y, s = 5, color = "red")
    plt.title(f'r = {r}', fontsize = 20)
    plt.xlabel('peak height', fontsize = 18)
    plt.savefig(f'./figs/peak_height_hist_r_{r}.png')
    #plt.savefig(f'./figs/peak_height_scatter_plot_r_{r}.png')
    # plt.show()
    plt.close()
