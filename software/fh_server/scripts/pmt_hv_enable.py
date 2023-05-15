#!/usr/bin/env python
#
# Enable PMT HV (via interlock).
#

import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="pmt_hv_enable", only_remote=True)
