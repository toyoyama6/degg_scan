#!/usr/bin/env python
#
# Reset the firmware fuse on the FieldHub
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="fuse_reset", only_local=True)
print("If fuse was tripped, wire pair still needs to be powered on.")

