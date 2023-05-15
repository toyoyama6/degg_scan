#!/usr/bin/env python
#
# Read wire pair voltage (V).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="wp_voltage", only_local=True)
