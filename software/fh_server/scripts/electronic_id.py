#!/usr/bin/env python
"""
    Parse, validate ICM, Mainboard 64-bit electronic IDs, using the Maxim vendor
    CRC8 algorithm.
"""

from maxim_crc8 import MaximCRC8
import sys


def main():

    if len(sys.argv) == 1:
        raise Exception('no input')

    maxim = MaximCRC8(sys.argv[1:])

    print('chip: %s' %  maxim.getChip() )
    bytes = maxim.getBytes()
    print('serial number:  0x %02x %02x %02x %02x %02x %02x'  %
        (bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6]))
    print('crc: 0x%02x valid: %s' % (bytes[-1], maxim.getStatus() ))

    sys.exit(0 if maxim.getStatus else 1)


if __name__ == "__main__":
    main()

