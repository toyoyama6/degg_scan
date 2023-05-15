import sys
import os
import json
import pymongo
import re
from bson.objectid import ObjectId

from fatcat_db.utils import *
from fatcat_db.filetools import *

# py2-3 compat
try:
    input = raw_input
except NameError:
    pass


class MongoReader:

    def __init__(self, host=None, port=None, database=None, user=None, pswd=None):

        self.isConnected = False

        config = FileTools().load('mongo_config')
        if host is None:
            host = config['host']
        if port is None:
            port = config['port']
        if database is None:
            database = config['database']
        if user is None:
            self.mongo_user = config['user']
        else:
            self.mongo_user = user
        if pswd is None:
            pswd = config['pswd']

        pfprint(1, 'Connecting to MongoDB on {0}:{1}'
                .format(host, port))

        # pymongo >= 4 will not work with mongodb serve v3
        pymongo_ver = pymongo.__version__
        if not int((pymongo_ver).split('.')[0]) < 4:
            pfprint(3, 'pymongo {0} is incompatible with the mongodb server\n'
                  '       Install pymongo 3.x to resolve this issue'.format(pymongo_ver))
            return

        try:
            connection = pymongo.MongoClient(host=host, port=port)
            connection.server_info()
            self.connection = connection
        except Exception as e:
            pfprint(3, 'Could not connect to MongoDB on {0}:{1}'
                    .format(host, port))
            print(e)
            return

        # get the database - warn if using production and not icecube
        """
        if database == 'production_calibration' \
           and self.mongo_user != 'icecube':
            doit = input(Color.cyan+Color.bold+
                         'Connecting to the production database! '
                         'Are you sure? [yes/no]: '
                         +Color.reset)
            if doit.lower() != 'yes':
                return
        """
        
        pfprint(1, 'Connecting to database \"{0}\"'.format(database))
        self.db = connection[database]
        
        pfprint(1, 'Authenticating mongo user \"{0}\"'.format(self.mongo_user))
        if self.mongo_user == 'icecube':
            pswd = 'skua'
        try:
            self.db.authenticate(self.mongo_user, pswd)
        except Exception as e:
            pfprint(3, 'Could not authenticate user \"{0}\"'
                    .format(self.mongo_user))
            print(e)
            self.connection.close()
            return
        """
        if self.mongo_user == 'icecube':
            print(Color.cyan+Color.bold+
                  'Mongo user \"icecube\" has read-only permissions. '
                  'Change via fatcat_db/configs/mongo_config.json'
                  +Color.reset)
        """
        # grab the collections we need
        self.collections = ['devices', 'measurements', 'goalposts']
        self.db.devices = self.db['devices']
        self.db.measurements = self.db['measurements']
        self.db.goalposts = self.db['goalposts']
        self.db.index = self.db['device_assembly']
        self.db.stfraw = self.db['stf_results_raw']
        
        self.isConnected = True
        pfprint(1, 'Successfully connected to MongoDB on {0}:{1}'
                .format(host, port))


    def __del__(self):
        try:
            self.connection.close()
        except:
            pass


    def countJsonFileName(self, coll, fname):
        return self.db[coll].find({'insert_meta.json_filename': fname}).count()

    
    def countJsonFileMD5(self, coll, md5):
        return self.db[coll].find({'insert_meta.json_md5': md5}).count()

    
    def searchJsonFileName(self, coll, fname):
        cursor = self.db[coll].find(
            {'insert_meta.json_filename':
             re.compile('^'+fname+'$', re.IGNORECASE)})
        return list(cursor)
    
    
    def searchJsonFileMD5(self, coll, md5):
        cursor = self.db[coll].find(
            {'insert_meta.json_md5':
             re.compile('^'+md5+'$', re.IGNORECASE)})
        return list(cursor)
    
    
    def findDeviceByUID(self, uid):
        cursor = self.db.devices.find({'uid': uid})
        return list(cursor)


    def findDeviceByUIDIgnoreCase(self, uid):
        cursor = self.db.devices.find(
            {'uid': re.compile('^'+uid+'$', re.IGNORECASE)})
        return list(cursor)


    def duplicateSubDevices(self, uid):
        cursor = self.db.devices.aggregate([
            {'$unwind': '$sub_devices'},
            {'$match': {'sub_devices.uid': uid}}])
        return list(cursor)


    def duplicateCount(self, uid):
        cursor = self.db.devices.aggregate([
            {'$unwind': '$sub_devices'},
            {'$match': {'sub_devices.uid': uid}},
            {'$group': {'_id': 'null', 'count': {'$sum': 1}}}])
        return cursor.next()['count']


    def findMeasByObjId(self, oid):
        cursor = self.db.measurements.find({'_id': ObjectId(oid)})
        return list(cursor)


    def getNickname(self, uid):
        docs = list(self.db.devices.find({'uid': uid}))
        if not docs:
            return 'NA'
        doc = docs[0]
        nickname = [aux_id['id'] for aux_id in doc['aux_ids'] \
                    if aux_id['type'] == 'nickname']
        if not nickname:
            return 'NA'
        return nickname[0]

    
    def findNickname(self, nickname):
        cursor = self.db.devices.aggregate([
            {'$unwind': '$aux_ids'},
            {'$match': {'aux_ids.type': 'nickname',
                        'aux_ids.id': re.compile(nickname, re.IGNORECASE)}}])
        return list(cursor)

    
    def findAuxIdbyDeviceType(self, deviceType, idType, auxId):
        cursor = self.db.devices.aggregate([
            {'$unwind': '$aux_ids'},
            {'$match': {'device_type': deviceType,
                        'aux_ids.type': idType,
                        'aux_ids.id': auxId}}])
        return list(cursor)

    
    def checkKnownDuplicateUID(self, uid):
        return self.db.devices.find({'known_duplicate_uid': uid}).count()


    def findAllTestnames(self):
        cursor = self.db.measurements.aggregate([
            {'$unwind': '$meas_data'},
            {'$unwind': '$meas_data.goalpost'},
            {'$group': {'_id': '$meas_data.goalpost.testname'}}])
        docs = list(cursor)
        return sorted([doc['_id'] for doc in docs])

    
    def findDeviceAssociationByUID(self, uid):
        #cursor = self.db.devices.aggregate([
        #    {'$unwind': '$sub_devices'},
        #    {'$match': {'sub_devices.uid': uid}}])
        cursor = self.db.devices.find({'sub_devices.uid': uid})
        return list(cursor)
    
    
    def findDeviceByGenericID(self, gid):
        cursor = self.db.devices.find({
            'uid': re.compile(gid, re.IGNORECASE)})
        docs = list(cursor)
        if not docs:
            cursor = self.db.devices.find({
                'aux_ids.id': re.compile('^'+gid+'$', re.IGNORECASE)})
            docs = list(cursor)
        return docs

    
    def getAllSubdevicesFromIndex(self, uid):
        cursor = self.db.index.find({'_id': uid})
        docs = list(cursor)
        if not docs:
            return []
        else:
            # by definition only 1 doc in db with _id:uid
            return docs[0]['devices']


    def findDeviceAssociationByIndex(self, uid):
        cursor = self.db.index.find({'devices': uid})
        docs = list(cursor)
        if not docs:
            return []
        else:
            return [doc['_id'] for doc in docs]

        
    def getFatMeasurements(self, uid, run_num):
        meas_docs = list(self.db.measurements.find({
            'run_number': run_num,
            'meas_stage': 'fat',
            'device_uid': uid,
            'meas_class': {'$ne': 'storage'}}))
        return meas_docs


    def getFatMeasWithGoalpost(self, uid, run_num):
        meas_docs = list(self.db.measurements.find({
            'run_number': run_num,
            'meas_stage': 'fat',
            'device_uid': uid,
            'meas_class': {'$ne': 'storage'},
            #'meas_data.goalpost.testname': {'$regex': '.*'}
            'meas_data.goalpost': {'$exists': True}
        }))
        return meas_docs


    def getRunNumbers(self):
        run_nums = (self.db.measurements.distinct(
            'run_number', {
                'meas_stage': 'fat',
                'meas_class': {'$ne': 'storage'}}))
        return run_nums


    def getUIDsFromRun(self, run_num):
        uids = (self.db.measurements.distinct(
            'device_uid', {
                'run_number': run_num,
                'meas_stage': 'fat',
                'meas_class': {'$ne': 'storage'}}))
        return uids


    def getRunsFromUID(self, uid):
        runs = (self.db.measurements.distinct(
            'run_number', {
                'device_uid': uid,
                'meas_stage': 'fat',
                'meas_class': {'$ne': 'storage'}}))
        return runs


    def getGoalposts(self, testname, testtype):
        goalposts = list(self.db.goalposts.find({
            'goalpost_testname': testname,
            'goalpost_testtype': testtype}))
        return goalposts
