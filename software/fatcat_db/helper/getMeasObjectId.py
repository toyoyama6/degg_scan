#!/usr/bin/env python

# find the object id of an inserted measurement using
# the original measurement json file

import argparse

from fatcat_db.forwarder import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *


def main():

    tunnel = Tunnel()
    mongo = MongoReader()
    
    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument(dest='jsonfile', type=str,
                           help='specify the measurement json file')
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

    
    data = loadJson(args.jsonfile)
    md5 = getObjMD5(data)
    
    objectId = None
    docs = mongo.searchJsonFileMD5('measurements', md5)
    if len(docs) == 0:
        print('No documents found associated with json md5')
    elif len(docs) > 1:
        print('Found {0} documents associated with json md5?'
              .format(len(docs)))
    else:
        objectId = docs[0]['_id']
        print('Found object id = {0}'
              .format(objectId))

    return objectId


if __name__ == "__main__":
    main()

