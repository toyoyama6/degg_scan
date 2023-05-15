#!/usr/bin/env python

from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from iceboot.test_waveform import parseTestWaveform
from optparse import OptionParser
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import os
import signal
from tqdm import tqdm


def main():
    parser = getParser()
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--threshold0", dest="threshold0",
                      help="Threshold for channel 0", default=8050)
    parser.add_option("--threshold1", dest="threshold1",
                      help="Threshold for channel 1", default=8050)
    parser.add_option("--adcMin", dest="adcMin",
                      help="Minimum ADC value to plot", default=None)
    parser.add_option("--adcRange", dest="adcRange",
                      help="Plot this many ADC counts above min",
                      default=None)
    parser.add_option("--pulserPeriodUS", dest="pulserPeriodUS",
                      help="Enable the front-end pulser and set the period",
                      default=0)

    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)

    session.setDEggHV(0, 0)
    session.setDEggHV(1, 0)
    session.disableHV(0)
    session.disableHV(1)
    session.enableHV(0)
    session.setDEggHV(0, 0)
    dac_value = 30000
    session.setDAC('A', dac_value)
    
    baseline = 7913
    threshold = baseline + 400

    name = "colton"
    file_name = os.path.expandvars(f"$HOME/workshop/{name}/flasher")

    channel = 0
    period = 100000
    deadtime = 24
    session.setDEggTriggerConditions(channel, threshold)
    session.enableDEggTrigger(channel)
    session.enableScalers(channel, period, deadtime)
    time.sleep(10)

    ##led0 = 0x0001
    ##led1 = 0x0002
    ##led2 = 0x0004
    ##led3 = 0x0008
    ##led4 = 0x0010

    flasher_mask = [0x0492]
    flasher_mask_str = ["0x0492"]

    for i in range(0, len(flasher_mask)):
        flasher_measurement(session, baseline, threshold, channel, period,
                            False, flasher_mask[i], flasher_mask_str[i], file_name)
        time.sleep(20)
        flasher_measurement(session, baseline, threshold, channel, period,
                            True, flasher_mask[i], flasher_mask_str[i], file_name)
        #time.sleep(60*5)

def flasher_measurement(session, baseline, threshold, channel, period,
                        flasher_on=False, flasher_mask=0xFFFF, flasher_mask_str="0xFFFF"):

    session.disableCalibrationPower()
    print(f"Running with {flasher_mask_str}")
    
    if flasher_on is True:
        print("Flasher is On!")
        f = open(file_name + "_on_" + str(flasher_mask_str) + ".txt", "w+")
        f.write("bl:" + str(baseline) + ", th:" + str(threshold) + '\n')
        session.enableCalibrationPower()
        session.setCalibrationSlavePowerMask(2)
        session.setFlasherBias(0xFFFF)
        session.enableCalibrationTrigger(1000)
        session.setFlasherMask(flasher_mask)
        f.write("LED: " + str(flasher_mask) + '\n')
        time.sleep(5)

    if flasher_on is False:
        print("Flasher is Off!")
        f = open(file_name + "_off_" + str(flasher_mask_str) + ".txt", "w+")
        f.write("bl:" + str(baseline) + ", th:" + str(threshold) + '\n')
        f.write("LED: none" + '\n')

    hv_vals = [800, 900, 1000]
    n_runs = 250

    for hv_val in hv_vals:
        session.setDEggHV(0, int(hv_val))
        print(f"Setting HV to {hv_val} V")
        time.sleep(10)
        scaler_count_sum = 0
        for i in tqdm(range(n_runs)):
            scaler_count = session.getScalerCount(channel)
            scaler_count_sum += scaler_count
            time.sleep(period / 1e6)
        f.write(str(hv_val) + ", " + str(scaler_count_sum) + '\n')

    session.disableCalibrationPower()
    f.close()

if __name__ == "__main__":
    main()

##end
