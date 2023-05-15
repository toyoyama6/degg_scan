#!/usr/bin/env python

try:
    input = raw_input
except NameError:
    pass

import argparse

from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader
from fatcat_db.utils import setVerbosity


def main():

    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument(dest='uid', type=str,
                           help='The ID of the device of interest')
    cmdparser.add_argument('-p', '--production', dest='production', action='store_true',
                           help='Use the production database')
    cmdparser.add_argument('--no-tunnel', dest='tunnel', action='store_false',
                           help='Do not port forward mongodb server')
    args = cmdparser.parse_args()

    # quiet the output
    setVerbosity('warning')
    
    # open ssh tunnel to mongo port
    if args.tunnel:
        tunnel = Tunnel()

    # connect to mongo
    if args.production:
        mongo = MongoReader(user='icecube',
                            database='production_calibration')
    else:
        mongo = MongoReader(user='icecube',
                            database='production_calibration_test')
    if not mongo.isConnected:
        return

    # search database for id
    devs = mongo.findDeviceByUID(args.uid)
    if not devs:
        devs = mongo.findDeviceByGenericID(args.uid)
        if not devs:
            print('No matches found')
            return
    print('Found device(s)')
    for dev in devs:
        print('uid: \"{0}\",  device_type: \"{1}\"'
              .format(dev['uid'], dev['device_type']))
    return


if __name__ == "__main__":
    main()

