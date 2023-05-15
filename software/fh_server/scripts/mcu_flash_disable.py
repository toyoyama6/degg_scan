#!/usr/bin/env python
#
# Disable MCU flash write (via interlock).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="mcu_flash_disable", only_remote=True)
