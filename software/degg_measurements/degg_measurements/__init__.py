import configparser
import os

config = configparser.ConfigParser()
config.read(os.path.join(__path__[0], 'utils/configs/paths.ini'))

RUN_DIR = config.get('DIRECTORIES', 'RUN_DIR')
DATA_DIR = config.get('DIRECTORIES', 'DATA_DIR')
REMOTE_DATA_DIR=config.get('DIRECTORIES', 'REMOTE_DATA_DIR')
DB_JSON_PATH = os.path.join(__path__[0], 'analysis',
                            'database_jsons')

##by-path
MFH_PATH00 = config.get('DEVICES', 'MFH_PATH00')
MFH_PATH01 = config.get('DEVICES', 'MFH_PATH01')
MFH_PATH10 = config.get('DEVICES', 'MFH_PATH10')
MFH_PATH11 = config.get('DEVICES', 'MFH_PATH11')
MFH_PATH20 = config.get('DEVICES', 'MFH_PATH20')
MFH_PATH21 = config.get('DEVICES', 'MFH_PATH21')
##by-id

IGNORE_LIST = config.get('FILES', 'DEGG_IGNORE_LIST')

USB_BAN_LIST = config.get('DEVICES', 'USB_BAN_LIST')

STF_PATH = config.get('EXTERNAL_SOFTWARE', 'STF')
FH_SERVER_SCRIPTS = config.get('EXTERNAL_SOFTWARE', 'FH_SERVER_SCRIPTS')
MCU_DEV_PATH = config.get('EXTERNAL_SOFTWARE', 'STM32_WORKSPACE')

FW_PATH = config.get('FILES', 'DEGG_FPGA_FIRMWARE_FILE')

from . import utils
from . import monitoring

__all__ = ('utils', 'monitoring')

