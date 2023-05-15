#!/usr/bin/env python
#
# Test that double-closing a device socket doesn't
# crash domnet
# (https://github.com/WIPACrepo/fh_server/issues/159)
#

import sys
import os
import time
import socket
import subprocess
import pytest

# Fix up import path automatically
sys.path.append(os.path.join(os.path.dirname(__file__), "../scripts"))
from icmnet import ICMNet

from icm_tester import ICMSimTester

TEST_CMDPORT = 9876

@pytest.fixture
def icmTestFixture():
    # Before test - create resource
    icmTester = ICMSimTester(TEST_CMDPORT, devsocks=False)
    yield icmTester
    # After test - remove resource
    icmTester.finish()
            
def test_double_close(icmTestFixture):

    # Create the ZMQ helper class
    icm = ICMNet(TEST_CMDPORT)
    
    # Check that we have devices
    reply = icm.request("devlist")
    assert reply["value"] == [2, 4, 6, 8]

    # Check that we can connect to a device port
    dev = 2
    devport = TEST_CMDPORT-1000+dev
    devhost = "localhost"
    devsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    devsock.settimeout(1)
    devsock.connect((devhost, devport))

    # Check for simulator echo
    msg = "This is a test of the emergency broadcasting system.".encode('utf-8')
    devsock.send(msg)

    chunks = []
    bytes_recd = 0
    while bytes_recd < len(msg):
        chunk = devsock.recv(min(len(msg) - bytes_recd, 2048))
        assert chunk != b''
        chunks.append(chunk)
        bytes_recd = bytes_recd + len(chunk)

    msg_recd = b''.join(chunks)
    assert msg == msg_recd

    # Now close the socket with the command
    reply = icm.request("disconnect %d" % dev)
    assert reply["status"] == "OK"
    
    # Check that it closed
    devsock.send(msg)
    chunk = devsock.recv(1)    
    assert chunk == b''

    devsock.close()
    time.sleep(0.5)
    
    # Now close it again
    reply = icm.request("disconnect %d" % dev)
    # This will return "?NOREPLY" if domnet died
    # This doesn't actually die even with the bug
    # Maybe because file handle doesn't go away?
    # Couldn't replicate with subprocess, threading, system call
    assert reply["status"] == "OK"

    # Try again by running helper script
    dev = 4
    devport = TEST_CMDPORT-1000+dev
    devsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    devsock.settimeout(1)    
    devsock.connect((devhost, devport))

    script = os.path.join(os.path.dirname(__file__), "../scripts", "socket_disconnect.py")
    p = subprocess.run("%s -p %d -w %d" % (script, TEST_CMDPORT, dev), shell=True, capture_output=True)
    assert p.stdout == b'4: OK\n'

    p = subprocess.run("%s -p %d -w %d" % (script, TEST_CMDPORT, dev), shell=True, capture_output=True)
    assert p.stdout == b'4: OK\n'
    
