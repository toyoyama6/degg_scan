"""Access class for ICM EEPROM and mainboard EEPROM."""
# requires Python3

import json
import os
import sys
import time

from icmnet import ICMNet
from icmregs import EEPROM_CTRL, GI_IND, Address as icm_addr, Name as icm_reg

EEPROM_ICM = 'icm'
EEPROM_MAINBOARD = 'mainboard'
CONFIG_SEARCH_PATH = ['.', '/usr/local/etc',
                      os.path.dirname(os.path.realpath(__file__)) + '/etc']
BYTEORDER = 'big'


def _int_or_hex(value) -> int:
    """Convert argument from int or hex string"""
    if isinstance(value, int):
        return value
    elif isinstance(value, str):
        return int(value, 0)
    else:
        raise Exception(f'unknown value {value} type {type(value)}')


class IcmMaximEeprom(object):
    """ICM Driver Maxim 1-Wire EEPROM chips.

    * DS24B33 4Kb EEPROM, used on Upgrade DEgg mainboard
    * DS2431 1024-bit EEPROM, used by Upgrade ICM, and mDOM mainboard

    ICM registers are 16-bit words unless noted.

    The ICM can mirror the selected EEPROM contents to to/from registers.
    Users can access EEPROM data in the mirror registers.
    Mirror registers <-> EEPROM transfers operate on the entire block,
    not individual addresses.
    """

    MAX_READY_POLL_DURATION = 1.0  # s
    READY_POLL_DELAY = 0.1  # s
    REGISTER_MIN = 0x00
    REGISTER_WRITE_MIN = 0x02
    REGISTER_MAX = 0xff
    OFFSET_MIN = 0x00
    OFFSET_WRITE_MIN = 0x04
    OFFSET_MAX = 0x7f

    class EepromConfig(object):
        """EEPROM JSON configuration API"""

        def __init__(self, eeprom=EEPROM_MAINBOARD, config_file=None,
                     quiet=False):
            self.eeprom = eeprom
            self.file = config_file
            self.config = None
            self.quiet = quiet
            if self.file is None:
                file = '%s-%s.json' % ('eeprom', self.eeprom)
                for _dir in CONFIG_SEARCH_PATH:
                    path = '%s/%s' % (_dir, file)
                    if os.path.exists(path):
                        self.file = path
                        break
            if self.file is None:
                raise Exception(f'configuration file {self.file} not found '
                                f'in {CONFIG_SEARCH_PATH}')
            if not self.quiet:
                print(f'using configuration file {self.file}')
            with open(self.file, 'r') as fileHandle:
                try:
                    data = fileHandle.read()
                    self.config = json.loads(data)
                except json.decoder.JSONDecodeError:
                    sys.stderr.write(
                        f'failure reading JSON configuration file '
                        f'{self.file}:\n')
                    raise
            for field in self.config:
                cfg = self.config[field]  # shorthand
                cfg['offset'] = _int_or_hex(cfg['offset'])
                cfg['length'] = _int_or_hex(cfg['length'])

        def find(self, name: str):
            """Find and return configuration for field name"""
            try:
                field = self.config[name]
                return field
            except KeyError:
                return None

        def get(self) -> dict:
            """Return configuration dictionary"""
            return self.config

    def __init__(self, icms: ICMNet, eeprom: str = EEPROM_MAINBOARD,
                 config_file: str = None, debug: bool = False,
                 device: str = None, quiet=False):
        self.icms = icms
        self.debug = debug
        self.device = device
        self.gi_ind = None
        self.quiet = quiet
        if not self.quiet:
            print(f'target EEPROM: {eeprom}')
        self.config = self.EepromConfig(eeprom=eeprom,
                                        config_file=config_file, quiet=quiet)
        if eeprom == EEPROM_MAINBOARD:
            self.eeprom = EEPROM_CTRL.OW_DEV_USR_SELECT_MB
        else:
            self.eeprom = 0x0000

    def _fh_request(self, request: str, exception: bool = True) -> dict:
        """wrapper fieldhub request """
        response = self.icms.request(request)
        if self.debug:
            print(f'-> {request}')
            print(f'<- {response}')
        if exception and response['status'] != 'OK':
            raise Exception(f'{request} {response}')
        return response

    def _read_icm_reg(self, register) -> bytes:
        """Return ICM register value as hex string, e.g. '0x0010'"""
        if isinstance(register, str):
            register = icm_addr[register]
        if register < self.REGISTER_MIN or register > self.REGISTER_MAX:
            raise Exception(f'illegal read register {register}')
        request = f'read {self.device} {register}'
        response = self._fh_request(request)
        return bytes.fromhex(response['value'][2:])  # truncate '0x' prefix

    def _read_eeprom_ctrl(self) -> int:
        """read ICM EEPROM control register"""
        return int.from_bytes(self._read_icm_reg(icm_reg.EEPROM_CTRL),
                              BYTEORDER)

    def _write_icm_reg(self, register, value: bytes):
        """write an ICM register"""
        if isinstance(register, str):
            register = icm_addr[register]
        if register < self.REGISTER_WRITE_MIN or register > self.REGISTER_MAX:
            raise Exception(f'illegal write register {register}')
        word = '0x' + value.hex()
        request = f'write {self.device} {register} {word}'
        self._fh_request(request)

    def _wait_read_ready(self):
        """wait for ICM to load EEPROM scratch registers from NV storage"""
        timeout = time.time() + self.MAX_READY_POLL_DURATION
        while time.time() < timeout:
            if self._read_eeprom_ctrl() & EEPROM_CTRL.OW_DATA_READY_VAL:
                return
            time.sleep(self.READY_POLL_DELAY)  # yield to other FH clients
        raise Exception(
            f'wait read data ready timout > {self.MAX_READY_POLL_DURATION}')

    def _write_eeprom_ctrl(self, value: int):
        """write ICM EEPROM control register"""
        _bytes = value.to_bytes(2, BYTEORDER)
        return self._write_icm_reg(icm_reg.EEPROM_CTRL, _bytes)

    def _load_scratch_from_eeprom(self):
        """load ICM eeprom scratch registers from eeprom NV storage"""
        eeprom_ctrl = self.eeprom | EEPROM_CTRL.READ_EEPROM
        self._write_eeprom_ctrl(eeprom_ctrl)
        self._wait_read_ready()

    def _is_write_enable(self):
        """Test if this ICM FW supports EEPROM writes"""
        if self.gi_ind is None:
            self.gi_ind = int.from_bytes(
                self._read_icm_reg(icm_addr[icm_reg.GI_IND]), BYTEORDER)
        if not self.gi_ind & GI_IND.EEPROM_WRITE_EN_VAL:
            raise Exception('This ICM FW does not support EEPROM writes')

    def _commit_scratch_to_eeprom(self):
        """commit ICM eeprom scratch registers to eeprom NV storage"""
        self._is_write_enable()
        eeprom_ctrl = self.eeprom | EEPROM_CTRL.EEPROM_WRITE
        self._write_eeprom_ctrl(eeprom_ctrl)

    def _write_scratch(self, offset: int, _bytes: bytes):
        """write bytes to  ICM eeprom scratch registers"""
        self._is_write_enable()  # raises exception if not writeable
        if offset < self.OFFSET_WRITE_MIN or offset & 1:
            raise Exception(f'illegal write offset {offset}')
        elif offset + len(_bytes) > self.OFFSET_MAX + 1 or len(_bytes) & 1:
            raise Exception(f'illegal write length')
        if len(_bytes) == 0:
            return
        for offs in range(0, len(_bytes), 2):
            register = self._offset_to_register(offset + offs)
            self._write_icm_reg(register, _bytes[offs:offs + 2])

    def write(self, name: str, value):
        """external write to EEPROM API"""
        field = self.config.find(name)
        if field is None:
            raise Exception(f'unknown field "{name}"')
        if field['format'] == 'string':
            _bytearray = bytearray(value.encode())
            delta = field['length'] - len(value)
            if delta < 0:
                raise Exception(f'write string overflow field')
            if delta > 0:
                _bytearray.extend(delta * b'\x00')  # null pad strings
            _bytes = bytes(_bytearray)
        elif field['format'] == 'integer':
            _bytes = _int_or_hex(value).to_bytes(field['length'], BYTEORDER)
        else:
            raise Exception(f'write {name} unknown format{field["format"]}')
        if len(_bytes) > field['length']:
            raise Exception(f'write overflow field')
        self._load_scratch_from_eeprom()
        self._write_scratch(field['offset'], _bytes)
        self._commit_scratch_to_eeprom()

    def clear(self):
        """clear EEPROM scratch and NV storage"""
        start = self._register_to_offset(icm_addr[icm_reg.EEPROM_START])
        end = self._register_to_offset(icm_addr[icm_reg.EEPROM_END] + 1)
        _bytes = b'\0' * (end - start)
        self._write_scratch(start, _bytes)
        self._commit_scratch_to_eeprom()

    def write_test_pattern(self):
        """Write a test pattern to EEPROM scratch and NV storage"""
        _bytearray = bytearray()
        start = self._register_to_offset(icm_addr[icm_reg.EEPROM_START])
        end = self._register_to_offset(icm_addr[icm_reg.EEPROM_END] + 1)
        for offset in range(start, end):
            _bytearray += offset.to_bytes(1, BYTEORDER)
        self._write_scratch(start, _bytearray)
        self._commit_scratch_to_eeprom()

    @staticmethod
    def _display(offset: int, _bytes: bytes, row_size: int = 16):
        """Display contents first in hex, then as strings"""
        num_rows = int(len(_bytes) / row_size)
        start = 0
        end = row_size
        if end > len(_bytes):
            end = len(_bytes)
        for row in range(num_rows):
            print('0x%02x\t' % offset, end='')
            # {row_size}')
            for byte in _bytes[start:end]:
                print('%02x ' % byte, end='')  # print binary
            print('\t', end='')
            for byte in _bytes[start:end]:
                if 0x20 <= byte <= 0x7e:
                    print(f'{chr(byte)} ', end='')  # printable ASCII
                else:
                    print('. ', end='')

            offset += row_size
            start += row_size
            if start > len(_bytes):
                break
            end += row_size
            if end > len(_bytes):
                end = len(_bytes)
            print('')

    @staticmethod
    def _offset_to_register(offset: int) -> int:
        """convert an EEPROM byte offset to scratch register address"""
        register = int(offset / 2)  # 2 bytes per ICM EEPROM scratch register
        register += icm_addr[icm_reg.EEPROM_DATA]  # 1st scratch register
        return register

    @staticmethod
    def _register_to_offset(register: int) -> int:
        """convert an EEPROM scratch register address to offset"""
        offset = register - icm_addr[
            icm_reg.EEPROM_DATA]  # 1st scratch register
        offset *= 2  # 2 bytes per ICM EEPROM scratch register
        return offset

    def _read_scratch(self, offset: int, length: int) -> bytes:
        """read from EEPROM scratch registers"""
        if offset < self.OFFSET_MIN or offset & 1:
            raise Exception(f'illegal read offset {offset}')
        elif offset + length > self.OFFSET_MAX + 1 or length & 1:
            raise Exception(f'illegal read length')
        if length == 0:
            return b''
        scratch = bytearray()
        for offs2 in range(offset, offset + length, 2):
            register = self._offset_to_register(offs2)
            scratch.extend(self._read_icm_reg(register))
        if offset == 0 and length == 4:
            # hack for unusual byte order of scratch field
            scratch = bytearray(scratch[2:4] + scratch[0:2])
        return bytes(scratch)

    def read(self, name: str):
        """external read from EEPROM API"""
        self._load_scratch_from_eeprom()
        field = self.config.find(name)
        if field is None:
            raise Exception(f'unknown field "{name}"')
        _bytes = self._read_scratch(field['offset'], field['length'])
        if field['format'] == 'string':
            # TODO test if value < length
            for i in range(len(_bytes)):
                if 0x20 > _bytes[i] > 0x7e:
                    if i - 1 <= 0:
                        return ''
                    _bytes = _bytes[0:i - 1]  # truncate non printable chars
            return _bytes.decode()
        elif field['format'] == 'integer':
            value = int.from_bytes(_bytes, BYTEORDER)
            return value
        else:
            raise Exception(f'read {name} unknown format{field["format"]}')

    def dump(self, offset: int = 0, length: int = 128):
        """read EEPROM NV storage to scratch then display to stdout"""
        self._load_scratch_from_eeprom()
        scratch = self._read_scratch(offset, length)
        self._display(offset, scratch)

    def list(self):
        config = self.config.get()
        for field in sorted(config.keys(), key=lambda f: config[f]['offset']):
            print(f'{field}')
            print(f'\tdescription: {config[field]["description"]}')
            print(f'\toffset: {config[field]["offset"]}')
            fmt = config[field]["format"]
            if fmt == 'integer':
                fmt = 'unsigned integer'     # TODO clarify in documenation
            print(f'\tformat: {fmt}')
            print(f'\tlength: {config[field]["length"]}')
            value = self.read(field)
            if isinstance(value, str):
                print(f'\tvalue: "{value}"')
            else:
                print(f'\tvalue: {value}')
