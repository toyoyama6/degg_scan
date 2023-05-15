import sys
import os

from fatcat_db.utils import *
from fatcat_db.filetools import *
from fatcat_db.datatypes import *


class OptionalFields:

    def __init__(self, data):
        self.data = data
        opt = FileTools().load('optional')
        self.optfields = opt['OPTIONAL']
    

    def validate(self):
        passed = True
        passed &= self.checkKnownFields()
        passed &= self.checkWrongNames()
        return passed


    def checkKnownFields(self):
        found = False
        passed = True
        for field in self.optfields:
            if field in self.data:
                found = True
                pfprint(1, 'Found optional field \"{0}\"'.format(field))
                # check it's the required format
                if not is_instance(self.data[field], self.optfields[field]):
                    pfprint(20, '\"{0}\" field is required to be a {1}'
                          .format(field, self.optfields[field]))
                    passed = False
                # check it's not empty
                if not self.data[field]:
                    pfprint(20, '\"{0}\" field is empty. Please fill or remove.'
                          .format(field))
                    passed = False
        if found:
            pfprint(passed, 'Valid format of optional fields: [{0}]'.format(passed))
        return passed

    
    def checkWrongNames(self):
        passed = True
        for key in self.data:
            if 'comment' in key and key != 'comments':
                pfprint(20, 'Found field \"{0}\", did you mean \"comments\"'.format(key))
                passed = False
            if 'ship' in key and key != 'shipping_manifest':
                pfprint(20, 'Found field \"{0}\", did you mean \"shipping_manifest\"'.format(key))
                passed = False
            if 'support' in key and key != 'support_files':
                pfprint(20, 'Found field \"{0}\", did you mean \"support_files\"'.format(key))
                passed = False
            if 'revision' in key and key != 'device_revision' and key != 'revision_notes':
                pfprint(20, 'Found field \"{0}\", did you mean \"revision_notes\"'.format(key))
                passed = False
        return passed
    

    
