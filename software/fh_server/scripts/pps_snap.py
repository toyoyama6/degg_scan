#!/usr/bin/env python
#
# Get a PPS snapshot from the FieldHub
#
from __future__ import print_function
import sys
import time
import argparse
from icmnet import ICMNet

# GPS ready bit
FH_GPS_CTRL_READY = 0x2

# GPS ready polling times
POLL_MAX = 1.25
POLL_INTERVAL = 0.25

# Get arguments
parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", type=int, default=6000,
                    help="domnet command port (default=6000)")
parser.add_argument("--host", default="localhost",
                    help="connect to host (default localhost)")
parser.add_argument("-v", "--version", action="store_true", help="print domnet version")
parser.add_argument("-n", "--cnt", type=int, default=1, help="# of iterations")

args = parser.parse_args(sys.argv[1:])

# Connect to server
icms = ICMNet(args.port, args.host)

if (args.version):
    reply = icms.request("version")
    if "value" in reply:
        print(reply["value"])            
    else:        
        print(str(reply["status"]))
    sys.exit(0)

last_icm = None
for i in range(args.cnt):
    # Enable one PPS snapshot
    reply = icms.request("gps_enable")

    # Now check GPS status for ready
    sleep_time = 0
    gps_ready = False
    while (sleep_time <= POLL_MAX) and not gps_ready:
        time.sleep(POLL_INTERVAL)
        sleep_time += POLL_INTERVAL
        try:
            reply = icms.request("get_gps_ctrl")
            val = int(reply["value"], 16)
            if (val & FH_GPS_CTRL_READY != 0):
                gps_ready = True
        except:
            print("Error polling for GPS ready bit, exiting!")
            sys.exit(-1)

    if gps_ready:
        reply = icms.request("get_gps_time")
        gps_str = reply["value"]
        reply = icms.request("get_icm_time %d" % ICMNet.FH_DEVICE_NUM)
        icm_str = reply["value"]
        icm_time = int(icm_str, 16)            
        if last_icm is not None:
            delta = icm_time-last_icm
            print(gps_str, icm_str, delta)
        else:
            print(gps_str, icm_str)
        last_icm = icm_time          
    else:
        print("GPS never reported ready!")
        sys.exit(-1)

    i=i+1

