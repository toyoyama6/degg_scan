#!/usr/bin/env python
#
# Force disconnection of all devices sockets regardless of whether remote
# devices is present.
#
import sys
import argparse
from icmnet import ICMNet

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    args = parser.parse_args(sys.argv[1:])

    # Connect to server
    icms = ICMNet(args.port, args.host)
    reply = icms.request({ "command" : "disconnect_all" })
    print(reply["status"])
    
if __name__ == "__main__":
    main()

