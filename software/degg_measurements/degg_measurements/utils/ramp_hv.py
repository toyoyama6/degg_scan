#!/usr/bin/env python3
import time
import sys
import os
from tqdm import tqdm
import numpy as np
from iceboot.iceboot_session import getParser
from warnings import warn
import json
import click
from concurrent.futures import ProcessPoolExecutor, wait, as_completed
from termcolor import colored
from datetime import datetime

#####
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.monitoring import readout
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
#####


def check_channel(session, channel, hv_ref_value, current_max_value=40e3):
    '''
    Read out the HV value and compare with the reference value.
    Check current draw against given max value for the current.

    Parameters
    ----------
    session : IceBoot Session
    channel : int
        Channel number
    hv_ref_value : float
        Reference HV value to check the current value against in V.
    current_max_value : float / int, default: 40e3 μA
        Max value of the current in μA.
    '''
    while True:
        try:
            obs_hv_val = session.sloAdcReadChannel(8+channel*2)
            obs_current = session.sloAdcReadChannel(9+channel*2)
        except IndexError:
            global STACK_OVERFLOW_CNT
            STACK_OVERFLOW_CNT += 1
            print(f'Catching the {STACK_OVERFLOW_CNT}th stack overflow in channel {channel}! Trying again...')
            if STACK_OVERFLOW_CNT >= 10:
                raise NotImplementedError()
            continue
        else:
            break

    if np.abs(obs_hv_val - hv_ref_value) > 100:
        warn(f'Observed HV value and set HV value are different!')
        warn(f'Observed value {obs_hv_val}, Set value {hv_ref_value}')
    if obs_current > current_max_value:
        raise ValueError(f'Observed current is above {current_max_value}μA! Aborting!')
    return obs_hv_val, obs_current


def make_degg_daq_holders_from_dicts(degg_dicts):
    daq_holders = []
    for degg_dict in degg_dicts:
        daq_holders.append(DEggDAQHolder(degg_dict))
    return daq_holders


class DEggDAQHolder():
    def __init__(self, degg_dict):
        self.degg_dict = degg_dict
        self.session = startIcebootSession(
            host='localhost',
            port=degg_dict['Port'])
        self.set_voltage = {
            0: None,
            1: None
        }

        self.obs_hv = {
            0: None,
            1: None
        }
        self.readout_time = {
            0: None,
            1: None
        }

    def setup_high_voltage(self, channel, set_voltage):
        channel = int(channel)
        set_voltage = int(set_voltage)
        self.session.enableHV(channel)
        self.session.setDEggHV(channel, set_voltage)
        self.set_voltage[channel] = set_voltage

    def finished_ramping_high_voltage(self, channel, time, obs_hv):
        if self.set_voltage[channel] is None:
            raise ValueError('Set a high voltage to start ramping first!')
        if (self.obs_hv[channel] is None and
                self.readout_time[channel] is None):
            raise ValueError('Previous reference measurement is required '
                             'to calculate a hv change rate!')
        max_hv_diff = 100
        max_dv_dt = 20
        voltage_is_close = np.abs(self.set_voltage[channel] - obs_hv) < max_hv_diff
        dv_dt = ((obs_hv - self.obs_hv[channel]) /
            (time - self.readout_time[channel]))
        dv_dt_is_small = dv_dt < max_dv_dt
        return voltage_is_close & dv_dt_is_small


def wait_until_ramped(degg_daq_holders, max_wait_time=40):
    finished = np.zeros(len(degg_daq_holders))
    t0 = time.monotonic()
    while time.monotonic() < (t0 + max_wait_time):
        for i, holder in enumerate(degg_daq_holders):
            if finished[i]:
                continue
            finished_i = [False, False]
            for channel in [0, 1]:
                t = time.monotonic()
                obs_hv, _ = check_channel(holder.session,
                                          channel,
                                          holder.set_voltage[0])
                if (holder.readout_time[channel] is not None and
                        holder.obs_hv[channel] is not None):
                    finished_i[channel] = holder.finished_ramping_high_voltage(
                        channel, t, obs_hv)

                holder.readout_time[channel] = t
                holder.obs_hv[channel] = obs_hv
            if sum(finished_i) == 2:
                finished[i] = True
        if sum(finished) == len(finished):
            print('Ramped all DEggs successfully!')
            return
    raise ValueError('Ramping was not successful!')


if __name__ == '__main__':
    main()

