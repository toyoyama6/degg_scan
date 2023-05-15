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
                               "to record at each DAC setting",  default=100)
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--dacMin", dest="dacMin",
                      help="Minimum DAC value to scan", default=0)
    parser.add_option("--dacMax", dest="dacMax",
                      help="Maximum DAC value to scan", default=65000)
    parser.add_option("--dacIncrement", dest="dacIncrement",
                      help="Increment the DAC by this unit", default=100)
    
    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    
    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    session.setDEggConstReadout(int(options.channel), 1, nSamples)

    
    dacMin = int(options.dacMin)
    dacMax = int(options.dacMax)
    dacIncrement = int(options.dacIncrement)
    channel = int(options.channel)
    dacChannel = 'A'
    if channel == 1:
        dacChannel = 'B'
    data = {}
    
    for dac in range(dacMin, dacMax, dacIncrement):
        
        session.setDAC(dacChannel, dac)
        time.sleep(0.1)
        
        vals = []
        for _ in range(int(options.count)):
            session.testDEggCPUTrig(int(options.channel))
            readout = session.testDEggWaveformReadout()
            if readout is None:
                continue
            wf = readout["waveform"]
            vals.extend(wf)
            
        av = (float(sum(vals))) / len(vals)
        rms = sqrt(sum([pow(x - av, 2) for x in vals]) / len(vals))
        data[dac] = {"average": av, "rms": rms}
        print ("DAC: %s Mean: %s, RMS: %s" % (dac, av, rms))
    
    plt.xlabel("ADC Mean")
    plt.ylabel("ADC RMS")
    x = [data[dac]["average"] for dac in sorted(data.keys())]
    y = [data[dac]["rms"] for dac in sorted(data.keys())]
    plt.plot(x, y, 'r-')
    plt.show()


if __name__ == "__main__":
    main()
