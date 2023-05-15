import sys
import os
import datetime
import json
import pymongo
import getpass

from fatcat_db.utils import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *
from fatcat_db.general import *
from fatcat_db.checks import *


class RunChecks:

    def __init__(self, filename, mongoObj=False, verbosity=False):
        self.filename = filename
        if verbosity:
            setVerbosity(verbosity)
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.passed = False
        
        checkRepoVersion()
        
        pfprint(1, 'Validating json --> {0}'.format(self.filename))
        
        cks = Checks(self.filename, self.mongo)
        if not cks.passed:
            self.passed = False
            return
        self.data = cks.data
        self.json_type = cks.json_type

        passed = True
        passed &= cks.generalChecks()
        passed &= cks.typeChecks()
        passed &= cks.additionalChecks()
        self.passed = passed

        self.allNestedUIDs = cks.allNestedUIDs
        self.indexDevice = cks.indexDevice
        
        if passed:
            pfprint(10, 'All checks passed: [{0}]'.format(passed))
        else:
            pfprint(30, 'All checks passed: [{0}]'.format(passed))


class Insert(RunChecks):

    def __init__(self, filename, mongoObj=False, verbosity=False):
        self.filename = filename
        if verbosity:
            setVerbosity(verbosity)
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj

        self.passed = False
        self.ObjectId = None
        
        RunChecks.__init__(self, self.filename, self.mongo)

        if self.passed is not True:
            pfprint(30, 'Vetting failed, not inserting')
            return
        
        if self.mongo.mongo_user == 'icecube':
            pfprint(30, 'Mongo user [icecube] has read-only permissions, not inserting')
            pfprint(30, '   Change via fatcat_db/configs/mongo_config.json')
            return
        
        self.addMeta()
        self.insertDocument()
        self.insertDeviceIndex()

    
    def addMeta(self):
        # find user name
        config = FileTools().load('ssh_config')
        if config['user'] not in [None, "", "auto"]:
            user = config['user']
        else:
            user = getpass.getuser()

        # add some meta about the insert
        self.data['insert_meta'] = {
            'insert_time': datetime.datetime.utcnow(),
            'json_filename': os.path.basename(self.filename).lower(),
            'json_md5': getObjMD5(loadJson(self.filename)),
            'insert_user': user,
            'mongo_user': self.mongo.mongo_user
        }

        
    def insertDocument(self):
        if self.passed is not True:
            return
        collection = self.json_type+'s'
        if collection in ['devices', 'measurements', 'goalposts']:
            pfprint(1, 'Inserting --> {0}'.format(self.filename))
            # the actual insert
            self.ObjectId = self.mongo.db[collection].insert(self.data)
        else:
            pfprint(30, 'Invalid collection [{0}], not inserting'
                  .format(collection))

        
    def insertDeviceIndex(self):
        if self.passed is not True:
            return
        if self.indexDevice and self.ObjectId is not None:
            pfprint(1, 'Inserting device assembly index for [{0}]'.format(self.indexDevice))
            count = self.mongo.db.index.find({'_id': self.indexDevice}).count()
            if count:
                pfprint(3, 'Device [{0}] already indexed?'.format(self.indexDevice))
                HELP()
                return
            else:
                idoc = {'_id': self.indexDevice,
                       'devices': sorted(self.allNestedUIDs)}
                # the actual insert
                self.mongo.db.index.insert(idoc)

