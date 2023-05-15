# -*- coding: utf-8 -*-
# Adaptation of Thomas' comms_testing.py script
import time
import sys
import click
import serial
import serial.tools.list_ports
import struct
import numpy as np

MFH_ICM_IDS = {
    '01282405000441153418545': 'Bottom MFH, Wire pair 0',
    '012824080044115357845': 'Bottom MFH, Wire pair 1',
    '012824013000441141911145': 'Top MFH, Wire pair 0',
    # '01282405000441153418545': 'Top MFH, Wire pair 0',
    '012824061004411542445': 'Top MFH, Wire pair 1',
}


class comms_testing_device(object):
    def __init__(self, PORT="COM10", baud_rate=3000000, rtscts=True, timeout=0, writeTimeout=0, address=0x7):
        portList = [comport.device for comport in serial.tools.list_ports.comports()]
        self.s = 0
        self.pck_ct = 0
        self.addr = address
        try:
            self.s = serial.Serial(PORT, baud_rate, rtscts=rtscts, timeout=timeout, writeTimeout=writeTimeout)
            self.s.flushInput()
        except:
            print("Unable to connect to FPGA.")
            sys.exit()

    def close(self):
        self.s.close()

    def flush_Buffer(self):
        self.s.flushInput()

    def resetPCK_CT(self):
        self.pck_ct=0

    def unpackData(buf, structure):
        package=[]
        unpackStruct=['B','H', '>L', 'Q']
        counter=0
        for i in structure:
                k= struct.unpack(unpackStruct[int(np.log2(i))], buf[counter:counter+i])
                package.append(int(k[0]))
                counter+=i
        return package

    def write_reg(self, module_addr, reg_addr, length, data):
        # Will write data to a register in the reconfiguration module
        # Inputs:
        # address: int register address
        # value: int Value to be written
        # Return: none
        self.pck_ct+=1

        if isinstance(reg_addr,int):
            if ((reg_addr >= 0x00) and (reg_addr <= 0xFF)):
                reg_addr_int = reg_addr
            else:
                print("Register Map out of Range")
                return -2
        elif isinstance(reg_addr,str):
            try:
                reg_addr_int = self.rgmp[reg_addr]
            except:
                print("Invalid Register Name")
                return -3
        else :
            print("Invalid Register Address Type")
            return -4

        read_cmd = struct.pack('>B', 0x9)
        tx_length =  struct.pack('>H', length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr_int)

        transmission = read_cmd + tx_length + mod_dest_add + reg_dest_add
        if(length>5):
            for i in range(length-5):
                data2 = struct.pack('>B', data[i])
                transmission+=data2

        self.s.write(transmission)
        return -1


    def read_reg(self, module_addr, reg_addr, rx_length, pr=1):
        # Will read data from a register in the reconfiguration module
        # Inputs:
        # address: int register address
        # Return: int register content // -1 when read failed.
        self.pck_ct+=1
        if isinstance(reg_addr,int):
            if ((reg_addr >= 0x00) and (reg_addr <= 0xFF)):
                reg_addr_int = reg_addr
            else:
                print("Register Map out of Range")
                return -2
        elif isinstance(reg_addr,str):
            print("Invalid Register Name")
            return -3
        else:
            print("Invalid Register Address Type")
            return -4

        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', rx_length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr_int)

        transmission = read_cmd + length + mod_dest_add + reg_dest_add

        self.s.write(transmission)
        time.sleep(0.01)
        bytes_to_read=0
        count=0
        while(bytes_to_read<4 and count<100):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.01)

        if(bytes_to_read>0):
            bytes_to_read = self.s.inWaiting()
            line=self.s.read(bytes_to_read)
            data_package = ( comms_testing_device.unpackData(line, [1]*bytes_to_read) )
            if(pr==1):
                print( (data_package) )
            return(data_package)
        else:
            print("Unexpected - Bytes in read buffer:",bytes_to_read)
            return [-1]

    def read_reg_no_resp(self, module_addr, reg_addr, rx_length, pr=1):
        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', rx_length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)

        transmission = read_cmd + length + mod_dest_add + reg_dest_add

        self.s.write(transmission)

    def write_spi_bytes(self, value):
        # Will write several bytes of data to the serial port
        # Inputs:
        # value: multiple data bytes to be written
        # Return: none
        self.pck_ct+=1
        self.s.write(value)

    def read_uart(self, pr=0):
        bytes_to_read = self.s.inWaiting()

        if(bytes_to_read>1):
            time.sleep(0.01)
            line=self.s.read(bytes_to_read)
            if(pr==1):
                print(list(line))
            return(list(line))
        else:
            return [0]


def compare_return_values(func):
    def wrapper(*args, **kwargs):
        ret, ret_, dev = func(*args, **kwargs)
        if ret != ret_:
            print(f'Readback from {func.__name__} not expected! '
                  f'Got {ret}, expected {ret_} on device {dev}.')
        return ret
    return wrapper


class ICMController():
    def __init__(self, port, connected_devices, sleep_time=0.5):
        self.port = port
        self.connected_devices = connected_devices
        self.ser = comms_testing_device(port)
        self.sleep_time = sleep_time
        print(f'Created ICMController object for: {port}')

    def close(self):
        self.ser.close()

    def read_firmware_version(self, device):
        ret = self.ser.read_reg(device, 0xff, 6, pr=0)
        time.sleep(self.sleep_time)
        if ret[0] == -1:
            raise IOError(f'While Reading the FW for device {device}, returned -1!')
        return ret

    # @compare_return_values
    def set_multiboot_image_id(self, device, image_id):
        value = [0, image_id]
        self.ser.write_reg(device, 0x12, 7, value)
        time.sleep(self.sleep_time)
        # ret = self.ser.read_reg(device, 0x12, 6, pr=0)[-2:]
        # return ret, value

    def reboot_device(self, device):
        ret = self.ser.write_reg(device, 0x10, 7, [0, 0xab])
        time.sleep(self.sleep_time)
        return ret

    @compare_return_values
    def enable_token_passing(self, device):
        value = [0x80, 10]
        self.ser.write_reg(device, 0x34, 7, value)
        time.sleep(self.sleep_time)
        ret = self.ser.read_reg(device, 0x34, 6, pr=0)[-2:]
        return ret, value, device

    @compare_return_values
    def disable_token_passing(self, device):
        value = [0, 10]
        self.ser.write_reg(device, 0x34, 7, value)
        time.sleep(self.sleep_time)
        ret = self.ser.read_reg(device, 0x34, 6, pr=0)[-2:]
        return ret, value, device

    @compare_return_values
    def set_icm_dac_amp(self, device, amp):
        self.ser.write_reg(device, 0xed, 7, [0, amp])
        time.sleep(self.sleep_time)
        ret = self.ser.read_reg(device, 0xed, 6, pr=0)[-1]
        return ret, amp, device

    @compare_return_values
    def set_icm_adc_thresh(self, device, thresh):
        self.ser.write_reg(device, 0xee, 7, thresh)
        time.sleep(self.sleep_time)
        ret = self.ser.read_reg(device, 0xee, 6, pr=0)[-2:]
        return ret, thresh, device

    def get_image_id(self, device):
        ret = self.ser.read_reg(device, 0xfe, 6, pr=0)
        time.sleep(self.sleep_time)
        return ret

    @compare_return_values
    def terminate_cable(self, device):
        term = 0x14
        self.ser.write_reg(device, 0x0, 7, [0x0, term])
        time.sleep(self.sleep_time)
        ret = self.ser.read_reg(device, 0x0, 6, pr=0)[-1]
        return ret, term, device

    def read_available_devices(self):
        ret = self.ser.read_reg(8, 0x3, 6, pr=0)[5]
        bin_rep = bin(ret).partition('0b')[-1].zfill(4)[::-1]
        return bin_rep

    def identify_mfh_icm(self, ignore=False):
        if ignore == True:
            return
        else:
            ret = self.ser.read_reg(8, 0xf0, 12, pr=0)
            ret = ''.join(map(str, ret))
            print(f'Running on {MFH_ICM_IDS[ret]}')

    def setup_icms(self, mfh_image_id, inice_image_id, ignore=False):
        print('Setting up ICMs.')
        pre_ver = self.read_firmware_version(8)
        self.set_multiboot_image_id(8, mfh_image_id)
        self.reboot_device(8)
        post_ver = self.read_firmware_version(8)
        print(
            f'Rebooted MFH ICM from version {pre_ver[-1]} to {post_ver[-1]}')

        #0x454e is on, 0x6469 is off
        #self.ser.write_reg(8, 0x33, 2, [0x0, 0x454e])
        #self.ser.write_reg(8, 0x33, 2, 0x6469)

        print(f'Found devices: {self.read_available_devices()}')

        self.identify_mfh_icm(ignore=ignore)
        self.set_icm_dac_amp(8, 0x50)
        print(f'Found devices: {self.read_available_devices()}')

        dac_amp = 0x1c
        while self.read_available_devices() == '0000':
            self.disable_token_passing(8)
            self.set_icm_dac_amp(8, dac_amp)
            self.set_icm_adc_thresh(8, [1, 0])

            for device in self.connected_devices:
                self.set_multiboot_image_id(device, inice_image_id)
                self.reboot_device(device)

            time.sleep(3)
            self.enable_token_passing(8)
            print(f'Found devices: {self.read_available_devices()} '
                  f'at MFH DAC amplitude {dac_amp}')
            dac_amp += 5
            if dac_amp >= 80:
                print('Reached dac_amp = 80, stopping...')
                break

        for device in self.connected_devices:
            post_ver = self.read_firmware_version(device)
            print(
                f'Rebooted Dev{device} ICM to version '
                f'{post_ver[-1]}\n')
            if post_ver[-1] != 52:
                self.disable_token_passing(8)
                self.set_multiboot_image_id(device, inice_image_id)
                self.reboot_device(device)
                time.sleep(1)
                self.enable_token_passing(8)
                post_ver = self.read_firmware_version(device)
                print(
                    f'Rebooted Dev{device} ICM to version '
                    f'{post_ver[-1]}\n')
            # print(self.get_image_id(device))

        print(f'Found devices: {self.read_available_devices()}')
        print('Terminating cables for each connected device!')
        for device in self.connected_devices:
            self.terminate_cable(device)
            self.set_icm_adc_thresh(device, [1, 0])

        time.sleep(1)
        print(f'Found devices: {self.read_available_devices()}')

    def setup_mfh_icm(self, mfh_image_id,  ignore=False):
        print('Setting up MFH ICMs.')
        pre_ver = self.read_firmware_version(8)
        self.set_multiboot_image_id(8, mfh_image_id)
        self.reboot_device(8)
        post_ver = self.read_firmware_version(8)
        print(
            f'Rebooted MFH ICM from version {pre_ver[-1]} to {post_ver[-1]}')

    def setup_inice_icm(self, inice_image_id, ignore=False):
        print(f'Found devices: {self.read_available_devices()}')

        self.identify_mfh_icm(ignore=ignore)
        self.set_icm_dac_amp(8, 0x50)
        print(f'Found devices: {self.read_available_devices()}')

        dac_amp = 0x1c
        while self.read_available_devices() == '0000':
            self.disable_token_passing(8)
            self.set_icm_dac_amp(8, dac_amp)
            self.set_icm_adc_thresh(8, [1, 0])

            for device in self.connected_devices:
                self.set_multiboot_image_id(device, inice_image_id)
                self.reboot_device(device)

            time.sleep(3)
            self.enable_token_passing(8)
            print(f'Found devices: {self.read_available_devices()} '
                  f'at MFH DAC amplitude {dac_amp}')
            dac_amp += 5
            if dac_amp >= 80:
                print('Reached dac_amp = 80, stopping...')
                break

        for device in self.connected_devices:
            post_ver = self.read_firmware_version(device)
            print(
                f'Rebooted Dev{device} ICM to version '
                f'{post_ver[-1]}\n')
            if post_ver[-1] != 52:
                self.disable_token_passing(8)
                self.set_multiboot_image_id(device, inice_image_id)
                self.reboot_device(device)
                time.sleep(1)
                self.enable_token_passing(8)
                post_ver = self.read_firmware_version(device)
                print(
                    f'Rebooted Dev{device} ICM to version '
                    f'{post_ver[-1]}\n')
            # print(self.get_image_id(device))

        print(f'Found devices: {self.read_available_devices()}')
        print('Terminating cables for each connected device!')
        for device in self.connected_devices:
            self.terminate_cable(device)
            self.set_icm_adc_thresh(device, [1, 0])

        time.sleep(1)
        print(f'Found devices: {self.read_available_devices()}')


@click.command()
@click.argument('port')
@click.option('-mfh_image_id', '-m', default=1, type=int)
@click.option('-inice_image_id', '-i', default=1, type=int)
def main(port, mfh_image_id, inice_image_id):
    conn_devs = [0, 1, 2, 3]

    icm_ctrl = ICMController(port, conn_devs, sleep_time=1.5)
    icm_ctrl.setup_icms(mfh_image_id, inice_image_id)
    icm_ctrl.close()


if __name__ == '__main__':
    main()
