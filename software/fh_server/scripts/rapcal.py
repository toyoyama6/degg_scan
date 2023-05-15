#!/usr/bin/env python
#
# Initiate RAPCal on the requested devices.
#

import sys
import icm_command_script as ics

# Special case: use different command for all devices
if (len(sys.argv) == 1):
    print("Use rapcal_all to initiate RAPCal to all connected devices.");
    sys.exit(0)

ics.single_command(sys.argv, cmd="rapcal", only_remote=True)
