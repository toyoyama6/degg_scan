#!/usr/bin/env python
#
# Probe a wire pair for ICMs present and report key register values.
# Connects via ICM command port.
#
import sys
import time
import argparse
import zmq

from icmnet import ICMNet

# Python2 backward compatibility
try:
    q_input = raw_input
except NameError:
    q_input = input

# Header names
HDRS =    ["FW_VERS", "PWR",    "CSTAT", "CTRL1", "CTRL2", "CERR", "PKT_CNT", "ICM_ID", "MB_ID"]
REGS =    ["FW_VERS", "MB_PWR", "CSTAT", "CTRL1", "CTRL2", "CERR", "PKT_CNT", "ICM_ID", "MB_ID"]

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description='Probe a wire pair for ICMs.')
    parser.add_argument("-w", "--wp_addr", type=int, default=None,
                        help="scan only this wire pair address (default: scan 0-8)")
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("-f", "--force", action="store_true",
                        help="force re-probe the wire pair (default: use domnet cache)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="enable debug output")    
    parser.add_argument("-v", "--version", action="store_true",
                        help="print version and exit")
    args = parser.parse_args()
    
    # Connect to server
    icms = ICMNet(args.port, host=args.host)
    if args.debug:
        print("Connected to command server on port %s" % args.port);

    # Get version and exit
    if args.version:
        reply = icms.request("version")
        if "value" in reply:
            print(reply["value"])
        else:
            print(str(reply["status"]))
        sys.exit(0)
    
    # Force re-probe the wire pair if requested
    if args.force:
        user_ok = q_input("WARNING: re-probe of wire pair will disrupt comms. Continue (y/n)? ")
        if user_ok.lower() in ['y', 'yes']:
            print("OK, forcing re-probe...");
            reply = icms.request("probe")
            if (reply['status'] == "?NOREPLY"):
                print("Error: no reply from server, is domnet running?")
                sys.exit(-1)
            elif (reply['status'] != "OK"):
                print("Error getting list of connected devices: %s" % reply['status'])
                sys.exit(-1)
            time.sleep(1)
        else:
            print("OK, re-probe aborted.")

    # Get list of connected ICMs
    reply = icms.request("devlist")
    if (reply['status'] == "?NOREPLY"):
        print("Error: no reply from server, is domnet running?")
        sys.exit(-1)
    elif (reply['status'] != "OK"):
        print("Error getting list of connected devices: %s" % reply['status'])
        sys.exit(-1)
    connected = reply['value']
    
    # Probe the requested device, or all of them
    if args.wp_addr is not None:
        dev_list = [ args.wp_addr ]
    else:
        dev_list = range(9)

    # Loop over devices
    results = {}
    for dev in dev_list:
        if dev not in connected:
            continue
        results[dev] = {}
        for reg in REGS:
            # Swap power register for fieldhub
            if (reg == "MB_PWR") and (dev == ICMNet.FH_DEVICE_NUM):
                reg = "WP_PWR"
            reply = icms.request("read %d %s" % (dev, reg))
            if reply['status'] == 'OK':
                results[dev][reg] = reply['value']
            else:
                results[dev][reg] = reply['status']

    # Print table of results
    rows = []
    rows.append(["Dev#"] + HDRS)
    for dev in dev_list:
        row = [ str(dev) ]
        if dev in results:            
            for reg in REGS:
                # Swap power register for fieldhub
                if (reg == "MB_PWR") and (dev == ICMNet.FH_DEVICE_NUM):
                    reg = "WP_PWR"
                # Append result string, remove leading 0x for brevity
                row.append(results[dev][reg].replace("0x","",1))
        else:
            row.append("  ---")
            row = row + [""]*(len(rows[0])-2)
        rows.append(row)

    widths = [max(map(len, col)) for col in zip(*rows)]
    for row in rows:
        print("  ".join((val.ljust(width) for val, width in zip(row, widths))))
    
if __name__ == "__main__":
    main()

    
