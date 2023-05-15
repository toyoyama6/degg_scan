
from opcode import (define_opcode, define_fifo, Datatype)
from . import xdomapp_session_cmd
from . import xdomapp_data
from . import xdomapp_msg
import socket
import fcntl
import os
import select
import time
from contextlib import contextmanager

class XDOMAppSessionCmdDispatch(object):
    """
    Class that provides simple Python functions to access xDOM
    functionality.  Datatypes are converted between bytearrays
    and those listed in the xDOM interface document
    """

    def __init__(self, comms, defaultTimeout=2, **kwargs):
        self._defaultTimeout = defaultTimeout
        self.cmd = xdomapp_session_cmd.XDOMAppSessionCmd(comms, **kwargs)

        self.flashFifo = define_fifo(
            self.def_opcode(0x0210, Datatype.BYTEARRAY, timeout=5),
            self.def_opcode(0x0211, Datatype.UNSIGNED_INT, datasize=2),
            self.def_opcode(0x0212, Datatype.UNSIGNED_INT, datasize=4),
            self.def_opcode(0x0213, Datatype.VOID)
        )

        self.cameraFifo = define_fifo(
            self.def_opcode(0xC120, Datatype.BYTEARRAY),
            self.def_opcode(0xC121, Datatype.UNSIGNED_INT, datasize=2),
            self.def_opcode(0xC122, Datatype.UNSIGNED_INT, datasize=4),
            self.def_opcode(0xC123, Datatype.VOID)
        )

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        self.cmd.close()

    # Special echo command type doesn't care about opcode value
    def echo(self, data, timeout=1):
        return self.cmd.echo(data, timeout)

    # Provide a user-overrideable default timeout for poor connections
    def def_opcode(self, opcode, datatype, datasize=None, timeout=None):
        if timeout == None:
            timeout = self._defaultTimeout
        return define_opcode(opcode, datatype, datasize, timeout)

    # Section 00: Handle operations associated with opcodes starting with 00

    def softwareId(self):
        opc = self.def_opcode(0x0000, Datatype.UNSIGNED_INT, datasize=2)
        return self.cmd.poll_opcode(opc)

    def stmUUID(self):
        opc = self.def_opcode(0x0001, Datatype.STRING, datasize=25)
        return self.cmd.poll_opcode(opc)

    def reboot(self):
        opc = self.def_opcode(0x0002, Datatype.VOID, timeout=5)
        try:
            self.cmd.write_opcode(opc)
        except IOError:
            # Command is expected to timeout
            pass

    def hardwareType(self):
        opc = self.def_opcode(0x0003, Datatype.UNSIGNED_INT, datasize=2)
        return self.cmd.poll_opcode(opc)

    def interlockBitmask(self):
        opc = self.def_opcode(0x0004, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc)

    def readFlashInterlock(self):
        return (self.interlockBitmask() & 
                                    xdomapp_data.FLASH_INTERLOCK_BIT) != 0

    def readFPGAConfigInterlock(self):
        return (self.interlockBitmask() & xdomapp_data.FPGA_INTERLOCK_BIT) != 0

    def readLIDInterlock(self):
        return (self.interlockBitmask() & xdomapp_data.LID_INTERLOCK_BIT) != 0

    def readHVInterlock(self):
        return (self.interlockBitmask() & xdomapp_data.HV_INTERLOCK_BIT) != 0

    def readGPIO(self, gpioPort, gpioPinNumber):
        try:
            # User passed in a string
            gpioPort = ord(gpioPort)
        except:
            pass
        opc = self.def_opcode(0x00D0, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=gpioPort, token2=gpioPinNumber)

    # Section 02: Handle operations associated with opcodes starting with 02

    def flashID(self):
        opc = self.def_opcode(0x0200, Datatype.STRING, datasize=33)
        return self.cmd.poll_opcode(opc)

    def flashClear(self):
        opc = self.def_opcode(0x0201, Datatype.VOID, timeout=5)
        self.cmd.write_opcode(opc)

    def flashOpen(self, filename, modestr):
        opcn = None
        if modestr == "r":
            opcn = 0x0202
        elif modestr == "w":
            opcn = 0x0203
        elif modestr == "a":
            opcn = 0x0204
        else:
            raise Exception("Bad file mode string: %s" % modestr)
        opc = self.def_opcode(opcn, Datatype.STRING, datasize=32, timeout=5)
        self.cmd.write_opcode(opc, filename)

    def flashRemove(self, filename):
        opc = self.def_opcode(0x0205, Datatype.STRING, datasize=32)
        self.cmd.write_opcode(opc, filename)

    def flashLS(self):
        opc = self.def_opcode(0x0206, Datatype.BYTEARRAY)
        return xdomapp_data.parseFlashLSRecord(self.cmd.poll_opcode(opc))

    def flashClose(self):
        self.cmd.reset_fifo(self.flashFifo)

    @contextmanager
    def flashFileContext(self, filename, modestr):
        self.flashOpen(filename, modestr)
        try:
            yield
        finally:
            self.flashClose()

    def flashCat(self, filename):
        data = bytearray()
        with self.flashFileContext(filename, "r"):
            while self.cmd.get_fifo_available_bytes(self.flashFifo) > 0:
                data.extend(self.cmd.poll_fifo(self.flashFifo))
        return str(data)

    def flashUploadBytes(self, remoteFileName, content):
        with self.flashFileContext(remoteFileName, "w"):
            blocksize = 30000
            ptr = 0
            while ptr < len(content):
                # Python will automatically truncate the slice
                data = content[ptr:ptr + blocksize]
                ptr += len(data)
                self.cmd.write_fifo(self.flashFifo, data)

    def flashUpload(self, remoteFileName, infile):
        if not os.path.exists(infile):
            raise Exception("File %s does not exist" % infile)
        with open(infile, "rb") as f:
            fsz = os.fstat(f.fileno()).st_size
            # Don't send anything over 64 MB
            if fsz > (64 * 1024 * 1024):
                raise Exception("File %s is too large" % infile)
            # In 2020, everyone has 64 MB RAM to spare...
            self.flashUploadBytes(remoteFileName, f.read())

    # Section 04: Handle operations associated with opcodes starting with 04
    def sensorsRecover(self):
        opc = self.def_opcode(0x0403, Datatype.VOID)
        self.cmd.write_opcode(opc)

    def sensorsRetryCmd(self, cmd):
        # Retry sensor reads twice in case of failure
        for _ in range(2):
            try:
                return cmd()
            except xdomapp_msg.XDOMAppException:
                # Recover is automatic, but need to sleep at least 550 ms
                time.sleep(0.6)
        return cmd()

    def readAccelerometer(self):
        opc = self.def_opcode(0x0400, Datatype.BYTEARRAY)
        return self.sensorsRetryCmd(lambda:
                 xdomapp_data.parseAccelerometerRecord(
                                self.cmd.poll_opcode(opc)))

    def readMagnetometer(self):
        opc = self.def_opcode(0x0401, Datatype.BYTEARRAY)
        return self.sensorsRetryCmd(lambda:
                 xdomapp_data.parseMagnetometerRecord(
                                self.cmd.poll_opcode(opc)))

    def readPressure(self):
        opc = self.def_opcode(0x0402, Datatype.BYTEARRAY)
        return self.sensorsRetryCmd(lambda:
                 xdomapp_data.parsePressureSensorRecord(
                                self.cmd.poll_opcode(opc)))

    def sensorsI2CRead(self, deviceAddr, register, len=1):
        opc = self.def_opcode(0x04D0, Datatype.BYTEARRAY)
        return (self.cmd.read_opcode(opc, len,
                                     token1=deviceAddr, token2=register))

    def sensorsI2CWrite(self, deviceAddr, register, data):
        opc = self.def_opcode(0x04D0, Datatype.BYTEARRAY)
        self.cmd.write_opcode(opc, data, token1=deviceAddr, token2=register)

    # Section 06: xDOM ICM
    def icmID(self):
        opc = self.def_opcode(0x0600, Datatype.STRING, datasize=17)
        return self.cmd.poll_opcode(opc)

    def mainboardID(self):
        opc = self.def_opcode(0x0601, Datatype.STRING, datasize=17)
        return self.cmd.poll_opcode(opc)

    def icmReadReg(self, reg):
        opc = self.def_opcode(0x06D0, Datatype.UNSIGNED_INT, datasize=2)
        return self.cmd.poll_opcode(opc, token1=reg)

    def icmWriteReg(self, reg, value):
        opc = self.def_opcode(0x06D0, Datatype.UNSIGNED_INT, datasize=2)
        self.cmd.write_opcode(opc, value, token1=reg)

    # Section 10: xDOM FPGA configuration, id, and debug
    def isFPGAConfigured(self):
        opc = self.def_opcode(0x1000, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc))

    def fpgaVersion(self):
        opc = self.def_opcode(0x1001, Datatype.UNSIGNED_INT, datasize=2)
        return self.cmd.poll_opcode(opc)

    def fpgaChipID(self):
        opc = self.def_opcode(0x1002, Datatype.STRING, datasize=17)
        return self.cmd.poll_opcode(opc)

    def flashConfigureFPGA(self, remoteFilename):
        opc = self.def_opcode(0x1080, Datatype.STRING, datasize=32, timeout=5)
        self.cmd.write_opcode(opc, remoteFilename)

    def fpgaWrite(self, addr, data):
        opc = self.def_opcode(0x10D0, Datatype.BYTEARRAY)
        token1 = addr & 0xFF
        token2 = (addr >> 8) & 0xFF
        self.cmd.write_opcode(opc, xdomapp_data.LE16Pack(data),
                              token1=token1, token2=token2)

    def fpgaRead(self, addr, len):
        opc = self.def_opcode(0x10D0, Datatype.BYTEARRAY)
        token1 = addr & 0xFF
        token2 = (addr >> 8) & 0xFF
        return xdomapp_data.LE16Unpack(
                self.cmd.read_opcode(opc, 2*len, token1=token1, token2=token2))

    # Section C0: Calibration operations
    def enableCalibrationPower(self):
        opc = self.def_opcode(0xC000, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 1)

    def disableCalibrationPower(self):
        opc = self.def_opcode(0xC000, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 0)

    def getCalibrationPowerStatus(self):
        opc = self.def_opcode(0xC000, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc))

    def enableCameraPower(self):
        opc = self.def_opcode(0xC001, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 1)

    def disableCameraPower(self):
        opc = self.def_opcode(0xC001, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 0)

    def getCameraPowerStatus(self):
        opc = self.def_opcode(0xC001, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc))

    def enableFlasherPower(self):
        opc = self.def_opcode(0xC002, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 1)

    def disableFlasherPower(self):
        opc = self.def_opcode(0xC002, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 0)

    def getFlasherPowerStatus(self):
        opc = self.def_opcode(0xC002, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc))

    def enableCamera(self, cameraNumber):
        opc = self.def_opcode(0xC010, Datatype.VOID)
        self.cmd.write_opcode(opc, token1=cameraNumber)

    def getCameraEnableStatus(self, cameraNumber):
        opc = self.def_opcode(0xC011, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc, token1=cameraNumber))

    def enableIllumination(self, cameraNumber):
        opc = self.def_opcode(0xC012, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 1, token1=cameraNumber)

    def disableIllumination(self, cameraNumber):
        opc = self.def_opcode(0xC012, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, 0, token1=cameraNumber)

    def getIlluminationEnableStatus(self, cameraNumber):
        opc = self.def_opcode(0xC012, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc, token1=cameraNumber))

    def setFlasherBias(self, bias):
        opc = self.def_opcode(0xC020, Datatype.UNSIGNED_INT, datasize=2)
        self.cmd.write_opcode(opc, bias)

    def setFlasherMask(self, mask):
        opc = self.def_opcode(0xC021, Datatype.UNSIGNED_INT, datasize=2)
        self.cmd.write_opcode(opc, mask)

    def writeCalSPI(self, data):
        opc = self.def_opcode(0xC0D0, Datatype.BYTEARRAY)
        self.cmd.write_opcode(opc, data)

    def readCalSPI(self, len):
        opc = self.def_opcode(0xC0D0, Datatype.BYTEARRAY)
        return self.cmd.read_opcode(opc, len)

    def setCalSlaveSelect(self, slaveSelect):
        opc = self.def_opcode(0xC0D1, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, slaveSelect)

    # Section C1: Operations associated with cameras
    def writeCameraRegister(self, cameraNumber, value, register):
        opc = self.def_opcode(0xC100, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, value, token1=cameraNumber, token2=register)

    def readCameraRegister(self, cameraNumber, register):
        opc = self.def_opcode(0xC100, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=cameraNumber, token2=register)

    def initCamera(self, cameraNumber):
        opc = self.def_opcode(0xC102, Datatype.VOID)
        self.cmd.write_opcode(opc, token1=cameraNumber)

    def isCameraReady(self, cameraNumber):
        opc = self.def_opcode(0xC103, Datatype.UNSIGNED_INT, datasize=1)
        return bool(self.cmd.poll_opcode(opc, token1=cameraNumber))

    def testCameraSPI(self, cameraNumber, nTrials):
        # Return the number of successful trials, max 255
        if nTrials > 255:
            nTrials = 255;
        opc = self.def_opcode(0xC104, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=cameraNumber, token2=nTrials)

    def setCameraCaptureMode(self, cameraNumber, mode):
        opc = self.def_opcode(0xC105, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, mode, token1=cameraNumber)

    def setCameraGainConversionMode(self, cameraNumber, mode):
        opc = self.def_opcode(0xC106, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, mode, token1=cameraNumber)

    ##### These should have enum'ed STATES
    def getCameraSensorStandby(self, cameraNumber):
        opc = self.def_opcode(0xC107, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=cameraNumber)

    def setCameraSensorStandby(self, cameraNumber, mode):
        opc = self.def_opcode(0xC107, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, mode, token1=cameraNumber)

    def getCameraSensorSSMode(self, cameraNumber):
        opc = self.def_opcode(0xC108, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=cameraNumber)

    def setCameraSensorSSMode(self, cameraNumber, mode):
        opc = self.def_opcode(0xC108, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, mode, token1=cameraNumber)

    def getCameraID(self, cameraNumber):
        opc = self.def_opcode(0xC109, Datatype.STRING, datasize=17)
        return self.cmd.poll_opcode(opc, token1=cameraNumber)

    def setCameraExposureMs(self, cameraNumber, exposureMs):
        opc = self.def_opcode(0xC10A, Datatype.UNSIGNED_INT, datasize=2)
        self.cmd.write_opcode(opc, exposureMs, token1=cameraNumber)

    def setCameraGain(self, cameraNumber, gain):
        opc = self.def_opcode(0xC10B, Datatype.UNSIGNED_INT, datasize=2)
        self.cmd.write_opcode(opc, gain, token1=cameraNumber)

    def captureCameraImage(self, cameraNumber):
        opc = self.def_opcode(0xC10C, Datatype.VOID)
        self.cmd.write_opcode(opc, token1=cameraNumber)

    def isCameraImageReady(self, cameraNumber):
        opc = self.def_opcode(0xC10D, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc, token1=cameraNumber)

    def cameraImageSize(self, cameraNumber):
        return self.cmd.get_fifo_available_bytes(
                              self.cameraFifo, token1=cameraNumber)

    def readCameraImage(self, cameraNumber):
        data = bytearray()
        while self.cameraImageSize(cameraNumber) > 0:
            data.extend(self.cmd.poll_fifo(self.cameraFifo,
                                           token1=cameraNumber))
        self.cmd.reset_fifo(self.cameraFifo, token1=cameraNumber)
        return data

    def downloadCameraImage(self, cameraNumber, filename):
        data = self.readCameraImage(cameraNumber)
        try:
            with open(filename, "wb") as f:
                f.write(data)
        except:
            print("Unable to open file %s" % outFile)

    def writeCameraSensorRegister(self, cameraNumber, value, register):
        registerHighBits = register >> 8
        registerLowBits = register & 0xFF
        if registerHighBits not in [0x30, 0x31, 0x32, 0x33]:
            raise Exception("Unknown image sensor register")
        opcodeNumber = 0xC100 | registerHighBits
        opc = self.def_opcode(opcodeNumber, Datatype.UNSIGNED_INT, datasize=1)
        self.cmd.write_opcode(opc, value,
                              token1=cameraNumber, token2=registerLowBits)

    def readCameraSensorRegister(self, cameraNumber, register):
        registerHighBits = register >> 8
        registerLowBits = register & 0xFF
        if registerHighBits not in [0x30, 0x31, 0x32, 0x33]:
            raise Exception("Unknown image sensor register")
        opcodeNumber = 0xC100 | registerHighBits
        opc = self.def_opcode(opcodeNumber, Datatype.UNSIGNED_INT, datasize=1)
        return self.cmd.poll_opcode(opc,
                        token1=cameraNumber, token2=registerLowBits)


def startXDOMAppEthSession(host="192.168.0.10", port=5012, **kwargs):
    
    session = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if host is None:
        host = options.host
    if port is None:
        port = options.port
    session.connect((host, int(port)))    
    fcntl.fcntl(session, fcntl.F_SETFL, os.O_NONBLOCK)
    return XDOMAppSessionCmdDispatch(session, **kwargs)
