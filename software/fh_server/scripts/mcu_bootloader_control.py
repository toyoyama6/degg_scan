import select
import socket
import fcntl
import os
import time

from icmnet import ICMNet, ICMError
from st_uart_bootloader_client import ST_UART_BootloaderClient

class MCU_Bootloader_Control():

    MCU_FLASH_SIZE = 2097152
    MINIMUM_FW_VERSION = 0x1535

    def __init__(self, host, wp_addr, cmd_port):
        self.host = host
        self.wp_addr = wp_addr
        self.cmd_port = cmd_port
        self.dev_port = cmd_port-1000+int(wp_addr)
        # Command port connection
        self.icm = ICMNet(self.cmd_port, self.host)
        # Device port connection
        self.ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ssocket.connect((self.host, self.dev_port))
        fcntl.fcntl(self.ssocket, fcntl.F_SETFL, os.O_NONBLOCK)
        # Bootloader client
        self.bootloader_client = ST_UART_BootloaderClient(self.send_n, self.read_n)
        
    def read_next(self, n_bytes, timeout):
        rdy = select.select([self.ssocket.fileno()], [], [], timeout)
        if rdy[0]:
            recv_bytes = self.ssocket.recv(n_bytes)
            return recv_bytes
        else:
            raise IOError('Timeout!')

    def read_n(self, n_bytes, timeout):
        buf = bytearray()
        while len(buf) < n_bytes:
            buf.extend(self.read_next(n_bytes - len(buf), timeout))
        return buf
    
    def send_next(self, data, timeout):
        rdy = select.select([], [self.ssocket.fileno()], [], timeout)
        if rdy[1]:
            send_bytes = self.ssocket.send(data)
            return send_bytes
        else:
            raise IOError('Timeout!')

    def send_n(self, data, timeout):
        data = bytearray(data)
        while len(data) > 0:
            cnt = self.send_next(data, timeout)
            data = data[cnt:]

    def start(self):
        # Set up the MCU for bootloader mode by
        #  - setting the MCU_BOOT pin and switching the UART mode
        #  - resetting the MCU
        #  - performing a comms reset just in case
        
        # Check the firmware version first
        reply = self.icm.request("read %d FW_VERS" % self.wp_addr)
        if (reply['status'] == "OK") and ("value" in reply):
            fw_val = int(reply['value'], 16)
            if fw_val < MCU_Bootloader_Control.MINIMUM_FW_VERSION:
                raise ICMError("Firmware version 0x%04x too low, 0x%04x required" % \
                                   (fw_val, MCU_Bootloader_Control.MINIMUM_FW_VERSION))
        else:
            raise ICMError("could not get firmware version: %s" % reply['status'])

        reply = self.icm.request("mcu_boot_mode_enable %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])

        reply = self.icm.request("mcu_reset %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])
        time.sleep(0.5)

        reply = self.icm.request("mcu_reset_n %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])
        time.sleep(0.5)

        reply = self.icm.request("comm_reset %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])

        # Enter the special bootloader reprogram mode        
        self.bootloader_client.bootloaderInit()

    def program(self, filename):
        # Read the file
        with open(filename, mode='rb') as f:
            data = f.read()

        # Check that it looks sane
        if (len(data) == 0) or (len(data) > MCU_Bootloader_Control.MCU_FLASH_SIZE):
            raise Exception("bad file length (%dB)" % len(data))
        
        # Now program the MCU bootloader
        self.bootloader_client.bootloaderProgramBootImage(data)

    def finish(self):
        reply = self.icm.request("mcu_reconfig_reset %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])
        
        reply = self.icm.request("mcu_reset %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])
        time.sleep(0.5)

        reply = self.icm.request("mcu_reset_n %d" % self.wp_addr)
        if reply["status"] != "OK":
            raise ICMError(reply["status"])
        time.sleep(0.5)        
