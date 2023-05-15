#!/usr/bin/env python
#
# Test that ZMQ port is responsive during startup
# (https://github.com/WIPACrepo/fh_server/issues/148)
#

import sys
import os
import pytest

# Fix up import path automatically
sys.path.append(os.path.join(os.path.dirname(__file__), "../scripts"))
from icmnet import ICMNet

from icm_tester import ICMSimTester

TEST_CMDPORT = 9000

@pytest.fixture
def icmTestFixture():
    # Before test - create resource
    icmTester = ICMSimTester(TEST_CMDPORT)
    yield icmTester
    # After test - remove resource
    icmTester.finish()

def test_zmq_startup(icmTestFixture):

    # Create the ZMQ helper class
    icm = ICMNet(TEST_CMDPORT)
    
    # Check that we have devices
    reply = icm.request("devlist")
    assert reply["value"] == [2, 4, 6, 8]

    # Drop device 2 from the simulator
    reply = icm.request("write 2 0x80 1")
    assert reply["status"] == "OK"
    
    # Issue a probe to start the reinit
    reply = icm.request("probe")
    assert reply["status"] == "OK"

    # Try a remote read from a different device
    # The probe will be taking a long time to drop device 2
    reply = icm.request("read 4 icm_id")
    assert reply["status"] != "?NOREPLY"
    assert reply["status"] == "?NOTREADY"
