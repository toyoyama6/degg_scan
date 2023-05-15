#!/usr/bin/env python
#
# Power cycle the connected mainboard(s)
#

import sys
import time
import icm_command_script as ics

print("Powering off mainboard(s)...")
ics.single_command(sys.argv, cmd="mb_off", only_remote=True)
time.sleep(2)
print("Powering on mainboard(s)...")
ics.single_command(sys.argv, cmd="mb_on", only_remote=True)
