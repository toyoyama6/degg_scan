#!/usr/bin/env python

import argparse
from fatcat_db.eeprom_crc import MaximCRC8

cmdparser = argparse.ArgumentParser()
cmdparser.add_argument(dest='id', type=str, help='eeprom id')
args = cmdparser.parse_args()

crc = MaximCRC8(args.id)
passed = crc.isValid()
print('Valid eeprom = {0}'.format(passed))
if not passed:
    print('Expected CRC = {0}'.format(crc.getCRC()))

