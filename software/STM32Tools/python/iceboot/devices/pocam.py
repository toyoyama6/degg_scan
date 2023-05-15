import time

import numpy as np

from .unmodified_mmb import UnmodifiedMMB


class POCAM(UnmodifiedMMB):
    def __init__(self, comms, **kwargs):
        super().__init__(comms, **kwargs)
        self.symbolic = {
            'ib': 'Interface Board',
            'db': 'Digital Board',
            'lmg1': 'DC/DC LMG HV1',
            'lmg2': 'DC/DC LMG HV2',
            'sipm1': 'DC/DC SiPM HV1',
            'sipm2': 'DC/DC SiPM HV2',
            'kapu1': 'DC/DC Kapustinski HV1',
            'kapu2': 'DC/DC Kapustinski HV2',
            'opamp': '+5V for Photodiode readout',
            'timing': '+5V for LMG',
        }
        self.branch = {
            'db_33': 'Digital Board 3.3V',
            'db_18': 'Digital Board 1.8V',
            'opamps': '+5V PD opamp',
            'lmg': '+5V DC/DC HV LMG',
            'sipm': '+5V DC/DC HV SiPM',
            'kapu': '+5V DC/DC HV Kapustinski',
            'timing': '+5V LMG',
        }
        self.spi = {
            '0': 'Interface board FPGA',
            '1': 'Digital board prime FPGA',
            '2': 'Digital board minor FPGA',
            '3': 'Digital board prime + minor FPGA (broadcast, write-only)'
        }
        self.channel = {
            'kapu1': 'HV1 Kapustinski',
            'kapu2': 'HV2 Kapustinksi',
            'lmg1': 'HV1 LMG',
            'lmg2': 'HV2 LMG',
            'sipm1': 'HV1 SiPM',
            'sipm2': 'HV2 SiPM',
            'mmb_33': '3.3V Mini Main Board',
            'mmb_18': '1.8V Mini Main Board',
        }
        self.hv = {
            'lmg1': 'HV1 LMG',
            'lmg2': 'HV2 LMG',
            'sipm1': 'HV1 SiPM',
            'sipm2': 'HV2 SiPM',
            'kapu1': 'HV1 Kapustinski',
            'kapu2': 'Hv2 Kapustinksi',
        }
        self.sensor = {
            's_generic': 'Slave Analog Board',
            's_sipm': 'Slave Analog Board SiPM',
            's_led': 'Slave Analog Board LED',
            'unused': 'guess what',
            'm_generic': 'Master Analog Board',
            'm_sipm': 'Master Analog Board SiPM',
            'm_led': 'Master Analog Board LED',
            'ib': 'Interface Board',
        }
        self.fpga = {
            'ib': 'Interface FPGA',
            'dbm': 'Digital Master FPGA',
            'dbs': 'Digital Slave FPG',
        }
        self.flasher = {
            'f1': ['kapu1', '', '',
                   'Kapustinski HV 1, 405nm, fast'],
            'f2': ['kapu2', '', '',
                   'Kapustinski HV 2, 405nm, fast'],
            'f3': ['kapu1', '', '',
                   'Kapustinski HV 1, 405nm, default'],
            'f4': ['kapu2', '', '',
                   'Kapustinski HV 2, 405nm, default'],
            'f5': ['kapu1', '', '',
                   'Kapustinski HV 1, 465nm, fast'],
            'f6': ['kapu2', '', '',
                   'Kapustinski HV 2, 465nm, fast'],
            'f7': ['kapu1', '', '',
                   'Kapustinski HV 1, 465nm, default'],
            'f8': ['kapu2', '', '',
                   'Kapustinski HV 2, 465nm, default'],
            'f9': ['lmg1', '', '',
                   'LMG HV 1, 365nm'],
            'f10': ['lmg2', '', '',
                    'LMG HV 2, 365nm'],
            'f11': ['lmg1', '', '',
                    'LMG HV 1, 405nm'],
            'f12': ['lmg2', '', '',
                    'LMG HV 2, 405nm'],
            'f13': ['lmg1', '', '',
                    'LMG HV 1, 450nm'],
            'f14': ['lmg2', '', '',
                    'LMG HV 2, 450nm'],
            'f15': ['lmg1', '', '',
                    'LMG HV 1, 520nm'],
            'f16': ['lmg2', '', '',
                    'LMG HV 2, 520nm'],
        }
        self.smsensor = {
            's1': ['sipm1', 'SiPM HV 1'],
            's2': ['sipm2', 'SiPM HV 2'],
        }
        self.dicts = {
            'Symbolic': self.symbolic,
            'UI_branch': self.branch,
            'Channel': self.channel,
            'High_voltage': self.hv,
            'Sensor': self.sensor,
            'FPGA': self.fpga,
            'Flasher Info': self.flasher,
        }

    def testCmd(self):
        return int(self.cmd('softwareVersion .s drop', strip_stack=True))

    def pcmCmd(self, cmdString):
        """
        Sends cmdString to POCAM via Iceboot and handles return cases.

        Keyword arguments:
            cmdString       POCAM Iceboot command string
        """
        msg = self.cmd(cmdString)
        if ('ERROR' in msg.split()):
            ec = msg.split()[1]
            raise RuntimeError('Error occurred while running "%s". '
                               'Error code: %s' % (cmdString, ec))
        else:
            return msg

    def symbCmd(self, symbolic, cmd):
        """
        Returns correctly formatted symbolic command string.

        Keyword arguments:
            symbolic    symbolic pin name
            cmd         pocam iceboot command
        """
        return 's" %s" %s' % (symbolic, cmd)

    def symbCmdVal(self, symbolic, val, cmd):
        """
        Returns correctly formatted symbolic command string with value.

        Keyword arguments:
            symbolic    symbolic pin name
            val         value to set
            cmd         pocam iceboot command
        """
        return 's" %s" %i %s' % (symbolic, val, cmd)

    def symbCmdSPI(self, trg, cmd, val):
        """
        Returns correctly formatted SPI command string.

        Keyword arguments:
            trg     str, SPI target
            cmd     str, hex command to send
            val     str, hex value to write
        """
        return '%s $%s %i $%s pcmSPI' % (trg, cmd, 0, val)

    def symbCmdFlash(self, fpga, fn, cmd):
        """
        Returns correctly formatted FPGA flash command string.

        Keyword arguments:
            fpga    fpga name
            fn      file name
            cmd     POCAM Icecboot command
        """
        return 's" %s" s" %s" %s' % (fpga, fn, cmd)

    def symbCmdADC(self, fpga, addr, rw, data):
        """
        Returns correctly formatted ADC configuration command string.

        Keyword arguments:
            fpga    fpga name
            addr    register address, int
            rw      read/write bit, int
            data    data to write, int
        """
        return 's" %s" %i %i %i pcmADC_ctrl' % (fpga, addr, rw, data)

    def oneHotEnc(self, length, index):
        """
        Format and return one-hot-encoded string of given length and index.

        Keyword arguments:
            length      int, length of the string
            index       int, index of the one-hot-encoding
        """
        ohenc = ['0' for i in range(length)]
        ohenc[int(index)] = '1'
        ohenc = ''.join(ohenc[::-1])
        return ohenc

    def bitFill(self, length):
        """
        Format and return bit-fill string of given length.

        Keyword arguments:
            length      int, length of the fill string
        """
        fill = ['0' for i in range(length)]
        fill = ''.join(fill)
        return fill

    def parseUI(self, msg):
        """
        Returns parsed voltage and current of 'OK' U/I return message.

        Keyword arguments:
            msg    return message of U/I command
        """
        _, voltage, current, address = msg.split()
        voltage = float(voltage) / 1000.
        current = float(current) / 1000.
        return voltage, current, address

    def parseADC(self, msg):
        """
        Returns parsed voltages of 'OK' ADC return message.

        Keyword arguments:
            msg    return message of U/I command
        """
        _, voltage, voltage_raw = msg.split()
        voltage = float(voltage)
        voltage_raw = float(voltage_raw)
        return voltage, voltage_raw

    def info_symAll(self):
        """
        Print all used symbolic link names.
        """
        print('\n------------')
        print('--- Symbolic links for POCAM Iceboot')
        print('--- Format: key - description\n')
        for name, dictionary in self.dicts.items():
            print('Dict: %s' % (name))
            for key in dictionary:
                print('%s - %s' % (key, dictionary[key]))
            print()
        print('------------\n')

    def info_symFlasher(self):
        """
        Print all used flasher symbolic link names.
        """
        print('\n------------')
        print('--- Symbolic flasher links for POCAM Iceboot')
        print('--- Format: key - [config, description]\n')
        for dictionary in [self.flasher]:
            for key in dictionary:
                print('%s - %s' % (key, dictionary[key]))
            print()
        print('------------\n')

    def init(self):
        """
        Initializes all POCAM functionality and communication streams.
        """
        return self.pcmCmd('pcmBRD_init')

    def scan_I2C(self):
        """
        Scans I2C network and returns found device addresses.
        """
        return self.pcmCmd('pcmI2C_scan')

    def ui(self, branch):
        """
        Reads the U/I values of the branch.

            Keyword arguments:
                branch    branch pin name of U/I chain

            Returns:
                voltage amperes     units: [Volts], [milli-Amperes]
        """
        return self.pcmCmd(self.symbCmd(branch, 'pcmUI'))

    def pwr_set(self, symbolic, on=False):
        """
        Turns on the voltage of the symbolic chain.

            Keyword arguments:
                symbolic    symbolic pin name of chain
                val         0 switches off, 1 switches on
        """
        val = 1 if on else 0
        return self.pcmCmd(self.symbCmdVal(symbolic, val, 'pcmPWR_set'))

    def pwr_get(self, symbolic):
        """
        Reads the voltage of the symbolic chain.

            Keyword arguments:
                symbolic    symbolic pin name of chain
        """
        return self.pcmCmd(self.symbCmd(symbolic, 'pcmPWR_get'))

    def spi_write(self, target, offset, value):
        """
        Write FPGA register via SPI.

            Keyword arguments:
                target      SPI target
                offset      str, hex register offset [0, f]
                value       str, value to write to register
        """
        offset = hex(int(offset))[2:]
        command = '0' + offset
        print('\t writing SPI offset "%s" with value "%s" to target "%s"'
              % (offset, value, target))
        return self.pcmCmd(self.symbCmdSPI(target, command, value))

    def spi_read(self, target, offset):
        """
        Read FPGA register via SPI.

            Keyword arguments:
                target      SPI target
                offset      str, hex register offset [0, f]
        """
        offset = hex(int(offset))[2:]
        command = '8' + offset
        MSG = self.pcmCmd(self.symbCmdSPI(target, command, 0))
        print('\t reading SPI offset "%s" of target "%s": %s'
              % (offset, target, MSG.split()[1]))
        return MSG

    def adc_read(self, channel):
        """
        Reads the ADC-sampled voltage value of the channel.

            Keyword arguments:
                channel     channel name
        """
        return self.pcmCmd(self.symbCmd(channel, 'pcmADC'))

    def adc_ctrl(self, fpga, addr, rw, data):
        """
        Controls configuration of ADC AD9251 on DBs.

            Keyword arguments:
                fpga    fpga name, only dbm/dbs
                addr    register address
                rw      read/write bit
                data    data to write
        """
        if fpga not in ['dbm', 'dbs']:
            raise ValueError('Allowed FPGAs: [dbm, dbs]')
        else:
            return self.pcmCmd(self.symbCmdADC(fpga, addr, rw, data))

    def pwm(self, hv, val):
        """
        Sets the HV PWM of a specific channel to a specific value.

            Keyword arguments:
                hv      hv name of chain
                val     value to set in [0, 65535]
        """
        if 0 <= val <= 65535:
            self.pcmCmd(self.symbCmdVal(hv, val, 'pcmPWM'))
            time.sleep(0.5)
        else:
            raise ValueError('PWM value must be between 0 and 65535.')

    def ow_uid(self, sensor):
        """
        Reads the unique ID of a one-wire temperature sensor.

            Keyword arguments:
                sensor      sensor name
        """
        return self.pcmCmd(self.symbCmd(sensor, 'pcm1W_uid'))

    def ow_temp(self, sensor):
        """
        Reads the temperature of a one-wire temperature sensor.

            Keyword arguments:
                sensor      sensor name
        """
        return self.pcmCmd(self.symbCmd(sensor, 'pcm1W_temp'))

    def cfg_id(self, fpga):
        """
        Reads the unique ID of an FPGA.

            Keyword arguments:
                fpga      fpga name
        """
        return self.pcmCmd(self.symbCmd(fpga, 'pcmCFG_id'))

    def cfg_flash(self, fpga, fn):
        """
        Flashes an FPGA with the file fn via SPI.

            Keyword arguments:
                fpga    fpga name
                fn      file name
        """
        return self.pcmCmd(self.symbCmdFlash(fpga, fn, 'pcmCFG_flash'))

    def cfg_flashJTAG(self, fpga, fn):
        """
        Flashes an FPGA with the file fn via JTAG.

            Keyword arguments:
                fpga    fpga name
                fn      file name
        """
        return self.pcmCmd(self.symbCmdFlash(fpga, fn, 'pcmJTAG'))

    def toggle_boards(self, on=False, sleep=1, verbose=False):
        """
        Switch on/off POCAM master/slave DBs and IB.
        """
        if on:
            val = True
            print('Switching on FPGAs...')
        else:
            val = False
            print('Switching off FPGAs...')

        for sym in ['ib', 'db']:
            MSG_SET = self.pwr_set(sym, val)
            MSG_GET = self.pwr_get(sym)

            if verbose:
                print('\t%s: %s' % (sym, MSG_GET.split()[1]))

        if on:
            time.sleep(sleep)

    def toggle_pwm(self, on=False, sleep=1, verbose=False):
        """
        Switch on/off POCAM PWM HV supplies.
        """
        if on:
            val = True
            print('Switching on HVs...')
        else:
            val = False
            print('Switching off HVs...')

        for sym in ['lmg1', 'lmg2', 'sipm1', 'sipm2',
                    'kapu1', 'kapu2', 'opamp', 'timing']:
            MSG_SET = self.pwr_set(sym, val)
            MSG_GET = self.pwr_get(sym)

            if verbose:
                print('\t%s: %s' % (sym, MSG_GET.split()[1]))

        if on:
            time.sleep(sleep)

    def info_pwr(self):
        """
        Test and report levels of all power channels
        of the MMB, IB and DBs.
        """
        print('Checking MMB...')
        for sym in ['mmb_18', 'mmb_33']:
            MSG = self.adc_read(sym)
            v, v_raw = self.parseADC(MSG)
            print('\t%s: %.3fV (%i)' % (sym, v, v_raw))

        print('Checking IB/DBs...')
        for sym in ['db_18', 'db_33', 'opamps',
                    'lmg', 'sipm', 'kapu', 'timing']:
            MSG = self.ui(sym)
            volt, amp, addr = self.parseUI(MSG)
            print('\t%s: %.3fV, %.3fA' % (sym, volt, amp))

    def info_pwm(self):
        """
        Test and report ADC values of all HV channels.
        """
        print('Checking HVs...')
        for sym in ['lmg1', 'lmg2', 'sipm1', 'sipm2',
                    'kapu1', 'kapu2']:
            MSG = self.adc_read(sym)
            v, v_raw = self.parseADC(MSG)
            print('\t%s: %.3fV (%i)' % (sym, v, v_raw))

    def scan_pwm(self, hv, start=0, stop=65535, step=10, wait=5):
        """
        Scans HV PWM of a specific channel from start to stop.

        Keyword arguments:
            hv      name of hv channel
            start   starting value of scan
            stop    stopping value of scan
            step    number of steps to scan
            wait    time to wait for next step [s]
        """
        pwm_steps = np.linspace(start, stop, step)
        print('Scanning voltage %s' % (hv))

        for val in pwm_steps:
            MSG_PWM = self.pwm(hv, val)
            MSG_ADC = self.adc_read(hv)
            v, v_raw = self.parseADC(MSG_ADC)
            print('\t%s: %i --> %.2fV' % (hv, val, v))
            time.sleep(wait)

    @staticmethod
    def set_sensorAdc():
        """ placeholder?
        """
        pass

    @staticmethod
    def set_i2cFram():
        """ placeholder?
        """
        pass

    def set_numberOfPulses(self, target, n):
        """
        Set number of pulses to flash for via SPI in DB FPGA registers.

        From the DB documentation:
            D[31:0]   number of pulses

        Keyword arguments:
            target      str, SPI target
            n           int, number of pulses
        """
        value = hex(n)[2:]  # to hex without '0x'

        # write to register and read back
        MSG_W = self.spi_write(target, '6', value)
        MSG_R = self.spi_read(target, '6')

    def set_pulserSettings(self, target, enable=False, tpulse=10, period=1000):
        """
        Set pulser settings via SPI in the DB FPGA registers.

        From the DB documentation:
            D[31]     enable bit (0 = disabled)
            D[30:24]  length of pulse (<100), unit is 10ns
            D[23:0]   period counter, unit is 1us

            Remark: it is recommended to disable pulser before changing settings.
            Strange things may occur in case of altering settings while pulser
            logic is active.

            The pulser uses a granularity of 100 sysclk periods (i.e. 100x 10ns = 1us).
            The length of pulse should therefore be limited to less than 100, and it is
            recommended to provide a sufficient "off" and "on" time for the pulse
            (i.e. > 10, <90).

            The pulse period is set in units of 1us, and will be "+1" in real, so if a value
            of 100 is requested, set 99 in the register.

            Example: 0x32000063  0x32    => 50 = 500ns pulse length
                                0x00063 => 99 = (99+1)*1us = 100us => 10kHz

        Keyword arguments:
            target          str, SPI target
            enable          bool, enable pulser
            tpulse          int, length of pulse [units of 10ns] [0, ... 99]
            period          int, period between pulses [units of 1us] [100, ... +inf]

        """
        if tpulse >= 100:
            raise ValueError('Pulse length must be smaller than 1us.')
        if period < 100:
            raise ValueError('Flash frequency should be slower than 10kHz.')

        # print settings
        print('Pulser settings: Enable = %s, Tpulse = %ins, ' \
              'Period = %ius --> %.2fHz' % (enable, tpulse,
                                            period, 1 / (period) * 1e6))

        # calculate 32-bit register entry for settings
        hex1 = hex(tpulse + 128) if enable else hex(tpulse)
        hex1 = hex1[2:]
        hex2 = hex(period - 1)
        hex2 = hex2[2:]
        fill = ['0' for i in range(8 - (len(hex1) + len(hex2)))]
        value = hex1 + ''.join(fill) + hex2

        # write to register and read back
        MSG_W = self.spi_write(target, '7', value)
        MSG_R = self.spi_read(target, '7')

    def set_kapu(self, target, enable0=False, enable1=False,
                 hv='0', cap='0'):
        """
        Setup Kapustinski pulser via SPI in DB FPGA registers.

        From the DB documentation:
            D[15]     enable LMG trigger 1 (0 = disabled)
            D[14]     enable LMG trigger 0 (0 = disabled)
            D[13:6]   ---
            D[5:4]    enable Kapustinski HVs (one hot encoded)
            D[3:0]    select Kapustinsky capacitors (one hot encoded)

            This register allows to configure the Kapustinksi flasher.
            You can select between two HVs, and also select one capacitor bank
            out of four.
            To get flashes, both HV and capacitors must be set correctly, and in addition,
            the corresponding HV must be activated at the IB, and a suitable voltage set
            by PWM.

        Keyword arguments:
            target          str, SPI target
            enable0         bool, enable KAP trigger 0
            enable1         bool, enable KAP trigger 1
            hv              str, select KAP HV, [0, 1]
            cap             str, select capacitors, [0, 1, 2, 3]
        """
        if hv not in ['0', '1']:
            return ValueError('HV identifier not recognized.')

        if cap not in ['0', '1', '2', '3']:
            return ValueError('Capacitor identifier not recognized.')

        # calculate 16-bit register entry for settings as string
        ena1 = '1' if enable1 else '0'
        ena0 = '1' if enable0 else '0'
        fill = self.bitFill(8)
        oh1 = self.oneHotEnc(2, hv)
        oh2 = self.oneHotEnc(4, cap)
        value = ena1 + ena0 + fill + oh1 + oh2  # binary
        value = hex(int(value, 2))[2:]  # to hex without '0x'

        # write to register and read back
        MSG_W = self.spi_write(target, '8', value)
        MSG_R = self.spi_read(target, '8')

    def set_lmg(self, target, enable0=False, enable1=False,
                vcc='0', hv='0', gan='0', discharge='0'):
        """
        Setup LMG pulser via SPI in DB FPGA registers.

        From the DB documentation:
            D[15]     enable KAP trigger 1 (0 = disabled)
            D[14]     enable KAP trigger 0 (0 = disabled)
            D[13:10]  ---
            D[9:8]    enable LMG Vcc (one hot encoded)
            D[7:6]    enable LMG HVs (one hot encoded)
            D[5:4]    select LMG GaN FET (one hot encoded)
            D[3:0]    select LMG charge path (one hot encoded)

            This register allows to configure the LMG flasher.
            You can select between two HVs, two LVs, two GaN FETs and four charge pathes.
            To get flashes, both HV, LV, GaN FET and charge path have to be set
            correctly, and in addition, the corresponding HV must be activated at the IB, and
            a suitable voltage set by PWM.

        Keyword arguments:
            target          str, SPI target
            enable0         bool, enable LMG trigger 0
            enable1         bool, enable LMG trigger 1
            vcc             str, select LMG supply voltage, [0, 1]
            hv              str, select LMG HV, [0, 1]
            gan             str, select GaNFET, [0, 1]
            discharge       str, select discharge path, [0, 1, 2, 3]
        """
        if vcc not in ['0', '1']:
            return ValueError('Vcc identifier not recognized.')

        if hv not in ['0', '1']:
            return ValueError('HV identifier not recognized.')

        if gan not in ['0', '1']:
            return ValueError('GaNFET identifier not recognized.')

        if discharge not in ['0', '1', '2', '3']:
            return ValueError('Discharge path identifier not recognized.')

        # calculate 16-bit register entry for settings as string
        ena1 = '1' if enable1 else '0'
        ena0 = '1' if enable0 else '0'
        fill = self.bitFill(4)
        oh1 = self.oneHotEnc(2, vcc)
        oh2 = self.oneHotEnc(2, hv)
        oh3 = self.oneHotEnc(2, gan)
        oh4 = self.oneHotEnc(4, discharge)
        value = ena1 + ena0 + fill + oh1 + oh2 + oh3 + oh4  # binary
        value = hex(int(value, 2))[2:]  # to hex without '0x'

        # write to register and read back
        MSG_W = self.spi_write(target, '9', value)
        MSG_R = self.spi_read(target, '9')

    def set_sensors(self, target, enable5v=False, SipmHv='0',
                    enableTdcBuffer=False, enableTdc0=False,
                    enableTdc1=False, enableTdc2=False,
                    enableTdc3=False, polarity0='0',
                    polarity1='0', enable0=False, enable1=False):
        """
        Setup self-monitoring sensors via SPI in DB FPGA registers.

        From the DB documentation:
            D[15]     enable +5V OpAmps
            D[14]     ---
            D[13:12]  enable SiPM HVs (one hot encoded)
            D[11:9]   ---
            D[8]      enable TDC data buffer (0 = disabled)
            D[7]      enable TDC 3, ICM sync (0 = disabled)
            D[6]      enable TDC 2, charge slow (0 = disabled)
            D[5]      enable TDC 1, charge fast (0 = disabled)
            D[4]      enable TDC 0, timing(0 = disabled)
            D[3]      TDC 1 polarity
            D[2]      TDC 1 enable
            D[1]      TDC 0 polarity
            D[0]      TDC 0 enable

        Keyword arguments:
            target                  str, SPI target
            enable5v                bool, enable +5V OpAmps
            SipmHv                  str, enable SiPM HVs (OHE), [0, 1]
            enableTdcBuffer         bool, enable TDC data buffer
            enableTdc0              bool, enable TDC 0
            enableTdc1              bool, enable TDC 1
            enableTdc2              bool, enable TDC 2
            enableTdc3              bool, enable TDC 3
            polarity0               str, TDC 0 polarity, [0, 1]
            polarity1               str, TDC 1 polarity, [0, 1]
            enable0                 bool, enable TDC 0
            enable1                 bool, enable TDC 1
        """
        if SipmHv not in ['0', '1']:
            raise ValueError('SiPM HV identifier not recognized.')

        if polarity0 not in ['0', '1']:
            raise ValueError('Polarity0 identifier not recognized.')

        if polarity1 not in ['0', '1']:
            raise ValueError('Polarity1 identifier not recognized.')

        # calculate 16-bit register entry for settings as string
        ena5v = '1' if enable5v else '0'
        oh1 = self.oneHotEnc(2, SipmHv)
        enaTb = '1' if enableTdcBuffer else '0'
        enaT0 = '1' if enableTdc0 else '0'
        enaT1 = '1' if enableTdc1 else '0'
        enaT2 = '1' if enableTdc2 else '0'
        enaT3 = '1' if enableTdc3 else '0'
        po1 = polarity1
        ena1 = '1' if enable1 else '0'
        po0 = polarity0
        ena0 = '1' if enable0 else '0'
        value = ena5v + '0' + oh1 + '000' + enaTb + enaT0 + enaT1 \
                + enaT2 + enaT3 + po1 + ena1 + po0 + ena0  # binary
        value = hex(int(value, 2))[2:]  # to hex without '0x'

        # write to register and read back
        MSG_W = self.spi_write(target, '10', value)
        MSG_R = self.spi_read(target, '10')

    def set_lmgPhase(self, target, coarse=0, fine=0):
        """
        Set the LMG phase alignment via SPI in the DB FPGA registers.

        From the DB documentation:
            D[15:14]  ---
            D[13:12]  PLL output select (00 = LMG trigger clock)
            D[11:8]   coarse delay setting
            D[7:0]    fine delay setting

        Keyword arguments:
            coarse         int, number of coarse cycles [units of 10ns] [0, ... 16]
            fine           int, number of fine cycles [units of 208.3ps] [0, ... 47]
        """
        if coarse > 15:
            raise ValueError('Cannot shift by more than 16 coarse cycles.')

        if fine > 47:
            raise ValueError('Cannot shift by more than 47 fine cycles.')

        # calculate 16-bit register entry for settings as string
        fill = self.bitFill(2)
        pll = self.bitFill(2)
        coarse = format(coarse, '04b')
        fine = format(fine, '08b')
        value = fill + pll + coarse + fine  # binary
        value = hex(int(value, 2))[2:]  # to hex without '0x'

        # write to register and read back
        MSG_W = self.spi_write(target, '11', value)
        MSG_R = self.spi_read(target, '11')

    def flash_kapustinski(self, flasher, pwm, freq=1000, npulse=1e6):
        """
        Flashes a Kapustinsky flasher configuration with a bias
        voltage and frequency for a given number of pulses.

        Keyword arguments:
            flasher     Kapustinski flasher configuration key
            pwm         voltage pwm value
            freq        flash frequency [Hz]
            npulse      number of pulses
        """
        print('Setting up flashing procedure...\n' \
              '\tConfiguration: KEY %s, PWM %i FREQ %iHz, ' \
              'N %.0e' % (flasher, pwm, freq, npulse))

        if flasher not in self.flasher:
            raise AssertionError('Flasher key not known, aborting.')

        if 'Kapustinski' not in self.flasher[flasher][-1]:
            raise RuntimeError('Cannot flash LMG driver with this'
                               'function, aborting.')

        # parse configuration
        hv, wl, cfg = self.flasher[flasher][:3]

        # set and check hv
        MSG_PWM = self.pwm(hv, pwm)
        MSG_ADC = self.adc_read(hv)
        v, v_raw = self.parseADC(MSG_ADC)
        print('\tPWM: %i --> %.2fV' % (pwm, v))

        # set and check wavelength / discharge path
        ### TBD
        print('\tWL/PATH: ...' % ())

        # configure pulsing properties
        ### TBD
        print('\tCFG: ...' % ())

        # initiate flashing
        print('\t--> FLASHING...')
        ### TBD
        print('\t--> FINISHED.')

    def flash_lmg(self, flasher, pwm, width=10, freq=1000, npulse=1e6):
        """
        Flashes an LMG flasher configuration with a bias
        voltage and frequency for a given number of pulses.

        Keyword arguments:
            flasher     Kapustinski flasher configuration key
            pwm         voltage pwm value
            width       pulse width [ns]
            freq        flash frequency [Hz]
            npulse      number of pulses
        """
        pass

    def flash(self, flasher, pwm, width=10, freq=1000, npulse=1e6):
        """
        Flashes a POCAM flasher configuration with a bias
        voltage and frequency for a given number of pulses.

        Keyword arguments:
            flasher     Kapustinski flasher configuration key
            pwm         voltage pwm value
            width       pulse width [ns], optional (LMG only)
            freq        flash frequency [Hz]
            npulse      number of pulses
        """
        # initialize
        self.init()
        self.toggle_boards(on=True)
        self.toggle_pwm(on=True)

        # flash
        if 'Kapustinski' in self.flasher[flasher][-1]:
            self.flash_kapustinski(flasher, pwm,
                                   freq=freq, npulse=npulse)

        if 'LMG' in self.flasher[flasher][-1]:
            self.flash_lmg(flasher, pwm,
                           width=width, freq=freq, npulse=npulse)

        # shut down
        self.toggle_pwm(on=False)
        self.toggle_boards(on=False)
