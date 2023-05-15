#
# Boilerplate code for single ICM command script
#
import sys
import argparse
from icmnet import ICMNet

def single_command(arglist, cmd, reg=None, val=None, only_remote=False, only_local=False, print_result=True):

    # Parse command-line options
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--wp_addr", type=int, default=None,
                        help="target this wire pair address (default: all)")
    parser.add_argument("-p", "--port", type=int, default=6000,
                        help="domnet command port (default=6000)")
    parser.add_argument("--host", default="localhost",
                        help="connect to host (default localhost)")
    parser.add_argument("-v", "--version", action="store_true", help="print domnet version")
    parser.add_argument('value', nargs='?', default=val)
    args = parser.parse_args(arglist[1:])

    # Connect to server
    icms = ICMNet(args.port, args.host)

    if (args.version):
        reply = icms.request("version")
        if "value" in reply:
            if print_result:
                print(reply["value"])
            return reply["value"]
        else:
            if print_result:
                print(str(reply["status"]))
            return str(reply["status"])

    # Get list of connected devices
    reply = icms.request("devlist")

    # Something went wrong, print result status and exit
    if "value" not in reply:
        if print_result:
            print(str(reply["status"]))
        return str(reply["status"])

    # List of connected devices
    connected = reply["value"]

    # Requested device is not connected, bail
    if (args.wp_addr is not None):
        if not (args.wp_addr in connected):
            sys.stderr.write("Device %d is not connected.\n" % args.wp_addr)
            return -1
        devlist = [ args.wp_addr ]
    else:
        devlist = connected

    # Does this only apply to remote ICMs?
    if (only_remote):
        try:
            devlist.remove(ICMNet.FH_DEVICE_NUM)
            if (len(devlist) == 0):
                sys.stderr.write("Command valid only for remote devices.\n")
        except ValueError:
            pass

    # Does this only apply to the local FieldHub ICM?
    if (only_local):
        if (ICMNet.FH_DEVICE_NUM in devlist):
            devlist = [ ICMNet.FH_DEVICE_NUM ]
        else:
            sys.stderr.write("Command valid only for local (mini-)FieldHub.\n")
            devlist = [ ]
    
    # Now send the command
    result_str = ""
    for dev in devlist:
        req = {}
        req["command"] = str(cmd)
        req["device"] = str(dev)
        if reg is not None:
            req["register"] = str(reg)
        if args.value is not None:
            req["value"] = str(args.value)
        reply = icms.request(req)
        if "value" in reply:
            result_str += "%d: %s" % (dev, reply["value"])
        else:
            result_str += "%d: %s" % (dev, reply["status"])

    if print_result:
        print(result_str)
    return result_str
