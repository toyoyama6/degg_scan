import os
import json

from fatcat_db.utils import *
from fatcat_db.datatypes import *
from fatcat_db.filetools import *
from fatcat_db.mongoreader import *
from fatcat_db.eeprom_crc import MaximCRC8


class AuxIds:

    def __init__(self, data, mongoObj=False):
        if not mongoObj:
            self.mongo = MongoReader()
        else:
            self.mongo = mongoObj
        self.data = data
        self.device_type = data['device_type']
        self.device_revision = str(data['device_revision'])
        reqs = FileTools().load('aux_ids')
        self.reqs = reqs
        self.field = reqs['format']['field']
        self.needs = reqs['format']['needs']
        self.types = reqs['format']['types']
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
            self.orig = False


    def validate(self):
        passed = self.checkGeneralFormat()
        if passed:
            passed &= self.checkRequirements()
            passed &= self.checkNonRequiredIDs()
            passed &= self.checkReworked()
        passed &= self.checkWrongPlacement()
        pfprint(passed, 'Valid \"{0}\" format and requirements: [{1}]'
                .format(self.field, passed))
        return passed
    
        
    def checkGeneralFormat(self):
        passed = True
        if self.field in self.data:
            # make sure it's a list of dictionarys
            if not validListOfDicts(self.data, self.field, self.needs):
                return False
            # check for duplicate types
            if not self.checkDupAuxIdTypes():
                return False
            for obj in self.data[self.field]:
                # make sure the type name is in the accepted list
                passed &= validTypeName(obj['type'], self.types)
        return passed
    
    
    def checkRequirements(self):
        # aux_ids should all be explicitly defined?
        #if (self.field in self.data) and (self.device_type not in self.reqs):
        #    pfprint(20, 'Device type \"{0}\" should not contain field \"{1}\"'
        #            .format(self.device_type, self.field))
        #    return False
        # No, I'll check undefined aux_ids separately in checkNonRequiredIDs()
        
        # if there are no defined requirements, return
        if self.device_type not in self.reqs:
            return True
        reqs = self.reqs[self.device_type]
        if self.field not in self.data:
            pfprint(20, 'Device \"{0}\" requires \"{1}\" with format: {2}'
                    .format(self.device_type, self.field, reqs))
            return False
        passed = True
        req_types = []
        for req in reqs:
            req_types.append(req['type'])
            subpass = self.checkAuxIdType(req['type'])
            passed &= subpass
            if subpass:
                if 'common_name' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'common_name', __name__))
                    passed &= self.checkAuxIdComName(req['type'], req['common_name'])
                if 'id_len' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_len', __name__))
                    passed &= self.checkAuxIdLength(req['type'], req['id_len'])
                if 'id_case' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_case', __name__))
                    passed &= self.checkAuxIdCase(req['type'], req['id_case'])
                else:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_case', __name__))
                    passed &= self.checkAuxIdCaseGeneral(req['type'])
                if 'id_end' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_end', __name__))
                    passed &= self.checkAuxIdEnding(req['type'], req['id_end'])
                if 'id_crc' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_crc', __name__))
                    passed &= self.checkAuxIdCRC(req['type'], req['id_crc'])
                if 'id_inUID' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'id_inUID', __name__))
                    passed &= self.checkAuxIdInUID(req['type'], req['id_inUID'])
                if 'isUnique' in req:
                    pfprint(0, '[{2}] checking \"{0}\" - \"{1}\"'
                            .format(req['type'], 'isUnique', __name__))
                    passed &= self.checkAuxIdUniqueForDevice(req['type'], req['isUnique'])
                if req['type'] == 'nickname':
                    pfprint(0, '[{1}] checking \"{0}\"'.format(req['type'], __name__))
                    passed &= self.checkAuxIdNickname(req['type'])
        # make sure devices do not have a nickname if it's not
        # explicitly defined in the requirements
        if 'nickname' not in req_types:
            passed &= self.checkNoNickname()
        
        return passed

    
    def checkNonRequiredIDs(self):
        # if no aux_ids return 
        if self.field not in self.data:
            return True
        # get list of required ids or nothing
        if self.device_type in self.reqs:
            reqs = [req['type'] for req in self.reqs[self.device_type]]
        else:
            reqs = []
        for obj in self.data[self.field]:
            if obj['type'] in reqs:
                continue
            pfprint(1, 'Found non-required aux_ids type \"{0}\"'.format(obj['type']))
            passed = self.checkAuxIdUniqueForDevice(obj['type'], True)
            pfprint(passed, '   Unique \"{0}\" ID [{1}]: [{2}]'
                    .format(obj['type'], obj['id'], passed))
        # take no action at this point
        # just want people to be aware if their IDs are not at least unique
        return True
    
        
    def checkWrongPlacement(self):
        passed = True
        for idtype in self.types:
            htype = idtype.replace('-', '_')
            if htype in self.data:
                pfprint(20, 'Found field \"{0}\", please move this under \"aux_ids\"\n'
                        '   as {{\"type\": \"{1}\", \"id\": \"{2}\"}}'
                        .format(htype, idtype, self.data[htype]))
                passed = False
        return passed
    
    
    def checkDupAuxIdTypes(self):
        auxtypes = [obj['type'] for obj in self.data['aux_ids']]
        dups = findDupsInList(auxtypes)
        if len(dups) > 0:
            pfprint(20, 'Aux_ids currently does not support duplicated types\n'
                    '   Duplicated types found for {0}'
                    .format(dups))
            return False
        else:
            return True

        
    def checkAuxIdType(self, auxid_type):
        if auxid_type not in [obj['type'] for obj in self.data['aux_ids']]:
            pfprint(20, 'Device \"{0}\" requires aux_ids type \"{1}\"'
                    .format(self.data['device_type'], auxid_type))
            return False
        return True
    

    def checkAuxIdComName(self, auxid_type, common_name):
        if common_name is False: return True
        if 'common_name' not in [obj for obj in self.data['aux_ids']
                                 if obj['type'] == auxid_type][0]:
            pfprint(20, 'aux_ids \"{0}\" requires \"common_name\"'
                    .format(auxid_type))
            return False
        if common_name != [obj['common_name']
                           for obj in self.data['aux_ids']
                           if obj['type'] == auxid_type][0]:
            pfprint(20, 'aux_ids \"{0}\" requires \"common_name\" of \"{1}\"'
                    .format(auxid_type, common_name))
            return False
        return True


    def checkAuxIdLength(self, auxid_type, length):
        if length is False: return True
        idlength = len([obj['id'] for obj in self.data['aux_ids']
                        if obj['type'] == auxid_type][0])
        lens = str(length).split('-')
        l1 = int(lens[0])
        l2 = int(lens[-1])+1
        if idlength not in list(range(l1, l2)):
        #if idlength != int(length):
            pfprint(20, 'aux_ids \"{0}\" \"id\" length [{1}] != [{2}]'
                    .format(auxid_type, idlength, length))
            return False
        return True


    def checkAuxIdCase(self, auxid_type, case):
        idstring = [obj['id'] for obj in self.data['aux_ids']
                    if obj['type'] == auxid_type][0]
        if case is False:
            return self.checkAuxIdCaseGeneral(auxid_type)
        else:
            return stringFormat(idstring, case)


    def checkAuxIdCaseGeneral(self, auxid_type):
        # all aux_ids must at least satisfy this requirement
        idstring = [obj['id'] for obj in self.data['aux_ids']
                    if obj['type'] == auxid_type][0]
        return stringFormat(idstring, 'a-zA-Z0-9-_.')


    def checkAuxIdEnding(self, auxid_type, ending):
        if ending is False: return True
        idstring = [obj['id'] for obj in self.data['aux_ids']
                    if obj['type'] == auxid_type][0]
        if isinstance(ending, dict):
            if self.device_revision in ending:
                ending = ending[self.device_revision]
            else:
                pfprint(20, 'Device revision [{0}] not found in aux_id requirements'
                        .format(self.device_revision))
                HELP()
                return False
        passed = True
        if not idstring.endswith(ending):
            pfprint(20, 'This \"{0}\" id [{1}] is expected to end with \"{2}\"'
                    .format(auxid_type, idstring, ending))
            passed = False
            if idstring.startswith(ending):
                pfprint(20, '   Looks like the byte order is reversed?')
        return passed


    def checkAuxIdCRC(self, auxid_type, crc):
        if crc is False: return True
        idstring = [obj['id'] for obj in self.data['aux_ids']
                    if obj['type'] == auxid_type][0]
        if not MaximCRC8(idstring).isValid():
            pfprint(20, 'This \"{0}\" id [{1}] did not pass the MaximCRC8'
                    .format(auxid_type, idstring))
            passed = False
        else:
            passed = True
        pfprint(passed, 'Valid \"{0}\" MaximCRC8: [{1}]'
                .format(auxid_type, passed))
        return passed
    
        
    def checkAuxIdInUID(self, auxid_type, inUID):
        if inUID is False: return True
        auxid = [obj['id'] for obj in self.data['aux_ids']
                 if obj['type'] == auxid_type][0]
        auxtype = [obj['type'] for obj in self.data['aux_ids']
                   if obj['type'] == auxid_type][0]
        if auxid not in self.data['uid']:
            pfprint(20, '\"{0}\" id \"{1}\" is required to be in the device UID'
                    .format(auxtype, auxid))
            return False
        else:
            return True

    
    def checkAuxIdUniqueForDevice(self, auxid_type, isUnique):
        if isUnique is False: return True
        auxid = [obj['id'] for obj in self.data['aux_ids']
                 if obj['type'] == auxid_type][0]
        passed = True
        if self.reworked:
            orig_auxid = [obj['id'] for obj in self.orig['aux_ids']
                             if obj['type'] == auxid_type][0]
            if auxid != orig_auxid:
                pfprint(20, 'Reworked device [{0}] \"{1}\" != \"{2}\"'
                        .format(auxid_type, auxid, orig_auxid))
                passed = False
        else:
            dbobjs = self.mongo.findAuxIdbyDeviceType(self.device_type, auxid_type, auxid)
            if len(dbobjs) > 0:
                pfprint(20, 'The {0} {1} {2} is not unique'
                        .format(self.device_type, auxid_type, auxid))
                for dbobj in dbobjs:
                    pfprint(20, '   {0} {1} {2} found in device [{3}]'
                            .format(self.device_type, auxid_type, auxid, dbobj['uid']))
                passed = False
        return passed
    

    def checkAuxIdNickname(self, auxid_type):
        nickname = [obj['id'] for obj in self.data['aux_ids']
                    if obj['type'] == auxid_type][0]
        passed = True
        if self.reworked:
            orig_nickname = [obj['id'] for obj in self.orig['aux_ids']
                             if obj['type'] == auxid_type][0]
            if nickname != orig_nickname:
                pfprint(20, 'Reworked device [{0}] \"{1}\" != \"{2}\"'
                        .format(auxid_type, nickname, orig_nickname))
                passed = False
        else:
            passed = validNickname(nickname, self.mongo)
        return passed
    

    def checkNoNickname(self):
        # only explicitly defined devices should have nicknames
        # make sure other devices do not have nicknames

        # some devices do not have aux_ids
        if self.field not in self.data:
            return True

        if [obj['id'] for obj in self.data['aux_ids']
            if obj['type'] == 'nickname']:
            pfprint(20, 'Device type \"{0}\" should not have a nickname'
                    .format(self.device_type))
            return False
        else:
            return True

        
    def checkReworked(self):
        if not self.reworked:
            return True
        # some reworked devices do not have aux_ids
        if self.field not in self.orig:
            return True
        passed = True
        for orig_obj in self.orig[self.field]:
            data_obj = [obj for obj in self.data[self.field]
                        if orig_obj['type'] == obj['type']]
            if not data_obj:
                pfprint(20, '[{0}] \"{1}\" not found in reworked json'
                        .format(self.field, orig_obj['type']))
                passed = False
                continue
            data_obj = data_obj[0]
            if orig_obj['id'] != data_obj['id']:
                pfprint(20, 'Reworked device [{0}] {1} \"{2}\" != \"{3}\"'
                    .format(self.field, data_obj['type'], data_obj['id'], orig_obj['id']))
                passed = False
        return passed

    
#-----------------------------------------------------------


def validNickname(nickname, mongoObj=False):
    if not mongoObj:
        mongo = MongoReader()
    else:
        mongo = mongoObj

    passed = True

    # double check format
    passed = stringFormat(nickname, 'a-zA-Z0-9_')

    # check first character is upper-case and not numeric
    if nickname[0].islower() or nickname[0].isnumeric():
        pfprint(20, 'First char of nickname \"{0}\" required to be upper case and not numeric'
                .format(nickname))
        passed = False

    # check database for duplicate Upgrade nicknames
    ndocs = mongo.findNickname(nickname)
    if len(ndocs) > 0:
        passed = False
        for ndoc in ndocs:
            inserted_name = ndoc['aux_ids']['id']
            pfprint(20, 'Nickname \"{0}\" is the same or too similar to [{2}] nickname \"{1}\"'
                    .format(nickname, inserted_name, ndoc['uid']))

    # check the Gen1 dom nicknames
    gen1names = FileTools().load('nicknames')
    gen1names = [line.strip() for line in gen1names]
    for gen1name in gen1names:
        if nickname.lower() == gen1name.lower():
            pfprint(20, 'Nickname \"{0}\" is the same or too similar to Gen1 nickname \"{1}\"'
                    .format(nickname, gen1name))
            passed = False

    pfprint(passed, 'Valid nickname \"{0}\": [{1}]'
            .format(nickname, passed))
    return passed

