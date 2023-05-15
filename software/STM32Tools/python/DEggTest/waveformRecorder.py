#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from iceboot.test_waveform import writeWaveformFile
from optparse import OptionParser
import sys


def main():
    parser = getParser()
    parser.add_option("--waveformCount", dest="waveformCount",
                      help="Number of waveforms to collect", default="1")
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--outputFile", dest="outputFile",
                      help="Name of file to write", default=None)
    parser.add_option("--external", dest="external", action="store_true",
                      help="Use external trigger", default=False)
    parser.add_option("--threshold", dest="threshold",
                      help="Apply threshold trigger instead of CPU trigger "
                           "and trigger at this level", default=None)
    parser.add_option("--pulserPeriodUS", dest="pulserPeriodUS",
                      help="Enable the front-end pulser and set the period",
                      default=0)
    
    (options, args) = parser.parse_args()
    if options.outputFile is None:
        parser.print_help()
        sys.exit()

    session = startIcebootSession(parser)

    # Number of samples must be divisible by 4
    nSamples = (int(options.samples) / 4) * 4
    if (nSamples < 16):
        print("Number of samples must be at least 16")
        sys.exit(1)

    pulserPeriod = int(options.pulserPeriodUS)
    if (pulserPeriod > 0):
        session.enableFEPulser(int(options.channel), pulserPeriod)

    session.setDEggConstReadout(int(options.channel), 1, nSamples)

    waveforms = []
    while len(waveforms) < int(options.waveformCount):
        if (options.external):
            session.testDEggExternalTrig(int(options.channel))
        elif options.threshold is None:
            session.testDEggCPUTrig(int(options.channel))
        else:
            session.testDEggThresholdTrig(int(options.channel),
                                          int(options.threshold))
        readout = session.testDEggWaveformReadout()
        if readout is not None:
            waveforms.append(readout)
    writeWaveformFile(waveforms, options.outputFile)


if __name__ == "__main__":
    main()
