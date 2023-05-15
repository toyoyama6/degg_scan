from termcolor import colored
from glob import glob
import json
import os
import numpy as np

class DEgg(object):
    def __init__(self, database_json_path=None):
        self._degg_serial_number = -1
        self._upper_glass_serial_number = -1
        self._lower_glass_serial_number = -1
        self._upper_pmt_serial_number = -1
        self._lower_pmt_serial_number = -1
        self._penetrator_type = -1
        self._penetraror_number = -1
        self._sealing_date = -1
        self._fpga_version = -1
        self._flash_id = -1
        self._iceboot_version = -1
        self._box_number = -1
        self._fat_date = -1
        self._port = -1
        self._icm_number = "0000"
        self._icm_id = -1
        self._degg_name = -1
        self._flasher_number = -1
        self._camera_number = -1
        self._mainboard_number = -1
        self._arrival_date = -1
        self._upper_glass_number = -1
        self._lower_glass_number = -1
        self._upper_hvb = -1
        self._lower_hvb = -1
        self._electrical_inspection_nme = None
        self._electrical_inspection_chiba = None
        self._lower_pmt_1e7_gain = None
        self._upper_pmt_1e7_gain = None
        self._analysis_info = []
        self._analysis_keys = []
        self._u_pass_fail = None
        self._l_pass_fail = None
        self._run_start_date = None
        #self._git_sha = None

        if database_json_path is not None:
            self._database_json_path = database_json_path
        else:
            self._database_json_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    '../analysis/database_jsons'))

    def setRunStartDate(self, date):
        if date != None:
            self._run_start_date = date
        else:
            raise ValueError("Date is none! - Check json file!")

    def getRunStartDate(self):
        return self._run_start_date

    #def setGitSha(self, sha):
        #if sha != None:
            #self._git_sha = sha
        #else:
            #raise ValueError("Sha is none! - Check json file!")

    #def getGitSha(self):
        #return self._git_sha

    def setPassFail(self, pmt, verdict):
        if pmt.lower() not in ['upper', 'lower']:
            raise ValueError(f'Choice {pmt} not valid! - Please use upper or lower')
        if type(verdict) != bool:
            raise TypeError(f'{verdict} must be a bool!')
        if pmt.lower() == 'upper':
            self._u_pass_fail = verdict
        if pmt.lower() == 'lower':
            self._l_pass_fail = verdict

    def getPassFail(self, pmt):
        if pmt.lower() not in ['upper', 'lower']:
            raise ValueError(f'Choice {pmt} not valid! - Please use upper or lower')
        if pmt.lower() == 'upper':
            verdict = self._u_pass_fail
        if pmt.lower() == 'lower':
            verdict = self._l_pass_fail
        if verdict != None:
            return verdict
        if verdict == None:
            raise ValueError('Verdict is None - use setPassFail() first!')

    def addAnalysis(self, analysis):
        if analysis == None:
            raise ValueError(f'Cannot add analysis, analysis object = {analysis}!')
        ana_key = analysis.getName()
        if ana_key == None:
            raise ValueError('Cannot add analysis, analysis object key (name) is None!')
        self._analysis_info.append(analysis)
        self._analysis_keys.append(ana_key)

    def getAnalysis(self, ana_key):
        if ana_key == None or type(ana_key) != str:
            raise TypeError('ana_key not valid!')
        ana_key_list = self._analysis_keys
        try:
            ind = ana_key_list.index(ana_key)
        except KeyError:
            print(f'Invalid key {ana_key} for DEgg analysis')
            print(f'Valid keys are: {ana_key_list}')
            exit(1)
        return self._analysis_info[ind]

    def getAnalysisKeys(self):
        return self._analysis_keys

    def setPort(self, port):
        if port == -1:
            raise ValueError("Port not set?")
        else:
            self._port = port

    def setDEggSerialNumber(self, serial_number):
        if serial_number == -1:
            raise ValueError("Serial Number Incorrect")
        else:
            self._degg_serial_number = serial_number

    def setGlassSerialNumber(self, serial_number, half):
        if serial_number == -1:
            raise ValueError("Serial Number Incorrect")

        if half.lower() == "upper":
            self._upper_glass_serial_number = serial_number
        elif half.lower() == "lower":
            self._lower_glass_serial_number = serial_number
        else:
            print(f" Input: {half}")
            print(" Choices are 'upper' and 'lower' ")
            raise ValueError("Invalid Choice")

    def setPmtSerialNumber(self, serial_number, half):
        if serial_number == -1:
            raise ValueError("Serial Number Incorrect")

        if half.lower() == "upper":
            self._upper_pmt_serial_number = serial_number
        elif half.lower() == "lower":
            self._lower_pmt_serial_number = serial_number
        else:
            print(f" Input: {half}")
            print(" Choices are 'upper' and 'lower' ")
            raise ValueError("Invalid Choice")

    def setGlassNumber(self, serial_number, half):
        if serial_number == -1:
            raise ValueError("Number Incorrect")

        if half.lower() == "upper":
            self._upper_glass_number = serial_number
        elif half.lower() == "lower":
            self._lower_glass_number = serial_number
        else:
            print(f" Input: {half}")
            print(" Choices are 'upper' and 'lower' ")
            raise ValueError("Invalid Choice")

    def setHVB(self, serial_number, half):
        if serial_number == -1:
            raise ValueError("Serial Number Incorrect")

        if half.lower() == "upper":
            self._upper_hvb = serial_number
        elif half.lower() == "lower":
            self._lower_hvb = serial_number
        else:
            print(f" Input: {half}")
            print(" Choices are 'upper' and 'lower' ")
            raise ValueError("Invalid Choice")

    def setPenetratorType(self, name):
        valid_names = ['seacon', 'hgs-xsjj', 'hgs-steel']
        if str(name).lower() not in valid_names:
            print(f"Input: {name}")
            print(f"Valid names include: {valid_names}")
            raise ValueError("Penetrator Name Incorrect")
        self._penetrator_type = name

    def setPenetratorNumber(self, number):
        self._penetrator_number = number

    def setSealingDate(self, date):

        try:
            split = date.split("-")
            year = int(split[0])
            month = int(split[1])
            day = int(split[2])
        except:
            print(colored("Sealing date not configured!", 'yellow'))
            return "2017-01-01"

        max_year = 2030 ##could change???
        min_year = 2017 ##first ones I think...
        if year > max_year or year < min_year:
            raise ValueError("Year Out Of Range")
        if month > 12 or month < 1:
            raise ValueError("Month Out of Range")
        if day > 31 or day < 1:
            raise ValueError("Day Out Of Range")

        self._sealing_date = date

    def setFpgaVersion(self, version):
        if int(version) < 0:
            raise ValueError(f"Check FPGA Version: {version}")
        self._fpga_version = int(version)

    def setFlashID(self, flash_id):
        if len(flash_id) == 12:
            print("You may be using an old 12 digit flash ID - consider updating your software")
            raise ValueError("Check flashID")
        if len(flash_id) != 32:
            raise ValueError("flashID != 32 char")
        self._flash_id = flash_id

    def setIcebootVersion(self, version):
        if int(version) < 0:
            raise ValueError("Check Iceboot Version")
        self._iceboot_version = int(version)

    def setBoxNumber(self, number):
        self._box_number = number

    def setFatDate(self, date):
        split = date.split("/")
        year = split[0]
        month = split[1]
        day = split[2]

        max_year = 2030 ##could change???
        min_year = 2017 ##first ones I think...
        if year > max_year or year < min_year:
            raise ValueError("Year Out Of Range")
        if month > 12 or month < 1:
            raise ValueError("Month Out of Range")
        if day > 31 or day < 1:
            raise ValueError("Day Out Of Range")
        self._fat_date = date

    def setFlasherNumber(self, flasher_number):
        self._flasher_number = str(flasher_number)

    def setCameraNumber(self, camera_number):
        self._camera_number = str(camera_number)

    def setICMNumber(self, icm_number):
        #icm_number = int(icm_number)
        #icm = f'{icm_number:04d}'
        self._icm_number = icm_number

    def setMainboardNumber(self, mainboard_number):
        if mainboard_number is None:
            raise ValueError("mainboard number is None")
        if mainboard_number == "":
            raise ValueError("mainboard number is empty - check logbook")
        mainboard_number = str(mainboard_number)
        self._mainboard_number = mainboard_number

    def setArrivalDate(self, arrival_date):
        if arrival_date is None or arrival_date == -1:
            print(colored("Arrival date to Chiba not set", 'yellow'))
        self._arrival_date = arrival_date

    def setICMID(self, icm_id):
        if icm_id is None or icm_id == -1:
            raise ValueError("ICM ID Not Set!")
        self._icm_id = icm_id

    def setDEggName(self, degg_name):
        self._degg_name = degg_name

    def setElectricalInspectionNME(self, electrical_inspection_nme):
        self._electrical_inspection_nme = electrical_inspection_nme

    def setElectricalInspectionChiba(self, electrical_inspection_chiba):
        self._electrical_inspection_chiba = electrical_inspection_chiba

    ##start getter functions
    def getPort(self):
        return self._port

    def getDEggSerialNumber(self):
        return self._degg_serial_number

    def getGlassSerialNumber(self, half):
        if half.lower() == "upper":
            return self._upper_glass_serial_number
        if half.lower() == "lower":
            return self._lower_glass_serial_number
        else:
            print(" Choices are 'upper' and 'lower' ")

    def getGlassNumber(self, half):
        if half.lower() == "upper":
            return self._upper_glass_number
        if half.lower() == "lower":
            return self._lower_glass_number
        else:
            print(" Choices are 'upper' and 'lower' ")

    def getHVB(self, half):
        if half.lower() == "upper":
            return self._upper_hvb
        if half.lower() == "lower":
            return self._lower_hvb
        else:
            print(" Choices are 'upper' and 'lower' ")

    def getPmtSerialNumber(self, half):
        if half.lower() == "upper":
            return self._upper_pmt_serial_number
        if half.lower() == "lower":
            return self._lower_pmt_serial_number
        else:
            print(" Choices are 'upper' and 'lower' ")

    def getGlashNumber(self, half):
        if half.lower() == "upper":
            return self._upper_glass_number
        if half.lower() == "lower":
            return self._lower_glass_number
        else:
            print(" Choices are 'upper' and 'lower' ")

    def getPenetratorType(self):
        return self._penetrator_type

    def getPenetratorNumber(self):
        return self._penetrator_number

    def getSealingDate(self):
        return self._sealing_date

    def getFpgaVersion(self):
        return self._fpga_version

    def getFlashID(self):
        return self._flash_id

    def getIcebootVersion(self):
        return self._iceboot_version

    def getBoxNumber(self):
        return self._box_number

    def getFatDat(self):
        return self._fat_date

    def getICMNumber(self):
        return self._icm_number

    def getFlasherNumber(self):
        return self._flasher_number

    def getCameraNumber(self):
        return self._camera_number

    def getMainboardNumber(self):
        return self._mainboard_number

    def getMCUVersion(self):
        return self._software_version

    def getPmtHV(self, half, measurement_number='latest'):
        if half.lower() == "upper":
            if self._upper_pmt_1e7_gain is None:
                self._upper_pmt_1e7_gain = self.readPmtHV(
                    self._upper_pmt_serial_number,
                    measurement_number)
            return self._upper_pmt_1e7_gain
        elif half.lower() == "lower":
            if self._lower_pmt_1e7_gain is None:
                self._lower_pmt_1e7_gain = self.readPmtHV(
                    self._lower_pmt_serial_number,
                    measurement_number)
            return self._lower_pmt_1e7_gain
        elif half.lower() == "default":
            return 1500
        else:
            raise ValueError('half has to be either upper or lower.')

    def getArrivalDate(self):
        return self._arrival_date

    def getICMID(self):
        return self._icm_id

    def getDEggName(self):
        return self._degg_name

    def getElectricalInspectionNME(self):
        return self._electrical_inspection_nme

    def getElectricalInspectionChiba(self):
        return self._electrical_inspection_chiba

    def readPmtHV(self, pmt_sn, measurement_number):
        files = glob(os.path.join(
            self._database_json_path,
            f'{pmt_sn.upper()}_gain_GainMeasurement_*_01.json'))

        if len(files) == 0:
            print('No gain measurement for this pmt found.')
            print('Setting default HV to -1.')
            return -1

        measurement_numbers = [int(file_i.split('.')[-2].split('_')[-2])
                               for file_i in files]

        if isinstance(measurement_number, int):
            idx = measurement_numbers.index(measurement_number)
        elif measurement_number == 'latest':
            idx = np.argmax(measurement_numbers)
        else:
            raise ValueError('measurement_number has to be '
                             '"latest" or int!')

        hv_file = files[idx]

        with open(hv_file, 'r') as open_file:
            hv_dict = json.load(open_file)

        hv = hv_dict['test_result']['value']
        gain = hv_dict['test_result']['gain']
        if gain != 1e7:
            raise ValueError(f'Gain is not 1e7, but {gain}!')
        return hv


##end
