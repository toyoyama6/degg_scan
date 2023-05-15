#!/usr/bin/env python
#
# Test that a re-probe after dropping all devices
# Does not loop forever or hang.
# (https://github.com/WIPACrepo/fh_server/issues/149)
#

import sys
import os
import time
import pytest

# Fix up import path automatically
sys.path.append(os.path.join(os.path.dirname(__file__), "../scripts"))
from icmnet import ICMNet

from icm_tester import ICMSimTester

TEST_CMDPORT = 9000
TEST_TIMEOUT_SEC = 30

@pytest.fixture
def icmTestFixture():
    # Before test - create resource
    icmTester = ICMSimTester(TEST_CMDPORT)
    yield icmTester
    # After test - remove resource
    icmTester.finish()
    
def test_all_dropped(icmTestFixture):

    # Create the ZMQ helper class
    icm = ICMNet(TEST_CMDPORT)
    
    # Check that we have devices
    reply = icm.request("devlist")
    devlist = reply["value"]
    assert devlist == [2, 4, 6, 8]

    # Drop all remote devices from the simulator
    for dev in [d for d in devlist if d != 8]:        
        reply = icm.request("write %d 0x80 1" % dev)
        assert reply["status"] == "OK"

    # Probe / reinit
    reply = icm.request("probe")
    assert reply["status"] == "OK"

    # Check to make sure it comes back
    start_time = time.time()
    devlist = None
    while ((time.time() - start_time < TEST_TIMEOUT_SEC) and not devlist):
        reply = icm.request("devlist")
        assert (reply["status"] == "?NOTREADY") or (reply["status"] == "OK")
        if reply["status"] == "?NOTREADY":
            time.sleep(2)
        else:
            devlist = reply["value"]

    assert devlist == [8]

