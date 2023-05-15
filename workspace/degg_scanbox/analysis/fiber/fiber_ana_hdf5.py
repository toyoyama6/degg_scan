import h5py
import glob
import click
import os
import sys
import time
from tqdm import tqdm
from scipy import integrate
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import numpy as np
import tables

def gaussian(x, A, mu, sigma):
    return A * np.exp(-(x-mu)**2/(2*sigma**2))


def find_charge(t, waveform):

    integrate_value = integrate.simps(waveform, t)
    
    charge = integrate_value/50*1e12
    return charge


def get_charge(i):

    charge_list = []

    with tables.open_file(i) as open_file:
        data = open_file.get_node('/data')
        waveforms = data.col("waveform")
        times = data.col("time")

        start_point = int(len(times[0])/2)
        end_point = int(start_point + len(times[0])//6)

        base = np.mean(waveforms[0][0:200])

        for time, waveform in tqdm(zip(times, waveforms)):
            # np.sum(waveform[start_point:end_point])
            waveform = -waveform[start_point:end_point] + base
            time = time[start_point:end_point]
            charge = find_charge(time, waveform)
            charge_list.append(charge)

    return charge_list


def fit_gaussian(bin, charge_list):

    y, bins = np.histogram(charge_list, bins=bin, range=(min(charge_list), max(charge_list)))

    x = []
    for b in range(len(bins)-1):

        x.append((bins[b+1]+bins[b])/2)

    popt, pcov = curve_fit(gaussian, x, y, p0=[max(y), x[np.argmax(y)], np.sqrt(x[np.argmax(y)])], maxfev=2000)

    return popt


def hist_charge(graph_dir, bin, volt, charge_list):

    popt = fit_gaussian(bin, charge_list)

    xd = np.arange(np.min(charge_list), np.max(charge_list), 0.01)
    estimated_curve = gaussian(xd, popt[0], popt[1], popt[2])

    plt.figure()
    plt.title(f'Charge distribution ({volt})', fontsize=18)
    plt.xlabel('Charge (pC)', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.hist(charge_list, bins=bin, range=(np.min(charge_list), np.max(charge_list)), color='blue')
    plt.plot(xd, estimated_curve, color='red')
    plt.savefig(f'{graph_dir}{volt}V.png', bbox_inches='tight')
    plt.close()
    mean_charge = popt[1]
    std_charge = popt[2]

    return mean_charge, std_charge

def plot_1d_approximate(x, y, y_err, graph_dir, xlabel='x', ylabel='y',
                    title='title'):

    a, b = np.polyfit(x, y, 1)
    xd = np.arange(np.min(x), np.max(x), 0.001)
    yd = a*xd + b
    RMS = []
    for i in range(len(x)):
        rms = ((a*x[i]+b)-y[i])**2
        RMS.append(rms)
    RMSerror = np.sqrt(np.sum(RMS)/len(RMS))
    RMSerror = float(format(RMSerror, '.2f'))

    a = float(format(a, '.2f'))
    b = float(format(b, '.2f'))

    plt.figure()
    plt.title(f'{title}', fontsize=18)
    plt.xlabel(f'{xlabel}', fontsize=16)
    plt.ylabel(f'{ylabel}', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.errorbar(x, y, yerr=y_err, markersize=5, fmt='o', ecolor='black', markeredgecolor='black', color='w')
    plt.plot(xd, yd, color='black', linestyle='dashed', label=f'y={a}x+{b}\nRMSE = {RMSerror}')
    plt.legend()
    plt.savefig(f'{graph_dir}Charge_Voltage.png', bbox_inches='tight')
    plt.close()


def plot_scatter(x, y, graph_dir, xlabel='x', ylabel='y',
                    title='title'):
    
    plt.figure()
    plt.title(f'{title}', fontsize=18)
    plt.xlabel(f'{xlabel}', fontsize=16)
    plt.ylabel(f'{ylabel}', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.scatter(x, y)
    # plt.legend()
    plt.savefig(f'{graph_dir}coefficient_of_variation_Voltage.png', bbox_inches='tight')



def fiber_mes(data_dir, graph_dir):

    print('start plotting')

    bin = 30
    mean_charge_list = []
    std_charge_list = []
    volt_list = []

    dfs = glob.glob(f'{data_dir}*.hdf5')
    dfs.sort()

    for i in dfs:
        
        volt = float(os.path.splitext(i)[0].split('/')[-1].split('_')[1])
        volt = float(format(volt, '.2f'))
        charge_list = get_charge(i)
        mean_charge, std_charge = hist_charge(graph_dir, bin, volt, charge_list)

        np.save(f'{data_dir}{volt}', charge_list)

        volt_list.append(volt)
        mean_charge_list.append(mean_charge)
        std_charge_list.append(std_charge)
    
    std_charge_list = np.array(std_charge_list)
    mean_charge_list = np.array(mean_charge_list)
    print(np.sqrt(len(charge_list)))
    np.savez(f'{graph_dir}/volt_charge', volt_list, mean_charge_list, std_charge_list/np.sqrt(len(charge_list)))
    plot_1d_approximate(volt_list, mean_charge_list, std_charge_list/np.sqrt(len(charge_list)), graph_dir,
                        xlabel='supply voltage for LD (V)', ylabel='Charge (pC)',
                        title='Charge vs supply voltage')

    coefficient_of_variation = std_charge_list/mean_charge_list
    # print(std_charge_list)
    # print(mean_charge_list)
    # print(coefficient_of_variation)

    plot_scatter(volt_list, coefficient_of_variation, graph_dir,
                xlabel='supply voltage for LD (V)',
                ylabel='coefficient of variation',
                title='coefficient of variation vs voltage')

    



@click.command()
@click.argument('dir_name')
@click.option('--data_dir', '-d', default='/home/icecube/Workspace/degg_scan/fiber_calibrations/data/filter_0.5/')
@click.option('--graph_dir', '-g', default='/home/icecube/Workspace/degg_scan/fiber_calibrations/graph/volt_charge/')
def main(data_dir, graph_dir, dir_name):

    graph_dir = graph_dir + dir_name + '/'
    try:
        os.mkdir(graph_dir)
    except:
        ans = input('Overwrite ??? (y/n): ')
        if(ans=='y'):
            print('OK!!')
        else:
            sys.exit()
    fiber_mes(data_dir, graph_dir)

if __name__ == "__main__":
    main()
##end
