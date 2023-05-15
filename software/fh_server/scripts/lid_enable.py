#!/usr/bin/env python
#
# Enable LID (via interlock).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="lid_enable", only_remote=True)
