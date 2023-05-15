import json
from contextlib import contextmanager

from .xdom import xDOM
from ..iceboot_comms import IceBootComms
from ..mDOMChargeStamp import parseChargeStampBlock


class DEgg(xDOM):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)

    def memtest(self, n_pages: int=65536) -> bool:
        resp = self.cmd('%d memtest' % n_pages, timeout=300)
        words = [word.replace(',', '') for word in resp.split()]
        return int(words[2]) == 1 and int(words[4]) == 1

    def testDEggCPUTrig(self, channel: int) -> None:
        self.cmd("%d testDEggCPUTrig" % channel)

    def testDEggThresholdTrig(self, channel: int, threshold: int) -> None:
        self.cmd("%d %d testDEggThresholdTrig" % (channel, threshold))

    def testDEggFIRTrig(self, channel: int, threshold: int) -> None:
        self.cmd("%d %d testDEggFIRTrig" % (channel, threshold))

    def testDEggExternalTrig(self, channel: int) -> None:
        self.cmd("%d testDEggExternalTrig" % channel)

    def setDEggExtTrigSourceSMA(self) -> None:
        self.cmd("setDEggExtTrigSourceSMA")

    def setDEggExtTrigSourceICM(self) -> None:
        self.cmd("setDEggExtTrigSourceICM")

    def startDEggSWTrigStream(self, channel: int, period_in_ms: int) -> None:
        self.cmd('%d %d 1 startDEggWfmStream\r\n' % (channel, period_in_ms))

    def startDEggThreshTrigStream(self, channel: int, threshold: int) -> None:
        self.cmd('%d %d 0 startDEggWfmStream\r\n' % (channel, threshold))

    def startDEggFIRTrigStream(self, channel: int, threshold: int) -> None:
        self.cmd('%d %d 4 startDEggWfmStream\r\n' % (channel, threshold))

    def startDEggExternalTrigStream(self, channel: int) -> None:
        self.cmd('%d %d 2 startDEggWfmStream\r\n' % (channel, 0))

    def startDEggDualChannelTrigStream(self, threshold0: int, threshold1: int) -> None:
        self.cmd('%d %d 3 startDEggWfmStream\r\n' % (threshold0, threshold1))

    def startDEggDualChannelFIRTrigStream(self, threshold0: int, threshold1: int) -> None:
        self.cmd('%d %d 5 startDEggWfmStream\r\n' % (threshold0, threshold1))

    @staticmethod
    def _getDEggChannelMask(channel):
        mask = 0x3
        if channel is not None:
            mask = (1 << channel)
        if mask > 0x3:
            raise Exception("Bad channel: %d" % channel)
        return mask

    def startDEggADCHBufTrigStream(self, channel: int=None) -> None:
        ch = self._getDEggChannelMask(channel)
        self.cmd('%d 0 64 startDEggWfmStream\r\n' % ch)

    def startDEggFIRHBufTrigStream(self, channel: int=None) -> None:
        ch = self._getDEggChannelMask(channel)
        self.cmd('%d 0 68 startDEggWfmStream\r\n' % ch)

    def startDEggExternalHBufTrigStream(self, channel: int=None) -> None:
        ch = self._getDEggChannelMask(channel)
        self.cmd('%d 0 66 startDEggWfmStream\r\n' % ch)

    def isDEggHitBufferEmpty(self) -> bool:
        return bool(int(self.cmd("isDEggHitBufferEmpty .s drop",
                                 strip_stack=True)))

    def DEggReadChargeBlock(self, backwardBins: int, forwardBins: int,
                            len: int=65536, timeout: float=10.0) -> dict:
        block = self.comms.receiveRawCmd("%d %d %d readDEggChargeBlock" %
                                         (len, backwardBins, forwardBins), len,
                                         timeout=timeout)
        return parseChargeStampBlock(block)

    def DEggReadChargeBlockFixed(self, firstBin: int, lastBin: int,
                                 len: int=65536, timeout: float=10.0) -> dict:
        block = self.comms.receiveRawCmd("%d %d %d readDEggChargeBlockFixed" %
                                         (len, firstBin, lastBin), len,
                                         timeout=timeout)
        return parseChargeStampBlock(block)

    def setDEggConstReadout(self, channel: int, preConfig: int,
                            nSamples: int) -> None:
        self.cmd("%d %d %d setDEggConstReadout" %
                 (channel, preConfig, nSamples))

    def setDEggVariableReadout(self, channel: int, preConfig: int,
                               postConfig: int) -> None:
        self.cmd("%d %d %d setDEggVariableReadout" %
                 (channel, preConfig, postConfig))

    # Depricated, check return for compatibility with MCU version < 0x3A
    def setDEggTriggerConditions(self, channel: int, threshold: int) -> None:
        if len(self.cmd("%d %d setDEggADCTriggerThreshold" % (
                channel, threshold))) > 0:
            # Clear MCU stack and issue pre-0x3A commands
            self.cmd("sdrop")
            self.cmd("%d %d setDEggTriggerConditions" % (channel, threshold))

    # Depricated, check return for compatibility with MCU version < 0x3A
    def enableDEggTrigger(self, channel: int) -> None:
        if len(self.cmd("%d enableDEggADCTrigger" % (channel))) > 0:
            # Clear MCU stack and issue pre-0x3A commands
            self.cmd("sdrop")
            self.cmd("%d enableDEggTrigger" % (channel))

    def setDEggADCTriggerThreshold(self, channel: int, threshold: int) -> None:
        self.cmd("%d %d setDEggADCTriggerThreshold" % (channel, threshold))

    def setDEggFIRTriggerThreshold(self, channel: int, threshold: int) -> None:
        self.cmd("%d %d setDEggFIRTriggerThreshold" % (channel, threshold))

    def disableDEggTriggers(self, channel: int) -> None:
        self.cmd("%d disableDEggTriggers" % (channel))

    def enableDEggADCTrigger(self, channel: int) -> None:
        self.cmd("%d enableDEggADCTrigger" % (channel))

    def enableDEggFIRTrigger(self, channel: int) -> None:
        self.cmd("%d enableDEggFIRTrigger" % (channel))

    def enableDEggExternalTrigger(self, channel: int) -> None:
        self.cmd("%d enableDEggExternalTrigger" % (channel))

    # no @requiresLightSensorPmtHvEnable decorator - used by non HV DAC channels
    def setDAC(self, channel: int, value: int) -> None:
        """
        Set DAC value according to channel letter, e.g. 'A'
        """
        if (value < 0) or (value > 65535):
            raise Exception("Bad DAC value: %d" % value)
        self.cmd("%d %d setDAC" % (ord(channel), value))

    def setBaselineDAC(self, channel: int, value: int) -> None:
        if (channel < 0) or (channel > 1):
            raise Exception("Bad channel: %s" % channel)
        dac_channel = 'A'
        if channel == 1:
            dac_channel = 'B'
        self.setDAC(dac_channel, value)

    def resetDAC(self) -> None:
        self.cmd("resetDAC")

    @xDOM.requiresHVInterlock
    def enableHV(self, channel: int) -> None:
        self.cmd("%d enableHV" % channel)

    def disableHV(self, channel: int) -> None:
        self.cmd("%d disableHV" % channel)

    def DEggHVEnabled(self, channel: int) -> bool:
        return int(self.cmd("%d DEggHVEnabled .s drop" % channel,
                            strip_stack=True)) == 1

    @xDOM.requiresHVInterlock
    def enableHV(self, channel: int) -> None:
        self.cmd("%d enableHV" % channel)

    @xDOM.requiresLightSensorPmtHvEnable(1)
    def setDEggHV(self, channel: int, hv: int) -> None:
        if self.interlockChecksEnabled:
            try:
                if not self.DEggHVEnabled(channel):
                    raise Exception("DEgg channel %s HV not enabled" % channel)
            except ValueError:
                # Support for Iceboot <0x30, which doesn't support this check
                self.cmd("sdrop")
        self.cmd("%d %d setDEggHV" % (channel, hv))

    def getFIRCoefficients(self, channel: int) -> list:
        ret = self.cmd("%d printDEggFIRCoefficients" % channel)
        return [int(s) for s in ret.split()]

    def resetADS4149(self, channel: int) -> None:
        self.cmd("%d resetADS4149" % channel)

    def writeADS4149(self, channel: int, register: int, value: int) -> None:
        self.cmd("%d %d %d writeADS4149" % (channel, register, value))

    def readADS4149(self, channel: int, register: int) -> int:
        return int(self.cmd("%d %d readADS4149 .s drop" % (channel,
                                                           register),
                            strip_stack=True))

    # A few helpful aliases to common sloADC channels...
    def readSloADCTemperature(self) -> float:
        return self.sloAdcReadChannel(7)

    def readSloADCLightSensor(self) -> float:
        return self.sloAdcReadChannel(6)

    def readSloADC_HVS_Voltage(self, channel: int) -> float:
        if channel in [0, 1]:
            return self.sloAdcReadChannel(8 + 2 * channel)
        else:
            return None

    def readSloADC_HVS_Current(self, channel: int) -> float:
        if channel in [0, 1]:
            return self.sloAdcReadChannel(9 + 2 * channel)
        else:
            return None

    def enableScalers(self, channel: int,
                      periodUS: int, deadtimeCycles: int) -> None:
        self.cmd("%d %d %d enableScalers" % (
            channel, periodUS, deadtimeCycles))

    def getScalerCount(self, channel: int) -> int:
        return int(self.cmd("%d getScalerCount .s drop" % (channel),
                            strip_stack=True))

    def enableDCDCFivePhase(self) -> None:
        self.cmd("enableDCDCFivePhase")

    def enableFEPulser(self, channel: int, periodUS: int) -> None:
        self.cmd("%d %d enableFEPulser" % (channel, periodUS))

    def disableFEPulser(self, channel: int) -> None:
        self.cmd("%d disableFEPulser" % (channel))

    def enableCalibrationTrigger(self, periodUS: int) -> None:
        self.cmd("%d enableCalibrationTrigger" % periodUS)

    def disableCalibrationTrigger(self) -> None:
        self.cmd("disableCalibrationTrigger")

    @xDOM.requiresLIDInterlock
    def setFlasherBias(self, bias: int) -> None:
        self.cmd("%d setFlasherBias" % bias)

    @xDOM.requiresLIDInterlock
    def setFlasherMask(self, mask: int) -> None:
        self.cmd("%d setFlasherMask" % mask)

    def calibrateDEggCh0Timing(self) -> dict:
        return json.loads(self.cmd("calibrateDEggCh0Timing"))

    def calibrateDEggCh1Timing(self) -> dict:
        return json.loads(self.cmd("calibrateDEggCh1Timing"))

    def calibrateDEggBaseline(self, channel: int) -> dict:
        return json.loads(
            self.cmd("%d calibrateDEggBaseline" % channel, timeout=10))

    def setDEggBaseline(self, channel: int, baselineValue: float) -> None:
        cal = self.calibrateDEggBaseline(channel)
        slope = float(cal["slope"])
        intercept = float(cal["intercept"])
        if (not cal["isValid"]) or slope == 0.:
            raise Exception("Baseline calibration failed: %s" % cal)
        dac_setting = int((baselineValue - intercept) / slope)
        self.setBaselineDAC(channel, dac_setting)

    def setFIRCoefficients(self, channel: int, coefficients: list) -> None:
        s = ("%d " % channel)
        for coeff in coefficients:
            s += ("%d " % coeff)
        s += "setDEggFIRCoefficients"
        self.cmd(s)

    @contextmanager
    def enableDEggHVContext(self, channel: int) -> None:
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
