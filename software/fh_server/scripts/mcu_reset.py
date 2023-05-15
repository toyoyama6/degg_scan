#!/usr/bin/env python
#
# Reset the connected mainboard MCU(s)
#

import sys
import time
import icm_command_script as ics

print("Enabling MCU reset...")
ics.single_command(sys.argv, cmd="mcu_reset", only_remote=True)
time.sleep(2)
print("Disabling MCU reset...")
ics.single_command(sys.argv, cmd="mcu_reset_n", only_remote=True)
