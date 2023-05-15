#!/usr/bin/env python
#
# Reprogram an IceCube Upgrade STM32 MCU bootloader.
# domnet must be running on the specified host.
# 
import sys
import argparse
import os

from mcu_bootloader_control import MCU_Bootloader_Control

def main():
    
    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--wp_addr", type=int, default=None,
                        help="device wire pair address", required=True)
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-f", "--file", default=None,
                        help="binary file for reprogramming", required=True)
    args = parser.parse_args(sys.argv[1:])
    
    # Check file
    if not os.path.isfile(args.file):
        print("Error: couldn't find or read file %s, exiting." % args.file)
        sys.exit(-1)

    if not args.file.endswith(".bin"):
        print("Error: %s does not appear to be a .bin file, exiting." % args.file)
        sys.exit(-1)

    try:
        mcu_bl = MCU_Bootloader_Control(args.host, args.wp_addr, args.port)
    except ConnectionRefusedError:
        print("Error: couldn't connect to device port, is domnet running?")
        sys.exit(-1)
    
    print("Connected to device %d on port %d, command port %d" \
          % (mcu_bl.wp_addr, mcu_bl.dev_port, mcu_bl.cmd_port))

    try:
        print("Entering MCU program mode and rebooting...")        
        mcu_bl.start()

        print("Reprogramming with file %s..." % args.file)
        mcu_bl.program(args.file)

        print("Exiting MCU program mode and rebooting...")
        mcu_bl.finish()

        print("Done.")
    except BrokenPipeError:
        print("Device socket error, does another process have the port open?")
        sys.exit(-1)
    except Exception as e:
        print(e)
        sys.exit(-1)
    

if __name__ == "__main__":
    main()
