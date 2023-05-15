#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from optparse import OptionParser
from math import sqrt, pow
import numpy as np
import matplotlib.pyplot as plt
import time
import sys


def main():
    parser = getParser()
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--count", dest="count", help="Number of waveforms "
                               "to record",  default=100)
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    
    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    
    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    session.setDEggConstReadout(int(options.channel), 1, nSamples)

    output = []
    
    for _ in range(int(options.count)):
        session.testDEggCPUTrig(int(options.channel))
        readout = session.testDEggWaveformReadout()
        if readout is None:
            continue
        wf = readout["waveform"]
        if len(output) == 0:
            output = [0.] * len(wf)
        else:
            if len(wf) != len(output):
                continue
        av = (float(sum(wf))) / len(wf)
        for i in range(len(wf)):
            wf[i] -= av
        ps = np.abs(np.fft.fft(wf))**2
        for i in range(len(ps)):
            output[i] += ps[i]

    time_step = 1. / 240000000.
    freqs = np.abs( np.fft.fftfreq(len(output), time_step) )
    
    plt.xlabel("Frequency")
    plt.ylabel("Power (A.U.)")
    ll = int(len(freqs) / 2) + 1
    plt.plot(freqs[int(0.01*ll):ll], output[int(0.01*ll):ll], "r-")
    plt.show()


if __name__ == "__main__":
    main()
