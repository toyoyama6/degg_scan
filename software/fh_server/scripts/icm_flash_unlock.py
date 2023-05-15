#!/usr/bin/env python
"""
Unlock the write protection on the ICM golden image flash area (images 0,1)
"""
# On ICM rev4 and above, this requires disabling hardware WP with an IR light.
# The "--tries" command line option may be used to continue unlock attempts
# while locating the ICM phototransistor with the IR light.
import sys
import time
import argparse

from icmnet import ICMNet

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description=__doc__,
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port")
    parser.add_argument("--host", default="localhost",
                        help="connect to host")
    parser.add_argument("-w", "--wp_addr", type=int, default=None, required=True,
                        help="device wire pair address")
    parser.add_argument("-t", "--tries", type=int, default=1,
                        help="Auto-repeat 1 Hz trial limit")
    args = parser.parse_args()

    dev = int(args.wp_addr)
    if (dev < 0) or (dev >= ICMNet.FH_DEVICE_NUM):
        print("Wire pair address must be [0-7], exiting.")
        sys.exit(1)

    print("Unlocking write protection on ICM device %d..." % dev)

    # Connect to server
    icms = ICMNet(args.port, host=args.host)

    # Reset the reconfiguration modules and clear any errors
    reply = icms.request("icm_reconfig_reset %d" % dev)
    if reply['status'] != 'OK':
        print("Error resetting ICM reconfiguration module: %s" % reply['status'])
        sys.exit(-1)

    # Loop attempting to unlock ICM flash.
    while True:
        # Issue unlock command
        reply = icms.request("flash_unlock %d" % dev)
        if reply['status'] != 'OK':
            print("Error sending unlock command: %s" % reply['status'])
            sys.exit(-1)

        # Check status register
        reply = icms.request("read %d rcfg_stat" % dev)
        if "value" in reply:
            rcfg_stat = int(reply["value"], 16)
            if (rcfg_stat & 0x1):
                reply = icms.request("read %d rcfg_err" % dev)
                print("Error reported by ICM when unlocking flash (%s)." % reply['value'])
            else:
                print("Done.")
                sys.exit(0)
        else:
            print("Error reading status register: %s" % reply['status'])
            sys.exit(-1)
        args.tries -= 1
        if args.tries <= 0:
            break
        time.sleep(1)
    print("ICM flash is likely not unlocked.")
    sys.exit(1)


if __name__ == "__main__":
    main()
