#!/usr/bin/env python
#
# Disable FieldHub external oscillator
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="ext_osc_disable", only_local=True)
