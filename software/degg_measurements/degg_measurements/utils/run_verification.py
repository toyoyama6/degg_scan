import sys, os
import click
from termcolor import colored

from chiba_slackbot import send_message, send_warning

from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import extract_runnumber_from_path

##these are saved to the general dict
CAMERA_MEASUREMENT_LIST = ['camera_darknoise', 'camera_pattern']

#these are per PMT
MEASUREMENT_LIST = ['DeltaTMeasurement', 'LinearityMeasurement', 'DoublePulse', 'GainMeasurement', 'TransitTimeSpread',
                    'DarkrateScalerMeasurement', 'LaserVisibilityMeasurement', 'DarkrateTemperature', 'FlasherCheck']

def verify_results(run_json):

    results_dict = {}

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        degg_name = degg_dict['DEggSerialNumber']
        for data_key in MEASUREMENT_LIST:
            for pmt in ['LowerPmt', 'UpperPmt']:
                if data_key == 'FlasherCheck' and pmt == 'UpperPmt':
                    continue
                eligible_keys = [key for key in degg_dict[pmt].keys() if key.startswith(data_key)]
                cts = [int(key.split('_')[1]) for key in eligible_keys]
                if len(cts) == 0:
                    print(f'No measurement found for {data_key}: {degg_dict[pmt]["SerialNumber"]}')
                    results_dict[f'{degg_name}_{pmt}_{data_key}'] = 'NoMeasurement'
                    continue
                ##If the measurement crashed, Folder might be empty.
                ##Just get the last one
                d = degg_dict[pmt][f'{data_key}_{cts[-1]:02d}']
                folder = d['Folder']
                if folder == 'None':
                    results_dict[f'{degg_name}_{pmt}_{data_key}'] = 'NoFolder'
                elif os.path.exists(folder) == True:
                    results_dict[f'{degg_name}_{pmt}_{data_key}'] = 'Pass'
                elif os.path.exists(folder) == False:
                    results_dict[f'{degg_name}_{pmt}_{data_key}'] = 'BadPath'
                else:
                    results_dict[f'{degg_name}_{pmt}_{data_key}'] = 'OtherError'

        for data_key in CAMERA_MEASUREMENT_LIST:
            eligible_keys = [key for key in degg_dict.keys() if key.startswith(data_key)]
            cts = [int(key.split('_')[-1]) for key in eligible_keys]
            if len(cts) == 0:
                print(f'No measurement found for {data_key}: {degg_name}')
                results_dict[f'{degg_name}_{data_key}'] = 'NoMeasurement'
                continue
            ##If the measurement crashed, Folder might be empty.
            ##Just get the last one
            d = degg_dict[f'{data_key}_{cts[-1]:02d}']
            folder = d['Folder']
            if folder == 'None':
                results_dict[f'{degg_name}_{data_key}'] = 'NoFolder'
            elif os.path.exists(folder) == True:
                results_dict[f'{degg_name}_{data_key}'] = 'Pass'
            elif os.path.exists(folder) == False:
                results_dict[f'{degg_name}_{data_key}'] = 'BadPath'
            else:
                results_dict[f'{degg_name}_{data_key}'] = 'OtherError'

    return results_dict

def print_format(key, val, results):
    pstr = f'{key}: {val}'
    if val == 'Pass':
        print(colored(pstr, 'green'))
        results[0] += 1
    if val == 'BadPath' or val == 'NoFolder':
        print(colored(pstr, 'yellow'))
        results[1] += 1
    if val == 'NoMeasurement' or val == 'OtherError':
        print(colored(pstr, 'red'))
        results[2] += 1
    return results

##format print results more clearly
def print_results(results_dict):
    results = [0, 0, 0]
    for key in results_dict.keys():
        val = results_dict[key]
        results = print_format(key, val, results)

    print('-'*20)
    print('Summary:')
    print(f'Number of Good Results        : {results[0]}')
    print(f'Number of Missing Results     : {results[1]}')
    print(f'Number of Missing Measurements: {results[2]}')

@click.command()
@click.argument('run_json')
def main(run_json):
    results_dict = verify_results(run_json)
    print_results(results_dict)

if __name__ == "__main__":
    main()

##end
