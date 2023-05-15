#!/usr/bin/env python
#
# Reset the ICM communications status.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="comm_reset")
