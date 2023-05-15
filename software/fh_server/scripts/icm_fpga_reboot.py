#!/usr/bin/env python
#
# Set the multiboot ID of the ICM and reboot into the
# new image.
#
import sys
import time
import argparse
import zmq

from icmregs import WP_PWR, MB_PWR
from icmnet import ICMNet

# Maximum time to wait on the ICM FPGA reconfiguration
MAX_RECONFIG_WAIT_SEC=20

# Time to wait for mainboard power rail to drop, to
# fix pressure sensor bug
MB_PWR_RAIL_WAIT_SEC=10
# Firmware revision after which the MB power rail wait
# makes sense
MB_PWR_RAIL_FWVERS=0x1549

# Python 2 backward compatibility
try:
    q_input = raw_input
except NameError:
    q_input = input

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description='Reboot the ICM into a multiboot image')
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-w", "--wp_addr", type=int, default=None, required=True,
                        help="device wire pair address")
    parser.add_argument("-i", "--id", type=int, default=None, required=True,
                        help="FPGA multiboot ID")
    args = parser.parse_args()
    
    # Connect to server
    icms = ICMNet(args.port, host=args.host)

    results = {}
    dev = int(args.wp_addr)

    # Check power and reset state before doing anything
    print("Saving device %d state before reboot..." % dev)
    if (dev != ICMNet.FH_DEVICE_NUM):
        reply = icms.request("read %d mb_pwr" % dev)
        if reply['status'] != 'OK':
            if reply['status'] == "?NOCONN":
                print("Error: device %d is not connected, exiting." % dev)
            else:
                print("Error reading MB power status: %s" % reply['status'])
            sys.exit(-1)
        pwr_on_save = (int(reply['value'], 16) == MB_PWR.MB_PWR_ON)

        reply = icms.request("read %d ctrl1" % dev)
        if reply['status'] != 'OK':
            print("Error reading CTRL1: %s" % reply['status'])
            sys.exit(-1)
        ctrl1_save = reply['value']

        reply = icms.request("read %d ctrl2" % dev)
        if reply['status'] != 'OK':
            print("Error reading CTRL2: %s" % reply['status'])
            sys.exit(-1)
        ctrl2_save = reply['value']
    else:
        reply = icms.request("read %d wp_pwr" % dev)
        if reply['status'] != 'OK':
            print("Error reading WP power status: %s" % reply['status'])
            sys.exit(-1)
        pwr_on_save = (int(reply['value'], 16) == WP_PWR.WP_PWR_ON)
        
    print("Setting the multiboot ID on device %d to %d..." % (dev, args.id))
    reply = icms.request("set_fpga_image_id %d %d" % (dev, args.id))
    if reply['status'] != 'OK':
        print("Error setting ID: %s" % reply['status'])
        sys.exit(-1)

    if (dev != ICMNet.FH_DEVICE_NUM):
        print("Putting MCU into reset on device %d..." % dev)
        reply = icms.request("mcu_reset %d" % dev)
        if reply['status'] != 'OK':
            print("Error putting MCU in reset: %s" % reply['status'])
            sys.exit(-1)

    print("Reconfiguring device %d..." % dev)
    reply = icms.request("fpga_reconfig %d" % dev)
    if reply['status'] != 'OK':
        print("Error reconfiguring: %s" % reply['status'])
        sys.exit(-1)

    # Wait nominal reconfiguration time
    if (dev == ICMNet.FH_DEVICE_NUM):
        print("Waiting for FieldHub to reboot...")
        time.sleep(12)
        
        # The FH requires a re-probe
        reply = icms.request("probe")
        if reply['status'] != 'OK':
            print("Error probing wire pair: %s" % reply['status'])
            sys.exit(-1)
        time.sleep(1)

    else:
        time.sleep(2)

    # Poll the firmware version to see if device is back
    reconfig_start_time = time.time()
    fwvers = None
    while (time.time() - reconfig_start_time < MAX_RECONFIG_WAIT_SEC):
        reply = icms.request("read %d fw_vers" % dev)
        if reply['status'] == '?TIMEOUT':
            print("Device %d not responding yet..." % dev)
            continue
        elif reply['status'] == '?NOCONN':
            break
        elif reply['status'] == 'OK':
            fwvers = reply['value']
            break
        else:
            print("Unexpected error reading firmware version: %s" % reply['status'])
            sys.exit(-1)

    if fwvers is None:
        print("Device never detected after reconfiguration, re-probe needed.")
        user_ok = q_input("WARNING: re-probe of wire pair will disrupt comms. Continue (y/n)? ")
        if user_ok.lower() in ['y', 'yes']:            
            reply = icms.request("probe")
            if reply['status'] != 'OK':
                print("Error probing wire pair: %s" % reply['status'])
                sys.exit(-1)
            time.sleep(1)
        else:
            print("Device %d dropped, exiting." % dev)
            sys.exit(-1)

        reply = icms.request("read %d fw_vers" % dev)

        if reply['status'] != 'OK':
            print("Error reading firmware version: %s" % reply['status'])
            sys.exit(-1)

        fwvers = reply['value']


    print("Device %d firmware version: %s" % (dev, fwvers))

    if (dev != ICMNet.FH_DEVICE_NUM):
        if pwr_on_save:
            # Check if we need to wait for MB rail to drop for pressure
            # sensor fix
            if (int(fwvers, 16) >= MB_PWR_RAIL_FWVERS):
                print("Waiting for MB power rail to drop...")
                time.sleep(MB_PWR_RAIL_WAIT_SEC)

            print("Re-enabling mainboard power on device %d..." % dev)
            reply = icms.request("mb_on %d" % dev)
            if reply['status'] != 'OK':
                print("Error re-enabling MB power: %s" % reply['status'])
                sys.exit(-1)

        # Restore CTRL1, includes MCU reset state, and CTRL2 (interlocks)
        print("Restoring device %d state..." % dev)
        reply = icms.request("write %d ctrl1 %s" % (dev, ctrl1_save))
        if reply['status'] != 'OK':
            print("Error restoring CTRL1: %s" % reply['status'])
            sys.exit(-1)

        reply = icms.request("write %d ctrl2 %s" % (dev, ctrl2_save))
        if reply['status'] != 'OK':
            print("Error restoring CTRL2: %s" % reply['status'])
            sys.exit(-1)

    else:
        if pwr_on_save:
            print("Turning wire pair power back on...")
            reply = icms.request("wp_on")
            if reply['status'] != 'OK':
                print("Error re-enabling WP power: %s" % reply['status'])
                sys.exit(-1)

            time.sleep(2)

            # Have to re-probe again
            reply = icms.request("probe")
            if reply['status'] != 'OK':
                print("Error probing wire pair: %s" % reply['status'])
                sys.exit(-1)
            time.sleep(1)            
        
    print("Done.")

if __name__ == "__main__":
    main()


