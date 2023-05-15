#!/usr/bin/env python

try:
    input = raw_input
except NameError:
    pass

import argparse

from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader


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

    fpd = findParentDevices(args.uid, mongo)
    if len(fpd.parents) == 0:
        print('[{0}] is not associated with any devices'
              .format(fpd.uid))
        return
    #print('[{0}] associations:'.format(fpd.uid))
    for device in fpd.parents:
        print('   uid: \"{0}\",  device_type: \"{1}\"'
              .format(device['uid'], device['device_type']))


class findParentDevices:
    
    def __init__(self, uid, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.uid = uid
        self.parents = []
        if self.searchForDevice():
            print('Found device [{0}], searching for associations...'
                  .format(self.uid))
            self.findAssociationTree()
            
        
    def searchForDevice(self):
        if not self.mongo.findDeviceByUID(self.uid):
            devs = self.mongo.findDeviceByGenericID(self.uid)
            if not devs:
                print('Device [{0}] is not in the database'.format(self.uid))
                return False
            elif len(devs) > 1:
                print('Found multiple matches...')
                for i, dev in enumerate(devs):
                    print('   [{2}] : device \"{0}\" uid \"{1}\"'
                          .format(dev['device_type'], dev['uid'], i+1))
                select = input('Select [1-{0}]: '.format(len(devs)))
                try:
                    select = int(select)
                except:
                    print('quitting, not int')
                    return False
                if select not in list(range(1, len(devs)+1)):
                    print('quitting, not in range')
                    return False
                self.uid = devs[select-1]['uid']
                return True
            else:
                self.uid = devs[0]['uid']
                return True
        else:
            return True
    
    
    def findAssociationTree(self):
        ids = self.mongo.findDeviceAssociationByIndex(self.uid)
        if ids:
            devs = []
            for _id in ids:
                devs.extend(self.mongo.findDeviceByUID(_id))
        # indexes might not be up-to-date, so then check the slower way
        else:
            devs = self.mongo.findDeviceAssociationByUID(self.uid)

        self.parents = devs
        return


if __name__ == "__main__":
    main()

