#!/usr/bin/env python
#
# socket_disconnect.py
# 
# Disconnect device socket(s) for remote devices that are present
#
import sys
import icm_command_script as ics

ics.single_command(sys.argv, cmd="disconnect", only_remote=True)
