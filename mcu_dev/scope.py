#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from iceboot.test_waveform import parseTestWaveform
from optparse import OptionParser
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import signal


def main():
    parser = getParser()
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--threshold", dest="threshold",
                      help="Apply threshold trigger instead of CPU trigger "
                           "and trigger at this level", default=None)
    parser.add_option("--adcMin", dest="adcMin",
                      help="Minimum ADC value to plot", default=None)
    parser.add_option("--adcRange", dest="adcRange",
                      help="Plot this many ADC counts above min",
                      default=None)
    parser.add_option("--swTrigDelay", dest="swTrigDelay",
                      help="ms delay between software triggers",
                      default=10)
    parser.add_option("--external", dest="external", action="store_true",
                      help="Use external trigger", default=False)
    
    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    
    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    session.setDEggConstReadout(int(options.channel), 1, int(nSamples))

    plt.ion()
    plt.show()
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.xlabel("Waveform Bin",ha='right',x=1.0)
    plt.ylabel("ADC Count",ha='right',y=1.0)
    line = None
    
    #print(session.readPressure())

    if options.external:
        session.startDEggExternalTrigStream(int(options.channel))
    elif options.threshold is None:
        session.startDEggSWTrigStream(int(options.channel), 
            int(options.swTrigDelay))
    else:
        session.startDEggThreshTrigStream(int(options.channel),
            int(options.threshold))

    # define signal handler to end the stream on CTRL-C
    def signal_handler(*args):
        print('\nEnding waveform stream...')
        session.endStream()
        print('Done')
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    while (True):

    
        try:
            readout = parseTestWaveform(session.readWFMFromStream())
        except IOError:
            print('Timeout! Ending waveform stream and exiting')
            session.endStream()
            break

        # Check for timeout
        if readout is None:
            continue
        wf = readout["waveform"]
        # Fix for 0x6a firmware
        if len(wf) != nSamples:
            continue
        xdata = [x for x in range(len(wf))]
        if not line:
            line, = ax.plot(xdata, wf, 'r-')
        else:
            line.set_ydata(wf)
        if (options.adcMin is None or options.adcRange is None):
            wfrange = (max(wf) - min(wf))
            plt.axis([0, len(wf),
                      max(wf) - wfrange * 1.2, min(wf) + wfrange * 1.2])
        else:
            plt.axis([0, len(wf), int(options.adcMin),
                      int(options.adcMin) + int(options.adcRange)])
        fig.canvas.draw()
        fig.canvas.flush_events()
        plt.pause(0.001)


if __name__ == "__main__":
    main()
