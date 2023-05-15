import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit




def Gaussian(x, Aped, Mped, Sped):
    return Aped * np.exp(-(x - Mped) ** 2 / (2 * Sped ** 2)) 

def Fit_gaussian(data, bin, Aped, Mped, Sped):
    hist, bins = np.histogram(data, bins = bin, range=(np.min(data), np.max(data)))
    class_value_list = []
    for k in range(len(bins) - 1):
        class_value = (bins[k] + bins[k + 1]) / 2
        class_value_list.append(class_value)
    popt, pcov = curve_fit(Gaussian, class_value_list, hist, p0 = [Aped, Mped, Sped])
    return popt

df = pd.read_hdf("./timing_1_TransitTimeSpread_128_matched_triggers.hdf5")
df_degg =  df_degg = df[(df.type=="degg") & (df.channel == 1) & (df.valid==True)]



plt.figure()
plt.hist(df_degg.charge)
plt.savefig('./charge_stamp.png')
plt.close()




fig, ax = plt.subplots()
fig1, ax1 = plt.subplots()

for block in df.blockNum.unique():
    ttList = ((df_degg[df_degg.blockNum==block].mfhTime - df_degg[df_degg.blockNum==block].t_match) / 1e15 + (df_degg[df_degg.blockNum==block].delta - df_degg[df_degg.blockNum==block].refDelta)) * 1e9
    #popt = Fit_gaussian(ttList, 50, 50, 0, 2)
    #x = np.linspace(np.min(ttList), np.max(ttList), 50)
    #ax.plot(x, Gaussian(x, popt[0], popt[1], popt[2]))
    ax.hist(ttList, bins = 30,  histtype="step", label = f"block = {block}")
    #ax1.scatter(df_degg[df_degg.blockNum==block].charge, bins = 200)
ax.set_xlabel('ns', fontsize = 18)
ax.set_ylabel('events', fontsize = 18)
ax.legend()
fig.savefig('./ttList.png')
#fig1.savefig('charge_stamp.png')
