###################################################
## This script is to provide simple functions
## you can run before starting a new run
###################################################
from termcolor import colored
import click
import time
import os, sys
import subprocess
import numpy as np
from degg_measurements.utils import filter_wheel_helper
from filter_wheel_helper import setup_fw
from degg_measurements import THERMOMETER_PATH
from degg_measurements import HUMIDITY_SENSOR_DRIVER


def check_filter_wheel():
    print(colored("Checking Filter Wheel...",
            'yellow'))
    try:
        from filterWheel.control102C import connect_wheel, check_wheel
        from filterWheel.control102C import disable_running_lights
        from filterWheel.control102C import change_filter, get_valid_strengths
    except ModuleNotFoundError:
        print(f'Filter wheel code is expected to be installed at {fw_code_path}!')
    fw0, fw1, validList = setup_fw(get_list=True)
    fw0_info = check_wheel(fw0)
    fw1_info = check_wheel(fw1)
    valid_strengths_0 = get_valid_strengths(0)
    valid_strengths_1 = get_valid_strengths(1)
    #to measure by increasing intensity, sort first
    valid_strengths_0 = np.sort(valid_strengths_0)
    valid_strengths_1 = np.sort(valid_strengths_1)
    print(f"Filter 0 Strengths: {valid_strengths_0}")
    print(f"Filter 1 Strengths: {valid_strengths_1}")
    print(colored("Check finished!", 'green'))


def check_thermometer():
    print(colored("Checking thermometer - verify all 4 channels are working...", 'yellow'))
    import goldschmidt
    goldschmidt_path = goldschmidt.__path__
    subprocess.run(['python3', os.path.join(goldschmidt_path[0], 'record_temp.py'),
                    f'{THERMOMETER_PATH}', '1', '2', '3', '4',
                    os.path.join('temp.csv'),
                    '-v'])
    print(colored("Finished checking thermometer", 'green'))


def check_humidity_sensor():
    print(colored("Checking Humidity Sensors...",
            'yellow'))
    sys.path.append(HUMIDITY_SENSOR_DRIVER)
    try:
        from humidity_readout import data_wrapper
    except ModuleNotFoundError:
        print(f'Code is expected to be installed at {code_path}!')
    data_wrapper('both', verbose=True)
    print(colored("Finished Reading Humidity Sensors...",
            'green'))

def check_function_generator():
    print(colored("Checking Function Generator...",
            'yellow'))

    try:
        from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
    except ImportError:
        raise ValueError('The library function_generators is missing! Go check!')# WARNING:

    fg = FG3101()
    fg.startup()
    time.sleep(2)
    fg.disable()
    print(colored("Check finished!", 'green'))

@click.command()
@click.option('--filter_wheel', '-fw', is_flag=True)
@click.option('--humidity_sensor', '-h', is_flag=True)
@click.option('--function_generator', '-fg', is_flag=True)
@click.option('--thermometer', '-t', is_flag=True)
@click.option('--check_all', is_flag=True)
def main(filter_wheel, humidity_sensor,
         function_generator, thermometer, check_all):
    if bool(filter_wheel) == False \
        and bool(humidity_sensor) == False \
        and bool(function_generator) == False \
        and bool(thermometer) == False:
        check_all = True

    print(colored(
        "Running checks for independent devices", 'green'))

    if bool(filter_wheel) == True or bool(check_all) == True:
        check_filter_wheel()
    if bool(humidity_sensor) == True or bool(check_all) == True:
        check_humidity_sensor()
    if bool(function_generator) == True or bool(check_all) == True:
        check_function_generator()
    if bool(thermometer) == True or bool(check_all) == True:
        check_thermometer()

    print(colored('Please TURN ON the freezer if it is not already!', 'yellow'))
    time.sleep(3)

    print(colored("Finished", 'green'))

if __name__ == "__main__":
    main()

##end
