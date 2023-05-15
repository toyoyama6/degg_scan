#!/usr/bin/env python
#
# Turn connected mainboards on.
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="mb_on", only_remote=True)
