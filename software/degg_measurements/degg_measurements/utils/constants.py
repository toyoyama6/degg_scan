import configparser
import os
import json

config = configparser.ConfigParser()
config.read(os.path.join(
    os.path.dirname(__file__), 'configs/paths.ini'))

_obj = open(os.path.join(os.path.dirname(__file__), "configs","version_list.json") ,'rt' )
_version_no = json.load(_obj)
_obj.close()

class SOFTWARE_VERSIONS:
    ICEBOOT = _version_no["IcebootVersion"]
    FPGA = _version_no["fpgaVersion"]

class MFH_SETUP_CONSTANTS:
    n_wire_pairs = int(config.get('MFH_CONSTANTS', 'N_WIRE_PAIRS'))
    in_ice_devices_per_wire_pair = int(config.get(
        'MFH_CONSTANTS', 'IN_ICE_DEVICES_PER_WIRE_PAIR'
    ))


class CALIBRATION_FACTORS:
    adc_to_volts = 0.075e-3
    adc_to_volts_rev3 = 0.089e-3
    fpga_clock_to_s = 1. / 240e6
    front_end_impedance_in_ohm = 36.96
    mainboard_peak_compression_factor = 0.462

