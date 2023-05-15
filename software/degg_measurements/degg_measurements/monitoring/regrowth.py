################################
## options for rebooting during
## monitoring, and options for
## cold boot
################################
import subprocess
import os, sys
import click
import time
import numpy as np
import pandas as pd
from tqdm import tqdm

from chiba_slackbot import send_message, send_warning

from degg_measurements.daq_scripts.degg_cal import DEggCal
from degg_measurements.daq_scripts.degg_cal import PMTCal

from degg_measurements.utils import load_run_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils.load_dict import add_default_calibration_meas_dict
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import update_json
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.flash_fpga import fpga_set
from degg_measurements.utils import DEggLogBook
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.analysis.analysis_utils import get_run_json
from degg_measurements.analysis import Result

from degg_measurements.monitoring import readout_sensor

from degg_measurements import FH_SERVER_SCRIPTS
from degg_measurements import DATA_DIR
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH


def setup_classes(run_file, mode, gain_reference='latest'):
    if mode not in ['reboot', 'coldboot']:
        print(f'The mode must be either reboot or coldboot, not {mode}! ')
        exit(1)
    if mode == 'reboot':
        meas_key = 'RebootMonitoring'
        measurement_type = 'reboot_monitoring'
    if mode == 'coldboot':
        meas_key = 'ColdBoot'
        measurement_type = 'cold_boot'

    DEggCalList = []
    #load all degg files
    list_of_deggs = load_run_json(run_file)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)
    ##filepath for saving data
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    key = add_default_calibration_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        meas_key,
        comment='',
        Folder=dirname
    )

    for degg_file in sorted_degg_files:
        degg = DEggCal(degg_file, key, gain_reference=gain_reference)
        DEggCalList.append(degg)

    return DEggCalList, dirname

def assignICMPort(deggCal):
    port = deggCal.degg_dict['Port']

    if port < 5004:
        deggCal.icmPort = 6000
        deggCal.wpAdd = (port - 5000)
    elif port < 5008:
        deggCal.icmPort = 6004
        deggCal.wpAdd = (port - 5004)
    elif port < 5012:
        deggCal.icmPort = 6008
        deggCal.wpAdd = (port - 5008)
    elif port < 5016:
        deggCal.icmPort = 6012
        deggCal.wpAdd = (port - 5012)
    else:
        raise ValueError(f'Port {port} not valid! You have a bug?')

def handle_wp(script):
    for wirepairaddress in [0, 1, 2, 3]:
        for icmport in [6000, 6004, 6008, 6012]:
            sendCommand(script, icmport, wirepairaddress)
        if wirepairaddress != 3:
            time.sleep(1)
    time.sleep(5)

def sendCommand(script, icmport, wirepairaddress):
    ##importing the functions got a bit tricky, easier to execute on the cmd line
    cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport} -w {wirepairaddress}'
    os.system(cmd_base)

def reflashFPGA(DEggCalList):
    for deggCal in DEggCalList:
        port = deggCal.degg_dict['Port']
        ##Note: fpga_set starts and closes sessions
        fpgaSet = fpga_set(port, auto_flash=True)
        ##if fpgaSet == True, reboot successful
        deggCal.fpgaSet = fpgaSet
        deggCal.nAttempts += 1

def checkStatus(DEggCalList, script_list):
    msg_str = ''
    retryDEggs = []
    for deggCal in DEggCalList:
        port = deggCal.degg_dict['Port']
        if deggCal.fpgaSet != True:
            msg_str += f'Reboot failed for {port}, '
            retryDEggs.append(deggCal)

    if msg_str != '':
        msg_str += 'Retrying...'
        send_warning(msg_str)
        for deggCal in retryDEggs:
            sendCommand(script_list['Off'], deggCal.icmPort, deggCal.wpAdd)
            time.sleep(1)
        time.sleep(5)
        for deggCal in retryDEggs:
            sendCommand(script_list['On'], deggCal.icmPort, deggCal.wpAdd)
            time.sleep(1)
        reflashFPGA(retryDEggs)
        msg_str = ''
        for deggCal in retryDEggs:
            if deggCal.fpgaSet != True:
                msg_str += 'Reboot failed for a second time {port}, '
        if msg_str != '':
            send_warning(msg_str)
            return False

    if msg_str == '':
        send_message('All modules successfully rebooted!')
        return True

def createOutputFile(DEggCalList, dirname, fname=None, coldBoot=False):

    ##make some 1D arrays for easy parsing
    fpgaSet     = []
    nAttempts   = []
    ports       = []
    temperature = []
    coldBootRetry  = []
    coldBootResult = []
    for deggCal in DEggCalList:
        ports.append(deggCal.degg_dict['Port'])
        fpgaSet.append(deggCal.fpgaSet)
        nAttempts.append(deggCal.nAttempts)
        _temperature = deggCal.temperature
        if _temperature == -1:
            for _d in DEggCalList:
                print(_d.temperature)
                print('Temperature should not be -1!')
        temperature.append(_temperature)
        if coldBoot == True:
            coldBootRetry.append(deggCal.retry)
            coldBootResult.append(deggCal.coldBoot)

    if coldBoot == True:
        d = {'fpgaSet': fpgaSet, 'nAttemps': nAttempts,
             'ports': ports, 'temperature': temperature,
             'coldBootRetry': coldBootRetry,
             'coldBootResult': coldBootResult}
    else:
        d = {'fpgaSet': fpgaSet, 'nAttemps': nAttempts,
             'ports': ports, 'temperature': temperature}

    ##conver to dataframe and save
    df = pd.DataFrame(d)

    if fname == None:
        if coldBoot == True:
            fname = os.path.join(dirname, 'coldboot_info.hdf5')
        else:
            fname = os.path.join(dirname, 'reboot_info.hdf5')

    df.to_hdf(fname, key='df', mode='w')
    return fname

def createSummary(DEggCalList, cold_boot=False):
    for deggCal in DEggCalList:
        degg_dict = deggCal.degg_dict
        d = degg_dict[deggCal.key]

        success = False
        ##try to avoid having to repeat cold boot
        if deggCal.temperature == -1:

            try:
                session = startIcebootSession(host='localhost', port=deggCal.degg_dict['Port'])
                success = True
            except:
                pass
            try:
                deggCal.temperature = readout_sensor(session, 'temperature_sensor')
            except:
                print('Temperature still -1')

        if success:
            session.close()
            del session

        d['temperature'] = deggCal.temperature
        ##sometimes order is changed
        try:
            d['fpgaSet']  = f'{deggCal.fpgaSet}'
            d['nAttemps'] = deggCal.nAttempts
        except AttributeError:
            pass

        ##only for cold boot
        if cold_boot == True:
            d['coldBootRetry']  = deggCal.retry
            d['coldBootStatus'] = deggCal.coldBoot

        update_json(deggCal.degg_file, degg_dict)


def disableHV(DEggCalList):
    wait_on = False
    for deggCal in DEggCalList:
        session = deggCal.session
        deggCal.nAttempts = 0
        for channel in [0, 1]:
            if deggCal.hvStatus[channel] == True:
                session.setDEggHV(channel, 0)
                wait_on = True
        session.close()

    if wait_on == True:
        for i in tqdm(range(40), desc='Disabling HV'):
            time.sleep(1)


##test connections, if fails repeat startup again
def startupVerify(DEggCalList):
    invalidConnections = ['a']
    retry = 0
    while len(invalidConnections) != 0:
        ##if retry is too many exit!
        if retry == 3:
            return False
        ##empty list for each try
        invalidConnections = []
        for deggCal in DEggCalList:
            deggCal.coldBoot = 'Fail'
            if deggCal.coldBoot != 'Pass':
                deggCal.retry = retry
            try:
                session = startIcebootSession(host='localhost', port=deggCal.degg_dict['Port'])
                time.sleep(1)
                session.close()
                deggCal.coldBoot = 'Pass'
            except:
                port = deggCal.degg_dict['Port']
                print(f'Could not start iceboot for {port}')
                invalidConnections.append(deggCal.icmPort)

        if len(invalidConnections) == 0:
            return True

        ##if it gets here, we had problems during the restart
        msg_str  = f'Problems during Cold Boot (Retry = {retry})'
        msg_str += f' - {len(invalidConnections)} modules are invalid!'
        send_warning(msg_str)

        ##increment retry
        retry += 1

        ##try to reboot again
        power_cycle_wp(np.unique(np.array(invalidConnections)))
        reboot_settings(np.unique(np.array(invalidConnections)))

##wire pair power is controlled via the ICMs on the MFH
##not by the individual D-Eggs
def power_cycle_wp(validICMPorts, cold_boot_time=0, verbose=True):
    ##disable the wire pair voltage
    script = 'wp_off.py'
    for icmport in validICMPorts:
        cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport}'
        os.system(cmd_base)
    time.sleep(5)
    print('WP Voltage Disabled')
    if verbose == True:
        send_message('WP voltage now disabled!')

    ##wait for cold boot time
    if cold_boot_time > 0:
        for i in tqdm(range(cold_boot_time), desc='Cold Boot'):
            time.sleep(1)
        print('Cold Boot wait finished')
        if verbose == True:
            send_message('Cold Boot wait finished')

    ##re-enable wp voltage
    script = 'wp_on.py'
    for icmport in validICMPorts:
        cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport}'
        os.system(cmd_base)
    time.sleep(5)
    print('WP Voltage Enabled')
    if verbose == True:
        send_message('WP Voltage Enabled')

def reboot_settings(validICMPorts, verbose=False):

    if verbose == True:
        print(f'Applying reboot settings to {validICMPorts}')
        print('First run icm_fpga_reboot.py')

    ##set to correct ICM firmware image
    ##'Saving device 0 state before reboot...'
    script = 'icm_fpga_reboot.py'
    for wpaddress in [0, 1, 2, 3]:
        for icmport in validICMPorts:
            cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport} -w {wpaddress} -i 2'
            #os.system(cmd_base)
            out_info = subprocess.run(cmd_base, shell=True, capture_output=True)
            print(f'out_info: {out_info}')
            try:
                send_message(out_info)
            except TypeError:
                send_message('I tried to send the output of {FH_SERVER_SCRIPTS}/{script}, here, but failed to')

            #for out_str in out_info:
            #    print(out_str)

        time.sleep(2)

    '''
    if verbose == True:
        print('Then run term_enable.py')
    ##terminate the ICMs to improve comms
    script = 'term_enable.py'
    for icmport in validICMPorts:
        cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport}'
        os.system(cmd_base)
    time.sleep(1)
    '''

    if verbose == True:
        print('Lastly run pmt_hv_enable.py')
    ##re-enable the HV interlock
    script = 'pmt_hv_enable.py'
    for icmport in validICMPorts:
        cmd_base = f'python3 {FH_SERVER_SCRIPTS}/{script} -p {icmport}'
        os.system(cmd_base)
    time.sleep(1)

##this is similar to the calibration jsons - not associated with a PMT!
def create_db_json(DEggCalList, fname, run_number):
    print('Creating cold boot db-jsons')
    logbook = DEggLogBook()
    for deggCal in DEggCalList:
        data_key = deggCal.key
        degg_dict = deggCal.degg_dict
        degg_id = degg_dict['DEggSerialNumber']
        mb_id   = degg_dict['MainboardNumber']
        result = Result(mb_id, logbook=logbook,
                        run_number=run_number,
                        remote_path=REMOTE_DATA_DIR)
        result.to_json(
            meas_group='monitoring',
            raw_files=None,
            folder_name=DB_JSON_PATH,
            filename_add=data_key,
            cold_boot_retry=deggCal.retry,
            cold_boot_result=deggCal.coldBoot,
            temperature=deggCal.temperature,
            cold_boot=True
        )

##cold boot test
def run_cold_boot(DEggCalList, dirname, run_number, verbose=False):

    print('Starting Cold Boot Procedure')
    send_message('Starting Cold Boot Procedure')

    ##generic valid ports
    validICMPorts = [6000, 6004, 6008, 6012]

    ##for safety, ramp down HV if it's on
    disableHV(DEggCalList)

    ##perform power cycle and wait
    cold_boot_time = 3600 * 8
    #cold_boot_time = 10
    power_cycle_wp(validICMPorts, cold_boot_time)

    ##re-enable settings
    reboot_settings(validICMPorts, verbose=verbose)

    ##verify that all D-Eggs on all WP are responsive
    ##if not, will retry a few times
    startupReady = startupVerify(DEggCalList)

    ##finished
    print(f'Finished startup procedure. Ready? {startupReady}')

    ##fill dict
    createSummary(DEggCalList, cold_boot=True)

    ##handle database json
    fname = os.path.join(dirname, 'coldboot_info.hdf5')
    create_db_json(DEggCalList, fname, run_number)

    if startupReady == False:
        raise IOError(f'Retry = 3 for Cold Boot startup - Please investigate!')

    elif startupReady == True:
        send_message(f'Cold Boot Completed, all modules are online.')

        ##reflash the FPGAs, then check if they are valid
        reflashFPGA(DEggCalList)
        script_list = {'Off': 'mb_off.py', 'On': 'mb_on.py'}
        overallStatus = checkStatus(DEggCalList, script_list)

        ##create summary output file - status, temperature
        createOutputFile(DEggCalList, dirname, fname, coldBoot=True)

        if overallStatus == False:
            raise IOError(f'One or more D-Eggs could not be successfully rebooted. DAQ is paused.')

    else:
        raise ValueError(f'startupReady returned but not True nor False! {startupReady}')


##power cycling can be handled on a MB-by-MB case
def run_reboot(DEggCalList, dirname, run_number):

    script_list = {'Off': 'mb_off.py', 'On': 'mb_on.py'}

    ##first turn off all of the boards
    ##for saftey, disable the HV, and close the sessions
    disableHV(DEggCalList)

    ##first turn off
    script = script_list['Off']
    handle_wp(script)

    ##then turn back on
    script = script_list['On']
    handle_wp(script)

    ##then need to reflash the FPGA
    reflashFPGA(DEggCalList)

    ##check for failed modules, log and try again
    overallStatus = checkStatus(DEggCalList, script_list)

    ##create summary output file - status, temperature
    createOutputFile(DEggCalList, dirname)

    ##update json dicts
    createSummary(DEggCalList)

    for deggCal in DEggCalList:
        deggCal.session.close()

    if overallStatus == False:
        raise IOError(f'One or more D-Eggs could not be successfully rebooted. DAQ is paused.')

def bootmon(run_file, mode, verbose=False):

    if mode not in ['reboot', 'coldboot']:
        print('mode must be reboot or coldboot')
        exit(1)

    DEggCalList, dirname = setup_classes(run_file, mode)
    ##just to get run_number
    run_json, run_number = get_run_json(run_file)

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


    if mode == 'reboot':
        run_reboot(DEggCalList, dirname, run_number)
    elif mode == 'coldboot':
        run_cold_boot(DEggCalList, dirname, run_number, verbose)
    else:
        raise ValueError(f'mode is not reboot or coldboot! {mode}')

    for deggCal in DEggCalList:
        deggCal.session.close()
    print('Done')

@click.command()
@click.argument('run_file')
@click.argument('mode')
@click.option('--verbose', '-v', is_flag=True)
def main(run_file, mode, verbose):
    bootmon(run_file, mode, verbose)

if __name__ == "__main__":
    main()

##end
