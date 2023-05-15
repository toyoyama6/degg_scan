#!/usr/bin/env python
#
# Disable LID (via interlock).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="lid_disable", only_remote=True)
