from .test_waveform import parseTestWaveform, waveformNWords
from optparse import OptionParser
import ymodem
import socket
import fcntl
import os
import time
import select
import json
import numpy as np
from contextlib import contextmanager

PROMPT = "\r\n> "

# Iceboot will retry failed I2C sensor reads for up to 2.0 sec.
SENSOR_READ_TIMEOUT = 3.0

def stripStackSize(s):
    ll = len(s.split()[0])
    return s[(ll + 1):]


class IcebootSessionCmd(object):
    
    def __init__(self, comms, debug, fpgaConfigurationFile=None, fpgaEnable=True):
        self.comms = comms
        self.debug = debug
        self.fpgaEnable = fpgaEnable

        # Get past bootloader if present.  This should be harmless if we're
        # already in iceboot
        self.bypassBootloader()
        self.cmd("true setecho\r\n")
        # Save logging output enable status, then disable.
        self.logOutput = self.cmd("disableLogOutput")
        time.sleep(0.1)
        # Clear the buffer
        while True:
            try:
                comms.recv(128)
            except:
                break
        # Clear the stack
        self.cmd("sdrop")

        if fpgaConfigurationFile is not None:
            self.ymodemConfigureCycloneFPGA(fpgaConfigurationFile)

        print("New IceBoot session: FPGA version %x Software version %x %s" %
                               (    self.fpgaVersion(), self.softwareVersion(),
                                    self.softwareId()
                               ))

    def __del__(self):
        # Restore initial logging output enable status
        # TODO destructor does not run upon some terminations, e.g. SIGTERM,
        # leaving final logging state altered from initial state.
        try:
            if self.logOutput == '0':
                self.cmd("disableLogOutput")
            else:
                # Print logging output queue and reenable logging output
                print(self.cmd("printLogOutput"))
                self.cmd("enableLogOutput")
        except:
            pass
        self.close()

    def cmd(self, cmdStr, timeout=1):
        """
        Send cmdStr to Iceboot and return the response as a string

            Keyword Arguments:
            cmdStr      command to send
            timeout     floating point seconds
        """
        output = self.raw_cmd(cmdStr, timeout=timeout)
        try:
            output = output.decode()
        except UnicodeDecodeError:
            print(f'Cant decode {output}')
            out = self.raw_cmd('.s drop')
            print('Running function once again')
            if timeout != 5:
                return self.cmd(cmdStr, timeout=timeout+1)
            else:
                raise ValueError(f'Cant decode {output}.')
        
        if self.debug:
            print("Received %s" % output)

        return output

    def uint16_cmd(self, cmdStr, n_words):
        ''' Send a command to Iceboot and return the response 
        as a tuple of ints 
        n_words is the number of expected words
        '''

        # 2 bytes per 16 bit word
        buff = self.raw_cmd(cmdStr, 2*n_words)        

        unpacked_response = np.frombuffer(buff, np.uint16)

        if self.debug:
            print("Received %s" % str(unpacked_response))

        return unpacked_response


    def raw_cmd(self, cmdStr, n_bytes=None, timeout=1):
        ''' Sends a command and returns the response as a binary buffer
            if n_bytes is not None, raw_cmd will not return unless
            n_bytes have been read from the socket 
            (not including the echo or the prompt) 

            Keyword Arguments:
            cmdStr      command to send
            n_bytes     see comment above
            timeout     floating point seconds
        ''' 
        if self.debug:
            print("SENT: %s" % cmdStr)

        if not cmdStr.endswith("\r\n"):
            cmdStr += "\r\n"

        self.comms.send(cmdStr.encode())
        
        # nbytes to read including the cmdStr and the prompt
        if n_bytes is not None:
            n_bytes_adj = n_bytes + len(PROMPT) + len(cmdStr)

        reply = bytearray()
        while True:        
            new_data = self._read_next(timeout=timeout)
            reply.extend(new_data)
            
            if n_bytes is None or len(reply) >= n_bytes_adj:
                try:
                    if reply[-len(PROMPT):].decode() == PROMPT:
                        break     
                except UnicodeDecodeError:
                    pass

        # Strip original command and prompt and return the reply
        reply = reply[len(cmdStr):-len(PROMPT)]

        return reply        


    def _read_next(self, n_bytes=128, timeout=1):
        ''' Read from socket.

            Keyword Arguments:
            n_bytes     read size
            timeout     floating point seconds

        '''

        rdy = select.select([self.comms], [], [], timeout)        

        if rdy[0]:
            recv_bytes = self.comms.recv(n_bytes)

            return recv_bytes
        else:
            raise IOError('Timeout!')
 
    def _read_n(self, n_bytes, timeout=1):
        buf = bytearray()
        while len(buf) < n_bytes:
            buf.extend(self._read_next(n_bytes - len(buf), timeout=timeout))
            
        return buf

    def bypassBootloader(self):
        try:
            self.cmd("boot", timeout=3)
        except:
            # Send a second "boot" because a prompt may not immediately
            # appear, depending on the specific communications channel.
            self.cmd("boot", timeout=3)

    def fpgaVersion(self):
        if self.fpgaEnable:
            return int(stripStackSize(self.cmd("fpgaVersion .s drop")))
        else:
            return 0xffff

    def fpgaChipID(self):
        return self.cmd('printFPGAChipID')
   
    def softwareVersion(self):
        return int(stripStackSize(self.cmd("softwareVersion .s drop")))

    def softwareId(self):
        return self.cmd("printSoftwareId")

    def stmUUID(self):
        return self.cmd("stmid")

    def domClock(self):
        val = stripStackSize(self.cmd("domClock .s drop drop")).split()
        return ( (int(val[0]) & 0xFFFFFFFF) | 
                 ((int(val[1]) & 0xFFFFFFFF) << 32))

    def fpgaWrite(self, addr, data):
        cmd = ""
        for s in data:
            cmd += "%s " % s
        cmd += "%s %s fpgaWrite" % (len(data), addr)
        self.cmd(cmd)

    def fpgaRead(self, addr, len):
        return [int(s) for s in
                     self.cmd("%s %s printFPGA" % (len, addr)).split()]

    def fpgaDump(self, adr, length):
        return self.uint16_cmd('%d %d dumpFPGA\r\n' % (length, adr), length)

    def DDR3Dump(self, adr, length, lane=2):
        cmd_str = '%d %d %d dumpDDR3\r\n' % (lane, length, adr)
        return self.uint16_cmd(cmd_str, length)

    def memtest(self, n_pages=65536):
        resp = self.cmd('%d memtest' % n_pages, timeout=300)

        words = [word.replace(',', '') for word in resp.split()]

        return int(words[2]) == 1 and int(words[4]) == 1

    def testDEggCPUTrig(self, channel):
        self.cmd("%s testDEggCPUTrig" % channel)

    def testDEggThresholdTrig(self, channel, threshold):
        self.cmd("%s %s testDEggThresholdTrig" % (channel, threshold))

    def testDEggFIRTrig(self, channel, threshold):
        self.cmd("%s %s testDEggFIRTrig" % (channel, threshold))

    def testDEggExternalTrig(self, channel):
        self.cmd("%s testDEggExternalTrig" % (channel))

    def nextDirectWaveformBuffer(self):
        self.cmd("nextDirectWaveformBuffer")
    
    def testDEggWaveformReadout(self):
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

    def startDEggSWTrigStream(self, channel, period_in_ms):
        self.cmd('%d %d 1 startDEggWfmStream\r\n' % (channel, period_in_ms))

    def startDEggThreshTrigStream(self, channel, threshold):
        self.cmd('%d %d 0 startDEggWfmStream\r\n' % (channel, threshold))

    def startDEggFIRTrigStream(self, channel, threshold):
        self.cmd('%d %d 4 startDEggWfmStream\r\n' % (channel, threshold))

    def startDEggExternalTrigStream(self, channel):
        self.cmd('%d %d 2 startDEggWfmStream\r\n' % (channel, 0))

    def startDEggDualChannelTrigStream(self, threshold0, threshold1):
        self.cmd('%d %d 3 startDEggWfmStream\r\n' % (threshold0, threshold1))

    def _recieveRawCmd(self, cmdStr, nBytes, timeout=1):
        if not cmdStr.endswith("\r\n"):
            cmdStr += "\r\n"
        encodedCmd = cmdStr.encode()
        self.comms.send(encodedCmd)
        self._read_n(len(encodedCmd), timeout)
        ret = self._read_n(nBytes, timeout)
        self._receiveRawPrompt()
        return ret

    def readWFMFromStream(self):
        ''' result is returned as an array of uint16s'''
        len_bytes = self._recieveRawCmd("readDEggWfmStream", 4, timeout=10)
        n_words = np.frombuffer(len_bytes, np.uint32)[0]
        wfm_buff = bytearray()
        while (n_words > 0):
            rlen = n_words
            if (rlen > 2048):
                rlen = 2048
            rbytes = 2 * rlen
            wfm_buff.extend(self._recieveRawCmd("readDEggWfmStream",
                                                rbytes, timeout=10))
            n_words -= rlen

        return np.frombuffer(wfm_buff, np.uint16)

    def endStream(self):
        # this message could be anything;
        # sending any data ends the stream
        self.comms.send('STOP\r\n'.encode())

        # empty out the rcv buffer
        while True:
            try:
                self._read_next(timeout=0.1)
            except IOError:
                break

    def startHBufController(self):
        return self.cmd('startHBufController')
    
    def stopHBufController(self):
        return self.cmd('stopHBufController')  

    def flushHBuf(self):
        return self.cmd('flushHBuf')
    
    def initHBufReader(self, startPage, nPages, lane=0):
        return int(self.cmd('%d %d %d HBufReaderInit' % (startPage, nPages, lane)))

    def resetHBufReader(self, startPage, nPages, lane=0):
        return int(self.cmd('%d %d %d HBufReaderReset' % (startPage, nPages, lane)))

    def HBufReaderEmpty(self):
        return int(self.cmd('HBufReaderEmpty'))

    def HBufReaderPop(self):
        ''' returns tuple: (retcode, event_data) '''
        resp = self.raw_cmd('HBufReaderPop')

        # read 4 byte return code
        retcode_buff = resp[:4]
        retcode = int(np.frombuffer(retcode_buff, dtype=np.int32)[0])

        evt_data = None
        if retcode == 1:        
            data_buff = resp[4:]
            evt_data = np.frombuffer(data_buff, np.uint16)

        return retcode, evt_data

    def HBufReaderCurrentPage(self):
        return int(self.cmd('HBufReaderCurrentPage'))

    def setDEggConstReadout(self, channel, preConfig, nSamples):
        self.cmd("%s %s %s setDEggConstReadout" %
                                          (channel, preConfig, nSamples))

    def setDEggVariableReadout(self, channel, preConfig, postConfig):
        self.cmd("%s %s %s setDEggVariableReadout" %
                                          (channel, preConfig, postConfig))

    def setDEggTriggerConditions(self, channel, threshold):
        self.cmd("%s %s setDEggTriggerConditions" % (channel, threshold))

    def enableDEggTrigger(self, channel):
        self.cmd("%s enableDEggTrigger" % (channel))

    def readFlashInterlock(self):
        return int(stripStackSize(self.cmd("readFlashInterlock .s drop"))) == 1

    def readFPGAConfigInterlock(self):
        return int(stripStackSize(
                           self.cmd("readFPGAConfigInterlock .s drop"))) == 1

    def readLIDInterlock(self):
        return int(stripStackSize(self.cmd("readLIDInterlock .s drop"))) == 1

    def readHVInterlock(self):
        return int(stripStackSize(self.cmd("readHVInterlock .s drop"))) == 1

    def resetDAC(self):
        self.cmd("resetDAC")

    def enableHV(self, channel):
        self.cmd("%s enableHV" % channel)

    def disableHV(self, channel):
        self.cmd("%s disableHV" % channel)

    @contextmanager
    def enableDEggHVContext(self, channel):
        """ A runtime context to run with HV enabled, and ensure HV disabled
        when done
        """
        self.enableHV(channel)
        self.setDEggHV(channel, 0)
        try:
            yield
        finally:
            self.setDEggHV(channel, 0)
            self.disableHV(channel)

    def setDEggHV(self, channel, hv):
        self.cmd("%s %s setDEggHV" % (channel, hv))

    def setFIRCoefficients(self, channel, coefficients):
        s = ("%d " % channel)
        for coeff in coefficients:
            s += ("%d " % coeff)
        s += "setDEggFIRCoefficients"
        self.cmd(s)

    def getFIRCoefficients(self, channel):
        ret = self.cmd("%d printDEggFIRCoefficients" % channel)
        return [int(s) for s in ret.split()]
        
    def sloAdcReadChannel(self, channel):
        return float(self.cmd("%d sloAdcReadChannel" % (channel)).split()[3])

    # A few helpful aliases to common sloADC channels...
    def readSloADCTemperature(self):
        return self.sloAdcReadChannel(7)

    def readSloADCLightSensor(self):
        return self.sloAdcReadChannel(6)

    def readSloADC_HVS_Voltage(self, channel):
        if channel in [0,1]:
            return self.sloAdcReadChannel(8+2*channel)
        else:
            return None

    def readSloADC_HVS_Current(self, channel):
        if channel in [0,1]:
            return self.sloAdcReadChannel(9+2*channel)
        else:
            return None

    def setDAC(self, channel, value):
        """
        Set DAC value according to channel letter, e.g. 'A'
        """
        self.cmd("%d %d setDAC" % (ord(channel), value))

    def resetADS4149(self, channel):
        self.cmd("%d resetADS4149" % channel)

    def writeADS4149(self, channel, register, value):
        self.cmd("%d %d %d writeADS4149" % (channel, register, value))
    
    def readADS4149(self, channel, register):
        ret = self.cmd("%d %d readADS4149 .s drop" % (channel, register))
        return int(stripStackSize(ret))

    def _receiveRawPrompt(self):
        prompt = "> "
        ret = ""
        while not ret.endswith(prompt):
            try:
                ret +=  self._read_next(n_bytes=128, timeout=10).decode()
            except UnicodeDecodeError:
                pass

    def _ymodemSend(self, infile, cmd):
        infile = os.path.expanduser(infile)
        if not os.path.exists(infile):
            print("File \"%s\" does not exist" % infile)
            return
        encodedCmd = cmd.encode()
        self.comms.send(encodedCmd)
        self._read_n(len(encodedCmd))
        ymodem.ymodemImpl(self.comms.fileno(), infile, verbose=False)
        # Remove partial prompt
        self._receiveRawPrompt()

    def ymodemConfigureCycloneFPGA(self, infile):
        cmd = "ymodemConfigureCycloneFPGA\r\n"
        self._ymodemSend(infile, cmd)

    def flashID(self):
        return self.cmd("flashID")

    def flashRemove(self, remoteFileName):
        cmdstr = "s\" %s\" flashRemove" % remoteFileName
        self.cmd(cmdstr)

    def flashClear(self):
        self.cmd("flashClear")

    def flashCat(self, fileName):
        return self.cmd("s\" %s\" flashCat" % fileName)

    def flashFileGet(self, flashFile, localFile=None):
        data = self.raw_cmd("s\" %s\" flashCat" % flashFile)
        if localFile is None:
            localFile = flashFile

        try:
            with open(localFile, "w") as f:
                f.write(str(data))
        except:
            print("Unable to open local file %s" % localFile)

    def ymodemFlashUpload(self, remoteFileName, infile):
        cmd = "s\" %s\" ymodemFlashUpload\r\n" % remoteFileName
        self._ymodemSend(infile, cmd)

    def ymodemFlashUploadBytes(self, remoteFileName, content):
        # This exists mainly for the flash STF test
        cmd = ("s\" %s\" ymodemFlashUpload\r\n" % remoteFileName).encode()
        self.comms.send(cmd)
        self._read_n(len(cmd))
        ymodem.ymodemSendContent(self.comms.fileno(), content,
                                 remoteFileName, verbose=False)
        # Remove partial prompt
        prompt = "> "
        ret = ""
        while not ret.endswith(prompt):
            try:
                ret +=  self._read_next(n_bytes=128, timeout=10).decode()
            except UnicodeDecodeError:
                pass

    def flashConfigureCycloneFPGA(self, remoteFileName, timeout=10):
        cmdstr = "s\" %s\" flashConfigureCycloneFPGA" % remoteFileName
        return self.cmd(cmdstr, timeout=timeout)

    def flashLS(self):
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

    def close(self):
        '''
        calls socket.shutdown and socket.close on iceboot's "comms" socket
        attribute
        '''

        if self.comms:
            try:
                self.comms.shutdown(socket.SHUT_RDWR)
                self.comms.close()
            except OSError:
                pass

    def reboot(self):
        try:
            self.cmd("reboot", timeout=3)
        except:
            self.bypassBootloader()

    def readAccelerometerXYZ(self):
        out = self.cmd("getAccelerationXYZ printAccelerationXYZ")
        try:
            out = out.replace(',', ' ')
            out = out.replace('(', ' ')
            out = out.replace(')', ' ')
            data = out.split()
            return [float(x) for x in data[:3]]
        except:
            return None

    def readMagnetometerXYZ(self):
        out = self.cmd("getBFieldXYZ printBFieldXYZ")
        try:
            out = out.replace(',', ' ')
            out = out.replace('(', ' ')
            out = out.replace(')', ' ')
            data = out.split()
            return [float(x) for x in data[:3]]
        except:
            return None

    def readPressure(self):
        out = self.cmd("getPressure printPressure", timeout=SENSOR_READ_TIMEOUT)
        try:
            return float(out.split()[0])
        except:
            return None

    def readAccelerometerTemperature(self):
        try:
            return float(self.cmd("getAccelerationTemperature printSensorsTemperature").split()[0])
        except:
            return None

    def readMagnetometerTemperature(self):
        try:
            return float(self.cmd("getBFieldTemperature printSensorsTemperature").split()[0])
        except:
            return None

    def readPressureSensorTemperature(self):
        try:
            return float(self.cmd("getPressureSensorTemperature printSensorsTemperature").split()[0])
        except:
            return None

    def enableScalers(self, channel, periodUS, deadtimeCycles):
        self.cmd("%d %d %d enableScalers" % (
                              channel, periodUS, deadtimeCycles))

    def getScalerCount(self, channel):
        out = stripStackSize(self.cmd(
            "%d getScalerCount .s drop" % (channel)))
        try:
            count = int(out)
        except ValueError:
            print(f'Catching "{out}". Rerunning.')
            return self.getScalerCount(channel)
        else:
            return count

    def enableDCDCFivePhase(self):
        self.cmd("enableDCDCFivePhase")

    def enableFEPulser(self, channel, periodUS):
        self.cmd("%d %d enableFEPulser" % (channel, periodUS))

    def disableFEPulser(self, channel):
        self.cmd("%d disableFEPulser" % (channel))

    def enableCalibrationTrigger(self, periodUS):
        self.cmd("%d enableCalibrationTrigger" % periodUS)

    def disableCalibrationTrigger(self):
        self.cmd("disableCalibrationTrigger")

    def enableCalibrationPower(self):
        self.cmd("enableCalibrationPower")

    def disableCalibrationPower(self):
        self.cmd("disableCalibrationPower")

    def setCalibrationSlavePowerMask(self, mask):
        self.cmd("%d setCalibrationSlavePowerMask" % mask)

    def setCameraEnableMask(self, mask):
        self.cmd("%d setCameraEnableMask" % mask)

    def setFlasherBias(self, bias):
        self.cmd("%d setFlasherBias" % bias)

    def setFlasherMask(self, mask):
        self.cmd("%d setFlasherMask" % mask)

    def isCameraReady(self, cam):
        return bool(int(stripStackSize(self.cmd("%d isCameraReady .s drop" % (cam)))))

    def testCameraSPI(self, cam, trials):
        cmdStr = "%d %d testCameraSPI .s drop" % (cam, trials)
        return int(stripStackSize(self.cmd(cmdStr, timeout=180)))

    def writeCameraRegister(self, cam, value, reg):
        self.cmd("%d %d %d writeCameraRegister" % (cam, value, reg))

    def readCameraRegister(self, cam, register):
        return int(stripStackSize(self.cmd("%d %d readCameraRegister .s drop" % (cam, register))))
                
    def initCamera(self, cameraNumber):
        self.cmd("%d initCamera" % cameraNumber, timeout=10)

    def captureCameraImage(self, cameraNumber):
        self.cmd("%d captureCameraImage" % cameraNumber, timeout=10)

    def cameraImageSize(self, cameraNumber):
        return int(stripStackSize(self.cmd(
                      "%d cameraImageSize .s drop" % cameraNumber)))

    def sendCameraImage(self, cameraNumber, outFile):
        size = self.cameraImageSize(cameraNumber)
        data = self.raw_cmd("%d sendCameraImage" % cameraNumber, timeout=100)
        try:
            with open(outFile, "wb") as f:
                f.write(str(data))
        except:
            print("Unable to open file %s" % outFile)

    def saveCameraImageFile(self, cameraNumber, flashFile):
        resp = self.cmd("s\" %s\" %d saveCameraImage" % (flashFile,
        cameraNumber), timeout=5000)

    def setCameraExposureMs(self, cameraNumber, exposureMs):
        self.cmd("%d %d setCameraExposureMs" % (cameraNumber, exposureMs))

    def setCameraGain(self, cameraNumber, gain):
        self.cmd("%d %d setCameraGain" % (cameraNumber, gain))

    def setCameraCaptureMode(self, cameraNumber, mode):
        self.cmd("%d %d setCameraCaptureMode" % (cameraNumber, mode))

    def setCameraCaptureWindow(self, cameraNumber, horizPStart, vertPStart,
                               hoirzWidth, vertWidth, vertOB):
        self.cmd("%d %d %d %d %d %d setCameraCaptureWindow" %
                           (cameraNumber, horizPStart, vertPStart,
                            hoirzWidth, vertWidth, vertOB))

    def setCameraGainConversionMode(self, cameraNumber, mode):
        self.cmd("%d %d setCameraGainConversionMode" % (cameraNumber, mode))

    def getCameraSensorStandby(self, cameraNumber):
        return int(self.cmd("%d getCameraSensorStandby" % cameraNumber))

    def setCameraSensorStandby(self, cameraNumber, mode):
        self.cmd("%d %d setCameraSensorStandby" % (cameraNumber, mode))

    def getCameraSensorSSMode(self, cameraNumber):
        return int(self.cmd("%d getCameraSensorSSMode" % cameraNumber))

    def setCameraSensorSSMode(self, cameraNumber, mode):
        self.cmd("%d %d setCameraSensorSSMode" % (cameraNumber, mode))

    def getCameraID(self, cameraNumber):
        return self.cmd("%d getCameraID" % cameraNumber)

    def writeCameraSensorRegister(self, cameraNumber, value, reg):
        self.cmd("%d %d %d writeCameraSensorRegister" % (cameraNumber, value, reg))

    def readCameraSensorRegister(self, cameraNumber, reg):
        return int(stripStackSize(self.cmd("%d %d readCameraSensorRegister .s drop" % (cameraNumber, reg))))

    def flushCameraBuffer(self, cameraNumber):
        self.cmd("%d flushCameraBuffer" % cameraNumber)

    def calibrateDEggCh0Timing(self):
        return json.loads(self.cmd("calibrateDEggCh0Timing"))

    def calibrateDEggCh1Timing(self):
        return json.loads(self.cmd("calibrateDEggCh1Timing"))

    def calibrateDEggBaseline(self, channel):
        return json.loads(self.cmd("%d calibrateDEggBaseline" % channel, timeout=10))

    # Enable logging output at current logging level.
    # Return previous logging output enable status: 0 or 1
    def enableLogOutput(self):
        return self.cmd("enableLogOutput")

    # Disable logging output at current logging level.
    # Return previous logging output enable status: 0 or 1
    def disableLogOutput(self):
        return self.cmd("disableLogOutput")

    # Set logging severity threshold level.
    # see https://wiki.icecube.wisc.edu/index.php/STM32_Logging
    # Return previous logging severity threshold level.
    def setLogLevel(self, level):
        return self.cmd(str(level) + " setLogLevel")

    # Return logging severity threshold level.
    # see https://wiki.icecube.wisc.edu/index.php/STM32_Logging
    def getLogLevel(self):
        return self.cmd("getLogLevel")

    # Return queued multi-line logging records string
    def printLogOutput(self):
        return self.cmd("printLogOutput")

    # Clear queued logging records.
    def clearLogOutput(self):
        self.cmd("clearLogOutput")


def configureOptions(parser):
    # Only support Ethernet host/port at the moment
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default="192.168.0.10")
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default="5012")
    parser.add_option("--debug", dest="debug", action="store_true",
                      help="Print board I/O stdout", default=False)
    parser.add_option("--fpgaConfigurationFile", dest="fpgaConfigurationFile",
                      help="FPGA configuration file", default=None)
    parser.add_option("--nofpga", dest="fpgaEnable", action="store_false",
                      help="Disable FPGA. Default: FPGA enabled", default=True)
    parser.add_option("--setBaseline", dest="setBaseline", type="float",
                      help="Set ADC baseline", default=None)


def init(options, fpgaConfigurationFile=None, host=None, port=None, fpgaEnable=True):
    # Default now is socket.  Add interfaces as needed
    session = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if host is None:
        host = options.host
    if port is None:
        port = options.port
    session.connect((host, int(port)))    
    fcntl.fcntl(session, fcntl.F_SETFL, os.O_NONBLOCK)
    if fpgaConfigurationFile == None:
        fpgaConfigurationFile = options.fpgaConfigurationFile
    return IcebootSessionCmd(session, options.debug,
                        fpgaConfigurationFile=fpgaConfigurationFile,fpgaEnable=fpgaEnable)
