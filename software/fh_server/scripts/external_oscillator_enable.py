#!/usr/bin/env python
#
# Enable FieldHub external oscillator
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="ext_osc_enable", only_local=True)
