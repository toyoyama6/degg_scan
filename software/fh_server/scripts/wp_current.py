#!/usr/bin/env python
#
# Read wire pair current (A).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="wp_current", only_local=True)
