#!/usr/bin/env python
#
# Turn wire pair on.
#

import sys
import time
import icm_command_script as ics

ics.single_command(sys.argv, cmd="wp_on", only_local=True)
time.sleep(2)
ics.single_command(sys.argv, cmd="probe", only_local=True)
