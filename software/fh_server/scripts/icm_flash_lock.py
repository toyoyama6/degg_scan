#!/usr/bin/env python
#
# Lock the write protection on the ICM golden image flash area (images 0 and 1).
# Unlocking likely requires physical access to the ICM.
#
import sys
import time
import argparse
import zmq

from icmnet import ICMNet

# Just in case someone is using Python2
try:
    q_input = raw_input
except NameError:
    q_input = input

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description='Lock the ICM flash write protection')
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-w", "--wp_addr", type=int, default=None, required=True,
                        help="device wire pair address")
    parser.add_argument("-y", "--yes", action='store_true', default=False,
                        help="override user prompt")
    args = parser.parse_args()

    # Check that the user really wants to do this
    if not args.yes:
        print("This will PERMANENTLY prevent ICM golden image updates without physical access!")
        if not (q_input("Continue? (y/n): ").lower().strip()[:1] == "y"): 
            print("Aborting.")
            sys.exit(1)

    dev = int(args.wp_addr)
    if (dev < 0) or (dev >= ICMNet.FH_DEVICE_NUM):
        print("Wire pair address must be [0-7], exiting.")
        sys.exit(1)

    print("Locking golden image flash on ICM device %d..." % dev)

    # Connect to server
    icms = ICMNet(args.port, host=args.host)

    # Reset the reconfiguration modules and clear any errors
    reply = icms.request("icm_reconfig_reset %d" % dev)
    if reply['status'] != 'OK':
        print("Error resetting ICM reconfiguration module: %s" % reply['status'])
        sys.exit(-1)

    # Issue lock command
    reply = icms.request("flash_lock %d" % dev)
    if reply['status'] != 'OK':
        print("Error sending lock command: %s" % reply['status'])
        sys.exit(-1)
    
    # Check status register
    reply = icms.request("read %d rcfg_stat" % dev)
    if "value" in reply:
        rcfg_stat = int(reply["value"], 16)
        if (rcfg_stat & 0x1):
            reply = icms.request("read %d rcfg_err" % dev)
            print("Error reported by ICM when locking flash (%s)." % reply['value'])
            sys.exit(1)
    else:
        print("Error reading status register: %s" % reply['status'])
        sys.exit(-1)

    print("Done.")

if __name__ == "__main__":
    main()
