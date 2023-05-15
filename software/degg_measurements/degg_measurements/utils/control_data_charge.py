import numpy as np
import tables
import pandas as pd
from glob import glob
import os
from matplotlib import pyplot as plt
from warnings import warn
from datetime import datetime


def write_chargestamp_to_hdf5(filename, chargestamps, timestamps):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col(shape=np.asarray(timestamps).shape)
            timestamp = tables.Int64Col(shape=np.asarray(timestamps).shape)
            chargestamp = tables.Float32Col(shape=np.asarray(chargestamps).shape)
            datetime_timestamp = tables.Float64Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/','data',Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        try:
            table = open_file.get_node('/data')
        except:
            with tables.open_file(filename, 'w') as open_file:
                table = open_file.create_table('/', 'data', Event)
            table = open_file.get_node('/data')

        event = table.row
        event['event_id'] = np.arange(len(timestamps))
        event['timestamp'] = timestamps
        event['chargestamp'] = chargestamps # in the unit [pC]
        event['datetime_timestamp'] = datetime.now().timestamp()
        event.append()
        table.flush()

def read_data_charge(filename):
    with tables.open_file(filename) as open_file:
        try:
            data = open_file.get_node('/data')
        except:
            print(f"{filename} missing /data")
        try:
            parameters = open_file.get_node('/parameters')
        except:
            print(f"{filename} missing /parameters")

        parameter_keys = parameters.keys[:]
        parameter_vals = parameters.values[:]
        parameter_dict = {}
        for key, val in zip(parameter_keys, parameter_vals):
            key = key.decode('utf-8')
            val = val.decode('utf-8')
            try:
                parameter_dict[key] = int(val)
            except ValueError:
                parameter_dict[key] = val

        charges = data.col('chargestamp')
        timestamps = data.col('timestamp')
        try:
            datetime_timestamp = data.col('datetime_timestamp')
        except:
            warning_str = filename + " does not include datetime timing information (file is probably older than 2022/05/11)."
            warn(warning_str)
            ##this was the start of FAT
            datetime_timestamp = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()

        if len(charges)==1:
            charge = charges[0]
        else:
            charge = charges
        if len(timestamps)==1:
            timestamp = timestamps[0]
        else:
            timestamp = timestamps

    return charge, timestamp, datetime_timestamp, parameter_dict

def write_qstamp_mon_to_hdf5(filename,
                             chargestamps,
                             timestamps,
                             pc_time,
                             obs_hv,
                             obs_temp):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            pctime = tables.Float64Col()
            hv = tables.Float32Col()
            temperature = tables.Float32Col()
            timestamp = tables.Int64Col(shape=np.asarray(timestamps).shape)
            chargestamp = tables.Float32Col(shape=np.asarray(chargestamps).shape)

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/','data',Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        try:
            table = open_file.get_node('/data')
        except:
            with tables.open_file(filename, 'w') as open_file:
                table = open_file.create_table('/', 'data', Event)
            table = open_file.get_node('/data')

        event = table.row

        #print(f'Stored time: {pc_time}, {datetime.datetime.fromtimestamp(pc_time)}')
        event['pctime'] = pc_time
        event['hv'] = obs_hv
        event['temperature'] = obs_temp
        event['timestamp'] = timestamps
        event['chargestamp'] = chargestamps # in the unit [pC]

        event.append()
        table.flush()

def write_flasher_chargestamp_to_hdf5(filename, chargestamps, timestamps, led_mask, led_bias, led_rate):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col(shape=np.asarray(timestamps).shape)
            timestamp = tables.Int64Col(shape=np.asarray(timestamps).shape)
            chargestamp = tables.Float32Col(shape=np.asarray(chargestamps).shape)
            ledmask = tables.Int64Col()
            ledbias = tables.Int64Col()
            ledrate = tables.Int64Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/','data',Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        try:
            table = open_file.get_node('/data')
        except:
            with tables.open_file(filename, 'w') as open_file:
                table = open_file.create_table('/', 'data', Event)
            table = open_file.get_node('/data')

        event = table.row
        event['event_id'] = np.arange(len(timestamps))
        event['timestamp'] = timestamps
        event['chargestamp'] = chargestamps # in the unit [pC]
        event['ledmask'] = led_mask
        event['ledbias'] = led_bias
        event['ledrate'] = led_rate

        event.append()

def write_chargestamp_to_hdf5_old(filename, index, chargestamp, timestamp, channel):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            timestamp = tables.Int64Col()
            chargestamp = tables.Float32Col()
            channel = tables.Int32Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/','data',Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        try:
            table = open_file.get_node('/data')
        except:
            with tables.open_file(filename, 'w') as open_file:
                table = open_file.create_table('/', 'data', Event)
            table = open_file.get_node('/data')

        event = table.row

        event['event_id'] = index
        event['timestamp'] = timestamp
        event['chargestamp'] = chargestamp * 1e12 # in the unit [pC]
        event['channel'] = channel

        event.append()
        table.flush()

def read_data_charge_old(filename):
    with tables.open_file(filename) as open_file:
        try:
            data = open_file.get_node('/data')
            parameters = open_file.get_node('/parameters')
        except:
            print(f"{filename} missing /data and/or /parameters")

        parameter_keys = parameters.keys[:]
        parameter_vals = parameters.values[:]
        parameter_dict = {}
        for key, val in zip(parameter_keys, parameter_vals):
            key = key.decode('utf-8')
            val = val.decode('utf-8')
            try:
                parameter_dict[key] = int(val)
            except ValueError:
                parameter_dict[key] = val

        event_id = data.col('event_id')
        charges = data.col('chargestamp')
        timestamps = data.col('timestamp')

    return event_id, charges, timestamps, parameter_dict

