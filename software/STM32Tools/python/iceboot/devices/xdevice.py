import functools
from contextlib import contextmanager

from boardtype import getBoardName

from ..iceboot_comms import IceBootComms
from ..logicCapture import (LOGIC_CAPTURE_RECORD_LEN, parseLogicCapture,
                            displayLogicCapture, bankNumber)
import numpy as np
import re
from typing import Tuple

# Iceboot will retry failed I2C sensor reads for up to 2.0 sec.
SENSOR_READ_TIMEOUT = 3.0


class xDevice(object):

    def __init__(self, comms: IceBootComms, **kwargs):
        self.debug = kwargs['debug'] if 'debug' in kwargs else False
        self.comms = comms
        self.interlockChecksEnabled = True
        self.__interlockChecksEnabledCache = self.interlockChecksEnabled
        self.lightSensorPmtHvCheckEnabled = True
        print("New IceBoot session: Device %s Software version %x %s" %
              (self.__class__.__name__, self.softwareVersion(),
               self.softwareId()))

    def name(self):
        return self.__class__.__name__

    device_type = name  # alias

    def cmd(self, cmdStr: str, timeout: float = 1.0, strip_stack: bool=False) -> str:
        return self.comms.cmd(cmdStr, timeout, strip_stack)

    def uint16_cmd(self, cmdStr: str, n_words: int) -> np.ndarray:
        return self.comms.uint16_cmd(cmdStr, n_words)

    def raw_cmd(self, cmdStr: str, n_bytes: int = None, timeout: float = 1.0) -> bytearray:
        return self.comms.raw_cmd(cmdStr, n_bytes, timeout)

    def read_n(self, n_bytes: int, timeout: float = 1.0) -> bytearray:
        return self.comms.read_n(n_bytes, timeout)

    # Test for Iceboot response
    def ping(self, timeout: float = 1.0) -> int:
        ping_cmd = '.s'  # benign command, can be seen in verbose output
        response = False
        try:
            response = len(self.cmd(ping_cmd, timeout)) > 0
        except Exception:
            pass
        return response

    def softwareVersion(self) -> int:
        return int(self.cmd("softwareVersion .s drop", strip_stack=True))

    def softwareId(self) -> str:
        return self.cmd("printSoftwareId")

    def stmUUID(self) -> str:
        return self.cmd("stmid")

    def getBoardType(self, unknown_value: int=0) -> int:
        return self.comms.getBoardType(unknown_value)

    def isDEgg(self) -> bool:
        return getBoardName(self.getBoardType()) == 'DEgg'

    def isMDOM(self) -> bool:
        return (getBoardName(self.getBoardType()) == 'mDOM') or (
                    getBoardName(self.getBoardType()) == 'mDOMRev1')

    def isPDOM(self) -> bool:
        return getBoardName(self.getBoardType()) == 'pDOM'

    def isXDOM(self) -> bool:
        return self.isDEgg() or self.isMDOM() or self.isPDOM()

    def hasFPGA(self) -> bool:
        return self.isXDOM()

    def uSleep(self, delayUS: int) -> None:
        self.cmd("%d usleep" % delayUS, timeout=300)

    def startLogicCapture(self, gpioPort: str) -> None:
        self.__interlockChecksEnabledCache = self.interlockChecksEnabled
        self.interlockChecksEnabled = False
        self.cmd("%d startLogicCapture" % bankNumber(gpioPort))

    def readLogicCapture(self) -> dict:
        self.interlockChecksEnabled = self.__interlockChecksEnabledCache
        buf = bytearray()
        buf.extend(self.comms.receiveRawCmd("readLogicCapture",
                                            LOGIC_CAPTURE_RECORD_LEN))
        return parseLogicCapture(buf)

    @contextmanager
    def displayLogicCaptureContext(self, gpioPort: str, pins: list=None) -> None:
        self.startLogicCapture(gpioPort)
        yield
        displayLogicCapture(self.readLogicCapture(), pins)

    def endStream(self) -> None:
        # endStream is depricated from the IceBoot side
        pass

    def readFlashInterlock(self) -> bool:
        return int(self.cmd("readFlashInterlock .s drop",
                            strip_stack=True)) == 1

    def readFPGAConfigInterlock(self) -> bool:
        return int(self.cmd("readFPGAConfigInterlock .s drop",
                            strip_stack=True)) == 1

    def readLIDInterlock(self) -> bool:
        return int(self.cmd("readLIDInterlock .s drop", strip_stack=True)) == 1

    def readHVInterlock(self) -> bool:
        return int(self.cmd("readHVInterlock .s drop", strip_stack=True)) == 1

    def _interlockWrapperCheck(self, interlockFunc, description):
        if self.interlockChecksEnabled:
            if not interlockFunc():
                raise Exception("%s interlock not set" % description)

    def requiresFlashInterlock(func):
        def wrapper(self, *args, **kwargs):
            self._interlockWrapperCheck(self.readFlashInterlock, "Flash")
            return func(self, *args, **kwargs)

        return wrapper

    def readLightSensorPmtHvEnable(self) -> bool:
        return int(self.cmd("readLightSensorPmtHvEnable .s drop",
                            strip_stack=True)) == 1

    def requiresLightSensorPmtHvEnable(hv_arg_index):
        """ hv_arg_index is index of HV value passed to decorated function, not
        counting 'self' """

        def _decorator(validate_function):
            @functools.wraps(validate_function)
            def _wrapper(self, *function_args):
                if (self.lightSensorPmtHvCheckEnabled and
                        function_args[hv_arg_index] > 0 and not
                        self.readLightSensorPmtHvEnable()):
                    raise Exception("LightSensor HV PMT enable failure")
                return validate_function(self, *function_args)

            return _wrapper

        return _decorator

    def flashID(self) -> str:
        return self.cmd("flashID")

    @requiresFlashInterlock
    def flashRemove(self, remoteFileName: str) -> None:
        cmdstr = "s\" %s\" flashRemove" % remoteFileName
        self.cmd(cmdstr)

    @requiresFlashInterlock
    def flashClear(self) -> None:
        self.cmd("flashClear")

    def flashCat(self, fileName: str) -> str:
        return self.cmd("s\" %s\" flashCat" % fileName)

    def flashFileGet(self, flashFile: str, localFile: str=None) -> None:
        data = self.raw_cmd("s\" %s\" flashCat" % flashFile)
        if localFile is None:
            localFile = flashFile
        try:
            with open(localFile, "w") as f:
                f.write(str(data))
        except:
            print("Unable to open local file %s" % localFile)

    @requiresFlashInterlock
    def ymodemFlashUpload(self, remoteFileName: str, infile: str) -> None:
        if len(remoteFileName) >= 32:
            raise Exception("remoteFileName %s length %s >= 32" %
                            (remoteFileName, len(remoteFileName)))
        cmd = "s\" %s\" ymodemFlashUpload\r\n" % remoteFileName
        self.comms.ymodemSend(infile, cmd)

    @requiresFlashInterlock
    def ymodemFlashUploadBytes(self, remoteFileName: str, content: bytes) -> None:
        self.comms.ymodemFlashUploadBytes(remoteFileName, content)

    def flashLS(self) -> list:
        outstr = self.cmd("flashLS")
        # Get the categories from the first line
        out = []
        lines = outstr.splitlines()
        if len(lines) == 0:
            return out
        categories = lines[0].split()
        if len(categories) == 0:
            return out
        # Skip the first two lines
        for line in lines[2:]:
            data = line.split()
            if len(data) != len(categories):
                continue
            entry = {}
            for i in range(len(categories)):
                entry[categories[i]] = data[i]
            out.append(entry)
        return out

    def close(self) -> None:
        self.comms.close()

    def reboot(self, timeout=3) -> None:
        try:
            self.cmd("reboot", timeout)
            # This command does not return.
        except Exception:
            pass

    def readAccelerometerXYZ(self) -> list:
        out = self.cmd("getAccelerationXYZ printAccelerationXYZ",
                       timeout=SENSOR_READ_TIMEOUT)
        out = out.replace(',', ' ')
        out = out.replace('(', ' ')
        out = out.replace(')', ' ')
        data = out.split()
        return [float(x) for x in data[:3]]

    def readMagnetometerXYZ(self) -> list:
        out = self.cmd("getBFieldXYZ printBFieldXYZ",
                       timeout=SENSOR_READ_TIMEOUT)
        out = out.replace(',', ' ')
        out = out.replace('(', ' ')
        out = out.replace(')', ' ')
        data = out.split()
        return [float(x) for x in data[:3]]

    def readPressure(self) -> float:
        out = self.cmd("getPressure printPressure",
                       timeout=SENSOR_READ_TIMEOUT)
        return float(out.split()[0])

    def readAccelerometerTemperature(self) -> float:
        out = self.cmd("getAccelerationTemperature printSensorsTemperature",
                       timeout=SENSOR_READ_TIMEOUT)
        if "ERROR" in out:
            raise Exception("Sensor read failure")
        return float(out.split()[0])

    def readMagnetometerTemperature(self) -> float:
        out = self.cmd("getBFieldTemperature printSensorsTemperature",
                       timeout=SENSOR_READ_TIMEOUT)
        if "ERROR" in out:
            raise Exception("Sensor read failure")
        return float(out.split()[0])

    def readPressureSensorTemperature(self) -> float:
        out = self.cmd("getPressureSensorTemperature printSensorsTemperature",
                       timeout=SENSOR_READ_TIMEOUT)
        if "ERROR" in out:
            raise Exception("Sensor read failure")
        return float(out.split()[0])

    def icmID(self) -> str:
        return self.cmd("icmID")

    def mainboardID(self) -> str:
        return self.cmd("mainboardID")

    def icmReadReg(self, reg: int) -> int:
        return int(self.cmd("%d icmReadReg .s drop" % (reg),
                            strip_stack=True))

    def icmWriteReg(self, reg: int, value: int) -> None:
        self.cmd("%d %d icmWriteReg" % (reg, value))

    def icmTxCnt(self) -> int:
        return int(self.cmd("icmTxCnt .s drop", strip_stack=True))

    def icmRxCnt(self) -> int:
        return int(self.cmd("icmRxCnt .s drop", strip_stack=True))

    def icmCalTimeFIFOWordCount(self) -> int:
        return int(self.cmd("icmCalTimeFIFOWordCount .s drop",
                            strip_stack=True))

    def icmReadCalTimeFIFO(self) -> list:
        return [int(x, 16) for x in self.cmd("icmReadCalTimeFIFO").split()]

    def icmCalTrigFIFOWordCount(self) -> int:
        return int(self.cmd("icmCalTrigFIFOWordCount .s drop",
                            strip_stack=True))

    def icmReadCalTrigFIFO(self) -> list:
        return [int(x, 16) for x in self.cmd("icmReadCalTrigFIFO").split()]

    def icmReadCurrentTime(self) -> int:
        return int(self.cmd("icmReadCurrentTime"), 16)

    def icmStartCalTrig(self, nPulses: int=0, pulsePer: int=1) -> int:
        return int(self.cmd("%d %d icmStartCalTrig" % (nPulses, pulsePer)), 16)

    def icmStopCalTrig(self) -> None:
        self.cmd("icmStopCalTrig")

    def icmReadSyncCount(self) -> int:
        return int(self.cmd("icmReadSyncCount"), 16)

    def icmMsSinceSync(self) -> int:
        return int(self.cmd("icmMsSinceSync .s drop", strip_stack=True))

    def readIcmTemperature(self) -> float:
        raw = self.icmReadReg(0xe2)
        return (raw >> 4) * 503.975 / 4096 - 273.15

    # Enable logging output at current logging level.
    # Return previous logging output enable status: 0 or 1
    def enableLogOutput(self) -> int:
        return int(self.cmd("enableLogOutput"))

    # Disable logging output at current logging level.
    # Return previous logging output enable status: 0 or 1
    def disableLogOutput(self) -> int:
        return int(self.cmd("disableLogOutput"))

    # Set logging severity threshold level.
    # see https://wiki.icecube.wisc.edu/index.php/STM32_Logging
    # Return previous logging severity threshold level.
    def setLogLevel(self, level: int) -> int:
        return int(self.cmd(str(level) + " setLogLevel"))

    # Return logging severity threshold level.
    # see https://wiki.icecube.wisc.edu/index.php/STM32_Logging
    def getLogLevel(self) -> int:
        return int(self.cmd("getLogLevel"))

    # Return queued multi-line logging records string
    def printLogOutput(self) -> str:
        return self.cmd("printLogOutput")

    # Clear queued logging records.
    def clearLogOutput(self) -> None:
        self.cmd("clearLogOutput")

    # Read canonical light sensor.
    def getLightSensor(self) -> float:
        return float(self.cmd("getLightSensor"))

    # Read canonical temperature sensor.
    def getTemperature(self) -> float:
        return float(self.cmd("getTemperature"))

    # Read system msec ticks since boot
    def getTick(self) -> str:
        return self.cmd("getTick")

    def getCommsLogs(self) -> str:
        return self.cmd("printCommsLogs")

    def allocate(self, size: int) -> int:
        return int(self.cmd(f"{size} allocate drop .s drop", strip_stack=True))

    def free(self, addr: int) -> None:
        self.cmd(f"{addr} free drop")

    def heapUtilization(self) -> Tuple[int, int, float]:
        """Return tuple of (used, capacity, percent_used)."""
        util_str = self.cmd("heapUtilization")
        pattern = r"heap utilization\s+(\d+)/(\d+)\s+=\s+([^%]+)"
        match = re.match(pattern, util_str)
        used = int(match.group(1))
        capacity = int(match.group(2))
        percent_used = float(match.group(3))
        return used, capacity, percent_used
