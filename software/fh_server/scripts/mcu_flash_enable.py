#!/usr/bin/env python
#
# Enable MCU flash write (via interlock).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="mcu_flash_enable", only_remote=True)
