#!/usr/bin/env python
#
# Turn connected mainboards off.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="mb_off", only_remote=True)
