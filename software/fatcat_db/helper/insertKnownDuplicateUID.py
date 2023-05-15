#!/usr/bin/env python

import argparse
import datetime

from fatcat_db.utils import *
from fatcat_db.forwarder import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *
from fatcat_db.devices import getDeviceTier


def main():

    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument(dest='uids', type=str, nargs='+',
                           help='The UID(s) of the known duplicate device(s)')
    cmdparser.add_argument('-i', '--insert', dest='insert', action='store_true',
                           help='Insert data into the mongo database')
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
        mongo = MongoReader(database='production_calibration')
    else:
        mongo = MongoReader(database='production_calibration_test')
    if not mongo.isConnected:
        return

    for uid in args.uids:
        pfprint(1, 'Checking UID [{0}]'.format(uid))
        
        # make sure the UID already exists in the db
        docs = mongo.findDeviceByUID(uid)
        if len(docs) == 1:
            pfprint(10, 'Device [{0}] exists in database'
                  .format(uid))
            doc = docs[0]
        elif len(docs) == 0:
            pfprint(20, 'Device [{0}] does not exist in database'
                  .format(uid))
            pfprint(20, 'Please insert the device file first')
            continue
        else:
            pfprint(30, 'Device [{0}] exists in database {1} times?'
                  .format(uid), len(docs))
            pfprint(30, contact())
            continue

        # make sure the UID is a low-level tier-4 device
        if not getDeviceTier(doc['device_type']) == 4:
            pfprint(20, 'Device [{0}] device_type [{1}] is not a fundemental device'
                    .format(uid, doc['device_type']))
            pfprint(20, contact())
            continue
        
        # make sure the UID is not already marked as a known duplicate
        count = mongo.checkKnownDuplicateUID(uid)
        if count == 0:
            pfprint(10, 'UID [{0}] is valid for insert'
                    .format(uid))
        elif count == 1:
            pfprint(20, 'UID [{0}] is already listed as a known duplicate'
                  .format(uid))
            continue
        else:
            pfprint(30, 'UID [{0}] is listed as a known duplicate {1} times?'
                  .format(uid, count))
            pfprint(30, contact())
            continue

        if args.insert:
            data = {}
            data['known_duplicate_uid'] = uid

            # get user for insert_meta
            config = FileTools().load('ssh_config')
            if config['user'] not in [None, "", "auto"]:
                user = config['user']
            else:
                user = getpass.getuser()

            # add some meta about the insert
            data['insert_meta'] = {
                'insert_time': datetime.datetime.utcnow(),
                'insert_user': user,
                'mongo_user': mongo.mongo_user
            }

            # insert the data
            objectid = None
            objectid = mongo.db.devices.insert(data)
            if objectid is not None:
                pfprint(10, 'Inserted [{0}] as a known duplicate'.format(uid))
                pfprint(10, 'ObjectId = {0}'.format(objectid))
            else:
                pfprint(30, 'The [{0}] insert did not succeed'.format(uid))
        else:
            print('Use -i or --insert to really insert')
            
    return

    
if __name__ == "__main__":
    main()

