import json
import sys, os
from termcolor import colored
import glob
import pandas as pd
import numpy as np

from degg_measurements import RUN_DIR
from degg_measurements import IGNORE_LIST

from degg_measurements.utils import update_json
#from degg_measurements.utils import add_git_infos_to_dict


##need to load individual D-Egg json files and forward to DAQ scripts
def audit_ignore_list(this_degg_file, this_degg_dict, keys,
                      file_path=IGNORE_LIST, analysis=False):
                      #file_path=None, analysis=False):
    print(IGNORE_LIST)
    keys = [keys, keys]
    #print(keys)
    this_degg = this_degg_dict['DEggSerialNumber']
    for k in load_ignore_json(file_path):
        if this_degg == k:
            if keys[0].split('_')[0] == "OnlineMon" or keys[0].split('_')[0] == "camera":
                _dict = this_degg_dict[keys[0]]
                _dict['Ignored'] = 'True'
            else:
                for ch, pmt in enumerate(['LowerPmt', 'UpperPmt']):
                    print(this_degg_dict[pmt])
                    _dict = this_degg_dict[pmt][keys[ch]]
                    _dict['Ignored'] = 'True'
            print(f'{this_degg} is being ignored based on {file_path}')
            if analysis == False:
                print("analysis didn't go well")
            update_json(this_degg_file, this_degg_dict)
            return True
    return False

def load_ignore_json(file_path=None):
    if not os.path.exists(file_path):
        return
        #raise FileNotFoundError(f'{file_path} does not exist!')

    with open(file_path, 'r') as open_file:
        current_dict = json.load(open_file)
    ##the keys are the DEggs serial numbers
    keys = current_dict.keys()
    if len(keys) == 0:
        print('No DEggs in the ignore list :)')
    list_of_deggs = []
    for k in keys:
        list_of_deggs.append(k)
    return list_of_deggs

#first load "run" file to get all D-Egg jsons
def load_run_json(file_path):
    if file_path is None:
        print("No file path - using most recent file")
        list_of_files = glob.glob(os.path.join(
            RUN_DIR, 'run/*.json'))
        latest_file = max(list_of_files, key=os.path.getmtime)
        file_path = latest_file

    if os.path.isfile(file_path):
        with open(file_path, 'r') as open_file:
            current_dict = json.load(open_file)
    else:
        print(f"Could not open file at {file_path}")
        print(colored("Exiting!", 'red'))
        exit(1)

    degg_path_list = []

    ban_list = ['comment', 'date', 'end_time', 'RunTerminated']
    for key in current_dict:
        #print(key)
        if key in ban_list:
            continue
        if key[:-1] == 'ManualInputTime':
            continue
        if current_dict[key] in [-1, 0, 1]:
            continue
        if key[:-3] == "MasterFAT":
            continue
        degg_json_path = current_dict[key]
        ##redundancy check for valid paths
        if os.path.isfile(degg_json_path) is False:
            raise IOError("Unable to find D-Egg json - error in creation?")

        degg_path_list.append(degg_json_path)

    return degg_path_list


##load an individual D-Egg dict
def load_degg_dict(degg_json_file):
    if os.path.isfile(degg_json_file):
        with open(degg_json_file, 'r') as open_file:
            current_dict = json.load(open_file)
    else:
        raise IOError(f"Error opening D-Egg json file {degg_json_file}")
        #exit(1)
    return current_dict


def sort_degg_dicts_and_files_by_key(
        degg_file_list, # Sequence[str]
        key='Port', # str
        key_type=int,
        return_sorting_index=False): #Type -> Tuple[Sequence[str], Sequence[dict]]
    degg_dicts = []
    values = []
    for degg_file in degg_file_list:
        degg_dict = load_degg_dict(degg_file)
        degg_dicts.append(degg_dict)
        value = key_type(degg_dict[key])
        values.append(value)

    sort_idx = np.argsort(values)
    sorted_degg_dicts = np.array(degg_dicts)[sort_idx]
    sorted_degg_files = np.array(degg_file_list)[sort_idx]
    if return_sorting_index:
        return sorted_degg_files, sorted_degg_dicts, sort_idx
    else:
        return sorted_degg_files, sorted_degg_dicts


def load_config_dict(config_json_file):
    if os.path.isfile(config_json_file):
        with open(config_json_file, 'r') as open_file:
            current_dict = json.load(open_file)
    else:
        print(f"Error opening analysis configuration file {config_json_file}")
        exit(1)
    return current_dict


def flatten_dict(dct, sep='.'):
    df = pd.json_normalize(dct, sep=sep)
    new_dct = df.to_dict(orient='records')[0]
    return new_dct


def check_dirname_in_pmt_dict(dirname, pmt_dict, key_name):
    relevant_keys = [key for key in pmt_dict.keys()
                     if key.startswith(key_name)]
    dirname_exists = False
    for key in relevant_keys:
        if pmt_dict[key]['Folder'] == dirname:
            dirname_exists = True
            return dirname_exists
    return dirname_exists


def create_key(dct, key, mon_pad=False):
    cnt = 0
    while True:
        if mon_pad == False:
            new_key = key + f'_{cnt:02d}'
        if mon_pad == True:
            new_key = key + f'_{cnt:04d}'
        try:
            dct[new_key]
        except KeyError:
            return new_key
        else:
            cnt += 1


def add_default_meas_dict(degg_dicts,
                          degg_files,
                          meas_key,
                          comment,
                          **kwargs):
    keys = []
    for degg_dict, degg_file in zip(degg_dicts, degg_files):
        keys_per_degg = []
        for pmt in ['LowerPmt', 'UpperPmt']:
            key = create_key(degg_dict[pmt], meas_key)
            keys_per_degg.append(key)

            meta_dict = {
                'Folder': 'None',
                'Comment': comment
            }
            meta_dict.update(kwargs)
            #meta_dict = add_git_infos_to_dict(meta_dict)
            degg_dict[pmt][key] = meta_dict
        keys.append(keys_per_degg)
        update_json(degg_file, degg_dict)
    return keys

def add_default_calibration_meas_dict(degg_dicts,
                                      degg_files,
                                      meas_key,
                                      comment,
                                      **kwargs):
    keys = []
    for degg_dict, degg_file in zip(degg_dicts, degg_files):
        key = create_key(degg_dict, meas_key)
        meta_dict = {
            'Folder': 'None',
            'Comment': comment
        }
        meta_dict.update(kwargs)
        #meta_dict = add_git_infos_to_dict(meta_dict)
        degg_dict[key] = meta_dict
        update_json(degg_file, degg_dict)
    return key

