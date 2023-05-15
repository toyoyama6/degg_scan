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
from fatcat_db.measurements import *



class MeasData:

    def __init__(self, top_device, meas_device, data):
        self.top_device = top_device
        self.meas_device = meas_device
        self.data = data
        reqs = FileTools().load('meas_data')
        self.reqs = reqs
        self.field = reqs['format']['field']
        self.needs = reqs['format']['needs']
        self.types = reqs['format']['types']
        self.projs = reqs['format']['projections']
        mform = FileTools().load('measurements')
        self.formats = mform
        gpform = FileTools().load('goalposts')
        self.formats.update(gpform)
        opts = FileTools().load('optional')
        self.not_here = opts['NOTINMEASDATA']

        
    def validate(self):
        passed = self.checkGeneralFormat()
        if passed:
            passed &= self.checkMeasDataReqs()
        pfprint(passed, 'Valid \"{0}\" format and requirements: [{1}]'
                .format(self.field, passed))
        return passed
    
        
    def checkGeneralFormat(self):
        passed = True
        if self.field in self.data:
            # make sure it's a list of dictionarys
            passed &= validListOfDicts(self.data, self.field, self.needs)
        else:
            pfprint(20, 'Measurement requires \"{0}\"'
                    .format(self.field))
            passed = False
        return passed
    
    
    def checkMeasDataReqs(self):
        if self.field not in self.data:
            pfprint(20, 'Measurement requires \"{0}\"'
                    .format(self.field))
            return False
        passed = True
        for i, meas_obj in enumerate(self.data[self.field]):
            pfprint(1, 'Checking meas_data object [{0}]'
                  .format(i))
            subpassed = self.checkObjectReqs(meas_obj)
            subpassed &= self.checkMoniReqs(meas_obj)
            subpassed &= self.checkSharedXMultiGraphReqs(meas_obj)
            if subpassed:
                subpassed &= validTypeName(meas_obj['data_format'], self.types)
            if subpassed:
                subpassed &= self.checkMoniData(meas_obj)
                subpassed &= self.checkSharedXMultiGraphData(meas_obj)
                subpassed &= self.checkListLengths(meas_obj)
                subpassed &= self.checkListDataTypes(meas_obj)
                subpassed &= self.checkProjection(meas_obj)
                subpassed &= self.checkStartStopTimes(meas_obj)
                subpassed &= self.checkMeasIndex(meas_obj)
                subpassed &= self.checkNoOptionalFields(meas_obj)
                subpassed &= self.checkMeasGoalpost(meas_obj)
                
            passed &= subpassed
            pfprint(subpassed, 'Valid meas_data object [{0}]: [{1}]'
                    .format(i, subpassed))
        
        return passed
    
    
    def checkObjectReqs(self, obj):
        pfprint(0, '[{0}] checking meas data requirements'.format(__name__))
        
        if obj['data_format'] not in self.reqs:
            pfprint(20, 'data_format \"{0}\" not found in requirements'
                    .format(obj['data_format']))
            return False
        reqs = self.reqs[obj['data_format']]
        passed = True
        for need in reqs['needs']:
            if need[0] not in obj:
                pfprint(20, 'data_format \"{0}\" requires {1}'
                        .format(obj['data_format'], need[0]))
                passed = False
            else:
                if not is_instance(obj[need[0]], need[1]):
                    pfprint(20, '\"{0}\" is not {1}'
                            .format(need[0], need[1]))
                    passed = False
        for option in (reqs['optional'] + self.reqs['optional']):
            if option[0] in obj:
                if not is_instance(obj[option[0]], option[1]):
                    pfprint(20, '\"{0}\" is not {1}'
                            .format(option[0], option[1]))
                    passed = False

        return passed


    def checkListLengths(self, obj):
        pfprint(0, '[{0}] checking meas data lengths'.format(__name__))
        
        data_format = obj['data_format']
        if 'equals' not in self.reqs[data_format]:
            pfprint(20, '\"{0}\" format mising \"equals\" '
                    'property in meas_data config'
                    .format(data_format))
            return False

        if not self.reqs[data_format]['equals']:
            return True
        
        reqs = self.reqs[data_format]['equals']
        for req in reqs:
            if len(req) == 1:
                pfprint(20, '\"equals\" property must have at least 2 '
                        'conditions in meas_data config')
                return False

        passed = True
        for req in reqs:
            for i in range(len(req)-1):
                # special case for list2d - meshgrid
                if isinstance(req[i], list):
                    req0 = [obj[x] for x in req[i]]
                else:
                    req0 = obj[req[i]]
                if isinstance(req[i+1], list):
                    req1 = [obj[x] for x in req[i+1]]
                else:
                    req1 = obj[req[i+1]]
                
                if not isEqualLength(req0, req1):
                    pfprint(20, 'Length \"{0}\" != \"{1}\"'
                            .format(req0, req1))
                    passed = False

        # check error list lengths if they exist
        for prefix in ['x', 'y', 'z', 'y1', 'y2']:
            if prefix+'_errors' in obj:
                pfprint(0, '[{0}] checking data length of \"{1}\"'.format(__name__, prefix+'_errors'))
                if not isEqualLength(obj[prefix+'_errors'], obj[prefix+'_values']):
                    pfprint(20, 'Length \"{0}\" != \"{1}\"'
                        .format(prefix+'_errors', prefix+'_values'))
                    passed = False
        
        return passed

    
    def checkListDataTypes(self, obj):
        # check first element of data list is int or float
        pfprint(0, '[{0}] checking meas data types'.format(__name__))

        passed = True
        for name in ['values', 'errors']:
            for prefix in ['x', 'y', 'z', 'y1', 'y2']:
                key = prefix+'_'+name
                if key in obj:
                    pfprint(0, '[{0}] checking data type of \"{1}\"'.format(__name__, key))
                    # check for 2d list - meshgrid
                    if is_instance(obj[key], ['list2d']):
                        val = obj[key][0][0]
                    else:
                        val = obj[key][0]
                    if not isinstance(val, (int, float)):
                        pfprint(20, 'Data in \"{0}\" is not int or float'
                                .format(key))
                        passed = False
        return passed


    def checkSharedXMultiGraphReqs(self, obj):
        # special treatment of shared-x-multi-graph
        if obj['data_format'] != 'shared-x-multi-graph':
            return True
        pfprint(0, '[{0}] checking shared-x-multi-graph requirements'.format(__name__))
        return validListOfDicts(obj, 'y_data',
                                [['label', ['str']],
                                 ['values', ['list']]])


    def checkSharedXMultiGraphData(self, obj):
        # special treatment of shared-x-multi-graph
        if obj['data_format'] != 'shared-x-multi-graph':
            return True
                            
        pfprint(0, '[{0}] checking shared-x-multi-graph data'.format(__name__))
                
        passed = True

        # get length of x_values
        N = len(obj['x_values'])
        
        # check all y_data lists are same length
        for yobj in obj['y_data']:
            if not isEqualLength(yobj['values'], N):
                pfprint(20, 'Length of \"{0}\" values list != {1}'
                        .format(yobj['label'], N))
                passed = False
            if 'errors' in yobj:
                if not isEqualLength(yobj['errors'], N):
                    pfprint(20, 'Length of \"{0}\" errors list != {1}'
                            .format(yobj['label'], N))
                    passed = False

        if not passed: return False

        # check all y_data lists are int or float
        for yobj in obj['y_data']:
            for val in yobj['values']:
                if not isinstance(val, (int, float)):
                    pfprint(20, '\"{0}\" values list is not int or float'.format(yobj['label']))
                    passed = False
                    break
            if 'errors' in yobj:
                for val in yobj['errors']:
                    if not isinstance(val, (int, float)):
                        pfprint(20, '\"{0}\" errors list is not int or float'.format(yobj['label']))
                        passed = False
                        break

        return passed

    
    def checkMoniReqs(self, obj):
        # special treatment of monitoring data
        if obj['data_format'] != 'monitoring':
            return True
        pfprint(0, '[{0}] checking monitoring data requirements'.format(__name__))
        return validListOfDicts(obj, 'monitoring',
                                [['moni_name', ['str']],
                                 ['moni_data', ['list']]])


    def checkMoniData(self, obj):
        # special treatment of monitoring data
        if obj['data_format'] != 'monitoring':
            return True
                            
        pfprint(0, '[{0}] checking monitoring data'.format(__name__))
                
        passed = True

        # check moni_times exists
        if 'moni_times' not in obj:
            return False
        
        # check moni_times are in unix time
        # just check the first time
        if not validUnixTime(obj['moni_times'][0]):
            pfprint(20, 'Timestamps in moni_times are not valid unix time')
            passed = False

        # get length of moni_times
        N = len(obj['moni_times'])
        
        # check all moni_data lists are same length
        for moni in obj['monitoring']:
            if not isEqualLength(moni['moni_data'], N):
                pfprint(20, 'Length of \"{0}\" != {1}'
                        .format(moni['moni_name'], N))
                passed = False

        if not passed: return False

        # check times are increasing
        for i in range(N-1):
            if not obj['moni_times'][i] < obj['moni_times'][i+1]:
                pfprint(20, 'Timestamp index [{0}] > [{1}] ie {2} > {3}'
                        .format(i, i+1, obj['moni_times'][i], obj['moni_times'][i+1]))
                passed = False
            
        # check all moni_data lists are int or float
        for moni in obj['monitoring']:
            for val in moni['moni_data']:
                if not isinstance(val, (int, float)):
                    pfprint(20, '\"{0}\" moni_data list is not int or float'.format(moni['moni_name']))
                    passed = False
                    break
        
        return passed


    def checkMeasIndex(self, obj):
        pfprint(0, '[{0}] checking meas device index'.format(__name__))
        
        if self.meas_device is False or self.meas_device is None:
            pfprint(20, 'Cannot check indexes because '
                    'device_type is invalid')
            return False

        if self.meas_device not in \
           self.formats['INDEXED_MEAS_TYPES'] and 'index' in obj:
            pfprint(20, 'Device \"{0}\" does not require measurement indexing'
                    .format(self.meas_device))
            return False

        if self.meas_device not in \
           self.formats['INDEXED_MEAS_TYPES']:
            return True

        N = self.formats['INDEXED_MEAS_TYPES'][self.meas_device]
        if obj['index'] not in list(range(N)):
            pfprint(20, 'Measurement \"index\" outside of range 0-{0}'
                    .format(N-1))
            return False
        pfprint(True, 'Valid measurement index of \"{0}\"'
                .format(obj['index']))
        return True
        
    
    def checkStartStopTimes(self, obj):
        pfprint(0, '[{0}] checking meas start/stop times'.format(__name__))

        if 'start_time' not in obj and 'stop_time' not in obj:
            return True
        elif 'start_time' not in obj and 'stop_time' in obj:
            pfprint(20, 'Found stop_time without start_time')
            return False
        elif 'start_time' in obj and 'stop_time' not in obj:
            pfprint(20, 'Found start_time without stop_time')
            return False
        elif 'start_time' in obj and 'stop_time' in obj:
            if obj['stop_time'] > obj['start_time']:
                return True
            else:
                pfprint(20, 'stop_time not greater than start_time')
                return False
        else:
            pfprint(20, 'Something wonky with start/stop times')
            return False

    
    def checkProjection(self, obj):
        pfprint(0, '[{0}] checking meas projection'.format(__name__))

        if obj['data_format'] not in ['data3d']:
            return True
        if 'projection' not in obj:
            return True
        if obj['projection'] not in self.projs:
            pfprint(20, '\"{0}\" projection of \"{1}\" not in {2}'
                    .format(obj['data_format'], obj['projection'], self.projs))
            return False
        else:
            return True
        
        
    def checkNoOptionalFields(self, obj):
        pfprint(0, '[{0}] checking optional fields'.format(__name__))

        passed = True
        for field in self.not_here:
            if field in obj:
                pfprint(20, 'Please move \"{0}\" out of meas_data'.format(field))
                passed = False
        return passed


    def checkMeasGoalpost(self, obj):
        pfprint(0, '[{0}] checking goalposts'.format(__name__))

        # check for something like goalpost
        for key in obj:
            if ('goal' in key.lower() or 'post' in key.lower()) \
               and key != 'goalpost':
                pfprint(20, 'Found field \"{0}\", did you mean \"goalpost\"'.format(key))
                return False
        
        if 'goalpost' not in obj:
            return True
        
        pfprint(0, 'Found \"goalpost\" in measurement object')

        if obj['data_format'] != 'value':
            pfprint(2, 'Goalposts are currently only supported for data_format \"value\"')
            #return False
        
        passed = True
        passed = validListOfDicts(obj, 'goalpost',
                                  [['testname', ['str']],
                                   ['testtype', ['str']]])
        if passed:
            for gpobj in obj['goalpost']:
                passed &= self.validTestnameFormat(gpobj['testname'])
                passed &= self.validTesttypeFormat(gpobj['testtype'])
        
        return passed

    
    def validTestnameFormat(self, testname):
        passed = True
        
        # make sure testname is alpha-numeric
        if not isAlphaNumUH(testname):
            pfprint(20, 'Found special character(s) in testname. '
                    'Replace or remove.')
            return False

        # testname should have format like
        # "<top-level-device>_<measured-device>_<device-model>_<measurment-name>"
        
        # determine expected device and subdevice names
        top_device = self.top_device
        meas_device = self.meas_device

        if self.top_device is False or self.meas_device is False:
            pfprint(20, 'Cannot determine expected testname format')
            pfprint(20, 'Invalid or non-existing device or subdevice uid')
            return False
        
        if self.top_device == self.meas_device:
            string1 = 'bare'
            string2 = self.top_device
        else:
            string1 = self.top_device
            string2 = self.meas_device

        # special case for indexed led units
        if self.top_device in self.formats['INDEXED_MEAS_TYPES']:
            string1 = self.top_device
            string2 = 'led'
            
        # split testname by '_'
        bits = testname.split('_')
        
        # compare expectation to observed
        if bits[0] != string1:
            pfprint(20, 'Substring \"{0}\" expected to be \"{1}\"'
                    .format(bits[0], string1))
            passed = False

        # compare expectation to observed
        if bits[1] != string2:
            pfprint(20, 'Substring \"{0}\" expected to be \"{1}\"'
                    .format(bits[1], string2))
            passed = False
            
        # at least X substrings
        minNumSub = self.formats['TESTNAME_MIN_SUBSTRINGS']
        if len(bits) < minNumSub:
            pfprint(20, 'Found less than {0} sub-strings in testname'.format(minNumSub))
            pfprint(20, '\"testname\" should look something like:')
            pfprint(20, '\"<top-level-device>_<measured-device>_'+
                             '<device-model>_<detailed-measurment-name>\"')
            passed = False
        
        # length > X
        minLength = self.formats['TESTNAME_MIN_LENGTH']
        if len(testname) < minLength:
            pfprint(20, '\"testname\" is too short (<{0} chars)'.format(minLength))
            pfprint(20, 'Try using a more detailed measurement name.')
            pfprint(20, '\"testname\" should look something like:')
            pfprint(20, '\"<top-level-device>_<measured-device>_'+
                             '<device-model>_<detailed-measurment-name>\"')
            passed = False
            
        pfprint(passed, 'Valid goalpost \"testname\" format: [{0}]'
                .format(passed))
        return passed

    
    def validTesttypeFormat(self, testtype):
        #formats = FileTools().load('goalposts')
        testtypes = self.formats['GOALPOST_TESTTYPES']
        if testtype in testtypes:
            return True
        else:
            pfprint(20, 'Invalid testtype \"{0}\"'.format(testtype))
            pfprint(20, 'Options: {0}'.format(testtypes))
            return False

    
#-----------------------------------------------------------


def isEqualLength(x, y):

    # special case for list2d
    is2d = False
    if is_instance(x, ['list2d']):
        x = [len(x), len(x[0])]
        is2d = True
    if is_instance(y, ['list2d']):
        y = [len(y), len(y[0])]
        is2d = True
    if is2d:
        return x == y

    # normal comparison
    if isinstance(x, list):
        x = len(x)
    if isinstance(y, list):
        y = len(y)
    return x == y

