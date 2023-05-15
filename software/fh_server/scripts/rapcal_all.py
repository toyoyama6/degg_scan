#!/usr/bin/env python
#
# Initiate RAPCal on all present devices on the wire pair.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="rapcal_all", only_local=True)
