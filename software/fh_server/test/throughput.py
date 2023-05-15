#!/usr/bin/env python
#
# Measure throughput of domnet + icm_simulator in loopback mode.
#

import sys
import signal
import time
import atexit
import datetime
import argparse

from icm_tester import ICMSimTester

@atexit.register
def finish():
    try:
        dt = (times["last"]-times["start"]).total_seconds()
    except KeyError:
        # We didn't make it to the testing phase
        sys.exit(0)
    totalBytes = 0
    print("")
    for dev in stats.keys():
        print("Device %d:  RX (MB) %.2f  TX (MB) %.2f" % (dev, stats[dev]["rx"]/1e6, stats[dev]["tx"]/1e6))
        totalBytes += stats[dev]["rx"] + stats[dev]["tx"]
    print("Average serial throughput: %.2f Mbps" % (totalBytes*8/1e6/dt))
    
def signal_handler(sig, frame):
    sys.exit(0)

stats = {}
times = {}

def main():
    NBYTES = 4000
    TESTSTR = "abcdefghijklmnopqrstuvwxyz0123456789"

    nrep = int(NBYTES/len(TESTSTR))
    test = bytes(TESTSTR*nrep, 'utf-8')

    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument('dev1', help="serial device for domnet (default: use socat)", nargs='?')
    parser.add_argument('dev2', help="serial device for ICM simulator (default: use socat)", nargs='?')
    args = parser.parse_args(sys.argv[1:])
    
    # Catch CTRL-C / SIGTERM and clean up when done
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create tester
    if (args.dev1 is not None and args.dev2 is not None):
        icmTester = ICMSimTester(args.port, icmSerial=args.dev1, simSerial=args.dev2, host=args.host)
    else:
        icmTester = ICMSimTester(args.port, host=args.host)

    sys.stdout.write("Testing...")
    sys.stdout.flush()

    for s in icmTester.devsocks:
        stats[s.dev] = {"rx": 0, "tx": 0}
    times["start"] = datetime.datetime.now()

    loopcnt = 0
    while True:
        # Some status / aliveness output
        if (loopcnt % 100 == 0):
            sys.stdout.write(".")
            sys.stdout.flush()
        loopcnt += 1
        if (loopcnt % 4000 == 0):
            sys.stdout.write("\n")

        # Loop through all the sockets and send the test packet
        # over the device port. The simulator echos it back
        for s in icmTester.devsocks:
            # Send the test packet
            s.send(test)
            echo = bytearray()
            # Receive until we have all the bytes
            while len(echo) < len(test):
                packet = s.recv(len(test)-len(echo))
                if not packet:
                    print("ERROR: socket closed")
                    sys.exit(1)
                echo.extend(packet)
            if (test != echo):
                print("ERROR: echo failure!")
                print(test)
                print(reply)
                sys.exit(1)
            # Update the statistics
            stats[s.dev]['rx'] += len(test)
            stats[s.dev]['tx'] += len(echo)
            times["last"] = datetime.datetime.now()                
    
if __name__ == "__main__":
    main()
    
