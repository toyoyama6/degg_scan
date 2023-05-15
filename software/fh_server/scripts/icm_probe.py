#!/usr/bin/env python
#
# Backward compatibility stub 
# 
import os
import sys
import subprocess

print("NB: icm_probe.py is deprecated, please use icm_status.py")
dir = os.path.dirname(os.path.realpath(__file__))
cmd = os.path.join(dir, "icm_status.py")
sys.argv[0] = cmd
subprocess.call(sys.argv)
#os.system(os.path.join(dir, "icm_status.py")+" "+sys.argv[1:])
