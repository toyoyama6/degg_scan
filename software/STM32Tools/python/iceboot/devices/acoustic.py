from .unmodified_mmb import UnmodifiedMMB
from ..iceboot_comms import IceBootComms

AM_fb_adc_to_voltage = 1/9.1
AM_FB_ADC_coeff_a = 1/9.1
AM_FB_ADC_coeff_b = 200

class Acoustic(UnmodifiedMMB):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)

    def AMInit(self) -> None:
        self.cmd("AMInit")

    def AMsendTestWaveform(self) -> None:
        """
        Send basic waveform, 10period, ~10kHz, blocking mode.
        """
        self.cmd("AMsendWaveform")
    
    def AMsendPulse(self) -> None:
        """
        Send 30 us pulse.
        """
        self.cmd("AMsendPulse")

    def AMallocWfBuffer(self) -> None:
        """
        Allocate waveform buffer.
        """
        self.cmd("AMallocWfBuffer")

    def AMinitWfTimer(self) -> None:
        """
        Initialize waveform timer.
        """
        self.cmd("AMinitWfTimer")

    def AMstartWfTimer(self) -> None:
        """
        Start waveform timer.
        """
        self.cmd("AMstartWfTimer")

    def AMsendWf(self) -> None:
        """
        Send waveform via timer.
        """
        self.cmd("AMsendWf")

    def AMsendWfBurst(self) -> None:
        """
        Send burst of waveforms via timer.
        """
        self.cmd("AMsendWfBurst")

    """
    T/R switch functions
    """

    def AMsetReceiveMode(self) -> None:
        """
        Receiver mode, receiver connected to transducer.
        """
        self.cmd("AMsetReceiveMode")

    def AMsetTransmitMode(self) -> None:
        """
        Transmitter mode, full-bridge connected to transducer.
        """
        self.cmd("AMsetTransmitMode")

    def AMgetTRstate(self):
        """
        Get the T/R switch state.

            Returns:
                0: reciver mode
                1: transmitter mode
        """
        out = self.cmd("AMgetTRstate")
        return out

    """
    charge functions
    """

    def AMchargeOn(self) -> None:
        """
        Enable charging.
        """
        self.cmd("AMchargeOn")

    def AMchargeOff(self) -> None:
        """
        Disable charging
        """
        self.cmd("AMchargeOff")

    def AMgetChargeState(self) -> int:
        """
        Get the charge state.

            Returns:
                0: charge disabled
                1: charge enabled
        """
        out = self.cmd("AMgetChargeState")
        return out
    
    def AMgetCapVoltage(self) -> float:
        """
        Get the voltage of the storage capcitor bank.

            Returns:
                voltage value 0..320
        """
        out = self.cmd("AMgetCapVoltage")
        return (int(out) - AM_FB_ADC_coeff_b) * AM_FB_ADC_coeff_a

    def AMgetCapVoltageAverage(self) -> float:
        """
        Get the average voltage of the storage capcitor bank.

            Returns:
                voltage value 0..320
        """
        out = self.cmd("AMgetFB_ADC_average")
        return (int(out) - AM_FB_ADC_coeff_b) * AM_FB_ADC_coeff_a

    def AMinitFB_ADC_Timer(self) -> None:
        """
        Initialize the feedback adc timer.
        """
        self.cmd("AMinitFB_ADC_Timer")

    def AMstartFB_ADC_singleMeasurement(self) -> None:
        """
        Start single average measurement of the feedback adc.
        """
        self.cmd("AMstartFB_ADC_singleMeasurement")

    def AMgetFB_ADC_average(self) -> int:
        """
        Get the average voltage of the storage capcitor bank.

            Returns:
                Error if average not completed
                voltage value 0..4095
        """
        out = self.cmd("AMgetFB_ADC_average")
        return out

    def AMchargeToVoltage(self, val) -> None:
        """
        Charge to target voltage.

            Arguments:
                voltage (0..320)
        """
        if 0 <= val <= 320:
            self.cmd("%d AMchargeToVoltage" % val)
        else:
            raise ValueError("Target voltage must be between 0 and 320V.")

    def AMhasReachedVoltage(self) -> int:
        """
        Check if target voltage has been reached.

            Returns:
                1: yes
                0: no
        """
        out = self.cmd("AMhasReachedVoltage")
        return out
    
    """
    discharge functions
    """

    def AMdischargeOn(self) -> None:
        """
        Enable discharging.
        """
        self.cmd("AMdischargeOn")

    def AMdischargeOff(self) -> None:
        """
        Disable discharging.
        """
        self.cmd("AMdischargeOff")

    def AMgetDischargeState(self) -> int:
        """
        Get the discharge state.

            Returns:
                0: discharge disabled
                1: discharge enabled
        """
        out = self.cmd("AMgetDischargeState")
        return out

    def AMsetFB_neutral(self) -> None:
        """
        Put fullbridge in neutral state.
        """
        self.cmd("AMsetFB_neutral")

    def AMsetFB_GND(self) -> None:
        """
        Put fullbridge in GND state.
        """
        self.cmd("AMsetFB_GND")
    
    """
    waveform configuration
    """

    def AMsetWfMode(self, val) -> None:
        """
        Set waveform mode.

            Arguments:
                mode (0: sine, 1: chirp)
        """
        if val in [0,1]:
            self.cmd("%d AMsetWfMode" % val)
        else:
            raise ValueError("Mode must be either 0 (sine) or 1 (chirp).")

    def AMgetWfMode(self) -> int:
        """
        Get waveform mode.

            Returns:
                0: sine
                1: chirp
        """
        out = self.cmd("AMgetWfMode")
        return out

    def AMsetWfChirpMode(self, val) -> None:
        """
        Set waveform chirp mode.

            Arguments:
                mode (0: linear, 1: logarithmic)
        """
        if val in [0,1]:
            self.cmd("%d AMsetWfChirpMode" % val)
        else:
            raise ValueError("Mode must be either 0 (sine) or 1 (chirp).")

    def AMgetWfChirpMode(self) -> int:
        """
        Get waveform chirp mode.

            Returns:
                0: linear
                1: logarithmic
        """
        out = self.cmd("AMgetWfChirpMode")
        return out

    def AMsetWfNBurst(self, val) -> None:
        """
        Set waveform n burst.

            Arguments:
                n bursts
        """
        self.cmd("%d AMsetWfNBurst" % val)

    def AMgetWfNBurst(self) -> int:
        """
        Get waveform n burst.

            Returns:
                n bursts
        """
        out = self.cmd("AMgetWfNBurst")
        return out

    def AMsetWfDurationMs(self, val) -> None:
        """
        Set waveform duration in ms.

            Arguments:
                duration in ms
        """
        if val < 1000:
            self.cmd("%d AMsetWfDurationMs" % val)
        else:
            raise ValueError("Waveform duration must be < 1000 ms.")

    def AMgetWfDurationMs(self) -> int:
        """
        Get waveform duration.

            Returns:
                waveform duration in ms
        """
        out = self.cmd("AMgetWfDurationMs")
        return out

    def AMsetWfDelayMs(self, val) -> None:
        """
        Set waveform delay in ms.

            Arguments:
                duration in ms
        """
        self.cmd("%d AMsetWfDelayMs" % val)

    def AMgetWfDelayMs(self) -> int:
        """
        Get waveform delay.

            Returns:
                waveform delay in ms
        """
        out = self.cmd("AMgetWfDelayMs")
        return out

    def AMsetWfSineFreqHz(self, val) -> None:
        """
        Set sine frequency in Hz.

            Arguments:
                frequeny in Hz
        """
        if val < 40001:
            self.cmd("%d AMsetWfSineFreqHz" % val)
        else:
            raise ValueError("Frequency must be <= 40 kHz")

    def AMgetWfSineFreqHz(self) -> float:
        """
        Get waveform sine frequency in Hz.

            Returns:
                waveform sine frequency in Hz
        """
        out = self.cmd("AMgetWfSineFreqHz")
        return out

    def AMsetWfChirpStartFreqHz(self, val) -> None:
        """
        Set chirp start frequency in Hz.

            Arguments:
                duration in ms
        """
        if val < 40000:
            self.cmd("%d AMsetWfChirpStartFreqHz" % val)
        else:
            raise ValueError("Frequency must be < 40 kHz")

    def AMgetWfChirpStartFreqHz(self) -> float:
        """
        Get waveform chirp start frequency in Hz.

            Returns:
                waveform chirp start frequency in Hz
        """
        out = self.cmd("AMgetWfChirpStartFreqHz")
        return out

    def AMsetWfChirpStopFreqHz(self, val) -> None:
        """
        Set chirp start frequency in Hz.

            Arguments:
                duration in ms
        """
        if val < 40001:
            self.cmd("%d AMsetWfChirpStopFreqHz" % val)
        else:
            raise ValueError("Frequency must be < 40 kHz")

    def AMgetWfChirpStopFreqHz(self) -> float:
        """
        Get waveform chirp stop frequency in Hz.

            Returns:
                waveform chirp stop frequency in Hz
        """
        out = self.cmd("AMgetWfChirpStopFreqHz")
        return out


    # receiver specific fucntions

    def ARgetStatus(self) -> int:
        """
        Get the receiver status.

            Returns:
                status [7] Waveform Ready, [1] HW Trigger, [0] SW Trigger
        """
        out = self.cmd("ARgetStatus")
        return out

    def ARgetGain(self) -> int:
        """
        Get the receiver gain.

            Returns:
                gain value 0..255 (higher values = smaller gain)
        """
        out = self.cmd("ARgetGain")
        return int(out)

    def ARenableSelfTrigger(self) -> None:
        """
        Enable the self trigger of the acoustic receiver
        """
        self.cmd("ARenableSelfTrigger")

    def ARdisableSelfTrigger(self) -> None:
        """
        Disable the self trigger of the acoustic receiver
        """
        self.cmd("ARdisableSelfTrigger")

    def ARsetGain(self, val) -> None:
        """
        Set the receiver gain.

            Arguments:
                gain (0..255)
        """
        if 0 <= val <= 255:
            self.cmd("%d ARsetGain" % val)
        else:
            raise ValueError("Gain value must be between 0 and 255.")

    def ARgetSampleIRQ(self) -> int:
        """
        Get the sample interupt counter. (defines sample rate)

            Returns:
                sample irq, default 467
        """
        out = self.cmd("ARgetSample_irq")
        return int(out)

    def ARsetSampleIRQ(self, val) -> None:
        """
        Set the sample interupt counter. (defines sample rate)

            Arguments:
                sample irq, default 467
        """
        if 0 <= val <= 65536:
            self.cmd("%d ARsetSample_irq" % val)
        else:
            raise ValueError("Sample IRQ value must be between 0 and 65536.")

    def ARgetWaveformSample(self) -> int:
        """
        Get the number of samples per waveform

            Returns:
                n sample, default 1000, max 10k without RAM
        """
        out = self.cmd("ARgetWaveform_sample")
        return int(out)

    def ARsetWaveformSample(self, val) -> None:
        """
        Set the number of samples per waveform

            Arguments:
                n samples, default 1000, max 10k without RAM
        """
        if 0 <= val <= 65536:
            self.cmd("%d ARsetWaveform_sample" % val)
        else:
            raise ValueError("N samples must be between 0 and 65536.")

    def ARgetTriggerMean(self) -> int:
        """
        Get the trigger mean

            Returns:
                trigger mean, default 2048 (center of ADC range)
        """
        out = self.cmd("ARgetTrigger_mean")
        return int(out)

    def ARsetTriggerMean(self, val) -> None:
        """
        Set the trigger mean

            Arguments:
                trigger mean, default 2048 (center of ADC range)
        """
        if 0 <= val <= 4096:
            self.cmd("%d ARsetTrigger_mean" % val)
        else:
            raise ValueError("Trigger mean must be between 0 and 4096.")

    def ARgetTriggerLevel(self) -> int:
        """
        Get the trigger level

            Returns:
                trigger mean, default 2048 (center of ADC range)
        """
        out = self.cmd("ARgetTrigger_level")
        return int(out)

    def ARsetTriggerLevel(self, val) -> None:
        """
        Set the trigger level

            Arguments:
                trigger level, default 300
        """
        if 0 <= val <= 4096:
            self.cmd("%d ARsetTrigger_level" % val)
        else:
            raise ValueError("Trigger level must be between 0 and 4096.")

    def ARgetPretriggerSample(self) -> int:
        """
        Get the number of pretrigger samples

            Returns:
                pretrigger samples, default 100
        """
        out = self.cmd("ARgetPretrigger_sample")
        return int(out)

    def ARsetPretriggerSample(self, val) -> None:
        """
        Set the number of pretrigger samples

            Arguments:
                pretrigger samples, default 100
        """
        if 0 <= val <= 65536:
            self.cmd("%d ARsetPretrigger_sample" % val)
        else:
            raise ValueError("Pretrigger samples must be between 0 and 65536.")

    def ARgetIRQCounter(self) -> int:
        """
        Get the interrupt counter

            Returns:
                interrupt counter value
        """
        out = self.cmd("ARgetIRQ_counter")
        return int(out)

    def ARgetACQ_ADC_Sample(self) -> int:
        """
        Get an adc sample

            Returns:
                adc sample value
        """
        out = self.cmd("ARgetACQ_ADC_sample")
        return out

    def ARgetTestData(self) -> str:
        """
        Get test data

            Returns:
                test data, default 0xD0D0CACA
        """
        out = self.cmd("ARgetTest_data")
        return out

    def ARgetWaveformData(self) -> list:
        """
        read out a waveform

            Returns:
                list waveform data
        """
        out = self.cmd("ARgetWaveformData", timeout=3.0)
        return [int(s) for s in out.split()]

    def ARgetSerialNumber(self) -> list:
        """
        Get the serial number

            Returns:
                serial number, 16 x 8bit
        """
        out = self.cmd("ARgetSerial_number")
        return out

    def ARsendSWTrigger(self) -> None:
        """
        Send software trigger

            Returns:
                None
        """
        self.cmd("ARsendSWTrigger")

    def ARsendHWTrigger(self) -> None:
        """
        Send hardware trigger

            Returns:
                None
        """
        self.cmd("ARsendHWTrigger")

    def ARreset(self) -> None:
        """
        Reset acoustic receiver

            Returns:
                None
        """
        self.cmd("ARReset")

    def ARfindBaseAddress(self) -> int:
        """
        find base address of acoustic receiver

            Returns:
                None
        """
        out = self.cmd("ARfindBaseAddress")
        try:
            print("Found acoustic sensor at address %s." % hex(int(out)))
        except:
            print("Could not find sensor.")
        return out
