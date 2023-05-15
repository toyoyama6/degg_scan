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


class Goalpost:
    
    def __init__(self, data, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.data = data
        formats = FileTools().load('goalposts')
        self.formats = formats


    # does this testname exist in measurements
    def testnameIsUsed(self):
        # This takes way too long. Tried indexing meas_data.goalpost.testname
        # but that didn't seem to speed it up.
        cursor = self.mongo.db.measurements.aggregate([
            {'$unwind': '$meas_data'},
            {'$unwind': '$meas_data.goalpost'},
            {'$match': {'meas_data.goalpost.testname': self.data['goalpost_testname']}},
            {'$group': {'_id': self.data['goalpost_testname'], 'count': {'$sum': 1}}}])
        results = list(cursor)[0]
        if 'count' in results:
            return results['count']
        else:
            return 0


    # does testname already exist
    def testnameExists(self):
        return self.mongo.db.goalposts.find(
            {'goalpost_testname': self.data['goalpost_testname']}
        ).count()


    # does testname and testtype already exist
    def testnameAndTypeExists(self):
        return self.mongo.db.goalposts.find(
            {'goalpost_testname': self.data['goalpost_testname'],
             'goalpost_testtype': self.data['goalpost_testtype']}
        ).count()


    def validTestname(self):
        passed = True
        if not stringFormat(self.data['goalpost_testname'], 'a-zA-Z0-9-_'):
            passed = False
        pfprint(passed, 'Valid goalpost testname: [{0}]'
                .format(passed))
        return passed

    
    def validTesttype(self):
        passed = True
        if self.data['goalpost_testtype'] not in \
           self.formats['GOALPOST_TESTTYPES']:
            pfprint(20, '{0} is not a valid test type'
                    .format(self.data['goalpost_testtype']))
            pfprint(20, 'Options: {0}'
                    .format(self.formats["GOALPOST_TESTTYPES"]))
            passed = False
        pfprint(passed, 'Valid goalpost testtype: [{0}]'
                .format(passed))
        return passed

        
    def validTestbounds(self):
        passed = True
        if self.data['goalpost_testtype'] in ['min', 'max', 'equals']:
            if not is_instance(self.data['goalpost_testbounds'],
                               ['int', 'float']):
                pfprint(20, 'Testbounds for \"{0}\" is '
                        'required to be an int or float'
                        .format(self.data['goalpost_testtype']))
                passed = False
        elif self.data['goalpost_testtype'] in ['in-range']:
            if not is_instance(self.data['goalpost_testbounds'], ['list']):
                pfprint(20, 'Testbounds for \"{0}\" is '
                        'required to be a list'
                        .format(self.data['goalpost_testtype']))
                passed = False
            elif len(self.data['goalpost_testbounds']) != 2:
                pfprint(20, 'Testbounds for \"{0}\" is '
                        'required to be length == 2'
                        .format(self.data['goalpost_testtype']))
                passed = False
            elif self.data['goalpost_testbounds'][0] >= \
               self.data['goalpost_testbounds'][1]:
                pfprint(20, 'Testbound [{0}] required to be less than [{1}]'
                        .format(self.data['goalpost_testbounds'][0],
                                self.data['goalpost_testbounds'][1]))
                passed = False
            else:
                pass
        else:
            passed = False
        pfprint(passed, 'Valid goalpost testbounds: [{0}]'
                .format(passed))
        return passed
    
    
    def checkValidDate(self):
        if not validDateTime(self.data['valid_date']):
            return False
        # if the testname already exists
        # make sure the new valid_date is greater than others
        passed = True
        if self.testnameAndTypeExists():
            cursor = self.mongo.db.goalposts.find(
                {'goalpost_testname': self.data['goalpost_testname'],
                 'goalpost_testtype': self.data['goalpost_testtype']}
            ).sort('valid_date', -1).limit(1)
            latest = cursor[0]['valid_date']
            latest = parser.parse(latest)
            newdate = parser.parse(self.data['valid_date'])
            if newdate <= latest:
                pfprint(20, 'New \"valid_date\" is not '
                        'greater than the current date [{0}]'
                        .format(latest))
                
                passed = False
        pfprint(passed, 'Valid goalpost valid_date: [{0}]'
                .format(passed))
        return passed
    
    
    def checkNewBounds(self):
        # if the testname already exists
        # make sure the new bounds are not the same as the old bounds
        passed = True
        if self.testnameAndTypeExists():
            cursor = self.mongo.db.goalposts.find(
                {'goalpost_testname': self.data['goalpost_testname'],
                 'goalpost_testtype': self.data['goalpost_testtype']}
            ).sort('valid_date', -1).limit(1)
            latest = cursor[0]['goalpost_testbounds']
            newbounds = self.data['goalpost_testbounds']
            if newbounds == latest:
                pfprint(20, 'New testbounds are the same as '
                        'the current bounds ({0})'
                        .format(newbounds))
                
                passed = False
        pfprint(passed, 'Valid update of testbounds: [{0}]'
                .format(passed))
        return passed
    
    
    
