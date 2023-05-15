#!/usr/bin/env python
#
# Turn wire pair off.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="wp_off", only_local=True)
ics.single_command(sys.argv, cmd="probe", only_local=True)

