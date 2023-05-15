import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from natsort import natsorted

# date = "2022_01_05_21_52"
# date = "2022_01_05_20_21"
# date = "2022_01_06_17_18"
# date = "2022_01_07_09_22"
date = "2022_01_07_09_39"
data_dir = "./data/{}/".format(date)
graph_dir = "./graph/{}/".format(date)

if (os.path.exists(graph_dir)==False):

    os.mkdir(graph_dir)

dfs = glob.glob("{}*.txt".format(data_dir))

dfs = natsorted(dfs)

# df = np.loadtxt(dfs[0], skiprows=1)

# print(df)

t_n = 0
count = 0
peak = []
c_list = []

for i in dfs:
    df = np.loadtxt(i, skiprows=1)
    print(i)

    for k in range(len(df)):
        peak.append(df[k][4])

    count += len(df)
    c_list.append(len(df)/0.32)
    t_n += 0.32

plt.figure()
plt.title('peak distribution', fontsize=18)
plt.xlabel('peak (mV)', fontsize=16)
plt.hist(peak, bins=30, range=(np.min(peak), np.max(peak)))
plt.savefig("{}peak_distribution.png".format(graph_dir), bbox_inches='tight')
plt.close()

plt.figure()
plt.title('rate vs time')
plt.scatter(range(len(c_list)), c_list)
plt.ylabel('rate (Hz)', fontsize=16)
plt.savefig("{}time_rate.png".format(graph_dir), bbox_inches='tight')
plt.close()

print(t_n, count, count/t_n)



