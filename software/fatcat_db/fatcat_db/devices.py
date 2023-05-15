import sys
import os
import datetime
from dateutil import parser
import json
import pymongo
import logging
import base64
import bz2
from bson.objectid import ObjectId
import re
# py2-3 compat
try:
    basestring
except NameError:
    basestring = str

from fatcat_db.utils import *
from fatcat_db.datatypes import *
from fatcat_db.forwarder import *
from fatcat_db.auxids import *
from fatcat_db.subdevices import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *
from fatcat_db.general import *


class Device:
    
    def __init__(self, data, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.data = data
        self.device_type = self.data['device_type']
        self.tier = getDeviceTier(self.device_type)
        formats = FileTools().load('devices')
        self.formats = formats
        self.allNestedUIDs = None
        self.indexDevice = False
        if 'reworked_from' in self.data:
            self.reworked = True
            self.orig = self.mongo.db.devices.find_one(
                {'uid': self.data['reworked_from']})
            if self.orig is None:
                pfprint(20, 'The \"reworked_from\" uid [{0}] is not found in database'
                        .format(self.data['reworked_from']))
                self.reworked = False
        else:
            self.reworked = False

        
    def checkDeviceType(self):
        passed = (self.tier > 0)
        pfprint(passed, 'Valid device_type \"{0}\": [{1}]'
                .format(self.device_type, passed))
        return passed
        

    def checkDeviceRevision(self):
        # skip further checks if revision can't be cast as float
        # mainly for mainboards where revision could be like "4a" 
        try:
            rev = float(self.data['device_revision'])
        except:
            return True
        # if the revision is a float, make sure it's >= 1
        passed = True
        if rev < 1.0:
            pfprint(20, '\"device_revision\" required to begin at \"1\"')
            passed = False
        pfprint(passed, 'Valid device revision \"{0}\": [{1}]'
                .format(self.data['device_revision'], passed))
        return passed
    

    def checkDeviceNotAssociated(self):
        # This shouldn't happen unless a device that has
        # already been inserted and associated is deleted
        # and then reinserted. But checking this is a
        # good idea just to make sure the full device
        # association tree is properly preserved.
        passed = True
        dups = self.mongo.duplicateSubDevices(self.data['uid'])
        if len(dups) > 0:
            passed = False
            pfprint(20, 'This device [{0}] is already associated with:'
                  .format(self.data['uid']))
            for dup in dups:
                pfprint(20, '   device_type: [{0}]  uid: [{1}]'
                      .format(dup['device_type'], dup['uid']))
        return passed

        
    def checkSubDeviceUIDsExist(self):
        passed = True
        for subUID in getSubDeviceUIDs(self.data):
            passed = passed & deviceUIDExists(subUID, self.mongo)
        return passed


    def getAllNestedUIDs(self):
        if self.allNestedUIDs is None:
            uids = []
            uids.append(getSubDeviceUIDs(self.data))
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
            self.allNestedUIDs = list(set(alluids))
            if self.allNestedUIDs:
                self.indexDevice = self.data['uid']
        return self.allNestedUIDs
    
    
    def checkAllNestedUIDsExist(self):
        passed = True
        uids = self.getAllNestedUIDs()
        for uid in uids:
            passed = passed & deviceUIDExists(uid, self.mongo)
        pfprint(passed, 'All sub_device UIDs exist: [{0}]'
                .format(passed))
        return passed


    def checkForDupNestedUIDs(self):
        # make sure a UID isn't duplicated within
        # the device itself
        passed = True
        uids = self.getAllNestedUIDs()
        dups = findDupsInList(uids)
        for dup in dups:
            # get the device type
            docs = self.mongo.findDeviceByUID(dup)
            if len(docs) == 0:
                pfprint(20, 'Device UID [{0}] not found in database'
                        .format(dup))
                passed = False
                continue
            device_type = docs[0]['device_type']
            
            # check known duplicate uids
            if self.mongo.checkKnownDuplicateUID(dup):
                pfprint(0, '[{2}] \"{0}\" [{1}] is a known duplicate uid'
                        .format(device_type, dup, __name__))
                continue
            else:
                pfprint(20, 'Device \"{0}\" UID [{1}] found '
                        'multiple times in device tree'
                        .format(device_type, dup))
                passed = False
                
        pfprint(passed, 'No duplicate UIDs in device tree: [{0}]'
                .format(passed))
        return passed

    
    def checkForDupSubDevices(self):
        field = 'sub_devices'
        if field not in self.data:
            return True
        reworked_uids = self.getReworkedSubdevices()
        reused_uids = self.getReusedSubdevices()
        passed = True
        for obj in self.data[field]:
            # skip same reworked devices
            if obj['uid'] in reworked_uids:
                pfprint(0, '[{3}] {0} \"{1}\" [{2}] is a known device'
                        .format(field, obj['device_type'], obj['uid'], __name__))
                continue

            # skip reused devices
            elif obj['uid'] in reused_uids:
                pfprint(0, '[{3}] {0} \"{1}\" [{2}] is a known device'
                        .format(field, obj['device_type'], obj['uid'], __name__))
                continue

            # skip known duplicate uids
            elif self.mongo.checkKnownDuplicateUID(obj['uid']):
                pfprint(0, '[{3}] {0} \"{1}\" [{2}] is a known duplicate uid'
                        .format(field, obj['device_type'], obj['uid'], __name__))
                continue
            
            else:
                dups = self.mongo.duplicateSubDevices(obj['uid'])
                if len(dups) > 0:
                    for dup in dups:
                        pfprint(20, 'This \"{0}\" UID [{1}] is already associated with:'
                                .format(obj['device_type'], obj['uid']))
                        pfprint(20, '   device_type: [{0}]  uid: [{1}]'
                                .format(dup['device_type'], dup['uid']))
                    passed = False

        pfprint(passed, 'Sub_devices are not already associated: [{0}]'
                .format(passed))
        return passed


    def checkReworked(self):
        if not self.reworked:
            return True
        passed = True
        passed &= self.compareDeviceType()
        passed &= self.compareProductionDate()
        passed &= self.compareDeviceRevision()
        passed &= self.compareWhatChanged()
        return passed

    
    def compareDeviceType(self):
        field = 'device_type'
        if self.data[field] != self.orig[field]:
            pfprint(20, 'Reworked device [{0}] \"{1}\" != \"{2}\"'
                    .format(field, self.data[field], self.orig[field]))
            return False
        return True

    
    def compareProductionDate(self):
        field = 'production_date'
        if parser.parse(self.data[field]) <= parser.parse(self.orig[field]):
            pfprint(20, 'Reworked device [{0}] \"{1}\" !> \"{2}\"'
                    .format(field, self.data[field], self.orig[field]))
            return False
        return True
    
    
    def compareDeviceRevision(self):
        field = 'device_revision'
        if int(self.data[field]) != int(self.orig[field])+1:
            pfprint(20, 'Reworked device [{0}] \"{1}\" != \"{2}+1\"'
                    .format(field, self.data[field], self.orig[field]))
            return False
        return True
    

    def compareWhatChanged(self):
        reworked_subdevices = {}
        for obj in self.data['sub_devices']:
            reworked_subdevices[obj['device_type']] = obj['uid']

        original_subdevices = {}
        for obj in self.orig['sub_devices']:
            original_subdevices[obj['device_type']] = obj['uid']

        changed = []
        for device in reworked_subdevices:
            if reworked_subdevices[device] != original_subdevices[device]:
                changed.append(device)

        if not changed:
            pfprint(20, 'Reworked device [{0}] is the same as [{1}]'
                    .format(self.data['uid'], self.orig['uid']))
            return False
        else:
            for device in changed:
                pfprint(0, '[{2}] Reworked device has new \"{0}\" with UID [{1}]'.
                        format(device, reworked_subdevices[device], __name__))
            return True
    

    def getReworkedSubdevices(self):
        skip_uids = []
        if not self.reworked:
            return skip_uids
        field = 'sub_devices'
        for orig_obj in self.orig[field]:
            data_obj = [obj for obj in self.data[field]
                        if orig_obj['device_type'] == obj['device_type']]
            if not data_obj:
                pfprint(20, '[{0}] \"{1}\" not found in reworked json'
                        .format(field, orig_obj['device_type']))
                continue
            data_obj = data_obj[0]
            if orig_obj['uid'] == data_obj['uid'] \
               and 'reused_from' not in data_obj:
                skip_uids.append(data_obj['uid'])
        return skip_uids
    

    def getReusedSubdevices(self):
        field = 'sub_devices'
        skip_uids = [obj['uid'] for obj in self.data[field]
                     if 'reused_from' in obj]
        return skip_uids
    

    def checkReusedSubdevices(self):
        # Make sure the reused device does exist
        # in the previously associated device.
        # Mostly a bookkeeping sanity check
        field = 'sub_devices'
        if field not in self.data:
            return True
        passed = True
        for obj in self.data[field]:
            # get uid of reused from device
            if 'reused_from' not in obj:
                continue
            pfprint(0, '[{2}] Found reused \"{0}\" with UID [{1}]'
                    .format(obj['device_type'], obj['uid'], __name__))
            device_type = obj['device_type']
            prev_doc = self.mongo.db.devices.find_one(
                {'uid': obj['reused_from']})
            if not prev_doc:
                pfprint(20, 'The \"reused_from\" uid [{0}] is not found in the database'
                        .format(obj['reused_from']))
                passed = False
                continue
            
            # check uid is really associated with previous device
            prev_uids = [pobj['uid'] for pobj in prev_doc[field]
                        if pobj['device_type'] == device_type]
            if not prev_uids:
                pfprint(20, 'Device [{0}] does not contain sub_device \"{1}\"'
                        .format(obj['reused_from'], device_type))
                passed = False
                continue

            if obj['uid'] not in prev_uids:
                pfprint(20, 'Reused UID [{0}] is not in previous device sub_devices [{1}]'
                        .format(obj['uid'], prev_uids))
                pfprint(20, 'Possibly the wrong UID is specified in \"reused_from\"')
                passed = False
                continue

            # production date of new device should be > than old device
            current_date = parser.parse(self.data['production_date'])
            prev_date = parser.parse(prev_doc['production_date'])
            if current_date <= prev_date:
                pfprint(20, 'Production date of current device [{0}] '
                        'is not greater than the previous device [{1}]'
                        .format(current_date, prev_date))
                passed = False

            # this could be a new device so do not compare device_revision
            # likewise, do not compare device_type
            
        return passed

    
    def checkMdomPMTMap(self):
        device = 'mdom'
        field = 'pmt_map'
        if self.device_type != device:
            return True
        passed = True
        if field not in self.data:
            pfprint(20, 'Device \"{0}\" requires field \"{1}\"'
                    .format(device, field))
            passed = False
        if passed:
            if not validListOfDicts(self.data, field,
                                    needs=[['channel', ['int']],
                                           ['pmt_index', ['int']]]):
                passed = False
        if passed:
            channels = sorted([obj['channel'] for obj in self.data[field]])
            if channels != list(range(24)):
                pfprint(20, '\"{0}\" channels are not in range [0-23]'.format(field))
                passed = False
            pmts = sorted([obj['pmt_index'] for obj in self.data[field]])
            if pmts != list(range(24)):
                pfprint(20, '\"{0}\" pmt_indexes are not in range [0-23]'.format(field))
                passed = False
        
        pfprint(passed, 'Valid {0} \"{1}\": [{2}]'.format(device, field, passed))
        return passed

    
    def conditionalDeviceChecks(self):
        passed = True
        passed &= self.checkMdomPMTMap()
        return passed

    
#-----------------------------------------------------------


def deviceUIDAlphaNumUH(uid):
    passed = isAlphaNumUH(uid)
    not_alloweds = ['true', 'false', 'null', 'none']
    # double check keywords are not in the uid
    for not_allowed in not_alloweds:
        if not_allowed in uid.lower():
            pfprint(20, 'Keywords not allowed in UID such as: {0}'.format(not_allowed))
            passed = False
    pfprint(passed, 'Valid alpha-numeric UID: [{0}]'
            .format(passed))
    return passed

    
def deviceUIDExists(uid, mongoObj=False):
    if not mongoObj:
        mongo = MongoReader()
    else:
        mongo = mongoObj
    found = len(mongo.findDeviceByUID(uid))
    if found == 1:
        pfprint(10, 'This device uid exists: [{0}]'
                .format(uid))
        return True
    elif found > 1:
        pfprint(30, 'This device uid exists [{0}] times: [{1}]'
                .format(found, uid))
        return False
    else:
        pfprint(20, 'This device uid does not exist: [{0}]'
                .format(uid))
        return False


def deviceUIDDoesNotExist(uid, mongoObj=False):
    if not mongoObj:
        mongo = MongoReader()
    else:
        mongo = mongoObj
    found = len(mongo.findDeviceByUIDIgnoreCase(uid))
    if found == 0:
        pfprint(10, 'This device uid does not exist: [{0}]'
                .format(uid))
        return True
    elif found == 1:
        pfprint(20, 'This device uid already exists: [{0}]'
                .format(uid))
        return False
    else:
        pfprint(30, 'This device uid exists [{0}] times: [{1}]'
                .format(found, uid))
        return False


def getSubDeviceUIDs(data):
    if 'sub_devices' in data:
        sub_uids = []
        for obj in data['sub_devices']:
            if 'uid' not in obj:
                pfprint(20, 'Field \"uid\" not found in sub_devices object')
                return []
            else:
                sub_uids.append(obj['uid'])
        return sub_uids
    else:
        return []

 
def getDeviceTier(device_type):
    formats = FileTools().load('devices')
    if device_type in formats['T4_DEVICE_TYPES']:
        return 4
    elif device_type in formats['T3_DEVICE_TYPES']:
        return 3
    elif device_type in formats['T2_DEVICE_TYPES']:
        return 2
    elif device_type in formats['T1_DEVICE_TYPES']:
        return 1
    else:
        return 0


