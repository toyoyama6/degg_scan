import os, sys
import numpy as np
from termcolor import colored
import time

from degg_measurements.utils import enable_pmt_hv_interlock
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import initialize_dual

from chiba_slackbot import send_message, send_warning


ICM_PORT = 6008
TABLETOP_PORT = 5011

class infoContainer(object):
    def __init__(self, timestamp, charge, channel, i_pair, triggerNum):
        self.timestamp = timestamp
        self.charge = charge
        self.channel = channel
        self.i_pair = i_pair
        self.triggerNum = triggerNum

def get_sync_freq(infoList):
    print('Checking sync frequency')
    ts_to_t = 240e6
    timestamps = []
    for info in infoList:
        if info.channel == 1:
            print(colored('You had a trigger in Ch1! How rare!', 'yellow'))
            print(colored('Check the code &/or repeat the test!', 'yellow'))
            continue
        timestamp = info.timestamp
        timestamps.append(timestamp)


    d_timestamp = np.diff(timestamps)
    diff = d_timestamp / ts_to_t

    ##the laser should always be operating at 500 Hz
    #mask = (diff  >= 0.0099) & (diff <= 0.0101)
    mask = (diff  >= 0.00199) & (diff <= 0.00201)
    print(f'Median: {np.median(diff[mask])} s')
    print(f'Pass: {np.sum(mask)}')

    return np.sum(mask)

def get_sync_signal(session, nevents):
    print('Checking for sync signal')

    infoList = []
    block = session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=60)
    channels = list(block.keys())
    for channel in channels:
        charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
        timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
        triggerNum = 0
        for ts, q in zip(timestamps, charges):
            info = infoContainer(ts, q, channel, 0, triggerNum)
            infoList.append(info)
            triggerNum += 1

    return infoList





def setup_tabletop():
    threshold = 10000
    enable_pmt_hv_interlock(ICM_PORT)
    session =startIcebootSession(host='localhost', port=TABLETOP_PORT)
    session = initialize_dual(session, n_samples=128, dac_value=30000,
                              high_voltage0=0, high_voltage1=0,
                              threshold0=threshold, threshold1=15000,
                              modHV=False)
    return session

def light_system_check():
    print('Readout mainboard signals to check for laser')
    session = setup_tabletop()

    nevents = 10000
    reset = False

    while True:
        ##this test will fail if there is a problem with the sync signal (e.x. laser is off)
        try:
            infoList = get_sync_signal(session, nevents)
        except OSError:
            print(colored('No sync signal found! Mainboard timed out!', 'yellow'))
            if reset is False:
                print(colored('The test will retry by resetting the function generator ONCE', 'yellow'))
                time.sleep(5)
                reset = True
                continue
            elif reset is True:
                print(colored('The function generator was previously reset, but the problem was not resolved.', 'red'))
                raise RuntimeError('Failure to get laser sync after reset.')

        ##this test will fail if the sync timing does not match the configured frequency
        num_pass = get_sync_freq(infoList)
        if num_pass >= nevents-1:
            print(colored('Laser Frequency Test Passed', 'green'))
            #send_message('- Laser frequency test passed -')
            break
        else:
            print(colored(f'Laser Frequency Test Failed ({num_pass} < {nevents-1})', 'yellow'))
            if reset is False:
                print(colored('The test will retry by resetting the function generator ONCE', 'yellow'))
                time.sleep(5)
                reset = True
            elif reset is True:
                print(colored('The function generator was previously reset, but the problem was not resolved.', 'red'))
                raise RuntimeError('Failure to get laser frequency after reset.')

    print('Done')

def main():
    print('-'*20)
    print('Checking the light system - sync signal and frequency')
    print('Make sure the settings are configured for this check')
    time.sleep(5)
    light_system_check()
    print('Turning off the function generator again')

if __name__ == "__main__":
    main()

##end
