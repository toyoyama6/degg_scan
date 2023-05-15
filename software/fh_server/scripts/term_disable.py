#!/usr/bin/env python
#
# Disable device termination.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="term_disable", only_remote=True)
