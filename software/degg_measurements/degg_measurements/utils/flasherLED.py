#!/usr/bin/env python3

from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from optparse import OptionParser, Option, OptionValueError
import time
import sys

### Main function ###
def startSession():
    ### Initial settings ###
    parser = getParser()
    (options, args) = parser.parse_args()

    session = iceboot_session_cmd.init(options)
                            #fpgaConfigurationFile="~/STM32Workspace/FPGAFirmware/degg_fw_v0x101.rbf",
                            #host="10.25.120.30",
                            #host="localhost",
                            #port="5013",
                            #fpgaEnable=options.fpgaEnable)
    return session

def enableLEDs(session, biasPower=0x3FFF):
    ### LED flashing code ###
    #allows power to be supplied to the board
    session.enableCalibrationPower()
    #you can also check the interlocks - readFlashInterlock .s drop
    #mask2 is the flasher ring, 1 is the camera system
    session.setCalibrationSlavePowerMask(2)
    #one bias is supplied to the whole board
    #max voltage is about 15V
    #session.setFlasherBias(0xFFFF)
    if int(biasPower) > 65535 or int(biasPower) < 0:
        raise ValueError(f'Value of flasher bias {biasPower} out of range!')
    #try to check value is in hex
    if str(hex(biasPower))[0] == '0' and str(hex(biasPower))[1] == 'x':
        #print(f"Setting flasher bias to {biasPower}")
        session.setFlasherBias(biasPower)
    return session

def disableLEDs(session):
    #does this disable the cameras also?
    #session.disableCalibrationPower() # old
    session.icmStopCalTrig() # new

def setContinuousFlashing(session, rate=1000, led_mask=0xFFFF):
    #session.enableCalibrationTrigger(rate)
    session.setFlasherMask(led_mask)
    session.icmStartCalTrig(0,rate)
    ##LEDs should be continuously flashing
    print("LED flashing...")

def flashLEDs(session, rate=1000, pause=0.05, led_mask=0xFFFF, num_pulses=0):
    #flashing frequency
    #session.enableCalibrationTrigger(rate) # old
    #specifies which LEDs to flash - there are 12 total
    #should be able to specify LEDs using 000000000000
    #session.setFlasherMask(0xFFFF)
    #for example 0x0001 --> LED 0
    #0x0002 --> LED 1
    #0x0003 --> LED 0 & 1
    #flash all horizontal
    #session.setFlasherMask(0x0B6D)
    #flash all vertical
    #session.setFlasherMask(0x0492)
    session.setFlasherMask(led_mask)
    session.icmStartCalTrig(num_pulses,rate) # periodical
    print("LED flashing...")
    #if num_pulses > 0:
    #    for counter in range(num_pulses):
    #        time.sleep(pause)
    #
    #elif num_pulses == -1:
    #    ### Finish LED flashing by Ctr-c ###
    #    try:
    #        while True:
    #            pass
    #            time.sleep(pause)
    #    except KeyboardInterrupt:
    #        return True

    return True

def main():
    state = False

    session = startSession()
    session = enableLEDs(session)
    setContinuousFlashing(session, rate=10000, led_mask=0xFFFF)
    #state = flashLEDs(session, rate=10000, led_mask=0xFFFF)
    time.sleep(60)
    disableLEDs(session)


    if state is False:
        print("Could not exit...")
    if state is True:
        print("Stopped flashing LEDs")

if __name__ == "__main__":
    main()
##end
