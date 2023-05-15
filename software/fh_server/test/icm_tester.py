#!/usr/bin/env python
#
# ICM testing support code. The ICMSimTester class takes care of
# launching the applications and socat pipe needed to set up a standalone
# domnet system test.
#
# NB: Python3 required

import sys
import os
import time
import argparse
import socket
import signal
import atexit
import asyncio
import shutil

# Fix up import path automatically
sys.path.append(os.path.join(os.path.dirname(__file__), "../scripts"))
from icmnet import ICMNet

async def run_cmd(cmd, quiet=True):
    if quiet:
        return await asyncio.create_subprocess_exec(*cmd.split(' '),
                                                    stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.DEVNULL )
    else:
        return await asyncio.create_subprocess_exec(*cmd.split(' '))

class DevSocket(socket.socket):
    # Device socket
    def __init__(self, dev):
        self.dev = dev
        super(DevSocket, self).__init__(socket.AF_INET, socket.SOCK_STREAM)


class ICMSimTester():
    # Counter to uniqify things
    idCounter = 0

    def __init__(self, cmdport, icmSerial=None, simSerial=None, host="localhost",
                 devsocks=True, debug=False):
        """
        Create an ICM tester to the specified device
        through domnet, using the ICM simulator.
        """
        self.cmdport = cmdport
        self.host = host
        self.devport = self.cmdport - ICMNet.FH_PORT_OFFSET

        # Paths
        scriptdir = os.path.dirname(__file__)
        bindir = scriptdir+"/../build/bin/"

        # Start up socat if we are using fake serial devices
        if (icmSerial is None or simSerial is None):
            self.icmSerial = "./icm-sim-%d.%d" % (os.getpid(), ICMSimTester.idCounter)
            self.simSerial = "./virtual-tty-%d.%d" % (os.getpid(), ICMSimTester.idCounter)
            socat_cmd = shutil.which("socat")
            cmd = "%s -d -d pty,raw,echo=0,link=%s pty,raw,echo=0,link=%s" % \
                (socat_cmd, self.icmSerial, self.simSerial)
            self.p_socat = asyncio.run(run_cmd(cmd))
        else:
            self.icmSerial = icmSerial
            self.simSerial = simSerial
            self.p_socat = None

        cmd = bindir+("icm_simulator %s" % self.simSerial)
        self.p_simulator = asyncio.run(run_cmd(cmd))

        if (debug):
            cmd = bindir+("domnet -d -c ../resources/domnet.sim.ini -p %d %s" %
                          (self.cmdport-ICMNet.FH_PORT_OFFSET, self.icmSerial))
        else:
            cmd = bindir+("domnet -c ../resources/domnet.sim.ini -p %d %s" %
                          (self.cmdport-ICMNet.FH_PORT_OFFSET, self.icmSerial))
        self.p_domnet = asyncio.run(run_cmd(cmd, quiet=(not debug)))

        time.sleep(1)

        # Connect to command server
        self.icm = ICMNet(self.cmdport, host=self.host)

        # Get present devices
        reply = self.icm.request("devlist")
        self.devlist = reply["value"]
        print("Devices present:", self.devlist)

        # Connect to device port(s)
        self.devsocks = []
        if devsocks:
            for dev in self.devlist:
                if (dev == ICMNet.FH_DEVICE_NUM):
                    continue
                devsock = DevSocket(dev)
                devsock.connect((self.host, self.devport+dev))
                self.devsocks.append(devsock)

        # Clean up
        atexit.register(self.finish)

        # Increment instance counter
        ICMSimTester.idCounter += 1

    def finish(self):
        try:
            for s in self.devsocks:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
        except:
            pass
        # There is perhaps a race condition here with killing
        # the processes.  If the process died already somehow,
        # that's fine.  Checking returncode is not reliable.
        try:
            self.p_domnet.terminate()
        except ProcessLookupError:
            pass
        try:
            self.p_simulator.terminate()
        except ProcessLookupError:
            pass
        if self.p_socat is not None:
            try:
                self.p_socat.terminate()
            except ProcessLookupError:
                pass
        # Cleanup the log file
        try:
            os.unlink("/var/tmp/domnet.%s.log" % os.path.basename(self.icmSerial))
        except:
            pass

def signal_handler(sig, frame):
    sys.exit(0)

def main():
    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("--no-devsocks", dest='devsocks', action='store_false',
                        help="don't connect automatically to the device sockets")
    parser.add_argument("-d", "--debug", dest='debug', action='store_true',
                        help="run domnet in debug mode")
    parser.add_argument('dev1', help="serial device for domnet (default: use socat)", nargs='?')
    parser.add_argument('dev2', help="serial device for ICM simulator (default: use socat)", nargs='?')
    args = parser.parse_args(sys.argv[1:])

    # Catch CTRL-C / SIGTERM and clean up when done
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create tester
    if (args.dev1 is not None and args.dev2 is not None):
        icmTester = ICMSimTester(args.port, icmSerial=args.dev1,
                                 simSerial=args.dev2, host=args.host,
                                 devsocks=args.devsocks, debug=args.debug)
    else:
        icmTester = ICMSimTester(args.port, host=args.host,
                                 devsocks=args.devsocks, debug=args.debug)

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
