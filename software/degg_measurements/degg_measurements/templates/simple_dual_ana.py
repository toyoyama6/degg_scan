import numpy as np
import matplotlib.pyplot as plt
import os, sys

def extract_values(file_path):
    ch0_wf_max = []
    ch1_wf_max = []
    ch0_baseline = []
    ch1_baseline = []
    ch0_mb_timestamp = []
    ch1_mb_timestamp = []

    if not os.path.exists(file_path):
        raise IOError(f"Could not find {file_path}!")

    if os.path.exists(file_path) is True:
        f = open(file_path, "r")
        print(f"Opening {file_path}")
        for line in f:
            split = line.split(", ")
            channel = split[0]
            wf_max = split[1]
            wf_baseline = split[2]
            mb_timestamp = split[3]

            ##convert values to int
            channel = int(channel)
            wf_max = int(wf_max)
            wf_baseline = float(wf_baseline)
            wf_baseline = int(wf_baseline)
            mb_timestamp = int(mb_timestamp)

            if channel == 0:
                ch0_wf_max.append(wf_max)
                ch0_baseline.append(wf_baseline)
                ch0_mb_timestamp.append(mb_timestamp)

            if channel == 1:
                ch1_wf_max.append(wf_max)
                ch1_baseline.append(wf_baseline)
                ch1_mb_timestamp.append(mb_timestamp)

        f.close()
        return (ch0_wf_max, ch1_wf_max, ch0_baseline, ch1_baseline, ch0_mb_timestamp, ch1_mb_timestamp)


def convert_to_mv(vals, conversion_factor):
    vals = np.array(vals)
    vals = vals * conversion_factor
    return vals

def max_hist(name, vals, channel="-1"):
    fig1, ax1 = plt.subplots()
    ax1.hist(vals, bins=50, color='royalblue')
    ax1.set_xlabel("Waveform Max [mV]")
    ax1.set_ylabel("Entries")
    ax1.set_title(f"{channel}")
    fig1.savefig(os.path.expandvars(
        f"$HOME/workshop/{name}/wf_max_{channel}.pdf"))

if __name__ == "__main__":

    conversion_factor = 0.089 ##convert to mV
    name = "colton"
    file_path = os.path.expandvars(
        f"$HOME/workshop/{name}/dual_channel_output_dict.txt")
   
    ch0_wf_max, ch1_wf_max, ch0_baseline, ch1_baseline, ch0_mb_timestamp, ch1_mb_timestamp = extract_values(file_path)

    ch0_wf_max = np.array(ch0_wf_max)
    ch1_wf_max = np.array(ch1_wf_max)
    ch0_baseline = np.array(ch0_baseline)
    ch1_baseline = np.array(ch1_baseline)

    ch0_peak = ch0_wf_max - ch0_baseline
    ch1_peak = ch1_wf_max - ch1_baseline

    ch0_peak = convert_to_mv(ch0_peak, conversion_factor)
    ch1_peak = convert_to_mv(ch1_peak, conversion_factor)

    max_hist(name, ch0_peak, "Ch0")
    max_hist(name, ch1_peak, "Ch1")

##end
