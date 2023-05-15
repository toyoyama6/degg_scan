# Aaron Fienberg
#
# Provides utility functions for:
# building DEgg ADC sample histograms in real time,
# plotting the histograms,
# and calculating summary statistics from the histograms
#
# Histograms are python dictionaries with
# the following three key value pairs:
# 'min': the minimum ADC value seen
# 'max': the maximum ADC value seen
# 'counts': an array of length (max-min) + 1; the histogram bin counts
#
# the ADC sample value associated with bin index i in the counts array
# is hist['min'] + i

from iceboot.test_waveform import parseTestWaveform
from matplotlib import pyplot as plt
import numpy as np
import math


def hist_mean(hist):
    bin_vals = np.arange(hist["min"], hist["max"] + 1)
    return np.average(bin_vals, weights=hist["counts"])


def hist_var(hist):
    bin_vals = np.arange(hist["min"], hist["max"] + 1)
    mean = hist_mean(hist)

    return np.average((bin_vals - mean) ** 2, weights=hist["counts"])


def hist_std(hist):
    return math.sqrt(hist_var(hist))


def plot_hist(hist, log_y=True):
    bin_vals = np.arange(hist["min"], hist["max"] + 1)
    plt.bar(bin_vals, hist["counts"], width=1, color="black")
    if log_y:
        plt.gca().set_yscale("log")
    plt.xlabel("ADU", fontsize=16)
    plt.ylabel("n samples", fontsize=16)
    plt.show()


def make_sw_trig_histogram(session, channel, wfm_period=3,
                           n_waveforms=1000, blocksize=0):
    """ Acquires software triggered waveforms and returns an
    ADC sample histogram dictionary """

    session.startDEggSWTrigStream(channel, wfm_period)

    total_counts = None
    wfm = None
    inputWfs = []
    for _ in range(n_waveforms):
        if blocksize == 0:
            # Read waveforms one-at-a-time
            wfm = parseTestWaveform(session.readWFMFromStream())
        else:
            # Read waveforms in blocks
            if len(inputWfs) == 0:
                inputWfs = session.readWFBlock(blocksize)
                if len(inputWfs) == 0:
                    raise RuntimeError("Read empty waveform block")
            wfm = inputWfs.pop()

        if wfm["channel"] != channel:
            raise RuntimeError("Read a waveform from the wrong channel!")

        # histogram the ADC samples from this waveform
        wfm_counts = np.bincount(wfm["waveform"], minlength=(1 << 14))

        # add this waveform's ADC histogram to the total histogram
        if total_counts is None:
            total_counts = wfm_counts
        else:
            total_counts += wfm_counts

    session.endStream()

    # prepare the histogram dictionary
    nonzero_args = np.argwhere(total_counts > 0)
    min_samp = nonzero_args[0][0]
    max_samp = nonzero_args[-1][0]

    histogram = {
        "counts": total_counts[min_samp : max_samp + 1],
        "min": min_samp,
        "max": max_samp,
    }

    return histogram


def calculate_quantiles(hist):
    """calculates the one percent and 99 percent quantiles
    Used in D-Egg and mDOM STF tests
    """
    cdf = np.cumsum(hist["counts"]) / np.sum(hist["counts"])

    # smallest x where p(ADC <= x) >= 0.01
    one_pct_q = hist["min"] + np.argwhere(cdf >= 0.01)[0][0]

    # smallest x where p(ADC <= x) >= 0.99
    ninetynine_pct_q = hist["min"] + np.argwhere(cdf >= 0.99)[0][0]

    return one_pct_q, ninetynine_pct_q


def print_hist_stats(hist):
    print("Hist metrics:")
    print(f'n samples: {hist["counts"].sum()}')
    print(f"mean: {hist_mean(hist)}")
    print(f"std: {hist_std(hist)}")
    print(f'min: {hist["min"]}')
    print(f'max: {hist["max"]}')
