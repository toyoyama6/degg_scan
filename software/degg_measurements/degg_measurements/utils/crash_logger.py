"""
This provides a utility function to log a collection of data to a csv file
"""

import os
from datetime import datetime
from degg_measurements import DATA_DIR
LOG_FOLDER = os.path.join(DATA_DIR, "crash_logs")
if not os.path.exists(LOG_FOLDER):
    try:
        os.makedirs(LOG_FOLDER)
    except:
        pass

def log_crash(filename:str,
            start_time:datetime,
            log_time:datetime,
            port_no:int,
            channel:int,
            temp:float,
            hv_readbck:float,
            hv_set:float,
            darkrate:float,
            threshold:float,
            spe_peak_height:float,
            is_fir:bool):
    """
        Filename should not be the absolute path, just the name of the file
    """
    full_name = os.path.join(LOG_FOLDER,filename)
    existed = os.path.exists(full_name)

    all_data = [start_time, log_time, port_no, channel, temp, hv_readbck, hv_set, darkrate, threshold, spe_peak_height, is_fir]
    all_data = [str(entry) for entry in all_data]

    this_file = open(full_name, 'at')
    if not existed:
        this_file.write("#Msmt start time, Except time, port no, channel, temp, hv_readback, hv_set, darkrate, threshold, spe peak height, is FIR\n")

    this_file.write(", ".join(all_data)+"\n")

    this_file.close()

