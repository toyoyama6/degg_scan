#!/usr/bin/env python
#
# Test ICM firmware reprogramming sequence (using simulator). Test
# bad MCS file detection as well.
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

@pytest.fixture
def filename(pytestconfig):
    return pytestconfig.getoption("filename")

def test_reprogram(icmTestFixture, filename):

    # Create the ZMQ helper class
    icm = ICMNet(TEST_CMDPORT)
    
    # Check that we have devices
    reply = icm.request("devlist")
    assert reply["value"] == [2, 4, 6, 8]

    # The MCS file is an external resource fetched by CMake
    mcs_file = filename
    print("MCS file: ",mcs_file)
    # mcs_file = os.path.join(os.path.dirname(__file__), "../resources/test_fw_good.mcs.gz")
    
    # "Reprogram" the simulator
    dev = 4
    image = 3
    script = os.path.join(os.path.dirname(__file__), "../scripts", "icm_reprogram.py")
    p = subprocess.run("%s -p %d -w %d -i %d -f %s" % (script, TEST_CMDPORT, dev, image, mcs_file),
                       shell=True,
                       capture_output=True)
    output = p.stdout.decode("utf-8")
    
    assert "Firmware check OK" in output
    assert "Reprogramming device %d slot %d" % (dev, image) in output
    assert "Ready for data" in output
    assert "Sending SYNC lines" in output
    assert output.endswith("Done.\n")
    assert not ("error" in output.lower())
    
    # Try using a bad .mcs file, make sure it doesn't work
    bad_mcs_file = os.path.join(os.path.dirname(__file__), "../resources/test_fw_bad.mcs")
    subprocess.run("gzcat %s | head -40 > %s" % (mcs_file, bad_mcs_file), shell=True)
    p = subprocess.run("%s -p %d -w %d -i %d -f %s" % (script, TEST_CMDPORT, dev,
                                                       image, bad_mcs_file),
                       shell=True,
                       capture_output=True)
    output = p.stdout.decode("utf-8")
    assert "error" in output.lower()
    os.unlink(bad_mcs_file)
