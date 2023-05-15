from degg_measurements.utils import startIcebootSession
import numpy as np
import time
import os
import click

from monitoring import readout


def monitor_hv(session0, session1, val, filename0, filename1):
    offsets = [-50, -10, 0, 10, 50]

    for offset in offsets:
        set_val = val + offset
        print(set_val)
        session0.setDEggHV(0, set_val)
        session1.setDEggHV(0, set_val)
        time.sleep(10)
        session0.setDEggHV(1, set_val)
        session1.setDEggHV(1, set_val)
        time.sleep(10)
        for counter in tqdm(range(2000)):
            readout(session0, filename0)
            readout(session1, filename1)
            time.sleep(3)

