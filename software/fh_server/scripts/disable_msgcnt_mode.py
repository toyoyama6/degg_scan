#!/usr/bin/env python
#
import sys
import time
import icm_command_script as ics

# Disable the token on the MFH
print("Disabling token on MFH...")
ics.single_command(sys.argv, cmd="write", reg="token_ctrl", val="0x000a", only_local=True)
time.sleep(2)
# Disable message counting mode on remote devices
print("Disabling message counting mode on remote devices...")
ics.single_command(sys.argv, cmd="write", reg="token_ctrl", val="0x800a", only_remote=True)
# Disable message counting mode on the MFH
print("Enabling message counting mode on the MFH...")
ics.single_command(sys.argv, cmd="write", reg="token_ctrl", val="0x000a", only_local=True)
# Reenable the token on the MFH
print("Re-enabling token on the MFH...")
ics.single_command(sys.argv, cmd="write", reg="token_ctrl", val="0x800a", only_local=True)
# Issue a comms reset
print("Resetting comms...")
ics.single_command(sys.argv, cmd="comm_reset")
# Check TOKEN_CTRL everywhere
print("Reading TOKEN_CTRL:")
ics.single_command(sys.argv, cmd="read", reg="token_ctrl")
