import sys
import os
# py2-3 compat
try:
    from urllib import request as liburl
except:
    import urllib as liburl
    
from fatcat_db.utils import *
from fatcat_db.forwarder import *
from fatcat_db.datatypes import *


class SupportFiles:

    def __init__(self, data):
        self.data = data
        self.field = 'support_files'
        if self.field in self.data:
            pfprint(1, 'Found field \"{0}\"'.format(self.field))
            self.exists = True
        else:
            self.exists = False
        self.serverFields = ['filetype', 'hostname', 'pathname']
        self.urlFields = ['url_description', 'url']

        
    def validate(self):
        if not self.exists:
            return True
        
        if not isinstance(self.data[self.field], list):
            pfprint(20, '\"{0}\" required to be a list'
                    .format(self.field))
            return False

        passed = True
        for i, obj in enumerate(self.data[self.field]):
            pfprint(1, 'Checking \"{0}\" object [{1}]'
                    .format(self.field, i))
            if not isinstance(obj, dict):
                pfprint(20, 'Object [{0}] required to be a dict'
                        .format(i))
                passed = False
                continue
            if not self.getObjType(obj):
                passed = False
                continue
            if self.isServer:
                if not self.fieldsAreStrings(obj, self.serverFields):
                    passed = False
                    continue
                if not self.checkServerFileExists(obj):
                    passed = False
                    continue
            if self.isURL:
                if not self.fieldsAreStrings(obj, self.urlFields):
                    passed = False
                    continue
                if not self.checkURLExists(obj):
                    passed = False
                    continue
        
        pfprint(passed, 'Valid \"{0}\" format and requirements: [{1}]'
                .format(self.field, passed))
        return passed

    
    def getObjType(self, obj):
        isServer = True
        for field in self.serverFields:
            if field not in obj:
                isServer = False
        isURL = True
        for field in self.urlFields:
            if field not in obj:
                isURL = False

        if isServer and isURL:
            pfprint(20, 'Found server and url fields in object. Use one or the other.\n'
                    '   A server requires fields {0}\n'
                    '   A URL requires fields {1}'
                    .format(self.serverFields, self.urlFields))
            return False
        elif not isServer and not isURL:
            pfprint(20, 'Can not determine whether this is a server or url object.\n'
                    '   A server requires fields {0}\n'
                    '   A URL requires fields {1}'
                    .format(self.serverFields, self.urlFields))
            return False
        else:
            self.isServer = isServer
            self.isURL = isURL
            return True


    def fieldsAreStrings(self, obj, fields):
        passed = True
        for field in fields:
            if not isString(obj[field]):
                pfprint(20, '\"{0}\" required to be a string'
                        .format(field))
                passed = False
        return passed

    
    def checkServerFileExists(self, obj):
        server = obj['hostname']
        filename = obj['pathname']
        #pfprint(1, 'Checking file \"{0}:{1}\"'.format(server, filename))
        if server.lower() in ['localhost', '127.0.0.1']:
            passed = os.path.exists(filename)
            pfprint(passed, 'File \"{0}\" exists on \"{1}\": [{2}]'
                    .format(filename, server, passed))
        else:
            passed = checkRemoteFile(server, filename)
        return passed

    
    def checkURLExists(self, obj):
        thisurl = obj['url']
        #pfprint(1, 'Checking URL \"{0}\"'.format(thisurl))
        if not thisurl.startswith('http'):
            pfprint(20, 'URL does not start with http(s)')
            return False
        return checkURL(thisurl)
    

#-----------------------------------------------------------

            
def checkRemoteFile(server, filename):
    passed = False
    
    if findFile(server+'.json'):
        ssh = ConnectSSH(server+'.json')
    else:
        pfprint(1, 'Could not find config file for \"{0}\"'
                .format(server))
        pfprint(1, 'Trying default settings...')
        ssh = ConnectSSH('ssh_config', 'data.icecube.wisc.edu')

    #ssh.connect()
    #if ssh.client is None:
    if not ssh.connect():
        pfprint(20, 'Could not connect to \"{0}\"'
                .format(server))
        return False

    stdin, stdout, stderr = ssh.client.exec_command(
        'test -e {0} && echo True || echo False'.format(filename)
    )
    
    out = stdout.read().strip()
    errs = stderr.read().strip()
    #print(str(out))
    #print(errs)
    out = out.decode("utf-8")
    errs = errs.decode("utf-8")
    #print(out)
    #print(errs)
    
    if out == 'True':
        passed = True

    pfprint(passed, 'File exists \"{0}:{1}\": [{2}]'
            .format(server, filename, passed))
    return passed


def checkURL(url):
    urlcode = liburl.urlopen(url).getcode()
    if urlcode == 200:
        pfprint(True, 'URL exists \"{0}\": [{1}]'
            .format(url, True))
        return True
    elif urlcode == 404:
        pfprint(20, 'URL \"{0}\" - Not Found'.format(url))
        return False
    else:
        pfprint(20, 'Recieved HTTP status code [{0}]'.format(urlcode))
        return False

    
