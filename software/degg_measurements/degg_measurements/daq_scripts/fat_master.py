##generic imports
import sys, os, time
import numpy as np
import shutil

##for interface with chiba-daq slack channel
from chiba_slackbot import send_message
from chiba_slackbot import send_warning
from chiba_slackbot import send_critical

from datetime import datetime

##coloured text
from termcolor import colored

##json file handling
import json

##stack print after except
import traceback

##progress bar
from tqdm import tqdm

##command line option parsing
import click

##iceboot related imports
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils.stack_fmt import stripStackSize
from degg_measurements.utils import create_key


##for copying dictionaries
from copy import deepcopy

##scheduler class
from degg_measurements.utils.scheduler import Scheduler

##update json function
from degg_measurements.utils.create_configs import update_json

##load json files
from degg_measurements.utils import extract_runnumber_from_path

##backup run config - between operations
from degg_measurements.utils import run_backup

# git related imports
#from degg_measurements.utils import uncommitted_changes
#from degg_measurements.utils import add_git_infos_to_dict

##generic functions from master_tools
from degg_measurements.utils.master_tools import open_json
from degg_measurements.utils.master_tools import get_run_info
from degg_measurements.utils.master_tools import get_degg_names
from degg_measurements.utils.master_tools import wait_time
from degg_measurements.utils.master_tools import report_status

##power control
from degg_measurements.utils.power_control import wp_off, wp_on

##freezer control
from degg_measurements.utils.freezer_control_wrapper import dummy_wrapper

##rebooting related controls
from degg_measurements.monitoring.regrowth import setup_classes
from degg_measurements.monitoring.regrowth import assignICMPort
from degg_measurements.monitoring.regrowth import run_reboot
from degg_measurements.analysis.analysis_utils import get_run_json
from degg_measurements.monitoring import readout_sensor
from degg_measurements.utils.hv_check import checkHV

##list of task modules
###########################################################
## disable laser as standalone function
from degg_measurements.utils import disable_laser

##NOTE - now handled on the boards
## ramping at low temperatures is important
#from degg_measurements.utils import ramp

##DEPRECATED!
## monitoring scripts
from degg_measurements.monitoring import readout_and_reboot
from degg_measurements.monitoring import readout_and_readout

## STF testing - external dependencies
from degg_measurements.daq_scripts.measure_stf import measure_stf

## Calculate scan points online
from degg_measurements.daq_scripts.measure_gain_online import measure_gain

## Relevant for dark rate measurements
from degg_measurements.daq_scripts.measure_scaler import measure_scaler

## Modernised linearity measurement
from degg_measurements.daq_scripts.measure_linearity import measure_linearity

## Can be run with 2 configs - double pulse or burst
from degg_measurements.daq_scripts.measure_pulsed_waveform import measure_pulsed_waveform

## Measure flashers - updated script
#from measure_flasher_low_gain import measure_baseline_flasher as measure_flasher
from degg_measurements.daq_scripts.measure_flasher_caltrig_chargestamp import measure_baseline_flasher

##DEPRECATED - please use monitoring scripts
## Measure dark rate using scalers and charge stamp (deltaT) regularly
#from degg_measurements.daq_scripts.measure_dark_temperature import wrapper


## Measure deltaT using the FIR trigger
from degg_measurements.daq_scripts.measure_dt import measure_spe

## Measure the PMT TTS
from degg_measurements.timing.get_offset import run_timing

##Analyze SPE data
from degg_measurements.analysis.gain.analyze_gain import analysis_wrapper

##Cameras
from degg_measurements.daq_scripts.measure_camera_darknoise import measure_camera
from degg_measurements.daq_scripts.measure_camera_pattern import measure_pattern

###########################################################

from degg_measurements import RUN_DIR

KEY_NAME = 'MasterFAT'


def book_keeping_slack(info, run_number):
    now = datetime.now()
    send_message("=======================================================")
    send_message("Executing FAT Master Script - Time is now: " + str(now))
    time.sleep(1)
    send_message("   -- Current Run: " + str(run_number))
    time.sleep(1)
    send_message("   -- D-Egg IDs: " + '\n')
    degg_file_list = get_degg_names(info, verbose=True)
    for degg_file_path in degg_file_list:
        current_dict = open_json(degg_file_path, verbose=False)
        port = current_dict['Port']
        split = degg_file_path.split("/")
        degg_id = split[-1]
        degg_id.replace(".json","")
        send_str = f'{port}: {degg_id}'
        send_message(send_str)

def book_keeping(schedule):
    run_number = extract_runnumber_from_path(schedule.get_run())
    verbose = schedule.verbosity()
    recover = schedule.recovery()
    print(f"Hello and welcome to the FAT Master Script! (Run {run_number})")
    print(f"Running with verbose={verbose}")
    print(f"Running with recover={recover}")

    ##get info & check run file is valid
    #schedule.get_run() gives the path to the run file
    info = get_run_info(schedule.get_run(), verbose)

    if verbose:
        book_keeping_slack(info, run_number)
    ##check for connections & valid fpga
    all_valid = run_check(info, verbose=verbose)
    return run_number

##check if all D-Eggs are connected before scheduling
def run_check(run_info, verbose=False):
    comment = run_info['comment']
    date = run_info['date']
    print(f"Run file generated on : {date}")
    print(f"with comment : {comment}")

    degg_paths = get_degg_names(run_info, verbose=verbose)
    valid_list = []
    print(colored("Checking D-Eggs before submitting schedule!", 'green'))
    for degg_path in degg_paths:
        valid = degg_check(degg_path, verbose)
        valid_list.append(valid)
        if valid is False:
            send_warning(f"D-Egg ({degg_path}) returned false during check!")

    print(colored(f'Ready D-Eggs: {np.sum(valid_list)}/{len(valid_list)}', 'green'))
    if np.sum(valid_list) < len(valid_list):
        return False
    else:
        return True

##check if all D-Eggs are connected during schedule
def status_check(run_json_path, verbose=True, reboot=False):
    if reboot == True:
        print('Rebooting:', colored(reboot, 'red'))
    run_info = get_run_info(run_json_path, verbose)
    degg_paths = get_degg_names(run_info, verbose=verbose)
    n_attempts = 0
    degg_info_list = []
    for i, degg_path in enumerate(degg_paths):
        running = degg_check(degg_path, verbose, reboot)
        if running is True:
            degg_info = get_info(degg_path, verbose)
            degg_info_list.append(degg_info)

        if running is False:
            send_warning(f"D-Egg ({degg_path}) returned false during check!")

    report_status(degg_info_list)

def get_info(degg_path, verbose):
    current_dict = open_json(degg_path, verbose=verbose)
    degg_id = current_dict['DEggSerialNumber']
    port = current_dict['Port']
    session = startIcebootSession(host='localhost', port=port)
    mb_temp = session.sloAdcReadChannel(7)
    hv_0 = session.sloAdcReadChannel(8)
    hv_1 = session.sloAdcReadChannel(10)
    session.close()
    del session
    return (degg_id, port, mb_temp, hv_0, hv_1)

def reflash_fpga(session):
    reconfigured = False
    fails = 0
    while reconfigured == False:
        try:
            flashLS = session.flashLS()
            try:
                firmwarefilename = flashLS[len(flashLS)-1]['Name'] # latest uploaded file
            except KeyError:
                print(flashLS)
                raise
            output = session.flashConfigureCycloneFPGA(firmwarefilename)
            reconfigured = True
        except TimeoutError:
            print("Timeout during FPGA flash from reboot!")
            fails += 1
        except:
            print("Error during FPGA flash from reboot!")
            print(traceback.format_exc())
            send_message(traceback.format_exc())
            fails += 1
        if fails >= 3:
            send_warning("Failed to reconfigure FPGA 3 (or more) times in a row!")
            break
    fpgaVersion = session.cmd('fpgaVersion .s drop')
    return stripStackSize(fpgaVersion)

def degg_check(json_path, verbose=False, reboot=False):
    current_dict = open_json(json_path, verbose=verbose)
    fpga_version = current_dict['fpgaVersion']
    port = current_dict['Port']
    degg_id = current_dict['DEggSerialNumber']
    icm_id = current_dict['ICMID']


    ##warm reboot tests
    if reboot == True:
        DEggCalList, dirname = setup_classes(json_path, mode='reboot')
        ##just to get run_number
        run_json, run_number = get_run_json(json_path)
        hvOn = 0
        for deggCal in DEggCalList:
            deggCal.hvStatus = [False, False]
            degg_dict = deggCal.degg_dict
            port = degg_dict['Port']
            assignICMPort(deggCal)
            session = startIcebootSession(host='localhost', port=port)
            temperature = readout_sensor(session, 'temperature_sensor')
            deggCal.temperature = temperature
            deggCal.session = session
            pmtList = ['LowerPmt', 'UpperPmt']
            for channel in [0, 1]:
                hv_enabled = checkHV(session, channel)
                hvOn += hv_enabled
                deggCal.hvStatus[channel] = hv_enabled

        run_reboot(DEggCalList, dirname, run_number)

        return True

    ##try to start an iceboot session
    try:
        session = startIcebootSession(host='localhost', port=port)
    except TimeoutError:
        print(f"Unable to start Iceboot session: {port}")
        print(f"From Dict: D-Egg ID {degg_id}, ICM ID {icm_id}")
        return False

    time.sleep(0.5)

    ##now test FPGA version
    try:
        fpgaVersion = session.cmd('fpgaVersion .s drop')
    except:
        print(f"Could not determine fpgaVersion from session on port {port}")
        fpgaVersion = -1
        session.close()
        del session
        time.sleep(1)
        return False
    session_fpga_version = stripStackSize(fpgaVersion)

    ##this method is not sufficient for FAT
    ##code is left for now, but unused
    '''
    if reboot == True:
        send_message(f"Rebooting D-Egg: {degg_id}, Port: {port}")
        session.reboot()
        time.sleep(3)
        session.bypassBootloader()
        new_fpga_version = -1
        new_fpga_version = reflash_fpga(session)
        print(new_fpga_version)
        send_message(f"Post-Reboot Info: PRE: {session_fpga_version}, POST: {new_fpga_version}")

        ##make sure following if statement also gets checked afer rebooting
        session_fpga_version = new_fpga_version
    '''

    if int(session_fpga_version) != int(fpga_version):
        print(f"FPGA Versions do not match for {port}! \n " +
              f"{session_fpga_version} != {fpga_version}")
        ##if session could be opened, but D-Egg became
        ##unset, try to flash again
        new_fpga_version = reflash_fpga(session)
        if int(new_fpga_version) != int(fpga_version):
            send_warning("@channel - Master Script Stopped: FPGA version mis-match during status check!")
            return False
    session.close()
    del session
    time.sleep(1)

    return True

##copy config file from daq_scripts/configs to json directory
def config_arxiv(schedule):
    run_file = schedule.get_run()
    run_dir  = os.path.dirname(run_file)
    ##navigate to run_ directory
    run_name = os.path.splitext(os.path.basename(run_file))[0]
    run_specific_dir = os.path.join(run_dir, f'../{run_name}')

    unique_num = 0
    config_file = schedule.get_config_file()
    basename = os.path.basename(config_file)
    split    = os.path.splitext(basename)
    new_name = split[0] + f"_{unique_num}" + split[1]
    while os.path.isfile(new_name) == True:
        unique_num += 1
        new_name = split[0] + f"_{unique_num}" + split[1]

    arxiv_path = os.path.join(run_specific_dir, new_name)
    shutil.copy(config_file, arxiv_path)
    return arxiv_path

##unformatted sending messages fills slack channel too much
##also consumes too much time since we have ~150 measurements * 0.5s sleep
def schedule_summary(schedule, msg_str_list):
    send_message("Condensed Schedule:")
    for msg_t, task in zip(msg_str_list, schedule.get_task_list()):
        t_str = schedule.get_task_string(task)
        if t_str not in ['status_check', 'disable_laser', 'wrapper', 'manual_input',
                         'online_mon', 'bootmon', 'slowmon', 'trigger_remote_wrapper',
                         'analysis_wrapper', 'dummy_wrapper', 'validate_gain',
                         'constant_monitor']:
            send_message(msg_t)
            time.sleep(0.2)


def list_schedule(schedule, send_all=False):
    verbose = schedule.verbosity()
    recover = schedule.recovery()
    task_list = schedule.get_task_list()
    task_arg_list = schedule.get_task_arg_list()
    task_title_list = schedule.get_task_title_list()
    if len(task_list) == 0 or len(task_arg_list) == 0:
        raise IndexError("Length of schedule/args is 0!")

    msg_str_list = [''] * len(task_list)
    if verbose:
        for index, task in enumerate(task_list):
            msg_str = schedule.get_task_print_string(task, index)
            msg_str_list[index] = msg_str
            if send_all == True:
                send_message(msg_str)
                time.sleep(0.2)
        if not send_all:
            schedule_summary(schedule, msg_str_list)


    ##copy config file for achiving
    arxiv_path = config_arxiv(schedule)

    current_dict = open_json(schedule.get_run(), verbose)
    new_dict = deepcopy(current_dict)
    task_num = 0
    meta_dict = dict()
    #meta_dict = add_git_infos_to_dict(meta_dict)
    for task, task_title in zip(task_list, task_title_list):
        task_str = schedule.get_task_print_string(task_title,
                                                  task_num)
        meta_dict[task_str] = -1
        task_num += 1

    meta_dict['ConfigPath'] = str(arxiv_path)
    today = datetime.today()
    today = today.strftime("%Y-%m-%d")
    meta_dict['Date'] = today

    key = create_key(new_dict, KEY_NAME)
    schedule.set_run_key(key)
    print(f'Measurement Key: {key}')
    new_dict[key] = meta_dict
    #print(new_dict)
    update_json(schedule.get_run(), new_dict)


def manual_input(run_json_path, message, verbose=True):
    send_message("DAQ is waiting for manual input")
    message = str(message)
    try:
        print(message)
        send_message(message)
    except:
        print("Error forwarding message to slack...")
    choice = input("DAQ is paused - Ready to continue? [Yes/No]")

    current_dict = open_json(run_json_path, verbose)
    new_dict = deepcopy(current_dict)

    manual_input_num = 0
    for key in new_dict:
        if 'ManualInputTime' in key:
            manual_input_num += 1

    if choice.lower() in ['yes', 'y']:
        now = datetime.now()
        send_message("Manual input received, continuing schedule...")
        key_str = 'ManualInputTime' + str(manual_input_num)
        new_dict[key_str] = str(now)
        update_json(run_json_path, new_dict)
        return True

    if choice.lower() not in ['yes', 'y']:
        choice_2 = input("Input interpreted as False - Please confirm choice [Yes/No]")
        if choice_2.lower() not in ['yes', 'y']:
            print("DAQ stopped by manual input")

            reason = ""
            while reason == "":
                reason = input("Please provide a reason:")

            send_warning("@channel - DAQ stopped by manual input")
            send_warning("@channel - Reason given: " + reason)

            new_dict['RunTerminated'] = reason
            update_json(run_json_path, new_dict)
            return False

##check if json has HV1e7Gain != -1
def validate_gain(run_json_file, verbose=False):
    #json_dict = open_json(run_json_file)
    info = get_run_info(run_json_file, verbose)
    degg_file_list = get_degg_names(info, verbose=True)
    validList = [False] * 32
    i = 0
    for degg_file_path in degg_file_list:
        current_dict = open_json(degg_file_path, verbose=False)
        for pmt in ['UpperPmt', 'LowerPmt']:
            try:
                hv_val = current_dict[pmt]['HV1e7Gain']
            except KeyError:
                raise KeyError(f'HV1e7Gain not filled in dictionary {degg_file_path}!')
            if float(hv_val) != -1:
                validList[i] = True
            else:
                print("Gain Analysis did not fill HV1e7Gain")
                send_message('DAQ Paused to run gain analysis!')
                choice = manual_input(run_json_file, 'Pausing for gain analysis')
                if choice == True:
                    continue

            i += 1

    print(f'PMTs with a valid HV at 1e7 Gain: {np.sum(validList)}')

    return True

def run_schedule(schedule):
    verbose = schedule.verbosity()
    current_dict = open_json(schedule.get_run())
    task_list = schedule.get_task_list()
    task_title_list = schedule.get_task_title_list()
    print(task_title_list)
    print("=" * 20)
    task_num = 0
    send_message("--- Now Running: ---")
    for task, task_title in zip(task_list, task_title_list):
        print_task_str = schedule.get_task_print_string(task,
                                                        task_num)
        print(print_task_str)
        task_str = schedule.get_task_string(task)
        dict_task_str = "[" + str(task_num) + "] " + str(task_title)
        if verbose:
            send_message(print_task_str)
        try:
            schedule.execute_task(task_title)
            ##true
            current_key = schedule.get_run_key()
            current_dict[current_key][dict_task_str] = 1
            update_json(schedule.get_run(), current_dict)
        except KeyboardInterrupt:
            current_dict[dict_task_str] = 0
            print("DAQ Stopped by Manual Interrupt")
            reason = ""
            while reason == "":
                reason = input("Please provide a reason:")
            send_warning("@channel - DAQ stopped by manual input")
            send_warning("@channel - Reason given: " + reason)
            current_dict['RunTerminated'] = reason
            update_json(schedule.get_run(), current_dict)
            print("Exiting...")
            exit(1)
        except:
            ##false
            current_dict[dict_task_str] = 0
            update_json(schedule.get_run(), current_dict)
            ##because general except, print stack
            print(traceback.format_exc())
            send_warning("@channel - DAQ stopped automatically")
            send_warning(traceback.format_exc())
            exit(1)
        task_num += 1
        ##unfinished task stays set to -1
    return True

def get_recovery_run_key(run_dict, key=KEY_NAME):
    highest_num = 0
    highest_key = ""
    for k in run_dict.keys():
        kk = k.split("_")
        if len(kk) > 2 or len(kk) < 2:
            continue
        this_key_name = kk[0]
        if this_key_name != key:
            continue
        this_key_num  = kk[1]
        if int(this_key_num) >= int(highest_num):
            highest_num = int(this_key_num)
            highest_key = k
    return highest_key


def recover_schedule(schedule):
    if bool(schedule.recovery()) is not True:
        raise ValueError('Schedule recover option not True, \
                         but recover_schedule was enabled!')

    verbose = schedule.verbosity()
    ##get the latest key from the dictionary
    current_dict = open_json(schedule.get_run())
    run_key = get_recovery_run_key(current_dict, KEY_NAME)

    print(colored("Running in recovery mode", 'green'))
    if verbose:
        send_message("Attempting to recover failed run")

    prev_task_list = []
    for key in current_dict[run_key]:
        val = current_dict[run_key][key]
        if val in [-1, 0, 1]:
            ##slice away "[i] task": ...
            split = key.split(" ")
            if len(split) > 1:
                k = split[1]
                prev_task_list.append((key, val))
            else:
                print("Skipping: ", key, val)

    new_task_list = []
    print("Previous task list:")
    for task, val in prev_task_list:
        ##failed or did not run
        if val == 0 or val == -1:
            print(colored(f"{task}: {val}", 'yellow'))
            new_task_list.append(task)
        if val == 1:
            print(colored(f"{task}: {val}", 'green'))

    schedule.set_recovery_task_title_list(new_task_list)
    schedule.resolve_recovery()
    #convert_str_to_task(schedule, new_task_list)

def convert_str_to_task(schedule, task_list):
    for task_str in task_list:
        task = locals().get(task_str)
        if task is None:
            raise KeyError("Unexpected String in json - unable to recover file")
        schedule.add_task(task)

def run_complete(schedule):
    verbose = schedule.verbosity()
    if verbose:
        print("-- Schedule Completed --")
    send_message("Schedule Completed")
    current_dict = open_json(schedule.get_run(), verbose=False)
    ##check all tasks could write "1"
    all_pass = True
    for key in current_dict[schedule.get_run_key()]:
        val = current_dict[schedule.get_run_key()][key]
        if val in [-1, 0]:
            warn_str = f"Completed, but {key} = {val}"
            send_warning(warn_str)
            all_pass = False
    current_dict[schedule.get_run_key()]['end_time'] = str(datetime.now())
    if all_pass is True:
        send_message("All tasks in schedule completed successfully")
    update_json(schedule.get_run(), current_dict)

def cleanup():
    print("Process Terminating...")
    send_message("All actions completed - master script terminating")

def monitoring_session(schedule, title, comment, reboot=False, n_sets=6):
    print("WARN - THESE ARE NOW DEPRECATED.")
    print("Consier using prying_eyes or regrowth")
    ##20 hours equally distributed for all D-Eggs
    ##to allow breaks for status checks
    ##one session configured to: ~80 min
    ##input from config is string by default
    n_sets = int(n_sets)
    for i in range(n_sets):
        schedule.add_task(task=readout_and_readout,
                          title=title+f'rr{i}',
                      args=[60*60*1, f"{comment}:{i}"],
                      run_backup=True)
        if reboot == True:
            schedule.add_task(readout_and_reboot,
                           title=title+f'rb{i}',
                      args=[f"{comment}:{i}", 60*20],
                      run_backup=True)
        return schedule

##start the main function
@click.command()
@click.argument('config_file')
@click.option('--recover', is_flag=True, default=False)
@click.option('--test', is_flag=True, default=False)
@click.option('--force', is_flag=True)
def main(config_file, recover, test, force):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')

    if test == True:
        print("You are running with a testing configuration! - No data will be collected!")
        send_message("You are running with a testing configuration! - No data will be collected!")

    ##construct schedule
    schedule = Scheduler(bool(recover))

    ##configure schedule, if recover grabs constants only
    schedule.get_schedule_from_file(config_file)

    ##try to recover failed schedule from file
    if schedule.recovery() is True:
        recover_schedule(schedule)

    ##check for errors in run json, option to enable recovery
    run_number = book_keeping(schedule)

    # Set a function to backup the run json files
    schedule.set_backup_task(
        task=run_backup,
        kwargs={'local_path':RUN_DIR,
        'remote_folder':'/misc/disk19/users/icecube/fat_backup',
        'run_number':run_number,
        'remote_filename':'run_json.tar.gz'})

    ##Very noisy - only use temporarily for debugging
    send_all = False
    ##send info to slack, update json
    list_schedule(schedule, send_all=send_all)

    if test == True:
        return

    ##execute schedule
    run_schedule(schedule)

    ##update jsons
    run_complete(schedule)

    ##cleanup
    cleanup()

if __name__ == "__main__":
    main()

##end

