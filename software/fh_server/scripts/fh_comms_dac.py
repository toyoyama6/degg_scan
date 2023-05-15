#!/usr/bin/env python
#
# Set the local ICM comms DAC to
# a user specified value
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="write", reg="dac_amp", only_local=True)
