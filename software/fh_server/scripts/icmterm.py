#!/usr/bin/env python
#
import sys
import signal
import argparse
from icmnet import ICMNet

# Signal handler
def signal_handler(sig, frame):
    sys.exit(0)

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    args = parser.parse_args(sys.argv[1:])

    # Catch CTRL-C
    signal.signal(signal.SIGINT, signal_handler)

    # Connect to server
    icms = ICMNet(args.port, args.host)

    print("Connected to command server on host %s, port %s" % (args.host, args.port));

    while True:
        line = sys.stdin.readline()
        reply = icms.request(line)
        if "value" in reply:
            result = reply["value"]
        else:
            result = reply["status"]
        print(str(result))

if __name__=="__main__":
    main()
