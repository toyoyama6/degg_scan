#!/usr/bin/env python
#
# Get the ICM IDs of connected devices.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="read", reg="icm_id")
