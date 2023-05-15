#!/usr/bin/env python
#
# Enable device termination.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="term_enable", only_remote=True)
