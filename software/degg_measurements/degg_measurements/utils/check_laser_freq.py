import os, sys
import numpy as np
from termcolor import colored
import time
import click

from degg_measurements.utils import enable_pmt_hv_interlock
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import initialize_dual



ICM_PORT = 6008
TABLETOP_PORT = 5011

class infoContainer(object):
    def __init__(self, timestamp, charge, channel, i_pair, triggerNum):
        self.timestamp = timestamp
        self.charge = charge
        self.channel = channel
        self.i_pair = i_pair
        self.triggerNum = triggerNum

def get_sync_freq(infoList, freq=100):
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
    print(f'Median Before Mask: {np.median(diff)} s')

    ##the laser should almost always be operating at 100 Hz
    if freq == 100:
        mask = (diff  >= 0.0099) & (diff <= 0.0101)
    elif freq == 1000:
        mask = (diff >= 0.00099) & (diff <= 0.00101)
    elif freq == 500:
        mask = (diff >= 0.0019)  & (diff <= 0.0021)
    else:
        print(f'Modification needed to check_laser_freq for frequency: {freq}')
        exit(1)
    print(f'Median After: {np.median(diff[mask])} s')
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
    enable_pmt_hv_interlock(ICM_PORT)
    session = startIcebootSession(host='localhost', port=TABLETOP_PORT)
    session = initialize_dual(session, n_samples=128, dac_value=30000,
                              high_voltage0=0, high_voltage1=0,
                              #threshold0=9500, threshold1=14000,
                              threshold0=8900, threshold1=14000,
                              modHV=False)
    return session


def light_system_check(freq=100):
    print('Readout mainboard signals to check for laser')
    session = setup_tabletop()

    nevents = 1000
    reset = False

    while True:
        ##this test will fail if there is a problem with the sync signal (e.x. laser is off)
        try:
            infoList = get_sync_signal(session, nevents)
        except OSError:
            print(colored('No sync signal found! Mainboard timed out!', 'yellow'))
            print('No sync signal found! Mainboard timed out!')

        ##this test will fail if the sync timing does not match the configured frequency
        num_pass = get_sync_freq(infoList, freq)

        if num_pass >= nevents-1:
            print(colored('Laser Frequency Test Passed', 'green'))
            print('- Laser frequency test passed -')
            break
        else:
            print(colored(f'Laser Frequency Test Failed ({num_pass} < {nevents-1})', 'yellow'))

    print('Done')

@click.command()
@click.argument('freq')
def main(freq):
    freq = int(freq)
    print('-'*20)
    print('Checking the light system - sync signal and frequency')
    print('Make sure the settings are configured for this check')
    time.sleep(5)
    light_system_check(freq)

if __name__ == "__main__":
    main()

##end
