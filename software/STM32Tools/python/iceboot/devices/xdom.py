import functools

import numpy as np

from .xdevice import xDevice
from ..iceboot_comms import IceBootComms
from ..test_waveform import parseTestWaveform, waveformNWords


class xDOM(xDevice):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)

    def fpgaVersion(self) -> int:
        return int(self.cmd("fpgaVersion .s drop", strip_stack=True))

    def fpgaChipID(self) -> str:
        return self.cmd('printFPGAChipID')

    def fpgaRead(self, addr: int, len: int) -> list:
        return [int(s) for s in
                self.cmd("%d %d printFPGA" % (len, addr)).split()]

    def fpgaWrite(self, addr: int, data: list) -> None:
        cmd = ""
        for s in data:
            cmd += "%s " % s
        cmd += "%d %d fpgaWrite" % (len(data), addr)
        self.cmd(cmd)

    def fpgaDump(self, adr: int, length: int) -> np.ndarray:
        return self.uint16_cmd('%d %d dumpFPGA\r\n' % (length, adr), length)

    def nextDirectWaveformBuffer(self) -> None:
        self.cmd("nextDirectWaveformBuffer")

    def testDEggWaveformReadout(self) -> dict:
        nwords = 0
        dpramcnt = self.fpgaRead(0xDFE, 1)[0]
        if (dpramcnt >= 8):
            version = (int(self.fpgaDump(0, 1)) >> 8) & 0xFF
            n_words = waveformNWords(self.fpgaDump(1, 1), version)
        else:
            return None
        wf_data = []
        while n_words > 0:
            rcnt = n_words
            if rcnt > 2048:
                rcnt = 2048
            wf_data.extend(self.fpgaDump(0, rcnt))
            n_words -= rcnt
            self.nextDirectWaveformBuffer()
        return parseTestWaveform(wf_data)

    def isHitBufferOverflown(self) -> bool:
        return bool(int(self.cmd("isHitBufferOverflown .s drop",
                                 strip_stack=True)))

    def stopHitBuffer(self) -> None:
        self.cmd("stopHitBuffer")

    def readWFMFromStream(self) -> np.ndarray:
        ''' result is returned as an array of uint16s'''
        len_bytes = self.comms.receiveRawCmd("readDEggWfmStream", 4,
                                             timeout=10)
        n_words = np.frombuffer(len_bytes, np.uint32)[0]
        wfm_buff = bytearray()
        while (n_words > 0):
            rlen = n_words
            if (rlen > 2048):
                rlen = 2048
            rbytes = 2 * rlen
            wfm_buff.extend(self.comms.receiveRawCmd("readDEggWfmStream",
                                                     rbytes, timeout=10))
            n_words -= rlen
        return np.frombuffer(wfm_buff, np.uint16)

    def requiresHVInterlock(func):
        def wrapper(self, *args, **kwargs):
            self._interlockWrapperCheck(self.readHVInterlock, "PMT HV")
            return func(self, *args, **kwargs)

        return wrapper

    # TODO Redundant declaration with xDevice
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

    def requiresLIDInterlock(func):
        def wrapper(self, *args, **kwargs):
            self._interlockWrapperCheck(self.readLIDInterlock, "LID")
            return func(self, *args, **kwargs)

        return wrapper

    @requiresLIDInterlock
    def enableCalibrationPower(self) -> None:
        self.cmd("enableCalibrationPower")

    @requiresLIDInterlock
    def disableCalibrationPower(self) -> None:
        self.cmd("disableCalibrationPower")

    @requiresLIDInterlock
    def setCalibrationSlavePowerMask(self, mask: int) -> None:
        self.cmd("%d setCalibrationSlavePowerMask" % mask)

    @requiresLIDInterlock
    def setCameraEnableMask(self, mask: int) -> None:
        self.cmd("%d setCameraEnableMask" % mask)

    @requiresLIDInterlock
    def isCameraReady(self, cameraNumber: int) -> bool:
        return bool(int(self.cmd("%d isCameraReady .s drop" % (cameraNumber),
                                                             strip_stack=True)))

    @requiresLIDInterlock
    def writeCameraRegister(self, cameraNumber: int, value: int, reg: int) -> None:
        self.cmd("%d %d %d writeCameraRegister" % (cameraNumber, value, reg))

    @requiresLIDInterlock
    def readCameraRegister(self, cameraNumber: int, register: int) -> int:
        return int(self.cmd("%d %d readCameraRegister .s drop" % (cameraNumber,
                                                                  register),
                                                                strip_stack=True))

    @requiresLIDInterlock
    def initCamera(self, cameraNumber: int) -> None:
        self.cmd("%d initCamera" % cameraNumber, timeout=10)

    @requiresLIDInterlock
    def captureCameraImage(self, cameraNumber: int) -> None:
        self.cmd("%d captureCameraImage" % cameraNumber, timeout=10)

    @requiresLIDInterlock
    def cameraImageSize(self, cameraNumber: int) -> int:
        return int(self.cmd("%d cameraImageSize .s drop" % cameraNumber,
                            strip_stack=True))

    @requiresLIDInterlock
    def sendCameraImage(self, cameraNumber: int, outFile: str) -> None:
        size = self.cameraImageSize(cameraNumber)
        data = None
        if outFile.endswith(".gz"):
            data = self.comms.receiveGZDataTransfer(
                                 "%d sendGZCameraImage" % cameraNumber)
        else:
            data = self.raw_cmd("%d sendCameraImage" % cameraNumber,
                                n_bytes=size, timeout=100)
        try:
            with open(outFile, "wb") as f:
                f.write(data)
        except:
            print("Unable to open file %s" % outFile)

    def setCalSPIFastMode(self) -> None:
        self.cmd("setCalSPIFastMode")

    def setCalSPISlowMode(self) -> None:
        self.cmd("setCalSPISlowMode")

    @requiresLIDInterlock
    def saveCameraImageFile(self, cameraNumber: int, flashFile: str) -> None:
        resp = self.cmd("s\" %s\" %d saveCameraImage" % (flashFile,
                                                         cameraNumber),
                        timeout=5000)

    @requiresLIDInterlock
    def setCameraExposureMs(self, cameraNumber: int, exposureMs: int) -> None:
        self.cmd("%d %d setCameraExposureMs" % (cameraNumber, exposureMs))

    @requiresLIDInterlock
    def setCameraGain(self, cameraNumber: int, gain: int) -> None:
        self.cmd("%d %d setCameraGain" % (cameraNumber, gain))

    @requiresLIDInterlock
    def setCameraNFrames(self, cameraNumber: int, nFrames: int) -> None:
        self.cmd("%d %d setCameraNFrames" % (cameraNumber, nFrames))

    @requiresLIDInterlock
    def setCameraCaptureMode(self, cameraNumber: int, mode: int) -> None:
        self.cmd("%d %d setCameraCaptureMode" % (cameraNumber, mode))

    @requiresLIDInterlock
    def setCameraCaptureWindow(self, cameraNumber: int, horizPStart: int,
                               vertPStart: int, hoirzWidth: int,
                               vertWidth: int, vertOB: int) -> None:
        self.cmd("%d %d %d %d %d %d setCameraCaptureWindow" %
                 (cameraNumber, horizPStart, vertPStart,
                  hoirzWidth, vertWidth, vertOB))

    @requiresLIDInterlock
    def setCameraGainConversionMode(self, cameraNumber: int, mode: int) -> None:
        self.cmd("%d %d setCameraGainConversionMode" % (cameraNumber, mode))

    @requiresLIDInterlock
    def getCameraSensorStandby(self, cameraNumber: int) -> int:
        return int(self.cmd("%d getCameraSensorStandby" % cameraNumber))

    @requiresLIDInterlock
    def setCameraSensorStandby(self, cameraNumber: int, mode: int) -> None:
        self.cmd("%d %d setCameraSensorStandby" % (cameraNumber, mode))

    @requiresLIDInterlock
    def getCameraSensorSSMode(self, cameraNumber: int) -> int:
        return int(self.cmd("%d getCameraSensorSSMode" % cameraNumber))

    @requiresLIDInterlock
    def setCameraSensorSSMode(self, cameraNumber: int, mode: int) -> None:
        self.cmd("%d %d setCameraSensorSSMode" % (cameraNumber, mode))

    @requiresLIDInterlock
    def getCameraID(self, cameraNumber: int) -> str:
        return self.cmd("%d getCameraID" % cameraNumber)

    @requiresLIDInterlock
    def writeCameraSensorRegister(self, cameraNumber: int, value: int, reg: int) -> None:
        self.cmd(
            "%d %d %d writeCameraSensorRegister" % (cameraNumber, value, reg))

    @requiresLIDInterlock
    def readCameraSensorRegister(self, cameraNumber: int, reg: int) -> int:
        return int(self.cmd("%d %d readCameraSensorRegister .s drop" % (
            cameraNumber, reg), strip_stack=True))

    @requiresLIDInterlock
    def flushCameraBuffer(self, cameraNumber: int) -> None:
        self.cmd("%d flushCameraBuffer" % cameraNumber)

    def flashConfigureFPGA(self, remoteFileName: str, timeout: float=10.0) -> None:
        cmdstr = "s\" %s\" flashConfigureFPGA" % remoteFileName
        self.cmd(cmdstr, timeout=timeout)

    # Alias to preserve compatibility with STF and FAT scripts
    def flashConfigureCycloneFPGA(self, remoteFileName: str, timeout: float=10.0) -> None:
        cmdstr = "s\" %s\" flashConfigureFPGA" % remoteFileName
        self.cmd(cmdstr, timeout=timeout)

    def unconfigureFPGA(self) -> None:
        self.cmd("unconfigureFPGA")

    def DDR3Dump(self, adr: int, length: int, lane: int=2) -> np.ndarray:
        cmd_str = '%d %d %d dumpDDR3\r\n' % (lane, length, adr)
        return self.uint16_cmd(cmd_str, length)

    def _readWFBlockRaw(self, nBytes: int) -> list:
        wfm_buff = bytearray()
        cmd = ("%d readDEggWfmBlock" % nBytes)
        wfm_buff.extend(self.comms.receiveRawCmd(cmd, nBytes, timeout=10))
        ret = []
        idx = 0
        while (True):
            if (idx + 4) >= len(wfm_buff):
                break
            n_words = np.frombuffer(wfm_buff[idx:idx + 4], np.uint32)[0]
            idx += 4
            if n_words == 0:
                break
            nBytes = n_words * 2
            wfData = wfm_buff[idx:idx + nBytes]
            ret.append(parseTestWaveform(np.frombuffer(wfData, np.uint16)))
            idx += nBytes
        return ret

    def readWFBlock(self, nBytes: int=66000):
        return self._readWFBlockRaw(nBytes)

    @requiresLIDInterlock
    def testCameraSPI(self, cameraNumber: int, trials: int) -> int:
        cmdStr = "%d %d testCameraSPI .s drop" % (cameraNumber, trials)
        return int(self.cmd(cmdStr, strip_stack=True, timeout=180))

    def domClock(self) -> int:
        val = self.cmd("domClock .s drop drop", strip_stack=True).split()
        return ((int(val[0]) & 0xFFFFFFFF) |
                ((int(val[1]) & 0xFFFFFFFF) << 32))

    def sloAdcReadChannel(self, channel: int) -> float:
        return float(self.cmd("%d sloAdcReadChannel" % (channel)).split()[3])

    def sloAdcReadAll(self) -> str:
        return self.cmd("sloAdcReadAll")

