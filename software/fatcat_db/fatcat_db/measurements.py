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
from fatcat_db.devices import *


class Measurement:
    
    def __init__(self, data, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.data = data
        mformats = FileTools().load('measurements')
        self.formats = mformats
        dformats = FileTools().load('devices')
        self.formats.update(dformats)

        self.allNestedUIDs = None
        self.indexDevice = False

        self.valid_device = None
        self.device_type = None
        self.requires_subdevice = None
        self.valid_subdevice = None
        self.subdevice_type = None


    def getMeasDeviceType(self):
        # return the fundemental device being measured
        # this could either be the device or the sub-device
        if self.valid_device is None:
            self.setDeviceSubdeviceTypes()
        if self.valid_device is False:
            return False
        if (self.requires_subdevice is True and
            self.valid_subdevice is True):
            return self.subdevice_type
        elif (self.requires_subdevice is False and
              self.valid_device is True):
            return self.device_type
        else:
            return False
        
        
    def getTopDeviceType(self):
        # return the device_type of device_uid
        if self.valid_device is None:
            self.setDeviceSubdeviceTypes()
        if self.valid_device is False:
            return False
        elif self.valid_device is True:
            return self.device_type
        else:
            return False
        
        
    def getDeviceTypeByUID(self, uid):
        if not deviceUIDExists(uid, self.mongo):
            return False
        doc = self.mongo.findDeviceByUID(uid)
        device_data = Device(doc[0], self.mongo)
        return device_data.device_type

    
    def requiresSubdeviceUID(self, device_type):
        if (device_type not in self.formats['T4_DEVICE_TYPES'] and
            device_type not in self.formats['INDEXED_MEAS_TYPES']):
            return True
        else:
            return False

        
    def setDeviceSubdeviceTypes(self):
        device_type = self.getDeviceTypeByUID(self.data['device_uid'])
        if not device_type:
            self.valid_device = False
            return False
        else:
            self.valid_device = True
            self.device_type = device_type
            
        if not self.requiresSubdeviceUID(device_type):
            self.requires_subdevice = False
            if 'subdevice_uid' in self.data:
                pfprint(20, 'Device_uid [{0}] \"{1}\" does not require \"subdevice_uid\"'
                        .format(self.data['device_uid'], device_type))
                return False
            else:
                return True
        else:
            self.requires_subdevice = True
            if 'subdevice_uid' not in self.data:
                pfprint(20, 'Device_uid [{0}] \"{1}\" requires subdevice_uid '
                        'of the specific device under measurement'
                        .format(self.data['device_uid'], device_type))
                return False
            else:
                if self.data['subdevice_uid'] == self.data['device_uid']:
                    pfprint(20, 'The device and subdevice cannot have the same UID')
                    return False
                subdevice_type = self.getDeviceTypeByUID(self.data['subdevice_uid'])
                if not subdevice_type:
                    self.valid_subdevice = False
                    return False
                if self.requiresSubdeviceUID(subdevice_type):
                    pfprint(20, 'Subdevice_uid [{0}] \"{1}\" is not a valid low-level device'
                            .format(self.data['subdevice_uid'], subdevice_type))
                    pfprint(20, 'Options: {0}'
                            .format(self.formats['INDEXED_MEAS_TYPES'] +
                                    self.formats['T4_DEVICE_TYPES']))
                    self.valid_subdevice = False
                    return False
                else:
                    self.valid_subdevice = True
                    self.subdevice_type = subdevice_type
                    return True

    
    def validDeviceOrSubdevice(self):
        if self.valid_device is None:
            self.setDeviceSubdeviceTypes()
        if self.valid_device is False:
            pfprint(False, 'Valid device_uid and/or subdevice_uid: [{0}]'
                .format(False))
            return False
        if self.requires_subdevice is False:
            pfprint(True, 'Valid device_uid and/or subdevice_uid: [{0}]'
                .format(True))
            return True
        passed = True
        if self.requires_subdevice is True and self.valid_subdevice is True:
            # first try getting all subdevice uids from the device indexes (much faster)
            alluids = self.mongo.getAllSubdevicesFromIndex(self.data['device_uid'])
            # if indexed devices aren't found, do it the slow and thorough way
            if not alluids:
                pfprint(2, 'Device [{0}] does not appear to be indexed. Using the thorough method.'
                        .format(self.data['device_uid']))
                doc = self.mongo.findDeviceByUID(self.data['device_uid'])
                device_data = Device(doc[0], self.mongo)
                alluids = device_data.getAllNestedUIDs()
                # then set this to be indexed
                self.allNestedUIDs = device_data.allNestedUIDs
                self.indexDevice = device_data.indexDevice
            if self.data['subdevice_uid'] not in alluids:
                pfprint(20, 'Subdevice_uid [{0}] is not a subdevice of device_uid [{1}]'
                        .format(self.data['subdevice_uid'], self.data['device_uid']))
                passed = False
        else:
            passed = False
        pfprint(passed, 'Valid device_uid and/or subdevice_uid: [{0}]'
                .format(passed))
        return passed
    
    
    def validMeasurementClass(self):
        passed = True
        if self.data['meas_class'] not in self.formats['MEAS_CLASSES']:
            passed = False
        pfprint(passed, 'Valid meas_class \"{0}\": [{1}]'
                    .format(self.data['meas_class'], passed))
        if not passed:
            pfprint(20, 'Options: {0}'
                    .format(self.formats['MEAS_CLASSES']))
        return passed

    
    def validMeasurementGroup(self):
        passed = True
        if self.data['meas_group'] not in self.formats['MEAS_GROUPS']:
            passed = False
        pfprint(passed, 'Valid meas_group \"{0}\": [{1}]'
                .format(self.data['meas_group'], passed))
        if not passed:
            pfprint(20, 'Options: {0}'
                    .format(self.formats['MEAS_GROUPS']))
        return passed

        
    def validMeasurementName(self):
        passed = isAlphaNumUH(self.data['meas_name'])
        pfprint(passed, 'Valid meas_name \"{0}\": [{1}]'
                .format(self.data['meas_name'], passed))
        return passed

        
    def validMeasurementStage(self):
        passed = True
        if self.data['meas_stage'] not in self.formats['MEAS_STAGES']:
            passed = False
        pfprint(passed, 'Valid meas_stage \"{0}\": [{1}]'
                .format(self.data['meas_stage'], passed))
        if not passed:
            pfprint(20, 'Options: {0}'
                    .format(self.formats['MEAS_STAGES']))
        return passed
    

    def validMeasurementSite(self):
        passed = True
        if self.data['meas_site'] not in self.formats['MEAS_SITES']:
            passed = False
        pfprint(passed, 'Valid meas_site \"{0}\": [{1}]'
                .format(self.data['meas_site'], passed))
        if not passed:
            pfprint(20, 'Options: {0}'
                    .format(self.formats['MEAS_SITES']))
        return passed


    def validRunNumber(self):
        if 'run_number' in self.data and self.data['meas_stage'] == 'fat':
            passed = checkFATRunNumber(self.data['run_number'])
            pfprint(passed, 'Valid FAT run_number [{0}]: [{1}]'
                    .format(self.data['run_number'], passed))
            return passed
        elif 'run_number' in self.data and self.data['meas_stage'] != 'fat':
            passed = checkRunNumFormat(self.data['run_number'])
            pfprint(passed, 'Valid run_number \"{0}\": [{1}]'
                    .format(self.data['run_number'], passed))
            return passed
            #pfprint(20, '\"run_number\" is reserved for FAT measurements')
            #return False
        elif 'run_number' not in self.data and self.data['meas_stage'] == 'fat':
            pfprint(20, 'FAT measurment requires \"run_number\"')
            return False
        else:
            return True

        
    def checkDerivedSource(self):
        if (self.data['meas_class'] != 'derived'
            and 'derived_source' in self.data):
            pfprint(20, 'Found \"derived_source\" but '
                    'meas_class != \"derived\"')
            pfprint(20, 'Help: either remove \"derived_source\" '
                    'or set meas_class to \"derived\"')
            return False

        if (self.data['meas_class'] == 'derived'
            and 'derived_source' not in self.data):
            pfprint(20, 'Found meas_class == \"derived\" '
                    'but \"derived_source\" is missing')
            pfprint(20, 'Help: either add \"derived_source\" '
                    'or set meas_class to something else')
            return False
        
        if (self.data['meas_class'] != 'derived'
            and 'derived_source' not in self.data):
            return True
        
        if not isinstance(self.data['derived_source'], list):
            pfprint(20, '\"derived_source\" required to be a list')
            return False

        if not ((self.requires_subdevice is True and
                 self.valid_subdevice is True) or
                (self.requires_subdevice is False and
                 self.valid_device is True)):
            pfprint(20, 'Cannot continue checking derived source '
                    'because (sub)device_uid is not valid and/or '
                    'the device file has not been inserted yet')
            return False
        
        # Make sure the object ID exists in the db
        # and the object(s) have the same UID as this measurement
        passed = True
        for oid in self.data['derived_source']:
            docs = self.mongo.findMeasByObjId(oid)
            if len(docs) == 1:
                pfprint(10, 'This ObjectId exists: [{0}]'
                        .format(oid))
                # the linked measurement should not also be derived
                # might be exceptions to this in the future...
                if docs[0]['meas_class'] == 'derived':
                    pfprint(20, 'The derived_source object cannot be linked '
                            'to another derived measurement')
                    passed = False
                # derived device_uid should match the measurement device_uid
                if docs[0]['device_uid'] != self.data['device_uid']:
                    pfprint(20, 'Object device_uid [{0}] != '
                            'this device_uid [{1}]'
                            .format(docs[0]['device_uid'],
                                    self.data['device_uid']))
                    passed = False
                # derived subdevice_uid should match the measurement subdevice_uid
                if 'subdevice_uid' in self.data:
                    if docs[0]['subdevice_uid'] != self.data['subdevice_uid']:
                        pfprint(20, 'Object subdevice_uid [{0}] != '
                                'this subdevice_uid [{1}]'
                                .format(docs[0]['subdevice_uid'],
                                        self.data['subdevice_uid']))
                        passed = False
                        
            elif len(docs) > 1:
                pfprint(30, 'This ObjectId exists [{0}] times: [{1}]'
                        .format(found, oid))
                passed = False
            else:
                pfprint(20, 'This ObjectId does not exist: [{0}]'
                        .format(oid))
                passed = False
    
        pfprint(passed, 'Valid \"derived_source\" ObjectId(s): [{0}]'
                .format(passed))
        return passed


#-----------------------------------------------------------


def checkFATRunNumber(run_number):
    # Require FAT run_number to be an integer
    # NaN and Infinity get flagged by general checks
    # null is not an int
    passed = True
    if not isinstance(run_number, int) or isinstance(run_number, bool):
        pfprint(20, 'run_number [{0}] is required to be an integer'.format(run_number))
        passed = False
    if passed:
        if run_number <= 0:
            pfprint(20, 'run_number [{0}] is required to be >0'.format(run_number))
            passed = False
    return passed


def checkRunNumFormat(run_number):
    # non-FAT run_number required to be a string
    passed = isAlphaNumUHT(run_number)
    
    # make sure it's long to help uniqueness
    if len(run_number) < 16:
        pfprint(20, 'run_number \"{0}\" is not >= 16 chars'.format(run_number))
        passed = False
    
    return passed


def measObjectIdExists(oid, mongo):
    found = mongo.db.measurements.find({'_id': ObjectId(oid)}).count()
    if found == 1:
        pfprint(10, 'This ObjectId exists: [{0}]'
                .format(oid))
        return True
    elif found > 1:
        pfprint(30, 'This ObjectId exists [{0}] times: [{1}]'
                .format(found, oid))
        return False
    else:
        pfprint(20, 'This ObjectId does not exist: [{0}]'
                .format(oid))
        return False


