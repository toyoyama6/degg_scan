import os
import sys
import json
import select
import socketserver as SocketServer
import threading
from degg_measurements.utils.ssh_client import SSHClient
from degg_measurements.utils import rerun_after_exception
from paramiko.ssh_exception import SSHException

from fatcat_db.runchecks import RunChecks
from fatcat_db.runchecks import Insert
from fatcat_db.mongoreader import MongoReader
from fatcat_db.filetools import loadJson
from fatcat_db.filetools import getObjMD5

from degg_measurements import RUN_DIR

if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable


DBH_CONFIG = os.path.join(
    os.path.dirname(__file__),
    'configs/database_helper_config.json')


class ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(SocketServer.BaseRequestHandler):
    def handle(self):
        try:
            chan = self.ssh_transport.open_channel( "direct-tcpip",
                (self.chain_host, self.chain_port),
                self.request.getpeername(),
            )
        except Exception as e:
            verbose(
                "Incoming request to %s:%d failed: %s"
                % (self.chain_host, self.chain_port, repr(e))
            )
            return
        if chan is None:
            verbose(
                "Incoming request to %s:%d was rejected by the SSH server."
                % (self.chain_host, self.chain_port)
            )
            return

        verbose(
            "Connected!  Tunnel open %r -> %r -> %r"
            % (
                self.request.getpeername(),
                chan.getpeername(),
                (self.chain_host, self.chain_port),
            )
        )
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose("Tunnel closed from %r" % (peername,))


g_verbose = True
def verbose(s):
    if g_verbose:
        print(s)


class DatabaseHelper(object):
    def __init__(self, config_file=DBH_CONFIG):
        with open(config_file) as open_file:
            cfg = json.load(open_file)
        self.client = SSHClient(hostname=cfg['hostname'],
                                username=cfg['username'])
        self.local_port = cfg['local_port']
        self.remote_host = cfg['remote_host']
        self.remote_port = cfg['remote_port']

    @rerun_after_exception(SSHException, 2)
    def forward_tunnel_during_func(self, func, *args, **kwargs):
        with self.client as client:
            transport = client.transport
            # this is a little convoluted, but lets me configure things for the Handler
            # object.  (SocketServer doesn't give Handlers any way to access the outer
            # server normally.)
            class SubHander(Handler):
                chain_host = self.remote_host
                chain_port = self.remote_port
                ssh_transport = transport

            with ForwardServer(("", self.local_port), SubHander) as server:
                server_thread = threading.Thread(target=server.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                return_value = func(*args, **kwargs)
                server.shutdown()
        return return_value

    def _mongo_insert_file(self, filename, dry_run=False, mongo=None):
        if dry_run:
            jf = RunChecks(filename)
            obj_id = None
        else:
            jf = Insert(filename, mongoObj=mongo, verbosity='debug')
            if jf.passed:
                try:
                    obj_id = jf.ObjectId
                except AttributeError:
                    raise AttributeError(
                        'Database insert was unsuccessful, '
                        'ObjectID does not exist!')
            else:
                obj_id = self._get_obj_id(filename)
            if obj_id is None:
                raise ValueError(f'Could not get ObjectID for {filename}')
        return obj_id

    def _mongo_insert(self, json_filename, dry_run=False, mongo=None):
        if isinstance(json_filename, str):
            obj_id = self._mongo_insert_file(json_filename, dry_run, mongo)
        else:
            obj_id = []
            for json_file_i in json_filename:
                obj_id_i = self._mongo_insert_file(json_file_i, dry_run, mongo)
                obj_id.append(obj_id_i)
        return obj_id

    def _get_obj_id(self, json_filename):
        mongo = MongoReader()

        data = loadJson(json_filename)
        md5 = getObjMD5(data)
        obj_id = None
        docs = mongo.searchJsonFileMD5('measurements', md5)
        n_docs = len(docs)
        if n_docs == 0:
            print(f'No database entries with json_filename '
                  f'{json_filename} and md5 {md5} found via md5 sum.')
        elif n_docs > 1:
            print(f'Found {n_docs} database entries for json_filename '
                  f'{json_filename} with md5 {md5} via md5 sum.')
        else:
            obj_id = docs[0]['_id']
            print(f'Found object id {obj_id} via md5 sum.')

        json_filename = os.path.basename(json_filename).lower()
        if obj_id is None:
            for coll in mongo.collections:
                query = mongo.searchJsonFileName(coll, json_filename)
                n_docs = len(query)
                if n_docs == 1:
                    obj_id = query[0]['_id']
                    print(f'Found object id {obj_id} from json filename.')

        return obj_id

    def get_existing_object_id(self, json_filename):
        obj_id = self.forward_tunnel_during_func(self._get_obj_id, json_filename)
        return obj_id

    def mongo_insert(self, json_filename, dry_run=False):
        if isinstance(json_filename, str):
            if not os.path.exists(json_filename):
                raise FileNotFoundError(f'File {json_filename} does not exist!')
        elif isinstance(json_filename, Iterable):
            for json_filename_i in json_filename:
                if not os.path.exists(json_filename_i):
                    raise FileNotFoundError(
                        f'File {json_filename_i} does not exist!')

        obj_id = self.forward_tunnel_during_func(
            self._mongo_insert, json_filename, dry_run)
        return obj_id


def get_run_start(run_number):
    run_path = os.path.join(RUN_DIR, 'run', f'run_{int(run_number):05d}.json')
    with open(run_path, 'r') as open_file:
        run_json = json.load(open_file)
    start_date = run_json['date']
    return start_date


if __name__ == '__main__':
    json_filename = os.path.expanduser(
        '~/software/production-calibration-master/tier3/degg-mainboard-1.json')
    dbh = DatabaseHelper(DBH_CONFIG)
    dbh.mongo_insert(json_filename)

