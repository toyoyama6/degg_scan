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
from fatcat_db.forwarder import *
from fatcat_db.auxids import *
from fatcat_db.subdevices import *
from fatcat_db.mongoreader import *
from fatcat_db.filetools import *
from fatcat_db.general import *
from fatcat_db.devices import *
from fatcat_db.measurements import *
from fatcat_db.measdata import *
from fatcat_db.goalposts import *
from fatcat_db.supportfiles import *
from fatcat_db.optionalfields import *


class Checks:

    def __init__(self, filename, mongoObj=False):
        self.filename = filename
        self.passed = True
        json_type = determineJsonFileType(self.filename)
        if not json_type:
            self.passed = False
            return
        else:
            self.json_type = json_type

        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj

        self.allNestedUIDs = None
        self.indexDevice = False

        self.data = loadJson(self.filename)
    
    
    def generalChecks(self):
        passed = True
        passed &= checkJsonSyntax(self.data)
        passed &= uniqueJsonFileName(self.filename, self.json_type, self.mongo)
        passed &= uniqueJsonFileMD5(self.filename, self.json_type, self.mongo)
        passed &= validDocSize(self.filename)
        return passed


    def typeChecks(self):
        if self.json_type == "device":
            return self.deviceChecks()
        elif self.json_type == "measurement":
            return self.measurementChecks()
        elif self.json_type == "goalpost":
            return self.goalpostChecks()
        else:
            pfprint(30, 'Unknown json file type \"{0}\"'
                    .format(self.json_type))
            return False


    def deviceChecks(self):
        ck = Device(self.data, self.mongo)
        passed = True
        passed &= deviceUIDAlphaNumUH(self.data['uid'])
        passed &= deviceUIDDoesNotExist(self.data['uid'], self.mongo)
        passed &= validDateTime(self.data['production_date'])
        passed &= ck.checkDeviceType()
        passed &= ck.checkDeviceRevision()
        passed &= ck.checkDeviceNotAssociated()
        passed &= ck.checkReworked()
        passed &= ck.checkReusedSubdevices()
        passed &= ck.checkAllNestedUIDsExist()
        passed &= ck.checkForDupNestedUIDs()
        passed &= ck.checkForDupSubDevices()
        passed &= SubDevices(self.data, self.mongo).validate()
        passed &= AuxIds(self.data, self.mongo).validate()
        passed &= ck.conditionalDeviceChecks()
        self.allNestedUIDs = ck.allNestedUIDs
        self.indexDevice = ck.indexDevice
        return passed


    def measurementChecks(self):
        ck = Measurement(self.data, self.mongo)
        passed = True
        passed &= ck.validDeviceOrSubdevice()
        passed &= ck.validMeasurementClass()
        passed &= ck.validMeasurementGroup()
        passed &= ck.validMeasurementName()
        passed &= ck.validMeasurementStage()
        passed &= ck.validMeasurementSite()
        passed &= ck.checkDerivedSource()
        passed &= validUnixTime(self.data['meas_time'])
        passed &= ck.validRunNumber()
        topDevice = ck.getTopDeviceType()
        measDevice = ck.getMeasDeviceType()
        passed &= MeasData(topDevice, measDevice, self.data).validate()
        self.allNestedUIDs = ck.allNestedUIDs
        self.indexDevice = ck.indexDevice
        return passed


    def goalpostChecks(self):
        ck = Goalpost(self.data, self.mongo)
        passed = True
        passed &= ck.validTestname()
        passed &= ck.validTesttype()
        passed &= ck.validTestbounds()
        passed &= ck.checkValidDate()
        passed &= ck.checkNewBounds()
        #print(ck.testnameIsUsed())
        return passed


    def additionalChecks(self):
        passed = True
        passed &= SupportFiles(self.data).validate()
        passed &= OptionalFields(self.data).validate()
        return passed


