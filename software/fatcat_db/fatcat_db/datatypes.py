import re
import datetime
from dateutil import parser
import math

# py2-3 compat
try:
    basestring
except NameError:
    basestring = str

from fatcat_db.utils import *

MIN_DATE = '2017-01-01'


def validListOfDicts(data, field, needs=[]):
    passed = True
    if not isinstance(data[field], list):
        pfprint(20, '\"{0}\" is required to be a list of dicts'
                .format(field))
        return False
    for obj in data[field]:
        if not isinstance(obj, dict):
            pfprint(20, '\"{0}\" object is required to be a dict'
                    .format(field))
            passed = False
            continue
        for need in needs:
            if need[0] not in obj:
                pfprint(20, '\"{0}\" object requires \"{1}\" field'
                        .format(field, need[0]))
                passed = False
                continue
            if not is_instance(obj[need[0]], need[1]):
                pfprint(20, '\"{0}\" \"{1}\" field required to be {2}'
                        .format(field, need[0], need[1]))
                passed = False
    return passed


def validDictOfFields(data, field, needs=[]):
    obj = data[field]
    if not isinstance(obj, dict):
        pfprint(20, '\"{0}\" object is required to be a dict'
                .format(field))
        return False
    passed = True
    for need in needs:
        if need[0] not in obj:
            pfprint(20, '\"{0}\" object requires \"{1}\" field'
                    .format(field, need))
            passed = False
            continue
        if not is_instance(obj[need[0]], need[1]):
            pfprint(20, '\"{0}\" \"{1}\" field required to be {2}'
                    .format(field, need[0], need[1]))
            passed = False
    return passed


def isListOfDicts(obj):
    if not isinstance(obj, list):
        pfprint(20, 'Object required to be a list of dicts')
        return False
    for item in obj:
        if not isinstance(item, dict):
            pfprint(20, 'Object required to be a list of dicts')
            return False
    return True


def isList2d(obj):
    if not isinstance(obj, list):
        #pfprint(20, 'Object required to be a list of lists')
        return False
    for item in obj:
        if not isinstance(item, list):
            #pfprint(20, 'Object required to be a list of lists')
            return False
    return True


def is_instance(obj, types_as_strings):
    # handle some special types first
    # assumes 'unixtime' is a stand-alone type
    if 'unixtime' in types_as_strings:
        return validUnixTime(obj)
    # assumes 'listofdicts' is a stand-alone type
    if 'list-of-dicts' in types_as_strings:
        return isListOfDicts(obj)
    # assumes 'list2d' is a stand-alone type
    if 'list2d' in types_as_strings:
        return isList2d(obj)
    
    # now handle standard types
    types = []
    for tas in types_as_strings:
        if tas == 'str' or tas == 'string':
            types.append(basestring)
        elif tas == 'int':
            types.append(int)
        elif tas == 'float':
            types.append(float)
        elif tas == 'list':
            types.append(list)
        elif tas == 'dict':
            types.append(dict)
        else:
            pfprint(20, 'Unknown type \"{0}\"'.format(tas))
            return False
    type_tuple = tuple(types)
    return isinstance(obj, type_tuple)


def validTypeName(this_name, req_names):
    if this_name not in req_names:
        pfprint(20, '\"{0}\" not in accepted list of names {1}'
                .format(this_name, req_names))
        return False
    else:
        return True


def isString(string):
    if isinstance(string, basestring):
        return True
    else:
        pfprint(20, '{0} is required to be a string'.format(string))
        return False


def isHexString(string):
    # is a lower-case hex string and no leading 0x
    if not isString(string):
        return False
    #reg = re.compile('^[a-fA-F0-9]+\Z')
    reg = re.compile('^[a-f0-9]+\Z')
    if bool(reg.match(string)):
        return True
    else:
        pfprint(20, '{0} is not valid hex. Use lower-case a-f and no leading 0x'
                .format(string))
        return False


def stringFormat(string, match):
    if not isString(string):
        return False
    reg = re.compile('^['+match+']+\Z')
    if bool(reg.match(string)):
        return True
    else:
        pfprint(20, 'String \"{0}\" is not of format [{1}]'
                .format(string, match))
        return False


def isAlphaNum(string):
    # no spaces and is alpha-numeric
    return stringFormat(string, 'a-zA-Z0-9')

    
def isAlphaNumU(string):
    # no spaces and is alpha-numeric or underscores
    return stringFormat(string, 'a-zA-Z0-9_')

    
def isAlphaNumH(string):
    # no spaces and is alpha-numeric or hyphens
    return stringFormat(string, 'a-zA-Z0-9-')

    
def isAlphaNumUH(string):
    # no spaces and is alpha-numeric, underscores, or hyphens
    return stringFormat(string, 'a-zA-Z0-9-_')


def isAlphaNumUHT(string):
    # no spaces and is alpha-numeric, underscores, hyphens, or time (:.)
    return stringFormat(string, 'a-zA-Z0-9-_:.')


def validDateTime(dateString):
    # valid python datetime format (yyyy-mm-dd hh:mm:ss)
    passed = True

    # quick hack to skip unknown production dates for pocam
    #if dateString in ['N/A', 'n/a', 'na']:
    #    return True

    # check for '-' format
    if len(dateString.split('-')) != 3:
        pfprint(20, 'Please use \"yyyy-mm-dd\" format for datetime \"{0}\"'
                .format(dateString))
        return False

    # check that yyyy is 4 chars
    if len(dateString.split('-')[0]) != 4:
        pfprint(20, 'Please use \"yyyy-mm-dd\" format for datetime \"{0}\"'
                .format(dateString))
        return False

    # make sure it's parsable
    try:
        dateTime = parser.parse(dateString, yearfirst=True)
    except:
        pfprint(20, 'Could not parse datetime \"{0}\"'
                .format(dateString))
        return False

    # check that time is greater than 2018
    lowBound = parser.parse(MIN_DATE)
    if dateTime < lowBound:
        pfprint(20, 'Datetime [{0}] is less than [{1}]'
                .format(dateTime, lowBound))
        passed = False

    # check that time is less than now
    highBound = datetime.datetime.utcnow()
    if dateTime > highBound:
        pfprint(20, 'Datetime [{0}] is greater than now [{1}]'
                .format(dateTime, highBound))
        passed = False

    pfprint(passed, 'Valid datetime format: [{0}]'
            .format(passed))
    return passed
    
    
def validUnixTime(unixTime):
    # valid unix time format
    passed = True
    if type(unixTime) is not float:
        pfprint(20, 'Unix time is not a float: [{0}]'
                .format(unixTime))
        passed = False

    try:
        dateTime = datetime.datetime.utcfromtimestamp(unixTime)
    except:
        pfprint(20, 'Could not convert unix time to datetime: [{0}]'
                .format(unixTime))
        return False

    # check that time is greater than 2018
    lowBound = parser.parse(MIN_DATE)
    if dateTime < lowBound:
        pfprint(20, 'Unix time [{0}] is less than [{1}]'
                .format(unixTime, lowBound))
        passed = False

    # check that time is less than now
    highBound = datetime.datetime.utcnow()
    if dateTime > highBound:
        pfprint(20, 'Unix time [{0}] is greater than now [{1}]'
                .format(unixTime, highBound))
        passed = False
        
    pfprint(passed, 'Valid unix time format: [{0}]'
            .format(unixTime))
    return passed


def notNanInf(x):
    passed = True
    if isinstance(x, float):
        if math.isnan(x):
            pfprint(20, 'Found \"NaN\" in json, please replace with 0 or null?')
            passed = False
        if math.isinf(x):
            pfprint(20, 'Found \"Infinity\" in json, please replace with 0 or null?')
            passed = False
    return passed


def noHyphen(x):
    passed = True
    if isinstance(x, basestring):
        if '-' in x:
            pfprint(20, 'Found hyphen in \"{0}\", please replace with underscore'
                    .format(x))
            passed = False
    return passed


def notEmptyString(x):
    passed = True
    if isinstance(x, basestring):
        if not x.split():
            pfprint(20, 'Empty strings are not allowed')
            passed = False
    return passed


def findDupsInList(mylist):
    seen = {}
    dups = []
    for x in mylist:
        if x not in seen:
            seen[x] = 1
        else:
            if seen[x] == 1:
                dups.append(x)
            seen[x] += 1
    return dups

