#!/usr/bin/env python

# modified code from paramiko forward.py demo

import sys
import os
import socket
import select
import threading
from subprocess import Popen
import getpass
import paramiko
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

from fatcat_db.utils import *
from fatcat_db.filetools import *


def portIsFree(port):
    # port remains unavailable ~30 seconds after close
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # this overrides the TIME_WAIT state
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("localhost", int(port)))
        s.close()
        return True
    except Exception as e:
        s.close()
        #print(e)
        return False


class ConnectSSH:

    def __init__(self, config_file=None, server=None):
        
        if config_file is not None:
            config = FileTools().load(config_file)
        else:
            config = FileTools().load('ssh_config')
        if server is not None:
            self.server = server
        else:
            self.server = config['server']
        self.server_port = config['server_port']
        self.user = config['user']
        self.private_key = config['private_key']
        self.look_for_keys = bool(config['look_for_keys'])
        self.prompt_for_password = bool(config['prompt_for_password'])
        

    def connect(self):

        if self.user in [None, "", "auto"]:
            self.user = getpass.getuser()

        if self.prompt_for_password is True:
            password = getpass.getpass('Enter password for {0} for user \"{1}\": '
                                       .format(self.server, self.user))
        else:
            password = ''

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        #self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pfprint(1, 'Connecting to {0}@{1}:{2}'
                .format(self.user, self.server, self.server_port))
        try:
            self.client.connect(
                self.server,
                self.server_port,
                username=self.user,
                key_filename=self.private_key,
                look_for_keys=self.look_for_keys,
                password=password,
            )
            return True
        except Exception as e:
            pfprint(3, 'Failed to connect to {0}@{1}:{2}'
                    .format(self.user, self.server, self.server_port))
            print(e)
            self.client = None
            return False

            
    def __del__(self):
        try:
            self.client.close()
        except:
            pass


class Tunnel(ConnectSSH):

    def __init__(self):
        
        ConnectSSH.__init__(self, 'ssh_config')
        if not self.connect():
            return

        config = FileTools().load('ssh_config')
        remote = config['remote']
        remote_port = config['remote_port']
        local_port = config['local_port']

        if not portIsFree(local_port):
            pfprint(2, 'Port {0} is already in use'.format(local_port))
            return
        
        pfprint(1, 'Forwarding port {0} to {1}:{2}'
                .format(local_port, remote, remote_port))

        try:
            self.connection = forward_tunnel(
                local_port,
                remote,
                remote_port,
                self.client.get_transport())
            return
        except Exception as e:
            # warn but don't exit in case the user has already
            # opened the port by some other method
            pfprint(2, 'Failed to port forward {0}'.format(local_port))
            print(e)
            return


    def __del__(self):
        try:
            self.connection.shutdown()
        except:
            pass


class ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(SocketServer.BaseRequestHandler):
    def handle(self):
        try:
            chan = self.ssh_transport.open_channel(
                "direct-tcpip",
                (self.chain_host, self.chain_port),
                self.request.getpeername())
        except Exception as e:
            pfprint(3, "Incoming request to %s:%d failed"
                % (self.chain_host, self.chain_port))
            print(e)
            return

        if chan is None:
            pfprint(3, "Incoming request to %s:%d was rejected by the SSH server."
                % (self.chain_host, self.chain_port))
            return

        pfprint(0, '[{3}] Tunnel open {0} -> {1} -> {2}'
                .format(self.request.getpeername(), chan.getpeername(),
                        (self.chain_host, self.chain_port), __name__))

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
        pfprint(0, '[{1}] Tunnel closed from {0}'.format(peername, __name__))


def forward_tunnel(local_port, remote_host, remote_port, transport):
    # this is a little convoluted, but lets me configure things for the Handler
    # object.  (SocketServer doesn't give Handlers any way to access the outer
    # server normally.)
    class SubHander(Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport

    #ForwardServer(("", local_port), SubHander).serve_forever()
    fserver = ForwardServer(("", local_port), SubHander)
    server_thread = threading.Thread(target=fserver.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return fserver


