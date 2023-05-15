import sys
import os
import json
import re
import datetime
from dateutil import parser

from fatcat_db.utils import *
from fatcat_db.filetools import *
from fatcat_db.mongoreader import *
from fatcat_db.datatypes import *


def uniqueJsonFileName(filename, json_type, mongoObj=False):
    if not mongoObj:
        mongo = MongoReader()
    else:
        mongo = mongoObj
    passed = True
    fname = (os.path.basename(filename)).lower()
    coll = json_type + 's'
    found = mongo.countJsonFileName(coll, fname)
    if found > 0:
        pfprint(20, 'File name \"{0}\" exists in \"{1}\" collection [{2}] times'
                .format(fname, coll, found))
        passed = False
        for obj in mongo.searchJsonFileName(coll, fname):
            pfprint(1, 'Inserted on \"{0}\" by user \"{1}\"'
                    .format(obj['insert_meta']['insert_time'].date(),
                            obj['insert_meta']['insert_user']))
    pfprint(passed, 'Unique json filename: [{0}]'
            .format(passed))
    return passed


def uniqueJsonFileMD5(filename, json_type, mongoObj=False):
    if not mongoObj:
        mongo = MongoReader()
    else:
        mongo = mongoObj
    md5 = getObjMD5(loadJson(filename))
    passed = True
    coll = json_type + 's'
    found = mongo.countJsonFileMD5(coll, md5)
    if found > 0:
        pfprint(20, 'File md5 \"{0}\" exists in \"{1}\" collection [{2}] times'
                .format(md5, coll, found))
        passed = False
        for obj in mongo.searchJsonFileMD5(coll, md5):
            pfprint(1, 'Inserted on \"{0}\" by user \"{1}\"'
                    .format(obj['insert_meta']['insert_time'].date(),
                            obj['insert_meta']['insert_user']))
    pfprint(passed, 'Unique json md5: [{0}]'
            .format(passed))
    return passed


def determineJsonFileType(filename):
    formats = FileTools().load('general')
    data = loadJson(filename)

    # check whether it's a valid device file
    dr_count = 0
    isDevice = False
    for key in formats['DEVICE_REQUIREMENTS']:
        if key in data:
            dr_count += 1
    if len(formats['DEVICE_REQUIREMENTS']) == dr_count:
        isDevice = True

    # check whether it's a valid measurement file
    mr_count = 0
    isMeasurement = False
    for key in formats['MEASUREMENT_REQUIREMENTS']:
        if key in data:
            mr_count += 1
    if len(formats['MEASUREMENT_REQUIREMENTS']) == mr_count:
        isMeasurement = True

    # check whether it's a valid goalpost file
    gr_count = 0
    isGoalpost = False
    for key in formats['GOALPOST_REQUIREMENTS']:
        if key in data:
            gr_count += 1
    if len(formats['GOALPOST_REQUIREMENTS']) == gr_count:
        isGoalpost = True

    quitting = False
    # json file should not have fields from other type requirements
    if (isDevice and (mr_count + gr_count > 0)) \
       or (isMeasurement and (dr_count + gr_count > 0)) \
       or (isGoalpost and (dr_count + mr_count > 0)):
        pfprint(30, 'Ambiguity as to what type of json file this is')
        quitting = True

    # only one of these json types can be true
    typecount = int(isDevice) + int(isMeasurement) + int(isGoalpost)
    if typecount != 1:
        pfprint(30, 'Ambiguity as to what type of json file this is')
        quitting = True

    if quitting:
        # provide a hint as to what type of json this appears to be
        if dr_count > mr_count and dr_count > gr_count:
            pfprint(20, "The json looks closest to a \"device\" file but missing:")
            for key in formats['DEVICE_REQUIREMENTS']:
                if key not in data:
                    pfprint(20, '--> \"'+key+'\"')
        if mr_count > dr_count and mr_count > gr_count:
            pfprint(20, "The json looks closest to a \"measurement\" file but missing:")
            for key in formats['MEASUREMENT_REQUIREMENTS']:
                if key not in data:
                    pfprint(20, '--> \"'+key+'\"')
        if gr_count > dr_count and gr_count > mr_count:
            pfprint(20, "The json looks closest to a \"goalpost\" file but missing:")
            for key in formats['GOALPOST_REQUIREMENTS']:
                if key not in data:
                    pfprint(20, '--> \"'+key+'\"')

        # and then quit
        return

    if isDevice:
        pfprint(10, 'Valid json file type: [{0}]'.format('device'))
        return 'device'
    elif isMeasurement:
        pfprint(10, 'Valid json file type: [{0}]'.format('measurement'))
        return 'measurement'
    elif isGoalpost:
        pfprint(10, 'Valid json file type: [{0}]'.format('goalpost'))
        return 'goalpost'
    else:
        pfprint(30, 'Valid json file type: [{0}]'.format(False))
        return


def validDocSize(filename):
    data = loadJson(filename)
    passed = True
    # I forced a mongo error and it
    # said 16793598 bytes max?
    maxsize = 16000000
    docsize = getBsonObjSize(data)
    if docsize > maxsize:
        passed = False
    hr = 'Bytes'
    if docsize > 1000:
        docsize = round(docsize/1000., 1)
        hr = 'KB'
    if docsize > 1000:
        docsize = round(docsize/1000., 1)
        hr = 'MB'
    pfprint(passed, 'Document bson size [%s %s] less than 16MB: [%s]'
            %(docsize, hr, passed))
    return passed


def recursiveCheckForNansInfs(obj):
    passed = True
    if isinstance(obj, list):
        for x in obj:
            passed &= recursiveCheckForNansInfs(x)
    elif isinstance(obj, dict):
        for x in obj:
            passed &= recursiveCheckForNansInfs(obj[x])
    else:
        passed &= notNanInf(obj)
    
    return passed


def recursiveCheckForHyphens(obj):
    passed = True
    if isinstance(obj, dict):
        for x in obj:
            passed &= noHyphen(x)
            passed &= recursiveCheckForHyphens(obj[x])
    if isinstance(obj, list):
        for x in obj:
            passed &= recursiveCheckForHyphens(x)
    return passed


def recursiveCheckForEmptyStrings(obj):
    passed = True
    if isinstance(obj, list):
        for x in obj:
            passed &= recursiveCheckForEmptyStrings(x)
    elif isinstance(obj, dict):
        for x in obj:
            passed &= recursiveCheckForEmptyStrings(obj[x])
    else:
        passed &= notEmptyString(obj)
    
    return passed


def checkJsonSyntax(obj):
    passed = True
    passed &= recursiveCheckForNansInfs(obj)
    passed &= recursiveCheckForHyphens(obj)
    passed &= recursiveCheckForEmptyStrings(obj)
    return passed


