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
    parser = OptionParser()
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default="192.168.0.10")
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default="5012")
    parser.add_option("--debug", dest="debug", action="store_true",
                      help="Print board I/O stdout", default=False)
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--discDAC", dest="discDAC",
                      help="Apply discriminator trigger instead of CPU trigger "
                           "and set discriminator DAC to this level", default=None)
    parser.add_option("--biasDAC", dest="biasDAC",
                      help="Set the AFE bias DAC to this value", default=None)
    parser.add_option("--pulserDAC", dest="pulserDAC",
                      help="Set the FE pulser DAC to this value", default=None)
    parser.add_option("--swTrigDelay", dest="swTrigDelay",
                      help="ms delay between software triggers",
                      default=10)
    parser.add_option("--adcMin", dest="adcMin",
                      help="Minimum ADC value to plot", default=0)
    parser.add_option("--adcRange", dest="adcRange",
                      help="Plot this many ADC counts above min",
                      default=4096)
    parser.add_option("--discTrigger", dest="discTrigger", action="store_true",
                      help="Trigger on the discriminator level", default=False)
    parser.add_option("--externalTrigger", dest="externalTrigger", action="store_true",
                      help="Use external trigger", default=False)
    parser.add_option("--calibrationTrigger", dest="calibrationTrigger", action="store_true",
                      help="Readout simultaneous with calibration trigger", default=False)
    parser.add_option("--block", dest="block", action="store_true",
                      help="Use block readout of waveforms", default=False)
    parser.add_option("--hbuf", dest="hbuf", action="store_true",
                      help="Use FPGA hit buffer", default=False)
    parser.add_option("--pulserPeriodUS", dest="pulserPeriodUS",
                      help="Enable the front-end pulser and set the period",
                      default=0)
    parser.add_option("--pulserPulseWidthNS", dest="pulserPulseWidthNS",
                      help="Time in ns between pulser discharge and recharge",
                      default=200)
    parser.add_option("--pulserTrigger", dest="pulserTrigger", action="store_true",
                      help="Fire the pulser according to swTrigDelay and capture the waveform",
                      default=False)
    parser.add_option("--adcTrigger", dest="adcTrigger", action="store_true",
                      help="Trigger on the waveform ADC level", default=False)
    parser.add_option("--adcTriggerThreshold", dest="adcTriggerThreshold", default=0,
                      help="Trigger when the waveform ADC level is less than "
                           "or equal to this value")
    parser.add_option("--baseline", dest="baseline",
                      help="Set the ADC baseline to this value, calibrating "
                           "if needed.  Overrides --biasDAC.", default=None)
    parser.add_option("--discriminatorVoltage", dest="discriminatorVoltage",
                      help="Set the discriminator voltage to this value."
                           "  Overrides --discDAC.", default=None)
    
    (options, args) = parser.parse_args()

    trigcnt = 0;
    if options.pulserTrigger:
        trigcnt += 1
    if options.externalTrigger:
        trigcnt += 1
    if options.adcTrigger:
        trigcnt += 1
    if options.discTrigger:
        trigcnt += 1
    if options.calibrationTrigger:
        trigcnt += 1

    if trigcnt > 1:
        print("Multiple trigger sources specified, only one is allowed")
        sys.exit(-1)

    session = startIcebootSession(parser)
    
    channel = int(options.channel)
    if channel >= 24:
        print("Bad channel: %s" % channel)
        sys.exit(-1)

    if options.discDAC is not None:
        session.mDOMSetDiscThreshDAC(channel, int(options.discDAC))
    if options.biasDAC is not None:
        session.mDOMSetADCBiasDAC(channel, int(options.biasDAC))
    if options.pulserDAC is not None:
        session.mDOMSetFEPulserDAC(channel, int(options.pulserDAC))

    session.mDOMSetFEPulserWidth(int(options.pulserPulseWidthNS))
    session.mDOMSetADCTriggerThresh(int(options.adcTriggerThreshold))

    pulserPeriod = int(options.pulserPeriodUS)
    if (pulserPeriod > 0):
        session.mDOMEnableFEPulsers(pulserPeriod)
    else:
        session.mDOMDisableFEPulsers()

    # Set baseline if requested
    if options.baseline is not None:
        session.mDOMSetBaselines(int(options.baseline))

    # Set discriminator thresholds if requested
    if options.discriminatorVoltage is not None:
        session.mDOMSetDiscriminatorThresholds(float(options.discriminatorVoltage))

    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)
    session.mDOMSetConstReadout(nSamples)

    plt.ion()
    plt.show()
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.xlabel("Waveform Bin")
    plt.ylabel("ADC Count")
    line = None

    # define signal handler to end the stream on CTRL-C
    def signal_handler(*args):
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    # start the waveform stream
    if options.hbuf:
        if options.externalTrigger:
            session.mDOMStartExtHBufTrigStream(channel)
        elif options.discTrigger:
            session.mDOMStartDiscHBufTrigStream(channel)
        elif options.adcTrigger:
            session.mDOMStartADCThreshHBufTrigStream(channel)
        elif options.calibrationTrigger:
            session.mDOMStartCalibrationHBufTrigStream(channel)
    else:
      if options.pulserTrigger:
          session.mDOMStartPulserTrigStream(channel, int(options.swTrigDelay))
      elif options.externalTrigger:
          session.mDOMStartExtTrigStream(channel)
      elif options.discTrigger:
          session.mDOMStartDiscTrigStream(channel)
      elif options.adcTrigger:
          session.mDOMStartADCThreshTrigStream(channel)
      elif options.calibrationTrigger:
          session.mDOMStartCalibrationTrigStream(channel, int(options.swTrigDelay))
      else:
          session.mDOMStartSoftwareTrigStream(channel, int(options.swTrigDelay))

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

            wf = []
            for x in readout["waveform"]:
                wf.extend([x] * 8)
            disc = []
            for x in readout["discWords"]:
                for b in range(8):
                    disc.append(x & 0x01)
                    x >>= 1
            xdata = [x / 8. for x in range(len(wf))]
            if not line:
                line, = ax.plot(xdata, wf, 'r-')
            else:
                line.set_ydata(wf)
            wfrange = (max(wf) - min(wf))
            pmin = max(wf) - wfrange * 1.2
            pmax = min(wf) + wfrange * 1.2
            if (options.adcMin is not None and options.adcRange is not None):
                pmin = int(options.adcMin)
                pmax = int(options.adcMin) + int(options.adcRange)
            plt.axis([0, len(wf) / 8, pmin, pmax])
            fill_between_col = ax.fill_between(np.array(xdata), pmin, pmax, where=(np.array(disc) == 1), facecolor='yellow', alpha=0.5)
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.001)
            fill_between_col.remove()

if __name__ == "__main__":
    main()
