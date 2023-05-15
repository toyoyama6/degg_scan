#!/usr/bin/env python

# find all currently assigned goalpost testnames

import argparse

from fatcat_db.forwarder import *
from fatcat_db.mongoreader import *


def main():

    cmdparser = argparse.ArgumentParser()
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
        mongo = MongoReader(user='icecube',
                            database='production_calibration_test')
    if not mongo.isConnected:
        return

    testnames = mongo.findAllTestnames()

    print('Found testnames:')
    for testname in testnames:
        print(testname)
    print('Total = {0}'.format(len(testnames)))

    
if __name__ == "__main__":
    main()

