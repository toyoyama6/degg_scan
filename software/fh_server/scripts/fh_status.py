#!/usr/bin/env python
#
# Report (mini)FieldHub status.
# Connects via ICM command port.
#
import sys
import argparse
import zmq

from icmnet import ICMNet

# Header names
HDRS =    ["FW_VERS", "PWR", "CSTAT", "PSTAT", "CTRL1", "CERR", "CONN", "PKT_CNT",
           "ICM_ID", "VOLT (V)", "CUR (A)"]
REGS =    ["FW_VERS", "WP_PWR", "CSTAT", "PSTAT", "CTRL1", "CERR", "CONN_ICMS", "PKT_CNT",
           "ICM_ID", "WP_VOLT", "WP_CUR"]

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser(description='Report status of local (mini)FieldHub.')
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
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

    results = {}
    dev = ICMNet.FH_DEVICE_NUM

    for reg in REGS:
        reply = icms.request("read %d %s" % (dev, reg))
        if reply['status'] == 'OK':
            results[reg] = reply['value']
        else:
            results[reg] = reply['status']

    # Print table of results
    rows = []
    rows.append(HDRS)
    row = []
    for reg in REGS:
        # Append result string, remove leading 0x for brevity
        row.append(results[reg].replace("0x","",1))
    else:
        row.append("  ---")
        row = row + [""]*(len(rows[0])-2)
    rows.append(row)

    widths = [max(map(len, col)) for col in zip(*rows)]
    for row in rows:
        print("  ".join((val.ljust(width) for val, width in zip(row, widths))))
    
if __name__ == "__main__":
    main()
