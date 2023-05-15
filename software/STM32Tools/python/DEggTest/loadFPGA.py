#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
import sys


def main():
    parser = getParser()    
    (options, args) = parser.parse_args()
    if options.fpgaConfigurationFile == None:
        print("No FPGA configuration file specified")
        sys.exit(1)

    session = startIcebootSession(parser)


if __name__ == "__main__":
    main()
