#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from optparse import OptionParser
from math import sqrt, pow
import numpy as np
import matplotlib.pyplot as plt
import time
import sys


DIGITIZER_FREQ = 120000000


def main():
    parser = OptionParser()
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default="192.168.0.10")
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default="5012")
    parser.add_option("--debug", dest="debug", action="store_true",
                      help="Print board I/O stdout", default=False)
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--count", dest="count", help="Number of waveforms "
                               "to record",  default=100)
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--baseline", dest="baseline",
                      help="Set the ADC baseline to this value, calibrating "
                           "if needed.  Overrides --biasDAC.", default=None)

    
    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    
    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    channel = int(options.channel)

    # Set baseline if requested
    if options.baseline is not None:
        session.mDOMSetBaselines(int(options.baseline))

    session.mDOMSetConstReadout(nSamples)
    session.mDOMStartSoftwareTrigStream(channel, 0)

    # Build output power spectrum array
    output = []
    wfCnt = 0
    while wfCnt < int(options.count):

        # Trigger readouts
        try:
            readouts = session.readWFBlock()
        except IOError:
            print('Timeout! Ending waveform stream and exiting')
            session.endStream()
            sys.exit(1)

        for readout in readouts:

            if readout is None:
                continue
            # Readout waveform. Units: LSBs.  Convert from numpy format
            wf = [x for x in readout["waveform"]]
            if len(output) == 0:
                output = [0.] * len(wf)
            else:
                if len(wf) != len(output):
                    continue
            av = (float(sum(wf))) / len(wf)
            for i in range(len(wf)):
                wf[i] = float(wf[i]) - av
            # Calculate power density spectrum. Units: (LSB)**2.
            # Note: fft() returns complex vectors, abs() returns the magnitude.
            ps = np.abs(np.fft.fft(wf))
            for i in range(len(ps)):
                output[i] += ps[i] / nSamples
            wfCnt += 1
            if wfCnt == int(options.count):
                break

    session.endStream()

    # Remove negative frequency bins
    normOutput = output[:(int(len(output) / 2) + 1)]

    # Normalize power spectral density
    binWidth = DIGITIZER_FREQ * nSamples
    norm = 1. / (wfCnt * wfCnt * binWidth)
    for i in range(len(normOutput)):
        normOutput[i] = norm * normOutput[i] * normOutput[i]

    # Multiply power in bins with both positive and negative frequencies by
    # 2 to conserve total power
    for i in range(1, len(normOutput) - 1):
        normOutput[i] *= 2

    # Convert PSD back to amplitude in LSB
    for i in range(len(normOutput)):
        normOutput[i] = sqrt(normOutput[i] * binWidth)

    # Return sample frequencies
    time_step = 1. / DIGITIZER_FREQ
    freqs = np.abs( np.fft.fftfreq(len(output), time_step) )

    # Remove negative frequency bins
    freqs = freqs[:(int(len(freqs) / 2) + 1)]

    # Remove DC
    x = freqs[1:]
    y = normOutput[1:]
    noise_spectrum = { 'frequency': x, 'amplitude': y }

    # Development use
    plt.xlabel("Frequency")
    plt.ylabel("Amplitude (LSB/sqrt(bins))")
    #plt.yscale("log")
    title = 'FFT Amplitude Channel %d' % channel
    plt.grid(True)
    plt.title(title)
    plt.plot(x, y, "r-")
    plt.show()


if __name__ == "__main__":
    main()
