import click
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy import integrate
from tqdm import tqdm
import glob
import tables
from natsort import natsorted

def gaussian(x, A, mu, sigma):
    return A * np.exp(-(x-mu)**2/(2*sigma**2))


def fit_gaussian(bin, val, min_bin=None, max_bin=None):

    if(min_bin==None):
        min_bin = np.min(val)
    if(max_bin==None):
        max_bin = np.max(val)

    y, bins = np.histogram(val, bins=bin, range=(min_bin, max_bin))

    x = []
    for b in range(len(bins)-1):

        x.append((bins[b+1]+bins[b])/2)
    try:
        # popt, pcov = curve_fit(gaussian, x, y, p0=[max(y), x[np.argmax(y)], np.sqrt(x[np.argmax(y)])], maxfev=4000)
        popt, pcov = curve_fit(gaussian, x, y, p0=[max(y[20:]), x[np.argmax(y[20:])+20], np.sqrt(x[np.argmax(y[20:])+20])], maxfev=4000)
    except:
        plt.figure()
        plt.scatter(x, y)
        plt.show()
        plt.close()
    return popt


def plot_point_hist(charge, n_bin, theta, r, graph_dir, popt, min_bin, max_bin):

    xd = np.arange(np.min(charge), np.max(charge), 0.01)
    estimated_curve = gaussian(xd, popt[0], popt[1], popt[2])

    plt.figure()
    plt.title(f'theta={theta}:r={r} charge distribution', fontsize=18)
    plt.xlabel ('charge (pC)', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.xlim(min_bin, max_bin)
    plt.hist(charge, bins=n_bin, range=(min_bin,max_bin), color='blue')
    plt.plot(xd, estimated_curve, color='red')
    plt.savefig(f'{graph_dir}{theta}_{r}.png', bbox_inches='tight')
    # plt.show()
    plt.close()


def point_hist(data, theta, r_range, graph_dir):

    n_bin, min_bin, max_bin = 250, 0, 500
    mean_charge_list = []
    std_charge_list = []
    for i in r_range:
        
        charge = data[data.rVal == i]['charge']
        popt = fit_gaussian(n_bin, charge, min_bin, max_bin)
        plot_point_hist(charge, n_bin, theta, i, graph_dir, popt, min_bin, max_bin)
        mean_charge_list.append(popt[1])
        std_charge_list.append(popt[2])

    return mean_charge_list, std_charge_list


def plot_polar_heatmap(radii, theta, val, graph_dir, top_bottom, mean_std):

    X, Y = np.meshgrid(theta, radii)

    # print(X, '\n', Y, '\n', val)
    # print(type(X), type(Y), type(val))

    plt.figure()
    plt.subplot(projection="polar")
    plt.grid()
    plt.pcolormesh(X, Y, val.T)
    plt.title('x scan: relative CE heatmap', fontsize=18)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.colorbar()
    plt.savefig(f'{graph_dir}{top_bottom}_relative_{mean_std}_charge_mapxscan.png', bbox_inches='tight')
    plt.close()


def get_reference_data(filename):

    charges = []
    with tables.open_file(filename) as f:
        data = f.get_node('/data')
        waveforms = data.col("waveform")
        times = data.col("time")

        start_point = int(len(times[0])/2)
        end_point = int(start_point + start_point//3)
        base = np.mean(waveforms[0][0:200])

        for time, waveform in tqdm(zip(times, waveforms)):

            waveform = -waveform[start_point:end_point] + base
            time = time[start_point:end_point]
            charge = integrate.simps(waveform, time)/50*1e12
            charges.append(charge)
        
    popt = fit_gaussian(30, charges)
    return popt[1], popt[2]


def plot_ref_stability(x, y, y_err, graph_dir):

    plt.figure()
    plt.title('Reference PMT charge', fontsize=18)
    plt.ylabel('charge (pC)', fontsize=16)
    plt.xlabel('#theta', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.ylim(np.min(y)-10, np.max(y)+10)
    plt.errorbar(x, y, yerr=y_err, fmt='o')
    plt.savefig(f'{graph_dir}refpmt_stability.png', bbox_inches='tight')
    plt.close()


def plot_theta_efficiency(r_range, theta_range, relative_mean_charge, graph_dir, top_bottom):

    counter = 0
    colormap = plt.cm.Dark2.colors
    plt.figure()
    plt.title('theta vs relative efficiency')
    plt.xlabel('distance from center (mm)')
    plt.ylabel('relative CE')
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    for i in theta_range:

        plt.plot(r_range,relative_mean_charge[counter], label=f'theta = {i}', color=colormap[counter])
        plt.scatter(r_range,relative_mean_charge[counter], color=colormap[counter])

        counter += 1

    plt.savefig(f'{graph_dir}plot_thetavsintensity.png', bbox_inches='tight')
    plt.close()




def analysis_xscan(file_name, graph_dir, top_bottom, ref_data_dir):

    ##scan data
    df = pd.read_hdf(file_name, 'df')
    theta_range = np.array(df.tVal.unique())
    theta_range = np.sort(theta_range)
    r_range = np.array(df.rVal.unique())
    r_range = np.sort(r_range)
    mean_charge = []
    std_charge = []

    for i in tqdm(theta_range):
        data = df[df.tVal == i]
        mean_charge_theta, std_charge_theta = point_hist(data, i, r_range, graph_dir)
        mean_charge.append(mean_charge_theta)
        std_charge.append(std_charge_theta)

    mean_charge = np.array(mean_charge)
    std_charge = np.array(std_charge) 
    theta_range_rad = np.deg2rad(theta_range)

    relative_mean_charge = mean_charge/np.max(mean_charge)

    plot_polar_heatmap(r_range, theta_range_rad, relative_mean_charge, graph_dir, top_bottom, mean_std='mean')
    plot_polar_heatmap(r_range, theta_range_rad, std_charge, graph_dir, top_bottom, mean_std='std')
    plot_theta_efficiency(r_range, theta_range, relative_mean_charge, graph_dir, top_bottom)

    #reference PMT check
    dfs = glob.glob(f'{ref_data_dir}*hdf5')
    dfs = natsorted(dfs)

    strthetas = []
    ref_charge = []
    ref_charge_error = []
    for i in dfs:
        strtheta = i.split('.')[0].split('/')[-1].split('_')[-1]
        mean, std = get_reference_data(i)
        strthetas.append(strtheta)
        ref_charge.append(mean)
        ref_charge_error.append(std)
    plot_ref_stability(strthetas, ref_charge, ref_charge_error, graph_dir)

    


##################################################
@click.command()
@click.argument('data_dir')
@click.argument('top_bottom')
@click.argument('graph_dir_name')
def main(data_dir, top_bottom, graph_dir_name):

    graph_dir = '/home/icecube/Workspace/degg_scan/graph/'+graph_dir_name+'/'
    file_name = f'{data_dir}sig/degg_scan_data_stamp.hdf5'
    ref_data_dir = f'{data_dir}ref/'
    try:
        os.mkdir(graph_dir)
    except:
        ans = input('Overwrite ??? (y/n): ')
        if(ans=='y'):
            print('OK!!')
        else:
            sys.exit()
    analysis_xscan(file_name, graph_dir, top_bottom, ref_data_dir)
if __name__ == '__main__':
    main()
##end