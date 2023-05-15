import os
import click
import sys
import json
import inquirer
from datetime import datetime
from termcolor import colored
from tqdm import tqdm
import numpy as np
import threading
import pandas as pd
#########

from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *
import skippylab as sl

#########
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet
from degg_measurements.daq_scripts.master_scope import write_to_hdf5
from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.timing.setupHelper import makeBatches
from degg_measurements.timing.setupHelper import configureBaselines
from degg_measurements.timing.setupHelper import deggListInitialize, doInitialize
from degg_measurements.timing.setupHelper import recreateDEggStreams
from degg_measurements.timing.setupHelper import getTimeMFH
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_run_json, load_degg_dict, add_default_meas_dict, update_json
from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.setupHelper import getEventDataParallel
from degg_measurements.timing.rapcalHelper import calculateTimingInfoAfterDataTaking
from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.rapcalHelper import calculateTimingInfoAfterDataTaking




def prepare_metadata(run_json, comment, filepath, fStrength, laser_freq, nevents,
                     n_rapcals):
    list_of_deggs = load_run_json(run_json)
    meas_key = 'TransitTimeSpread'

    ignoreList = []
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        keys = add_default_meas_dict(
            [degg_dict],
            [degg_file],
            meas_key,
            comment,
        )
        key = keys[0]
        key = key[0]

    icm_ports = []
    for _degg in list_of_deggs:
        degg_dict = load_degg_dict(_degg)
        port = int(degg_dict['Port'])
        icm_ports.append(6000)

        ignored = False
        if port in ignoreList:
            ignored = True
        degg_dict['LowerPmt'][key]['Filter'] = fStrength
        degg_dict['UpperPmt'][key]['Filter'] = fStrength
        degg_dict['LowerPmt'][key]['LaserFreq'] = laser_freq
        degg_dict['UpperPmt'][key]['LaserFreq'] = laser_freq
        degg_dict['LowerPmt'][key]['EventsPerBlock'] = nevents
        degg_dict['UpperPmt'][key]['EventsPerBlock'] = nevents
        degg_dict['LowerPmt'][key]['NumBlocks'] = n_rapcals
        degg_dict['UpperPmt'][key]['NumBlocks'] = n_rapcals
        degg_dict['LowerPmt'][key]['Ignored'] = f'{ignored}'
        degg_dict['UpperPmt'][key]['Ignored'] = f'{ignored}'

        ##Fill both to maintain compatability
        degg_dict['LowerPmt'][key]['Filepath'] = filepath
        degg_dict['UpperPmt'][key]['Filepath'] = filepath
        degg_dict['LowerPmt'][key]['Folder'] = filepath
        degg_dict['UpperPmt'][key]['Folder'] = filepath

        update_json(_degg, degg_dict)

    return icm_ports, key, ignoreList


def setup_paths(degg_id, meas_type):
    data_dir = '/home/scanbox/data/scanbox/'
    if(not os.path.exists(data_dir)):
        os.mkdir(data_dir)
    dirname = create_save_dir(data_dir, degg_id, meas_type)
    dirname_ref = os.path.join(dirname, 'ref')
    dirname_sig = os.path.join(dirname, 'sig')
    if not os.path.exists(dirname_ref):
        os.mkdir(dirname_ref)
    if not os.path.exists(dirname_sig):
        os.mkdir(dirname_sig)
    return dirname_ref, dirname_sig

def get_deggID(run_json):
    json_open = open(run_json, 'r')
    json_load = json.load(json_open)
    deggID = list(json_load.keys())[0]
    print(f'DeggID : {deggID}')
    return deggID

def create_save_dir(data_dir, degg_id, meas_type):
    if(not os.path.exists(f'{data_dir}{degg_id}/')):
        os.mkdir(f'{data_dir}{degg_id}/')
    if(not os.path.exists(f'{data_dir}{degg_id}/{meas_type}/')):
        os.mkdir(f'{data_dir}{degg_id}/{meas_type}/')
    today = datetime.today()
    today = today.strftime("%Y%m%d")
    cnt = 0
    while True:
        today = today + f'_{cnt:02d}'
        dirname = os.path.join(data_dir, degg_id, meas_type, today)
        if os.path.isdir(dirname):
            today = today[:-3]
            cnt += 1
        else:
            os.makedirs(dirname)
            print(f"Created directory {dirname}")
            break
    return dirname


def run(filepath, run_json, r_point, t_point, icmConnectList, deggBatches, deggsList, tabletop, method='charge_stamp', 
        verbose=False, ALT_FITTING=False):
    
    ##get the ICM seed times in parallel to reduce offset between them
    t_threads = []
    for icms, deggBatch in zip(icmConnectList, deggBatches):
        t_threads.append(threading.Thread(target=getTimeMFH, args=[icms, deggBatch]))
    for t in t_threads:
        t.start()
    for t in t_threads:
        t.join()

    n_rapcals = 5
    rapcal_ports = [6000, 6008]
    nevents = 500
    for i in range(n_rapcals):
        print(f'Event: {i}')
        threads = []
        print("RapCal A")
        for deggBatch, icmConnect, rapcal_port in zip(deggBatches, icmConnectList, rapcal_ports):
            if len(deggBatch) != 0:
                seedTime = [deggBatch[0].seedTimeICM, deggBatch[0].seedTimeUTC]
                threads.append(threading.Thread(target=getRapCalData, args=[icmConnect, rapcal_port, deggBatch, 1, verbose, seedTime, ALT_FITTING]))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        threads = []
        print("Waveforms")
        for deggBatch in deggBatches:
            for degg in deggBatch:
                threads.append(threading.Thread(target=getEventDataParallel,
                                                args=[degg, nevents, method, i, ALT_FITTING]))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        threads = []
        print("RapCal B")
        for deggBatch, icmConnect, rapcal_port in zip(deggBatches, icmConnectList, rapcal_ports):
            if len(deggBatch) != 0:
                seedTime = [deggBatch[0].seedTimeICM, deggBatch[0].seedTimeUTC]
                threads.append(threading.Thread(target=getRapCalData, args=[icmConnect, rapcal_port, deggBatch, 1, verbose, seedTime, ALT_FITTING]))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        time.sleep(1.1)

    print("- Finished data taking -")
    ##calculate timing and save info
    deggsList.append(tabletop)
    calculateTimingInfoAfterDataTaking(deggsList, method, ALT_FITTING)

    run_number = os.path.basename(run_json)
    run_number = run_number.split('.')[0]
    run_number = run_number.split('_')[-1]
    saveContainer(deggsList, filepath, r_point, t_point, method, run_number, ALT_FITTING)
    deggsList = []

def saveContainer(deggContainerList, filepath, r_point, t_point, method='charge_stamp', run_number='00000',
                  ALT_FITTING=False):

    dfList = []
    for degg in deggContainerList:
        degg_temperature = degg.temperature
        for info in [degg.info0, degg.info1]:
            if method == 'charge_stamp':
                timestampList = [0] * len(info)
                chargeList = [0] * len(info)
            elif method == 'waveform':
                for i in range(len(info)):
                    _dummyA = []
                    timestampList.append(_dummyA)
                    _dummyB = []
                    chargeList.append(_dummyB)
            channelList    = [0] * len(info)
            mfh_tList      = [0] * len(info)
            #mfh_t2List     = [0] * len(info)
            deltaList      = [0] * len(info)
            offsetList     = [0] * len(info)
            blockNumList   = [0] * len(info)
            triggerNumList = [0] * len(info)
            cableDelayList = [[0,0]] * len(info)
            clockDriftList = [0] * len(info)
            temperatureList = [degg_temperature] * len(info)
            if ALT_FITTING == True:
                mfh_tList_LINEAR   = [0] * len(info)
                mfh_tList_QUAD     = [0] * len(info)
                mfh_tList_QUAD_MOD = [0] * len(info)
                mfh_tList_RICHARD  = [0] * len(info)
                cableDelayList_LINEAR   = [[0, 0]] * len(info)
                cableDelayList_QUAD     = [[0, 0]] * len(info)
                cableDelayList_QUAD_MOD = [[0, 0]] * len(info)
                cableDelayList_RICHARD  = [[0, 0]] * len(info)
                clockDriftList_LINEAR   = [0] * len(info)
                clockDriftList_QUAD     = [0] * len(info)
                clockDriftList_QUAD_MOD = [0] * len(info)
                clockDriftList_RICHARD  = [0] * len(info)

            for m, _info in enumerate(info):
                timestampList[m]  = _info.timestamp
                chargeList[m]     = _info.charge
                channelList[m]    = _info.channel
                mfh_tList[m]      = _info.mfh_t
                #mfh_t2List[m]     = _info.mfh_t2
                deltaList[m]      = _info.delta
                offsetList[m]     = _info.datetime_offset
                blockNumList[m]   = _info.i_pair
                triggerNumList[m] = _info.triggerNum
                cableDelayList[m] = [_info.cable_delay0, _info.cable_delay1]
                clockDriftList[m] = _info.clockDrift

                if ALT_FITTING == True:
                    mfh_tList_LINEAR[m]   = _info.mfh_LINEAR
                    mfh_tList_QUAD[m]     = _info.mfh_QUAD
                    mfh_tList_QUAD_MOD[m] = _info.mfh_QUAD_MOD
                    mfh_tList_RICHARD[m]  = _info.mfh_RICHARD

                    clockDriftList_LINEAR[m]   = _info.clockDrift_LINEAR
                    clockDriftList_QUAD[m]     = _info.clockDrift_QUAD
                    clockDriftList_QUAD_MOD[m] = _info.clockDrift_QUAD_MOD
                    clockDriftList_RICHARD[m]  = _info.clockDrift_RICHARD

                    cableDelayList_LINEAR[m]   = [_info.delay0_LINEAR, _info.delay1_LINEAR]
                    cableDelayList_QUAD[m]     = [_info.delay0_QUAD, _info.delay1_QUAD]
                    cableDelayList_QUAD_MOD[m] = [_info.delay0_QUAD_MOD, _info.delay1_QUAD_MOD]
                    cableDelayList_RICHARD[m]  = [_info.delay0_RICHARD, _info.delay1_RICHARD]


            data = {'timestamp': timestampList, 'charge': chargeList,
                'channel': channelList, 'mfhTime': mfh_tList,
                'delta': deltaList,
                'offset': offsetList, 'blockNum': blockNumList,
                'triggerNum': triggerNumList, 'cableDelay': cableDelayList,
                'clockDrift': clockDriftList,
                'files0': f'{degg.files[0]}',
                'files1': f'{degg.files[1]}',
                'temperature': temperatureList}

            if ALT_FITTING == True:
                data['mfhLINEAR']   = mfh_tList_LINEAR
                data['mfhQUAD']     = mfh_tList_QUAD
                data['mfhQUAD_MOD'] = mfh_tList_QUAD_MOD
                data['mfhRICHARD']  = mfh_tList_RICHARD

                data['cableDelayLINEAR']   = cableDelayList_LINEAR
                data['cableDelayQUAD']     = cableDelayList_QUAD
                data['cableDelayQUAD_MOD'] = cableDelayList_QUAD_MOD
                data['cableDelayRICHARD']  = cableDelayList_RICHARD

                data['clockDriftLINEAR']   = clockDriftList_LINEAR
                data['clockDriftQUAD']     = clockDriftList_QUAD
                data['clockDriftQUAD_MOD'] = clockDriftList_QUAD_MOD
                data['clockDriftRICHARD']  = clockDriftList_RICHARD

            for d in degg.__dict__:
                if d == 'session' or d == 'rapcals' or d == 'lock' or d == 'condition':
                    continue
                ##important for ALT_FITTING
                if d.split('_')[0] == 'rapcals':
                    continue
                if d != 'info' and d != 'info0' and d != 'info1' and d != 'files' and d != 'rapcal_utcs' and d != 'rapcal_icms':
                    vals = degg.__dict__[d]
                    valsList = [vals] * len(info)
                    _dict = {f'{d}':valsList}
                    data.update(_dict)
            df = pd.DataFrame(data=data)
            print(f'{degg.port} mfhTimeList before saving')
            for _i, _t in enumerate(mfh_tList):
                if _i <= 5:
                    print(f'\t {_t}')
            if ALT_FITTING == True:
                filename = f'timing_info_{method}_{degg.port}_{r_point}_{t_point}_ALT_FITS.hdf5'
            else:
                filename = f'timing_info_{method}_{degg.port}_{r_point}_{t_point}.hdf5'
            df.to_hdf(os.path.join(filepath, filename), key='df', mode='w')
            dfList.append(df)

    df_total = pd.concat(dfList, sort=False)
    if ALT_FITTING == True:
        t_filename = f'total_{run_number}_{method}_{r_point}_{t_point}_ALT_FITS.hdf5'
    else:
        t_filename = f'total_{run_number}_{method}_{r_point}_{t_point}.hdf5'
    df_total.to_hdf(os.path.join(filepath, t_filename), key='df', mode='w')

    

def setup_reference():
    print(colored("Setting up reference pmt readout (scope)...", 'green'))
    scope_ip = "10.25.101.2"
    scope = sl.instruments.RohdeSchwarzRTM3004(ip=scope_ip)
    scope.ping()
    return scope

def convert_wf(raw_wf):
    times, volts = raw_wf
    return times, volts


def measure_reference(filename, scope, reference_pmt_channel=1, num_reference_wfs=1000):
    print(colored(f"Reference Measurement - {num_reference_wfs} WFs", 'green'))
    for i in range(num_reference_wfs):
        raw_wf = scope.acquire_waveform(reference_pmt_channel)
        times, wf = convert_wf(raw_wf)
        write_to_hdf5(filename, i, times, wf, 0, 0)


def setup_LD(voltage):
    # LD = PMX70_1A('10.25.101.60')
    # LD.connect_instrument()
    # LD.set_volt_current(voltage, 0.02)
    #Warm up LD
    print('setting up LD')
    # for i in tqdm(range(600)):
    #     time.sleep(1)
    

def setup_thorlab_motor():
    print(colored("Setting up motors...", 'green'))
    rotate_stage = None
    ##USB3 - THORLABS
    try:
        rotate_stage = HDR50(serial_port="/dev/ttyUSB3", serial_number="40106754", home=True, swap_limit_switches=True)
        rotate_stage.wait_up()
    except:
        print(colored('Error in connecting to Thorlabs Motor!', 'red'))
    ##USB2 - ORIENTAL MOTORS

    rotate_stage.move_relative(-90)
    rotate_stage.wait_up()
    return rotate_stage

def setup_oriental_motor():
    print(colored("Setting up motors...", 'green'))
    stage = None
    ##USB2 - ORIENTAL MOTORS
    try:
        stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))
    print("Are motors at home position?")
    #stage.moveToHome(rotate_slave_address)
    #time.sleep(5)
    #stage.moveToHome(r_slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))
    # setup_LD(voltage)
    return stage

#############################################################################


def measure(run_json, dir_sig, dir_ref, comment, meas_type, theta_step, theta_scan_points, r_step, r_scan_points, 
            fStrength, rotate_slave_address, r_slave_address, stage, scope, rotate_stage = "", overwrite = True
            ):

    reference_pmt_channel = 1
    #initialize DEgg and MB
###################################################
    n_jobs = 1
    ##SPE level tests
    print(f'Total Filter Strength: {fStrength}')

    ##configure function generator
    laser_freq = 500 #Hz
    #light_system_check(laser_freq)
    tSleep = 40 ##seconds
    nevents = laser_freq ##charge block size
    ##already at 300 size is getting huge!
    n_rapcals = 5 ##number of repeats
    icm_ports, key, ignoreList = prepare_metadata(run_json, comment, dir_sig,
                                                fStrength, laser_freq,
                                                nevents, n_rapcals)
    ##this stage measures the PMT baselines
    deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList = configureBaselines(
        run_json=run_json, n_jobs=n_jobs, fStrength=fStrength, tSleep=tSleep,
        overwrite=overwrite, key=key, ignoreList=ignoreList)

    nevents = 1
    dac_value = 30000
    period = 100000 ##deprecated - only for scaler
    deadtime = 24 ##deprecated - only for scaler

    rapcal_ports = [6000, 6008]
    icmConnectList = []
    for rp_port in rapcal_ports:
        icms = ICMNet(rp_port, host='localhost')
        icmConnectList.append(icms)


    ##this just populates the deggsList, no calculations
    print('\n')
    print("Create D-Egg Class Objects")
    deggsList = deggListInitialize(deggNameList, degg_list=deggList, portList=portList,
                            icm_ports=sorted(icm_ports),
                            hvSetList=hvSetList, thresholdList=thresholdList, dacValue=dac_value,
                            period=period, deadtime=deadtime, baselineFileList=baselineFileList,
                            baselineList=baselineList, _type='degg', nevents=nevents,
                            filepath = dir_sig, overwrite=overwrite, ignoreSession=True,
                            sessionList=sessionList, ignoreList=ignoreList,
                            ALT_FITTING=False)


    print('1')
    # verify_hv([deggsList], verbose=True)
    #from IPython import embed
    #embed()
    ##mainly just calling initialize_dual for all DEggs
    recreateDEggStreams(deggsList)

    ##setup batches of 4 to avoid launching jobs
    ##simultaneously on same wire pair
    deggBatches = makeBatches(deggsList)

    # if verbose:
    #     print("Checking Batching:")
    #     for deggBatch in deggBatches:
    #         for degg in deggBatch:
    #             print(f'Port: {degg.port}')


    ##NOTE - The threshold is lowered when the splitter is used!
    tabletop = doInitialize('tabletop', ['tabletop', 'tabletop'], 5011, 6008, [0, 0], [9000, 14000],
                            dac_value, period, deadtime, [None, None], filepath=dir_sig,
                            baselines = [0, 0], _type='tabletop', createFile=False,
                            ALT_FITTING=False)
    recreateStreams(tabletop)
    deggBatches.append([tabletop])
    print("deggbatches1", deggBatches)
    

##########################################################

    # measuring
    for theta_point in theta_scan_points:
        #home r_stage
        stage.moveToHome(r_slave_address)
        print('r_stage homing...')
        time.sleep(15)
        
        #take reference data
        print("measuring reference PMT")
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        print(f'Measuring: {r_scan_points}')
        for event_num, r_point in enumerate(r_scan_points):
            print(f"Now is ... r_point = {r_point}, theta_point = {theta_point}")
            ##take DEgg data
            run(dir_sig, run_json, r_point, theta_point, icmConnectList, deggBatches, deggsList, tabletop, 
                method='charge_stamp', verbose=False, ALT_FITTING=False)
            
            print("r_motor moving...")
            stage.moveRelative(r_slave_address, r_step)
            time.sleep(5)
        if meas_type == "bottom-r" or meas_type == "bottom-z":
            rotate_stage.move_relative(theta_step)
            rotate_stage.wait_up()
        elif meas_type == "top-r" or meas_type == "top-z":
            stage.moveRelative(rotate_slave_address, -theta_step)
        print("theta_motor moving...")
        time.sleep(5)
    
    if meas_type == "bottom-r" or meas_type == "bottom-z":
        rotate_stage.move_relative(-270)
        rotate_stage.wait_up()
    elif meas_type == "top-r" or meas_type == "top-z":
        stage.moveRelative(rotate_slave_address, 360)
    print('stage homing...')
    for i in tqdm(range(120)):
        time.sleep(1)
    

def daq_wrapper(run_json, comment, meas_type):

    ##setup path
    degg_id = get_deggID(run_json)
    dir_ref, dir_sig = setup_paths(degg_id, meas_type)
    #set theta_range
    theta_step = 6 ##deg
    theta_max = 360 ##deg                                                                          
    theta_scan_points = np.arange(0, theta_max, theta_step)

    if(meas_type == "top-r"):
        #set r_range
        r_step = 3 ##mm
        r_max = 141 ##mm (radius)
        r_scan_points = np.arange(0, r_max, r_step)
        rotate_stage = ""
        rotate_slave_address = 5
        r_slave_address = 3
        fStrength = 1
    if(meas_type == "top-z"):
        #set r_range
        r_step = 3 ##mm
        r_max = 141 ##mm (radius)
        r_scan_points = np.arange(0, r_max, r_step)
        rotate_stage = ""
        rotate_slave_address = 5
        r_slave_address = 4
        fStrength = 1
    if(meas_type == "bottom-r"):
        #set r_range
        r_step = 3 ##mm
        r_max = 135 ##mm (radius)
        r_scan_points = np.arange(0, r_max, r_step)
        r_slave_address = 1
        rotate_stage = setup_thorlab_motor()    
        fStrength = 0
    if(meas_type == "bottom-z"):
        #set threshold
        fStrength = 0                                                            
        #set r_range
        r_step = 3 ##mm
        r_max = 135 ##mm (radius)
        r_scan_points = np.arange(0, r_max, r_step)
        r_slave_address = 2
        rotate_stage = setup_thorlab_motor()
        fStrength = 0

    #set up oriental motor 
    stage = setup_oriental_motor()
    #set up scope 
    scope = setup_reference()

    measure(run_json, dir_sig, dir_ref, comment, meas_type, theta_step, theta_scan_points, r_step, r_scan_points, 
            fStrength, rotate_slave_address, r_slave_address, stage, scope, rotate_stage
            )


###################################################

@click.command()
@click.argument('run_json')
@click.argument('comment')
def main(run_json, comment):

    questions = [
        inquirer.List(
            "type",
            message="Which side are you going to measure?",
            choices=["bottom-r", "bottom-z", "top-r", "top-z", "exit"],
            carousel=True,
        )
    ]
    meas_type = inquirer.prompt(questions)["type"]
    print(f'{meas_type}')
    if(meas_type=="exit"):
        print('bye bye')
        sys.exit()

    daq_wrapper(run_json, comment, meas_type)

if __name__ == "__main__":
    main()
##END
