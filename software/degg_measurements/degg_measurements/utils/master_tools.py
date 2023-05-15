import numpy as np
from termcolor import colored
from tqdm import tqdm


import sys, os, time
import json
##general purpose functions - used by the fat_master

def open_json(file_path, verbose=False):
    print(file_path)
    if os.path.isfile(file_path):
        with open(file_path, 'r') as open_file:
            current_dict = json.load(open_file)
            if verbose is True:
                print(f"Opened Run File: {file_path}")
            return current_dict
    else:
        print(f"Could not open file at {file_path}")
        print(colored("Exiting!", 'red'))
        raise IOError

def get_run_info(file_path, verbose):
    current_dict = open_json(file_path)
    ##loop over all keys in the run json
    try:
        for key in current_dict:
            value = current_dict[key]
            if value is None:
                raise ValueError("Key Value is None!")
    except:
        raise KeyError(f"Error Reading Key from Run File: {key}")

    return current_dict

##add exceptions to run_json
def get_degg_names(info, verbose=False):
    degg_id_list = []
    for key in info:
        if key in ['comment', 'date', 'end_time', 'RunTerminated']:
            continue
        if key[:-1] == 'ManualInputTime':
            continue
        if info[key] in [-1, 0, 1]:
            continue
        if key[:-3] == 'MasterFAT':
            continue
        degg_id_list.append(info[key])
    return degg_id_list

def wait_time(run_json_file, pause=10, verbose=False):
    pause = int(pause)
    if verbose:
        print("DAQ Paused for " + str(pause) + " seconds")
    for i in tqdm(range(pause)):
        time.sleep(1)
    return True

def report_status(degg_info_list, verbose=True):
    if len(degg_info_list) == 0:
        print("@channel No D-Eggs Returned STATUS")
        return False

    port_list = []
    for degg_info in degg_info_list:
        degg_id, port, mb_temp, hv_0, hv_1 = degg_info
        msg_string = f"D-Egg {degg_id} : Port {port} : \
                       Temp {mb_temp:.1f} : HV0 {hv_0:.1f} : HV1 {hv_1:.1f}"
        print('msg_string')
        port_list.append(port)

    total = 16
    num_responsive = len(degg_info_list)
    msg_string = f"D-Eggs Responsive: {num_responsive} / {total}"
    print(msg_string)
    all_ports = np.arange(5000, 5016, 1)

    if num_responsive != total:
        missing_ports = set(all_ports).difference(port_list)
        msg_string = f"Missing Ports: {missing_ports}"
        print(msg_string)
    return True

##end
