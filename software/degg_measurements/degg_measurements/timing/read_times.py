import tables
import pandas as pd
import os, sys
import numpy as np

def read_times(filename):
    with tables.open_file(filename) as open_file:
        data = open_file.get_node('/data')
        timestamp = data.col('timestamp')
        mfh_t = np.float128(data.col('mfh_times'))
        event_id = data.col('event_id')
        mbtimestamp = data.col('mb_timestamps')
        offset_time = data.col('offset_time')

    return event_id, timestamp, mbtimestamp, mfh_t, offset_time
