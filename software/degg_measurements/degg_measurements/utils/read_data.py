import numpy as np
import tables
import pandas as pd
from glob import glob
import os
from matplotlib import pyplot as plt
from warnings import warn
from datetime import datetime

def read_data(filename, ignoreParams=False):
    with tables.open_file(filename) as open_file:
        try:
            data = open_file.get_node('/data')
            if not ignoreParams:
                parameters = open_file.get_node('/parameters')
        except:
            raise IOError(f"{filename} missing /data and/or /parameters")

        print(f'read_data:{filename}')

        parameter_dict = {}
        if not ignoreParams:
            parameter_keys = parameters.keys[:]
            parameter_vals = parameters.values[:]
            for key, val in zip(parameter_keys, parameter_vals):
                key = key.decode('utf-8')
                val = val.decode('utf-8')
                try:
                    parameter_dict[key] = int(val)
                except ValueError:
                    parameter_dict[key] = val

        event_id = data.col('event_id')
        time = data.col('time')
        waveforms = data.col('waveform')
        timestamp = data.col('timestamp')
        try:
            pc_time = data.col('pc_time')
        except:
            warning_str = filename + " does not include PC timing information (file is probably old)."
            warn(warning_str)
            pc_time = np.ones_like(timestamp) * np.inf

        try:
            datetime_timestamp = data.col('datetime_timestamp')
        except:
            warning_str = filename + " does not include datetime timing information (file is probably older than 2022/05/11)."
            warn(warning_str)
            ##this was the start of FAT
            datetime_timestamp = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()

    return event_id, time, waveforms, timestamp, pc_time, datetime_timestamp, parameter_dict

