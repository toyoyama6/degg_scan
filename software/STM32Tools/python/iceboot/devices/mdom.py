import json
import math
from contextlib import contextmanager

from .xdom import xDOM
from ..iceboot_comms import IceBootComms
from ..mDOMChargeStamp import parseChargeStampBlock


class mDOM(xDOM):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)

    @staticmethod
    def _mDOMAllDACValueString(valueMap):
        out = ""
        for i in range(24):
            out += "%d " % valueMap[i]
        return out

    @staticmethod
    def _mDOMGetAllScalerCountMap(outStr):
        counts = outStr.split()
        if len(counts) != 24:
            raise Exception("Expected 24 counts, got %d" % len(counts))
        out = {}
        for i in range(24):
            out[i] = int(counts[i])
        return out

    @contextmanager
    def mDOMEnableHVContext(self) -> None:
        # A runtime context to ensure HV is disabled when finished
        self.mDOMEnableHV()
        try:
            yield
        finally:
            self.mDOMDisableHV()

    def mDOMReadChargeBlock(self, backwardBins: int, forwardBins: int,
                            len: int=65536, timeout: float=10.0) -> dict:
        block = self.comms.receiveRawCmd("%d %d %d mDOMReadChargeBlock" %
                                         (len, backwardBins, forwardBins), len,
                                         timeout=timeout)
        return parseChargeStampBlock(block)

    def mDOMReadChargeBlockFixed(self, firstBin: int, lastBin: int,
                                 len: int=65536, timeout: float=10.0) -> dict:
        block = self.comms.receiveRawCmd("%d %d %d mDOMReadChargeBlockFixed" %
                                         (len, firstBin, lastBin), len,
                                         timeout=timeout)
        return parseChargeStampBlock(block)

    def mDOMHVEnabled(self) -> bool:
        return int(self.cmd("mDOMHVEnabled .s drop", strip_stack=True)) == 1

    # Reset all mDOM AFE DACs
    def mDOMResetDACs(self) -> None:
        self.cmd("mDOMResetDACs")

    # Set the discriminator DAC value for the given mDOM channel
    def mDOMSetDiscThreshDAC(self, channel: int, dacValue: int) -> None:
        self.cmd("%d %d mDOMSetDiscThreshDAC" % (channel, dacValue))

    # Set all discriminator DAC values to those supplied in the channel map
    def mDOMSetAllDiscThreshDACs(self, dacValueMap: dict) -> None:
        valueString = self._mDOMAllDACValueString(dacValueMap)
        self.cmd("%s mDOMSetAllDiscThreshDACs" % valueString)

    # Set the ADC bias baseline DAC value for the given mDOM channel
    def mDOMSetADCBiasDAC(self, channel: int, dacValue: int) -> None:
        self.cmd("%d %d mDOMSetADCBiasDAC" % (channel, dacValue))

    # Set all ADC bias baseline DAC values to those supplied in the channel map
    def mDOMSetAllADCBiasDACs(self, dacValueMap: dict) -> None:
        valueString = self._mDOMAllDACValueString(dacValueMap)
        self.cmd("%s mDOMSetAllADCBiasDACs" % valueString)

    # Set the FE pulser amplitude DAC value for the given mDOM channel
    def mDOMSetFEPulserDAC(self, channel: int, dacValue: int) -> None:
        self.cmd("%d %d mDOMSetFEPulserDAC" % (channel, dacValue))

    # Set all FE pulser DAC values to those supplied in the channel map
    def mDOMSetAllFEPulserDACs(self, dacValueMap: dict) -> None:
        valueString = self._mDOMAllDACValueString(dacValueMap)
        self.cmd("%s mDOMSetAllFEPulserDACs" % valueString)

    # Write a register on all of the mDOM AFE ADCs
    def mDOMWriteADCs(self, reg: int, value: int) -> None:
        self.cmd("%d %d mDOMWriteADCs" % (reg, value))

    # Read back a register from the mDOM AFE ADCs
    def mDOMReadADCs(self, reg: int) -> int:
        return int(self.cmd("%d mDOMReadADCs .s drop" % (reg),
                            strip_stack=True))

    # Perform a hardware reset on all mDOM AFE ADCs
    def mDOMADCsReset(self) -> None:
        self.cmd("mDOMADCsReset")

    # Set the mDOM ADC test pattern for all channels to 'patternByte'.
    # patternByte = 3 --> "toggle" pattern
    # patternByte = 4 --> "ramp" pattern
    # See https://www.ti.com/lit/ds/symlink/adc3424.pdf page 55 for details.
    def mDOMSetChannelTestPattern(self, patternByte: int) -> None:
        self.cmd("%d mDOMSetChannelTestPattern" % (patternByte))

    # Return mDOM ADCs to normal mode
    def mDOMDisableChannelTestPattern(self) -> None:
        self.cmd("mDOMDisableChannelTestPattern")

    # Return the FPGA internal ADC temperature
    def mDOMGetFPGATemperature(self) -> float:
        return float(self.cmd("mDOMPrintFPGATemperature"))

    # Return the TMP101 temperature, near the center of the mDOM mainboard
    def mDOMGetTMP101Temperature(self) -> float:
        return float(self.cmd("mDOMPrintTMP101Temperature"))

    # Set the mDOM discriminator scalers to integrate data for periodUS
    # microseconds, with added deadtime of 8 ns * deadtimeCycles
    def mDOMEnableScalers(self, periodUS: int, deadtimeCycles: int) -> None:
        self.cmd("%d %d mDOMEnableScalers" % (periodUS, deadtimeCycles))

    # Get the discriminator scaler count for a particular mDOM channel
    def mDOMGetScalerCount(self, channel: int) -> int:
        return int(self.cmd("%d mDOMGetScalerCount .s drop" % (channel),
                            strip_stack=True))

    # Get a map of discriminator scaler counts for all mDOM channels
    def mDOMGetAllScalerCounts(self) -> dict:
        # Counts are ordered by channel
        return self._mDOMGetAllScalerCountMap(
            self.cmd("mDOMPrintAllScalerCounts"))

    # Get the ADC scaler count for a particular mDOM channel
    def mDOMGetADCScalerCount(self, channel: int) -> int:
        return int(self.cmd("%d mDOMGetADCScalerCount .s drop" % (channel),
                            strip_stack=True))

    # Get a map of ADC scaler count for all mDOM channels
    def mDOMGetAllADCScalerCounts(self) -> dict:
        # Counts are ordered by channel
        return self._mDOMGetAllScalerCountMap(
            self.cmd("mDOMPrintAllADCScalerCounts"))

    # Set the duration of the AFE pulser trigger pulse
    def mDOMSetFEPulserWidth(self, triggerPulseNS: int) -> None:
        self.cmd("%d mDOMSetFEPulserWidth" % triggerPulseNS)

    # Enable the FE pulser in all channels.  The pulser will fire every
    # periodUS microseconds.
    def mDOMEnableFEPulsers(self, periodUS: int) -> None:
        self.cmd("%d mDOMEnableFEPulsers" % periodUS)

    # Disable the mDOM FE pulsers
    def mDOMDisableFEPulsers(self) -> None:
        self.cmd("mDOMDisableFEPulsers")

    # Enable the mDOM discriminator trigger readout
    def mDOMEnableDiscTrigger(self) -> None:
        self.cmd("mDOMEnableDiscTrigger")

    # Enable the mDOM ADC threshold trigger readout
    def mDOMEnableADCTrigger(self) -> None:
        self.cmd("mDOMEnableADCTrigger")

    # Enable the mDOM external trigger readout
    def mDOMEnableExtTrigger(self) -> None:
        self.cmd("mDOMEnableExtTrigger")

    # Enable the mDOM calibration trigger readout
    def mDOMEnableCalibrationTrigger(self) -> None:
        self.cmd("mDOMEnableCalibrationTrigger")

    # Enable the mDOM global trigger readout
    def mDOMEnableGlobalTrigger(self) -> None:
        self.cmd("mDOMEnableGlobalTrigger")

    # Disable all mDOM trigger readout
    def mDOMDisableTriggers(self) -> None:
        self.cmd("mDOMDisableTriggers")

    # Set all mDOM channels to readout nSamples waveform bins
    def mDOMSetConstReadout(self, nSamples: int) -> None:
        self.cmd("%d mDOMSetConstReadout" % (nSamples))

    # Set all mDOM channels to readout all samples while trigger is satisfied,
    # along with preSamples samples before the trigger and postSamples
    # samples after the trigger
    def mDOMSetVariableReadout(self, preSamples: int, postSamples: int) -> None:
        self.cmd("%d %d mDOMSetVariableReadout" % (preSamples, postSamples))

    # Acquire a software trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestSoftwareMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestSoftwareMaskTrigger" % (channelMask))

    # Acquire a software trigger in the specified channel
    def mDOMTestSoftwareTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestSoftwareTrigger" % (channel))

    # Acquire a pulser trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestPulserMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestPulserMaskTrigger" % (channelMask))

    # Acquire a pulser trigger in the specified channel
    def mDOMTestPulserTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestPulserTrigger" % (channel))

    # Acquire a calibration trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestCalibrationMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestCalibrationMaskTrigger" % (channelMask))

    # Acquire a calibration trigger in the specified channel
    def mDOMTestCalibrationTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestCalibrationTrigger" % (channel))

    # Acquire a discriminator trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestDiscMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestDiscMaskTrigger" % (channelMask))

    # Acquire a discriminator trigger in the specified channel
    def mDOMTestDiscTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestDiscTrigger" % (channel))

    # Set the ADC less-than-equal-to threshold trigger to this value
    def mDOMSetADCTriggerThresh(self, thresh: int) -> None:
        self.cmd("%d mDOMSetADCTriggerThresh" % (thresh))

    # Acquire a ADC trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestADCThreshMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestADCThreshMaskTrigger" % (channelMask))

    # Acquire a ADC trigger in the specified channel
    def mDOMTestADCThreshTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestADCThreshTrigger" % (channel))

    # Acquire an external trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestExtMaskTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestExtMaskTrigger" % (channelMask))

    # Acquire an external trigger in the specified channel
    def mDOMTestExtTrigger(self, channel: int) -> None:
        self.cmd("%d mDOMTestExtTrigger" % (channel))

    # Set the source channel mask for the global trigger to channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMSetGlobalTriggerSourceMask(self, channelMask: int) -> None:
        self.cmd("%d mDOMSetGlobalTriggerSourceMask" % (channelMask))

    # Set the source channel for the global trigger to channel
    def mDOMSetGlobalTriggerSourceChannel(self, channel: int) -> None:
        self.cmd("%d mDOMSetGlobalTriggerSourceChannel" % (channel))

    # Acquire an global trigger in the channels specified by channelMask.
    # channelMask = 0b010000000000000000000001 would acquire channels 0 & 22
    def mDOMTestGlobalTrigger(self, channelMask: int) -> None:
        self.cmd("%d mDOMTestGlobalTrigger" % (channelMask))

    def mDOMEnableAFEChannel(self, channel: int) -> None:
        self.cmd("%d mDOMEnableAFEChannel" % channel)

    def mDOMDisableAFEChannel(self, channel: int) -> None:
        self.cmd("%d mDOMDisableAFEChannel" % channel)

    def mDOMEnableAFE(self) -> None:
        self.cmd("mDOMEnableAFE")

    def mDOMDisableAFE(self) -> None:
        self.cmd("mDOMDisableAFE")

    def mDOMAFEStatus(self) -> str:
        return self.cmd("mDOMAFEStatus")

    @xDOM.requiresLIDInterlock
    def mDOMSetFlasherChargeBiasDAC(self, flasherChain: int, value: int) -> None:
        self.cmd("%d %d mDOMSetFlasherChargeBiasDAC" % (flasherChain, value))

    @xDOM.requiresLIDInterlock
    def mDOMSetIlluminationBrightnessDAC(self, value: int) -> None:
        self.cmd("%d mDOMSetIlluminationBrightnessDAC" % (value))

    @xDOM.requiresLIDInterlock
    def mDOMReadFlasherChargeBiasADC(self, flasherChain: int) -> int:
        return int(self.cmd("%d mDOMReadFlasherChargeBiasADC .s drop" %
                            flasherChain, strip_stack=True))

    @xDOM.requiresLIDInterlock
    def mDOMPrintFlasherChargeBias(self) -> str:
        return self.cmd("mDOMPrintFlasherChargeBias")

    @xDOM.requiresLIDInterlock
    def mDOMSetFlasherEnableMask(self, flasherChain: int, value: int) -> None:
        self.cmd("%d %d mDOMSetFlasherEnableMask" % (flasherChain, value))

    def mDOMPrintRevision(self) -> int:
        return int(self.cmd("mDOMPrintRevision"))

    def mDOMReadMDABFWVersion(self) -> int:
        return int(self.cmd("mDOMReadMDABFWVersion .s drop", strip_stack=True))

    def mDOMReadMDABBoardVersion(self) -> int:
        return int(self.cmd("mDOMReadMDABBoardVersion .s drop",
                            strip_stack=True))

    @xDOM.requiresHVInterlock
    def mDOMEnableHV(self) -> None:
        self.cmd("mDOMEnableHV", timeout=25)

    def mDOMDisableHV(self) -> None:
        self.cmd("mDOMDisableHV")

    def mDOMStartSoftwareMaskTrigStream(self, mask: int, period_in_ms: int) -> None:
        self.cmd('%d %d 10 startWfmStream\r\n' % (mask, period_in_ms))

    def mDOMStartPulserMaskTrigStream(self, mask: int, period_in_ms: int) -> None:
        self.cmd('%d %d 14 startWfmStream\r\n' % (mask, period_in_ms))

    def mDOMStartCalibrationMaskTrigStream(self, mask: int) -> None:
        self.cmd('%d %d 15 startWfmStream\r\n' % (mask, 0))

    def mDOMStartDiscMaskTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 11 startWfmStream\r\n' % (mask))

    def mDOMStartADCThreshMaskTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 13 startWfmStream\r\n' % mask)

    def mDOMStartExtMaskTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 12 startWfmStream\r\n' % (mask))

    def mDOMStartGlobalTriggerStream(self, mask: int) -> None:
        self.cmd('%d 0 16 startWfmStream\r\n' % (mask))

    def mDOMStartCalibrationMaskHBufTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 143 startWfmStream\r\n' % (mask))

    def mDOMStartDiscMaskHBufTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 139 startWfmStream\r\n' % (mask))

    def mDOMStartADCThreshMaskHBufTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 141 startWfmStream\r\n' % mask)

    def mDOMStartExtMaskHBufTrigStream(self, mask: int) -> None:
        self.cmd('%d 0 140 startWfmStream\r\n' % (mask))

    def mDOMStartGlobalHBufTriggerStream(self, mask: int) -> None:
        self.cmd('%d 0 144 startWfmStream\r\n' % (mask))

    def mDOMStartSoftwareTrigStream(self, channel: int, period_in_ms: int) -> None:
        self.mDOMStartSoftwareMaskTrigStream(1 << channel, period_in_ms)

    def mDOMStartPulserTrigStream(self, channel: int, period_in_ms: int) -> None:
        self.mDOMStartPulserMaskTrigStream(1 << channel, period_in_ms)

    def mDOMStartCalibrationTrigStream(self, channel: int) -> None:
        self.mDOMStartCalibrationMaskTrigStream(1 << channel)

    def mDOMStartDiscTrigStream(self, channel: int) -> None:
        self.mDOMStartDiscMaskTrigStream(1 << channel)

    def mDOMStartADCThreshTrigStream(self, channel: int) -> None:
        self.mDOMStartADCThreshMaskTrigStream(1 << channel)

    def mDOMStartExtTrigStream(self, channel: int) -> None:
        self.mDOMStartExtMaskTrigStream(1 << channel)

    def mDOMStartCalibrationHBufTrigStream(self, channel: int) -> None:
        self.mDOMStartCalibrationMaskHBufTrigStream(1 << channel)

    def mDOMStartDiscHBufTrigStream(self, channel: int) -> None:
        self.mDOMStartDiscMaskHBufTrigStream(1 << channel)

    def mDOMStartADCThreshHBufTrigStream(self, channel: int) -> None:
        self.mDOMStartADCThreshMaskHBufTrigStream(1 << channel)

    def mDOMStartExtHBufTrigStream(self, channel: int) -> None:
        self.mDOMStartExtMaskHBufTrigStream(1 << channel)

    def mDOMIsHitBufferEmpty(self) -> bool:
        return bool(int(self.cmd("mDOMIsHitBufferEmpty .s drop",
                                 strip_stack=True)))

    def requiresMDOMHVEnabled(func):
        def wrapper(self, *args, **kwargs):
            if self.interlockChecksEnabled:
                try:
                    if not self.mDOMHVEnabled():
                        raise Exception("mDOM HV not enabled")
                except ValueError:
                    # Support for Iceboot <0x30, which doesn't support this check
                    pass
            return func(self, *args, **kwargs)

        return wrapper

    # Send uBase command 'cmd' to the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseSend(self, channel: int, cmd: str) -> None:
        self.cmd("%d s\" %s\" mDOMUBaseSend" % (channel, cmd), timeout=2)

    # Receive a uBase response from the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseRecv(self, channel: int) -> str:
        return self.cmd("%d mDOMUBaseRecv" % (channel), timeout=2)

    # Reset the uBase MCU from the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseReset(self, channel: int) -> None:
        self.cmd("%d mDOMUBaseReset" % (channel), timeout=5)

    # Reset the uBase MCU from the specified channel, power cycling if needed
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseForceReset(self, channel: int) -> None:
        self.cmd("%d mDOMUBaseForceReset" % (channel), timeout=5)

    # Return a string containing the uBase status on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseStatus(self, channel: int) -> str:
        return self.cmd("%d mDOMUBaseStatus" % (channel), timeout=2)

    # Return a string containing the uBase status for all channels
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseStatusAll(self) -> str:
        return self.cmd("mDOMUBaseStatusAll", timeout=2)

    # Set the uBase baud rate for all channels
    def mDOMSetUBaseBaudRate(self, baudRate: int) -> None:
        self.cmd("%d mDOMSetUBaseBaudRate" % baudRate, timeout=2)

    # Enable the uBase autobaud feature for all channels
    def mDOMEnableUBaseAutobaud(self) -> None:
        self.cmd("mDOMEnableUBaseAutobaud", timeout=2)

    # Disable the uBase autobaud feature for all channels
    def mDOMDisableUBaseAutobaud(self) -> None:
        self.cmd("mDOMDisableUBaseAutobaud", timeout=2)

    # Program the uBase on the specified channel with the specified
    # file on the mDOM flash
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseFlashProgram(self, channel: int, fileName: str) -> None:
        self.cmd("%d s\" %s\" mDOMUBaseFlashProgram" % (channel, fileName),
                 timeout=120)

    # Program all discovered uBases with the specified file on the mDOM flash
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseFlashProgramAll(self, fileName: str) -> None:
        for channel in range(24):
            self.cmd("%d s\" %s\" mDOMUBaseFlashProgram" % (channel, fileName),
                     timeout=120)

    # Erase the uBase flash for the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseFlashErase(self, channel: int) -> None:
        self.cmd("%s mDOMUBaseFlashErase" % channel)

    # Return the UID of the uBase on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetUID(self, channel: int) -> str:
        return self.cmd("%d mDOMUBasePrintUID" % (channel), timeout=2)

    # Return the software version of the uBase on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetSWVersion(self, channel: int) -> str:
        return self.cmd("%d mDOMUBasePrintSWVersion" % (channel), timeout=2)

    # Return the PWM frequency of the uBase on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetFrequency(self, channel: int) -> int:
        return int(
            self.cmd("%d mDOMUBasePrintFrequency" % (channel), timeout=2))

    # Return the target voltage of the uBase on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetTargetVoltage(self, channel: int) -> float:
        return float(
            self.cmd("%d mDOMUBasePrintTargetVoltage" % (channel), timeout=2))

    # Return the monitored voltage of the uBase on the specified channel
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetMonitorVoltage(self, channel: int) -> float:
        return float(
            self.cmd("%d mDOMUBasePrintMonitorVoltage" % (channel), timeout=2))

    # Return the monitored current of the uBase on the specified channel, in uA
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetMonitorCurrent(self, channel: int) -> float:
        return float(
            self.cmd("%d mDOMUBasePrintMonitorCurrent" % (channel), timeout=2))

    # Return the temperature of the uBase on the specified channel, in deg. C
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetTemperature(self, channel: int) -> float:
        return float(
            self.cmd("%d mDOMUBasePrintTemperature" % (channel), timeout=2))

    # Return the MCU voltage the uBase on the specified channel, in V
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetMCUVoltage(self, channel: int) -> float:
        return float(
            self.cmd("%d mDOMUBasePrintMCUVoltage" % (channel), timeout=2))

    # Return the status of the uBase oscillator.  0 indicates failure
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetOSCStatus(self, channel: int) -> int:
        return int(
            self.cmd("%d mDOMUBasePrintOSCStatus" % (channel), timeout=2))

    # Set the uBase trip mode
    #  0: Do not trip HV
    #  1: Slow: trip on average current (default)
    #  2: Fast: trip on instantaneous current
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseSetTripMode(self, channel: int, mode: int) -> None:
        self.cmd("%d %d mDOMUBaseSetTripMode" % (channel, mode), timeout=2)

    # Return whether the uBase HV overcurrent protection has tripped
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseGetTrippedState(self, channel: int) -> bool:
        return bool(int(self.cmd("%d mDOMUBaseGetTrippedState .s drop" % (
            channel), strip_stack=True, timeout=2)))

    # Reset the uBase HV overcurrent protection
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseResetTrip(self, channel: int) -> None:
        self.cmd("%d mDOMUBaseResetTrip" % (channel), timeout=2)

    # Set the PWM frequency and voltage of the uBase on the specified channel
    @xDOM.requiresLightSensorPmtHvEnable(2)
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseSetFrequencyVoltage(self, channel: int, frequency: float,
                                     voltage: float) -> None:
        voltage_v = int(math.floor(voltage))
        voltage_mv = int(math.floor((voltage - voltage_v) * 1000))
        self.cmd("%d %d %d %d mDOMUBaseSetFrequencyVoltage" %
                 (channel, frequency, voltage_v, voltage_mv), timeout=2)

    # Return the monitored current of the uBase on the specified channel, in uA
    @xDOM.requiresLightSensorPmtHvEnable(1)
    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseQuickscan(self, channel: int, voltage: float) -> None:
        voltage_v = int(math.floor(voltage))
        voltage_mv = int(math.floor((voltage - voltage_v) * 1000))
        self.cmd("%d %d %d mDOMUBaseQuickscan" %
                 (channel, voltage_v, voltage_mv), timeout=2)

    @xDOM.requiresHVInterlock
    @requiresMDOMHVEnabled
    def mDOMUBaseSetVDDU3V3(self, channel: int) -> None:
        self.cmd("%d mDOMUBaseSetVDDU3V3" % (channel), timeout=2)

    def mDOMDDR3Test(self, pageCnt: int) -> int:
        return int(self.cmd("%d mDOMDDR3Test .s drop" % (pageCnt),
                            strip_stack=True, timeout=60))

    def mDOMSetBaselineSumProperties(self, lengthSetting: int, pauseLength: int,
                                     maxDeviationLow: int,
                                     maxDeviationHigh: int) -> None:
        self.cmd("%d %d %d %d mDOMSetBaselineSumProperties" % (
            lengthSetting, pauseLength, maxDeviationLow, maxDeviationHigh))

    def mDOMCalibrateBaselines(self) -> dict:
        return json.loads(self.cmd("mDOMCalibrateBaselines", timeout=10))

    def mDOMSetBaselines(self, value: int) -> dict:
        return json.loads(self.cmd("%d mDOMSetBaselines" % value, timeout=3))

    def mDOMCalibratePulsers(self) -> dict:
        return json.loads(self.cmd("mDOMCalibratePulsers", timeout=10))

    def mDOMSetDiscriminatorThresholds(self, voltage: float) -> dict:
        uv = int(voltage * 1e6 + 0.5)
        return json.loads(
            self.cmd("%d mDOMSetDiscriminatorThresholdsUV" % uv, timeout=10))

    def mDOMSetLCWindow(self, clockCycles: int) -> None:
        self.cmd("%d mDOMSetLCWindow" % clockCycles, timeout=2)

    def mDOMSetLCThreshold(self, nChannels: int) -> None:
        self.cmd("%d mDOMSetLCThreshold" % nChannels, timeout=2)

    def mDOMSetLCRequired(self, requireLC: bool) -> None:
        val = 0
        if requireLC:
            val = 1
        self.cmd("%d mDOMSetLCRequired" % val, timeout=2)

    def _mDOMAllDACValueString(self, valueMap):
        out = ""
        for i in range(24):
            out += "%d " % valueMap[i]
        return out

    def _mDOMGetAllScalerCountMap(self, outStr):
        counts = outStr.split()
        if len(counts) != 24:
            raise Exception("Expected 24 counts, got %d" % len(counts))
        out = {}
        for i in range(24):
            out[i] = int(counts[i])
        return out

    @contextmanager
    def mDOMEnableHVContext(self) -> None:
        # A runtime context to ensure HV is disabled when finished
        self.mDOMEnableHV()
        try:
            yield
        finally:
            self.mDOMDisableHV()
