import os
import json

from fatcat_db.utils import *
from fatcat_db.datatypes import *
from fatcat_db.filetools import *
from fatcat_db.mongoreader import *


class SubDevices:

    def __init__(self, data, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.data = data
        self.device_type = data['device_type']
        reqs = FileTools().load('sub_devices')
        self.reqs = reqs
        self.field = reqs['format']['field']
        self.needs = reqs['format']['needs']
        self.types = reqs['format']['types']
        

    def validate(self):
        passed = True
        passed &= self.checkGeneralFormat()
        passed &= self.checkRequirements()
        pfprint(passed, 'Valid \"{0}\" format and requirements: [{1}]'
                .format(self.field, passed))
        return passed
    
        
    def checkGeneralFormat(self):
        if self.field not in self.data:
            return True
        passed = validListOfDicts(self.data, self.field, self.needs)
        if passed:
            passed &= self.checkUIDisCorrectDeviceType()
        return passed
    
        
    def checkRequirements(self):
        if self.device_type not in self.reqs:
            if self.field in self.data:
                pfprint(20, '\"{0}\" does not require {1} field'
                        .format(self.device_type, self.field))
                return False
            return True
        
        reqs = self.reqs[self.device_type]
        if self.field not in self.data:
            pfprint(20, 'Device \"{0}\" requires \"{1}\" with format: {2}'
                    .format(self.device_type, self.field, reqs))
            return False
        passed = True
        for req in reqs:
            if 'indexes' in req:
                passed = passed & self.checkIndexes(req['device_type'],
                                                    req['indexes'])
            else:
                passed = passed & self.checkNotIndexed(req['device_type'])
                passed = passed & self.checkDeviceType(req['device_type'])

            if 'id_inUID' in req:
                if req['id_inUID'] is True:
                    passed = passed & self.checkSubdeviceIDinUID(req['device_type'])
            
        passed = passed & self.checkDevicesNotReq(reqs)
        return passed


    def checkIndexes(self, req_type, index_range):
        if not stringFormat(index_range, '0-9-'):
            pfprint(20, 'Invalid index requirement format for \"{0}\"'
                    .format(req_type))
            return False
        ibits = index_range.split('-')
        if len(ibits) == 1:
            indexes = [int(ibits[0])]
        elif len(ibits) == 2:
            indexes = list(range(int(ibits[0]), int(ibits[1])+1))
        else:
            pfprint(20, 'Invalid index requirement format for {0}'
                    .format(req_type))
            return False
        
        Nindexes = len(indexes)
        sub_objs = [obj for obj in self.data[self.field]
                    if obj['device_type'] == req_type]
        for obj in sub_objs:
            if 'index' not in obj:
                pfprint(20, '{0} {1} object requires \"index\" field'
                        .format(self.field, req_type))
                return False
            if not isinstance(obj['index'], int):
                pfprint(20, '{0} {1} \"index\" required to be an int'
                        .format(self.field, req_type))
                return False
        if len(sub_objs) != Nindexes:
            pfprint(20, '{0} requires [{1}] \"{2}\"s with indexes'
                        .format(self.field, Nindexes, req_type))
            return False
        device_indexes = [obj['index'] for obj in sub_objs]
        device_indexes.sort()
        if device_indexes != indexes:
            pfprint(20, 'Invalid \"{0}\" indexing: '
                    'expected [{1}]: '
                    'got {2}'
                    .format(req_type, index_range, device_indexes))
            return False
        return True
    

    def checkNotIndexed(self, req_type):
        sub_objs = [obj for obj in self.data[self.field]
                    if obj['device_type'] == req_type]
        passed = True
        for obj in sub_objs:
            if 'index' in obj:
                pfprint(20, '{0} \"{1}\" should not have \"index\" field'
                        .format(self.field, req_type))
                passed = False
        return passed

    
    def checkDeviceType(self, req_type):
        sub_objs = [obj for obj in self.data[self.field]
                    if obj['device_type'] == req_type]
        if len(sub_objs) == 0:
            pfprint(20, '{0} {1} requires device_type \"{2}\"'
                        .format(self.device_type, self.field, req_type))
            return False
        if len(sub_objs) > 1:
            pfprint(20, '{0} {1} requires only 1 \"{2}\"'
                        .format(self.device_type, self.field, req_type))
            return False
        return True


    def checkSubdeviceIDinUID(self, req_type):
        sub_objs = [obj for obj in self.data[self.field]
                    if obj['device_type'] == req_type]
        # their should only be 1 matching object
        sub_obj = sub_objs[0]
        obj_id = sub_obj['uid'].split('_')[-1]
        if obj_id not in self.data['uid']:
            pfprint(20, 'The \"{0}\" sub-device ID [{1}] is required in the \"{2}\" UID'
                    .format(req_type, obj_id, self.data['device_type']))
            return False
        else:
            return True


    def checkDevicesNotReq(self, reqs):
        req_device_types = [obj['device_type'] for obj in reqs]
        sub_device_types = [obj['device_type'] for obj
                            in self.data[self.field]]
        passed = True
        for sub_device in sub_device_types:
            if sub_device not in req_device_types:
                pfprint(20, '{0} \"{1}\" is not in requirements {2}'
                        .format(self.field, sub_device, list(set(req_device_types))))
                passed = False
        return passed


    def checkUIDisCorrectDeviceType(self):
        passed = True
        for obj in self.data[self.field]:
            doc = self.mongo.db.devices.find_one({'uid': obj['uid']})
            if not doc:
                pfprint(20, 'Sub_device [{0}] not found in database'.format(obj['uid']))
                passed = False
            elif doc['device_type'] != obj['device_type']:
                pfprint(20, '{0} UID \"{1}\" is not a {2}'
                        .format(self.field, obj['uid'], obj['device_type']))
                passed = False
            else:
                continue
        return passed

    
