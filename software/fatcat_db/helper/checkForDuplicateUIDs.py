#!/usr/bin/env python

# quick helper script to check if a UID has already been
# associated with another device

import argparse

from fatcat_db.forwarder import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *


def main():

    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument(dest='uid', type=str,
                           help='specify a device UID')
    cmdparser.add_argument('-p', '--production', dest='production', action='store_true',
                           help='Use the production database')
    cmdparser.add_argument('--no-tunnel', dest='tunnel', action='store_false',
                           help='Do not port forward mongodb server')
    args = cmdparser.parse_args()

    # open ssh tunnel to mongo port
    if args.tunnel:
        tunnel = Tunnel()

    # connect to mongo
    if args.production:
        mongo = MongoReader(user='icecube',
                            database='production_calibration')
    else:
        mongo = MongoReader(user='icecube'
                            database='production_calibration_test')
    if not mongo.isConnected:
        return

    
    # check if the uid already exists in the db
    docs = mongo.findDeviceByUID(args.uid)
    if len(docs) == 1:
        print('Device [{0}] exists in database'
              .format(args.uid))
    elif len(docs) == 0:
        print('Device [{0}] does not exist in database'
              .format(args.uid))
    else:
        print('Device [{0}] exists {1} times in database?'
              .format(args.uid), len(docs))

    passed = True
    if not mongo.checkKnownDuplicateUID(args.uid):
        dups = mongo.duplicateSubDevices(args.uid)
        if len(dups) > 0:
            passed = False
            print('This device UID [{0}] is already associated with:'
                  .format(args.uid))
            for dup in dups:
                print('   device_type: [{0}]  uid: [{1}]'
                      .format(dup['device_type'], dup['uid']))
    
    print('No duplicate device associations for UID [{0}]: [{1}]'
          .format(args.uid, passed))

    return passed


if __name__ == "__main__":
    main()

