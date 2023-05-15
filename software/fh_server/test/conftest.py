#
# Pytest configuration file
#
def pytest_addoption(parser):
    parser.addoption("--filename", action="store", default="../resources/test_fw_good.mcs.gz")
