import sys
import os
import json
import bson
import hashlib

from fatcat_db.utils import *


class FileTools:
    
    def __init__(self):
        self.here = os.path.dirname(os.path.abspath(__file__))
        self.shortnames = {
            'ssh_config'    : 'ssh_config.json',
            'mongo_config'  : 'mongo_config.json',
            'nicknames'     : 'gen1-nicknames.txt',
            'general'       : 'general_format.json',
            'devices'       : 'device_format.json',
            'measurements'  : 'measurement_format.json',
            'goalposts'     : 'goalpost_format.json',
            'aux_ids'       : 'aux_ids.json',
            'sub_devices'   : 'sub_devices.json',
            'meas_data'     : 'meas_data.json',
            'optional'      : 'optional_fields.json'
        }

    
    def load(self, fname):
        filetype = False
        filename = self.getFile(fname)
        if filename:
            filetype = getFileType(filename)
        if filetype:
            if filetype == 'txt':
                return loadTxt(filename)
            elif filetype == 'json':
                return loadJson(filename)
            else:
                pfprint(2, 'Unknown file extension \".{0}\"'
                        .format(ftype))
                return False
        else:
            return False
        
    
    def getFile(self, fname):
        if fname in self.shortnames:
            return findFile(self.shortnames[fname])
        else:
            return findFile(fname)
    
    

#-----------------------------------------------------------


def findFile(fname):
    here = os.path.dirname(os.path.abspath(__file__))
    for path in ['configs', 'misc', 'requirements', 'servers']:
        if os.path.exists(os.path.join(here, path, fname)):
            return os.path.join(here, path, fname)
    if os.path.exists(os.path.join(here, fname)):
        return os.path.join(here, fname)
    elif os.path.exists(fname):
        return fname
    else:
        pfprint(2, 'Could not find file \"{0}\"'.format(fname))
        return False


def getFileType(fname):
    try:
        bits = fname.split('.')
    except Exception as e:
        print(e)
        return False
    if len(bits) == 1:
        pfprint(2, 'No file extension for \"{0}\"'.format(fname))
        return False
    if bits[-1].lower() in ['txt', 'json']:
        return bits[-1].lower()
    else:
        pfprint(2, 'Unknown file extension \"{0}\"'.format(ftype))
        return False


def loadJson(fname):
    if os.path.exists(fname):
        with open(fname) as fh:
            try:
                return json.load(fh, object_pairs_hook=raise_on_duplicates)
            except BaseException as e:
                pfprint(30, 'Error loading {0}: {1}'.format(fname, e))
                raise
    else:
        pfprint(2, 'File does not exist \"{0}\"'.format(fname))
        return {}

    
def raise_on_duplicates(ordered_pairs):
    # reject duplicate keys in json
    # https://stackoverflow.com/a/14902564
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValueError('Duplicate key \"{0}\"'.format(k))
        else:
            d[k] = v
    return d


def loadTxt(fname):
    if os.path.exists(fname):
        with open(fname) as fh:
            return fh.readlines()
    else:
        pfprint(2, 'File does not exist \"{0}\"'.format(fname))
        return False

    
def getBsonObjSize(obj):
    return len(bson.BSON.encode(obj))


def getObjMD5(obj):
    # Do not get md5 of a BSON.encoded object
    # because it changes with bson version!
    # This method produces a consistent md5
    return hashlib.md5(json.dumps(obj, separators=(',', ':'),
                                  indent=None, sort_keys=True)
                       .encode('utf-8')).hexdigest()


def globJSONFiles(paths_or_files):
    jsonfiles = []
    for jfile in paths_or_files:
        if os.path.isdir(jfile):
            files = glob.glob(os.path.join(jfile, '*'))
        else:
            files = glob.glob(jfile)
        files.sort()
        jsonfiles.extend(files)
    jsonfiles = [jfile for jfile in jsonfiles if jfile.endswith('.json')]
    return jsonfiles

