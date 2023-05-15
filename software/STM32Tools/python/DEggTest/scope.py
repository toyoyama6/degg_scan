#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from iceboot.test_waveform import parseTestWaveform, applyPatternSubtraction
from optparse import OptionParser
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import signal


def getYN(phrase):

    question = phrase + ' (y/n): '
    while True:
        resp = None
        try:
            resp = raw_input(question)
        except:
            # Python 3
            resp = str(input(question))

        if resp is None or len(resp) == 0:
            continue

        reply = resp.lower().strip()[0]
        if reply == 'y':
            return True
        if reply == 'n':
            return False


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
    parser.add_option("--baselineSubtract", dest="bsub", action="store_true",
                      help="Subtract FPGA baseline", default=False)
    parser.add_option("--hv", dest="hv",
                      help="DEgg HV (in volts) to set", default=0)
    parser.add_option("--pulserPeriodUS", dest="pulserPeriodUS",
                      help="Enable the front-end pulser and set the period",
                      default=0)
    parser.add_option("--hbuf", dest="hbuf", action="store_true",
                      help="Use FPGA hit buffer", default=False)
    parser.add_option("--block", dest="block", action="store_true",
                      help="Use block readout of waveforms", default=False)
    
    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    
    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    session.setDEggConstReadout(int(options.channel), 1, int(nSamples))

    pulserPeriod = int(options.pulserPeriodUS)
    if (pulserPeriod > 0):
        session.enableFEPulser(int(options.channel), pulserPeriod)

    hv = int(options.hv)
    if (hv > 0):
        if not getYN("Enable PMT high voltage"):
            print("Aborting")
            return
        session.enableHV(int(options.channel))
        session.setDEggHV(int(options.channel), int(hv))

    plt.ion()
    plt.show()
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.xlabel("Waveform Bin")
    plt.ylabel("ADC Count")
    line = None

    if options.hbuf:
        if options.external:
            session.startDEggExternalHBufTrigStream(int(options.channel))
        else:
            session.setDEggADCTriggerThreshold(int(options.channel), int(options.threshold))
            session.startDEggADCHBufTrigStream(int(options.channel))
    else:
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
        session.disableHV(int(options.channel))
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    while (True):

        readouts = []

        try:
            if options.block:
                readouts = session.readWFBlock()
            else:
                readouts = [parseTestWaveform(session.readWFMFromStream())]
        except IOError:
            print('Timeout! Ending waveform stream and exiting')
            session.endStream()
            break

        for readout in readouts:

            # Check for timeout
            if readout is None:
                continue
            if options.bsub:
                applyPatternSubtraction(readout)
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

    session.disableHV(int(options.channel))

if __name__ == "__main__":
    main()
