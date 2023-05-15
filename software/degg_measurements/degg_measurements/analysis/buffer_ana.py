import os, sys
import numpy
import matplotlib.pyplot as plt

f = open("/home/scanbox/data/develop/dual_channel_summary.txt", "r")

n_samples_list = []
t_buffer_empty = []
t_buffer_full = []
num_full = []
rate_list = []

for line in f:
    split = line.split(": ")
    if split[0] == "Samples":
        n_samples = split[1]
        n_samples = n_samples[:-1]
        n_samples = float(n_samples)
        n_samples = int(n_samples)
        n_samples_list.append(n_samples)

    if split[0] == "Time to Empty Buffer":
        t_empty = split[1]
        t_empty = t_empty[:-1]
        t_empty = float(t_empty)
        t_buffer_empty.append(t_empty)
    
    if split[0] == "Time to Fill Buffer":
        t_full = split[1]
        t_full = t_full[:-1]
        t_full = float(t_full)
        t_buffer_full.append(t_full)

    if split[0] == "Num WF to Fill Buffer":
        num = split[1]
        num = num[:-1]
        num = float(num)
        num = int(num)
        num_full.append(num)

    if split[0] == "Trigger Rate Corr.":
        rate = split[1]
        rate = rate[:-1]
        rate = float(rate)
        rate_list.append(rate)

f.close()

fig1, ax1 = plt.subplots()
ax1.plot(n_samples_list, t_buffer_empty, linewidth=0, marker='o', color='royalblue')
ax1.set_xlabel("Num. Samples")
ax1.set_ylabel("Median Time to Empty Buffer (Ch0) [s]")
fig1.savefig("/home/scanbox/data/develop/samples_vs_t_empty.pdf")

fig2, ax2 = plt.subplots()
ax2.plot(n_samples_list, t_buffer_full, linewidth=0, marker='o', color='royalblue')
ax2.set_xlabel("Num. Samples")
ax2.set_ylabel("Median Time to Fill Buffer (Ch0) [s]")
fig2.savefig("/home/scanbox/data/develop/samples_vs_t_full.pdf")

fig3, ax3 = plt.subplots()
ax3.plot(n_samples_list, num_full, linewidth=0, marker='o', color='royalblue')
ax3.set_xlabel("Num. Samples")
ax3.set_ylabel("Median Number of Samples to Fill Buffer (Ch0)")
fig3.savefig("/home/scanbox/data/develop/samples_vs_n_full.pdf")

fig4, ax4 = plt.subplots()
rate_list_err_guess = [1] * len(rate_list) ##1 Hz uncertainty

ax4.errorbar(n_samples_list, rate_list, yerr=rate_list_err_guess, linewidth=0, marker='o', color='royalblue', elinewidth=2)
ax4.set_xlabel("Num. Samples")
ax4.set_ylabel("Median Trigger Rate (Ch0) [Hz]")
fig4.savefig("/home/scanbox/data/develop/samples_vs_rate.pdf")

##end
