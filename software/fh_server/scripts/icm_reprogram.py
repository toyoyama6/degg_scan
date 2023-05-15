#!/usr/bin/env python
#
# Reprogram an ICM flash image with the specified .mcs firmware image,
# through a domnet connection. Ported from raw serial procedure in
# golden_image_control.py.
#

import sys
import time
import argparse
import os

from icmnet import ICMNet
from icm_flash_writer import ICMFlashWriter, ICMFlashWriterError        

# Just in case someone is using Python2
try:
    q_input = raw_input
except NameError:
    q_input = input

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description='Reprogram the ICM flash image slot with the specified firmware')
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-w", "--wp_addr", type=int, default=None, required=True,
                        help="device wire pair address")
    parser.add_argument("-f", "--filename", default=None, required=True,
                        help=".mcs[.gz] firmware file")
    parser.add_argument("-i", "--id", type=int, default=None, required=True,
                        help="FPGA multiboot image ID")
    args = parser.parse_args()

    # Check device number
    dev = int(args.wp_addr)
    if (dev < 0) or (dev > ICMNet.FH_DEVICE_NUM):
        print("Wire pair address must be [0-%d], exiting." % ICMNet.FH_DEVICE_NUM)
        sys.exit(1)

    # Check image ID
    image_id = int(args.id)
    if (image_id < 0) or (image_id > ICMFlashWriter.MAX_IMAGE_ID):
        print("Error, FPGA image ID must be between 0 and %d" % ICMFlashWriter.MAX_IMAGE_ID)
        sys.exit(1)
    
    # Check that the user really wants to overwrite a golden image slot
    if (image_id < 2):
        print("WARNING: you are attempting to rewrite a golden image slot.")
        if not (q_input("Continue? (y/n): ").lower().strip()[:1] == "y"): 
            print("Aborting.")
            sys.exit(1)

    # Check that MCS file is readable
    if not (os.path.isfile(args.filename) and os.access(args.filename, os.R_OK)):
        print("Error: firmware image file %s does not exist or is not readable, exiting." % args.filename)
        sys.exit(1)
        
    # FIXME: handle unlocking?

    # Initialize the flash writer for this specific device
    try:
        writer = ICMFlashWriter(args.port, dev, args.host, verbose=True)
    except socket.error:
        print("Socket error, is domnet running?")
        sys.exit(1)

    # Program the flash
    try:
        writer.program(args.filename, image_id)
    except Exception as e:
        print("ERROR: %s" % e)
        sys.exit(1)
    
if __name__ == "__main__":
    main()
