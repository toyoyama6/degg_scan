#!/usr/bin/env python

import os
import argparse

import numpy as np
import matplotlib
from matplotlib import pyplot as plt
from datetime import datetime
from dateutil import parser

# py2-3 compat
try:
    input = raw_input
except NameError:
    pass

from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader
from helper.fat_results.plotting import ShowMeas


def main():

    cmdParser = argparse.ArgumentParser()
    cmdParser.add_argument('-t', '--test', dest='testdb', action='store_true',
                           help='Force use of the production database')
    cmdParser.add_argument('-nt', '--no-tunnel', dest='tunnel', action='store_false',
                           help='Do not port forward mongodb server')
    
    args = cmdParser.parse_args()

    # open ssh tunnel to mongo port
    if args.tunnel:
        tunnel = Tunnel()
    
    # connect to mongo
    if args.testdb:
        fatmongo = MongoReader(database='production_calibration_test')
        run = 130
        uid = 'DEgg2020-2-033_v1'
    else:
        fatmongo = MongoReader(database='production_calibration')
        run = 136
        uid = 'DEgg2021-3-017_v1'
    if not fatmongo.isConnected:
        return

    # all stf data is in production_calibration
    stfmongo = MongoReader(database='production_calibration')
    if not stfmongo.isConnected:
        return
    """
    # stf results
    sr = StfResults(uid, run, stfmongo, fatmongo)
    print(sr.getConfigData())
    print(sr.getPassFailCount())
    # fatcat results
    fr = FatcatResults(uid, run, fatmongo)
    print(fr.getPassFailCount())
    """
    
    # pretty printed info
    rs = FatRunSummary(stfmongo=stfmongo, fatmongo=fatmongo,
                       run_numbers=[],
                       #run_numbers=run,
                       #uids=[]
                       uids=uid
                       )
    rs.printConfigInfo()
    print()
    rs.printPassFail()
    
    
    return


class FatRunSummary:
    # Use two databases in case user wants to look
    # at fatcat test data.
    def __init__(self, stfmongo, fatmongo, uids=False, run_numbers=False):

        self.stfmongo = stfmongo
        self.fatmongo = fatmongo

        # some logic here to grab the correct info from database
        # init runs/uids dict[run][uid] = {}
        self.run_uid_info = {}
        if not uids and not run_numbers:
            run_numbers = self.fatmongo.getRunNumbers()
            for run in run_numbers:
                self.run_uid_info[run] = {}
                uids = self.fatmongo.getUIDsFromRun(run)
                for uid in uids:
                    self.run_uid_info[run][uid] = {}
        elif not uids and run_numbers:
            if not isinstance(run_numbers, list):
                run_numbers = [run_numbers]
            for run in run_numbers:
                self.run_uid_info[run] = {}
                uids = self.fatmongo.getUIDsFromRun(run)
                for uid in uids:
                    self.run_uid_info[run][uid] = {}
        elif uids and not run_numbers:
            if not isinstance(uids, list):
                uids = [uids]
            for uid in uids:
                run_numbers = self.fatmongo.getRunsFromUID(uid)
                for run in run_numbers:
                    if run not in self.run_uid_info:
                        self.run_uid_info[run] = {}
                    self.run_uid_info[run][uid] = {}
        else:
            if not isinstance(uids, list):
                uids = [uids]
            if not isinstance(run_numbers, list):
                run_numbers = [run_numbers]
            for run in run_numbers:
                self.run_uid_info[run] = {}
                for uid in uids:
                    self.run_uid_info[run][uid] = {}

        self.getAllResults()
        
    
    def getAllResults(self):
        for run in self.run_uid_info:
            for uid in self.run_uid_info[run]:
                self.run_uid_info[run][uid] = self.getResultsByRunUID(run, uid)

    
    def getResultsByRunUID(self, run, uid):
        info = {}
        info['nickname'] = self.fatmongo.getNickname(uid)
        sr = StfResults(uid, run, self.stfmongo, self.fatmongo)
        info['config'] = sr.getConfigData()
        info['stf'] = sr.getPassFailCount()
        fr = FatcatResults(uid, run, self.fatmongo)
        info['fatcat'] = fr.getPassFailCount()
        return info

    
    def printConfigInfo(self):
        ver_keys = []
        for run in self.run_uid_info:
            for uid in self.run_uid_info[run]:
                ver_keys = self.run_uid_info[run][uid]['config']['ver_keys']
                break
        
        header = ''
        header += 'Run'.ljust(8)
        #header += 'Nickname'.ljust(26)
        header += 'xDevice UID'.ljust(21)
        header += 'Mainboard ID'.ljust(19)
        for key in ver_keys:
            header += key.ljust(len(key)+3)
        print(header)
        
        for run in sorted(self.run_uid_info):
            # clean up run_number for std out
            #try: _run = int(run.split('_')[-1])
            #except: _run = run
            _run = run
            
            for uid in sorted(self.run_uid_info[run]):
                string = ''
                string += str(_run).ljust(8)
                #string += self.run_uid_info[run][uid]['nickname'].ljust(26)
                string += uid.ljust(21)
                string += self.run_uid_info[run][uid]['config']['dut_id'].ljust(19)
                for key in ver_keys:
                    string += str(self.run_uid_info[run][uid]['config']['versions'][key]).ljust(len(key)+3)
                print(string)
        
        return

    
    def printPassFail(self):
        pl = 3
        fl = 2
        pfl = 17 + pl + fl
        header = ''
        header += 'Run'.ljust(8)
        header += 'xDevice UID'.ljust(21)
        header += 'Nickname'.ljust(30)
        header += 'FATCaT Pass/Fail'.ljust(pfl)
        header += 'STF Pass/Fail'.ljust(pfl)
        print(header)

        for run in sorted(self.run_uid_info):
            # clean up run_number for std out
            #try: _run = int(run.split('_')[-1])
            #except: _run = run
            _run = run
            
            for uid in sorted(self.run_uid_info[run]):
                string = ''
                string += str(_run).ljust(8)
                string += uid.ljust(21)
                string += self.run_uid_info[run][uid]['nickname'].ljust(30)
                string += '{0} pass / {1} fail'.format(
                    str(self.run_uid_info[run][uid]['fatcat']['pass']).rjust(pl),
                    str(self.run_uid_info[run][uid]['fatcat']['fail']).rjust(fl)).ljust(pfl)
                string += '{0} pass / {1} fail'.format(
                    str(self.run_uid_info[run][uid]['stf']['pass']).rjust(pl),
                    str(self.run_uid_info[run][uid]['stf']['fail']).rjust(fl)).ljust(pfl)
                print(string)
                
        return


class FatcatResults:
    def __init__(self, uid, run_number, fatmongo):
        self.uid = uid
        self.run_number = run_number
        self.fatmongo = fatmongo
        self.nickname = self.fatmongo.getNickname(uid)
        self.general_info = {
            'uid': self.uid,
            'run_number': self.run_number,
            'nickname': self.nickname
        }

        
    def getPassFailCount(self):
        meas_docs = self.fatmongo.getFatMeasWithGoalpost(self.uid, self.run_number)
        pass_count = 0
        fail_count = 0
        undefined = 0
        for meas_doc in meas_docs:
            sm = ShowMeas(meas_doc, self.fatmongo)
            for meas in meas_doc['meas_data']:
                if not ('goalpost' in meas and meas['data_format'] == 'value'):
                    continue
                passed, goalpost = sm.getPassFail(meas)
                if passed is None:
                    continue
                elif not goalpost:
                    undefined += 1
                elif passed:
                    pass_count += 1
                else:
                    fail_count += 1
        passfail = {'pass': pass_count, 'fail': fail_count, 'undefined': undefined}
        passfail.update(self.general_info)
        return passfail
    

class StfResults:
    # Use two databases in case user wants to look
    # at fatcat test data.
    def __init__(self, uid, run_number, stfmongo, fatmongo):
        self.uid = uid
        self.run_number = run_number
        #self.run_number = str(int(run_number.split('_')[-1]))
        self.stfmongo = stfmongo
        self.fatmongo = fatmongo
        self.have_info = self.getDeviceInfo()
        self.nickname = self.fatmongo.getNickname(uid)
        self.general_info = {
            'uid': self.uid,
            'run_number': self.run_number,
            'nickname': self.nickname
        }
        
        
    def getDeviceInfo(self):
        doc = self.fatmongo.db['devices'].find_one({'uid': self.uid})
        if not doc:
            return False
        self.device_type = doc['device_type']
        
        # need to make this a little smarter at some point
        # and i need to get degg mainboard eeproms into fatcat
        self.mbuid = [device['uid'] for device in doc['sub_devices'] \
                      if device['device_type'] == self.device_type+'-mainboard'][0]
        if self.device_type == 'degg':
            self.stf_name = 'fpgaChipID'
            self.stf_id = '0x'+self.mbuid.split('_')[-1]
            return True
        elif self.device_type == 'mdom':
            self.stf_name = 'mainBoardElectronicId'
            self.stf_id = self.mbuid.split('_')[-1]
            return True
        else:
            return False


    def getConfigData(self):
        config = {}
        config['versions'] = {
            'STFver':   'NA',
            'FhIcmFw':  'NA',
            #'FhIcmApi': 'NA',
            'FhServer': 'NA',
            'IcmFw':    'NA',
            'WPA':      'NA',
            'MbFpga':   'NA',
            #'MCUhash':  'NA',
            'MCUver':   'NA'
            #'Tools':    'NA',
            #'uBase':    'NA'
            }
        config['ver_keys'] = sorted(config['versions'].keys())
        config['dut_id'] = 'NA'
        config.update(self.general_info)
        
        if not self.have_info:
            return config
        config['dut_id'] = (self.stf_id).split('0x')[-1]
        
        docs = list(self.stfmongo.db['stf_results_raw'].find(
            {'phases.measurements.'+self.stf_name+'.measured_value': self.stf_id,
             'metadata.run_number': self.run_number
             #'$or': [{'metadata.run_number': int(self.run_number)},
             #        {'metadata.run_number': {'$regex': self.run_number+'$'}}]
             }).sort('start_time_millis', -1).limit(1))
        
        if not docs:
            return config
        doc = docs[0]
        #print(doc['_id'])
        
        versions = {}

        # get stf version
        versions['STFver'] = doc['metadata']['stf_version']

        # ubase version is only in newer versions of stf?
        if self.device_type in ['mdom']:
            if 'ubase_version' in doc['metadata']['stf_config']['iceboot']:
                versions['uBase'] = doc['metadata']['stf_config']['iceboot']['ubase_version']
        
        nicenames = {
            'fhIcmFirmwareVersion':  'FhIcmFw',
            #'fhIcmApiId':            'FhIcmApi',
            'fhSoftwareVersion':     'FhServer',
            'icmFirmwareVersion':    'IcmFw',
            'icmWirePairAddress':    'WPA',
            'fpgaVersion':           'MbFpga',
            #'softwareId':            'MCUhash',
            'softwareVersion':       'MCUver'
            #'toolsId':               'Tools'
        }
        # softwareId == MCU git hash
        # softwareVersion == MCU tagged version == iceboot
        
        tohex = [
            'fhIcmFirmwareVersion',
            'icmFirmwareVersion',
            'fpgaVersion',
            'softwareVersion',
        ]
        tonum = [
            #'fpgaVersion',
        ]
        
        # get other stuff under phases[1].measurements
        for key in nicenames:
            if key not in doc['phases'][1]['measurements']:
                versions[nicenames[key]] = 'none'
                continue
            if doc['phases'][1]['measurements'][key]['outcome'] != 'PASS':
                versions[nicenames[key]] = 'fail'
                continue
            value = doc['phases'][1]['measurements'][key]['measured_value']
            if key in tohex:
                value = hex(value)
            elif key in tonum:
                value = int(value)
            else:
                value = str(value).strip().split(' ')[0]
            versions[nicenames[key]] = value

        config['versions'] = versions
        config['ver_keys'] = sorted(versions.keys())
        return config

    
    def getPassFailCount(self):
        passfail = {'pass': 'NA', 'fail': 'NA'}
        passfail.update(self.general_info)
        if not self.have_info:
            return passfail
        pass_count = self.stfmongo.db['stf_results_raw'].count_documents(
            {'phases.measurements.'+self.stf_name+'.measured_value': self.stf_id,
             'outcome': 'PASS',
             'metadata.run_number': self.run_number
             #'$or': [{'metadata.run_number': int(self.run_number)},
             #        {'metadata.run_number': {'$regex': self.run_number+'$'}}]
             })
        fail_count = self.stfmongo.db['stf_results_raw'].count_documents(
            {'phases.measurements.'+self.stf_name+'.measured_value': self.stf_id,
             'outcome': 'FAIL',
             'metadata.run_number': self.run_number
             #'$or': [{'metadata.run_number': int(self.run_number)},
             #        {'metadata.run_number': {'$regex': self.run_number+'$'}}]
             })
        passfail['pass'] = pass_count
        passfail['fail'] = fail_count
        return passfail


    
        
if __name__ == "__main__":
    main()

