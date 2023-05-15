import os
from glob import glob
import numpy as np

from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements import RUN_DIR

def get_run_json(run_json):
    if run_json == 'latest':
        file_list = glob(os.path.join(RUN_DIR, 'run', '*.json'))
        latest_file = max(file_list, key=os.path.getctime)
        run_json = latest_file
        run_number = extract_runnumber_from_path(run_json)
    else:
        run_number = extract_runnumber_from_path(run_json)
        run_number = f'{int(run_number):05d}'
        run_json = os.path.join(RUN_DIR, 'run', f'run_{run_number}.json')
    return run_json, run_number


def get_measurement_numbers(degg_dict, pmt, measurement_number, data_key, returnAll=False):
    """

    """

    if measurement_number == 'latest':
        if pmt == None:
            eligible_keys = [key for key in degg_dict.keys()
                         if key.startswith(data_key)]
        else:
            eligible_keys = [key for key in degg_dict[pmt].keys()
                            if key.startswith(data_key)]
        cts = [int(key.split('_')[1]) for key in eligible_keys]
        if len(cts) == 0:
            print('No measurement found for '
                  f'{degg_dict[pmt]["SerialNumber"]} '
                  f'in DEgg {degg_dict["DEggSerialNumber"]}. '
                  'Skipping it!')
            print(f"I couldn't find any measurement numbers for {degg_dict['DEggSerialNumber']}, {pmt}, and {data_key}")
            raise ValueError(f'Measurement number not found for {eligible_keys}!')
        if returnAll == True:
            return cts
        else:
            measurement_number = np.max(cts)
    else:
        measurement_number = measurement_number.split(',')
    measurement_number = np.array(np.atleast_1d(measurement_number), dtype=int)
    return measurement_number

