#!/usr/bin/env python
#
# Test that the timeout counter is reset when a device
# starts talking again.
# (https://github.com/WIPACrepo/fh_server/issues/152)
#

import sys
import os
import pytest

# Fix up import path automatically
sys.path.append(os.path.join(os.path.dirname(__file__), "../scripts"))
from icmnet import ICMNet

from icm_tester import ICMSimTester

TEST_CMDPORT = 9876

@pytest.fixture
def icmTestFixture():
    # Before test - create resource
    icmTester = ICMSimTester(TEST_CMDPORT)
    yield icmTester
    # After test - remove resource
    icmTester.finish()

def test_timeout_counter(icmTestFixture):

    # Create the ZMQ helper class
    icm = ICMNet(TEST_CMDPORT)
    
    # Check that we have devices
    reply = icm.request("devlist")
    assert reply["value"] == [2, 4, 6, 8]

    # Drop device 2 from the simulator
    reply = icm.request("write 2 0x80 1")
    assert reply["status"] == "OK"
        
    # Check for timeout
    reply = icm.request("read 2 icm_id")    
    assert reply["status"] == "?TIMEOUT"

    # Check for timeout
    reply = icm.request("read 2 icm_id")    
    assert reply["status"] == "?TIMEOUT"

    # Now undrop and do a successful read
    reply = icm.request("write 2 0x80 0")
    assert reply["status"] == "OK"
    reply = icm.request("read 2 icm_id")    
    assert reply["value"] == "0x2021222324252627"

    # Now drop again
    reply = icm.request("write 2 0x80 1")
    assert reply["status"] == "OK"
        
    # Check for timeout
    reply = icm.request("read 2 icm_id")    
    assert reply["status"] == "?TIMEOUT"

    # Check for timeout, *not* NOCONN
    # This fails for domnet <= 1.4.7
    # NB: in domnet 1.4.8 and above this doesn't exactly
    # test the counter reset, but OK
    reply = icm.request("read 2 icm_id")    
    assert reply["status"] == "?TIMEOUT"    
