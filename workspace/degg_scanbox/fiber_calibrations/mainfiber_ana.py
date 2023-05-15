import glob
import numpy as np
from numpy.ma.extras import flatnotmasked_contiguous
from scipy import integrate
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import os
from tqdm import tqdm

def gaussian(x, A, mu, sigma):
    return A * np.exp(-(x-mu)**2/(2*sigma**2))

DEBUG = False
bin = 30

dirs = glob.glob('./data/singlefiber/*/')

dirs.sort()
dirs.remove('./data/singlefiber/trash/')

dt = np.arange(0, 12e-7, 12e-7/3000)

VOLT = []
CHARGE = []


for i in tqdm(dirs):

    dfs = glob.glob('{}*txt'.format(i))
    dfs.sort()

    charge = []
    volt = []

    for k in dfs:

        fig = k.split('/')

        df = np.loadtxt(k, skiprows=1)
        df = -df

        charge_list = []

        for t in range(len(df)):

            y = df[t] - np.mean(df[t][:500])

            inte_value = integrate.simps(y[1650:1770], dt[1650:1770])

            charge_list.append((inte_value/50)*10**12)

            if(DEBUG==True):
                plt.figure()
                plt.plot(dt[1650:1770], y[1650:1770])
                plt.show()

        y, bins = np.histogram(charge_list, bins=bin, range=(np.min(charge_list), np.max(charge_list)))

        x = []
        for b in range(len(bins)-1):
            
            x.append((bins[b+1]+bins[b])/2)

        x = [k for k in x if k > 0.1]
        xd = np.arange(min(x), max(x), 0.01)
        y = y[30-len(x):]
        try:
            popt, pcov = curve_fit(gaussian, x, y, p0=[np.max(y), x[15], np.sqrt(x[15])], maxfev=2000)
            estimated_curve = gaussian(xd, popt[0], popt[1], popt[2])

            y = [k for k in estimated_curve if k > 0]
            l = len(xd)
            xd =xd[l-len(y):]

            

            if(os.path.exists('./graph/{0}/{1}/'.format(fig[2], fig[3])) == False):
                os.mkdir('./graph/{0}/{1}/'.format(fig[2], fig[3]))

            plt.figure()
            plt.title("charge distribution", fontsize=18)
            # plt.plot(xd, y, color='r')
            plt.axvline(popt[1], color='black')
            plt.hist(charge_list, bins= bin, range=(np.min(charge_list), np.max(charge_list)))
            plt.xlabel("charge (pC)", fontsize=16)
            plt.yscale('log')
            plt.savefig('./graph/{0}/{1}/{2}V.png'.format(fig[2], fig[3], fig[4].split('V')[0]), bbox_inches='tight')
            # plt.show()
            plt.close()

            charge.append(popt[1])
            volt.append(float(fig[4].split('V')[0]))

        except:
            continue

    CHARGE.append(charge)
    VOLT.append(volt)

label_list = ['#1_1', '#1_2', '#1_3', '#2', '#3', '#4']

plt.figure()

plt.title('Splitfiber calibration', fontsize=18)
plt.ylabel('charge (pC)', fontsize=16)
plt.xlabel('supply voltage for LD (V)', fontsize=16)
plt.yscale('log')

for i in range(len(dirs)):

    plt.plot(VOLT[i], CHARGE[i], label=label_list[i])
plt.legend()
plt.savefig('./graph/singlefiber/test.png', bbox_inches='tight')


