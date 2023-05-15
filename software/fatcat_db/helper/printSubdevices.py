#!/usr/bin/env python

import argparse

from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader
from fatcat_db.devices import getSubDeviceUIDs

def main():

    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument(dest='uid', type=str,
                           help='The ID of the device of interest')
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

    cl = listSubdevices(args.uid, mongo)
    uids = cl.findSubdevices()
    uids = sorted(list(set(uids)))
    for uid in uids:
        print(uid)
    print('Found {0} unique sub_devices'.format(len(uids)))

    
class listSubdevices:
    
    def __init__(self, uid, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.uid = uid

    
    def findSubdevices(self):
        doc = self.mongo.findDeviceByUID(self.uid)
        if not doc:
            print('UID {0} not found in database'.format(self.uid))
            return
        uids = []
        uids.append(getSubDeviceUIDs(doc[0]))
        i = 0
        while len(uids[i]) > 0:
            uids.append([])
            for subUID in uids[i]:
                doc = self.mongo.findDeviceByUID(subUID)
                if len(doc) == 1:
                    uids[i+1].extend(getSubDeviceUIDs(doc[0]))
            i += 1
            
        alluids = []
        for item in uids:
            alluids.extend(item)

        return alluids

    
if __name__ == "__main__":
    main()

