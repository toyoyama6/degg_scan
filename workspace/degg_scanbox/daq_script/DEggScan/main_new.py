import os
import click
import sys
import json
import inquirer
from datetime import datetime
from termcolor import colored
from tqdm import tqdm
import threading


from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

import skippylab as sl

####
from deggContainer import *
from measure_scan import *
####

#########
from degg_measurements import FH_SERVER_SCRIPTS

sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet

from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.timing.setupHelper import makeBatches
from degg_measurements.timing.setupHelper import infoContainer, deggContainer
from degg_measurements.timing.setupHelper import configureBaselines
from degg_measurements.timing.setupHelper import deggListInitialize, doInitialize
from degg_measurements.timing.setupHelper import recreateDEggStreams
from degg_measurements.timing.setupHelper import getTimeMFH
from degg_measurements.utils import create_save_dir
from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.utils import load_run_json, load_degg_dict, add_default_meas_dict, update_json






def prepare_metadata(run_file, comment, filepath, fStrength, laser_freq, nevents,
                     n_rapcals):
    list_of_deggs = load_run_json(run_file)
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




def setup_degg_and_mb(run_file, filepath, comment, fStrength, n_jobs=1,
                        overwrite=False, verbose=False, ALT_FITTING=False):
    n_jobs = int(n_jobs)
    ##SPE level tests
    print(f'Total Filter Strength: {fStrength}')

    ##configure function generator
    laser_freq = 500 #Hz
    #light_system_check(laser_freq)
    tSleep = 40 ##seconds

    nevents = laser_freq ##charge block size
    ##already at 300 size is getting huge!
    n_rapcals = 5 ##number of repeats

    icm_ports, key, ignoreList = prepare_metadata(run_file, comment, filepath,
                                                fStrength, laser_freq,
                                                nevents, n_rapcals)

    ##this stage measures the PMT baselines
    deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList = configureBaselines(
        run_json=run_file, n_jobs=n_jobs, fStrength=fStrength, tSleep=tSleep,
        overwrite=overwrite, key=key, ignoreList=ignoreList)

    return icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList


def setup_paths(degg_id, measurement_type):
    data_dir = '/home/scanbox/data/scanbox/'
    if(not os.path.exists(data_dir)):
        os.mkdir(data_dir)
    dirname = create_save_dir(data_dir, degg_id, measurement_type)
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

def create_save_dir(data_dir, degg_id, measurement_type):
    if(not os.path.exists(f'{data_dir}{degg_id}/')):
        os.mkdir(f'{data_dir}{degg_id}/')
    if(not os.path.exists(f'{data_dir}{degg_id}/{measurement_type}/')):
        os.mkdir(f'{data_dir}{degg_id}/{measurement_type}/')
    today = datetime.today()
    today = today.strftime("%Y%m%d")
    cnt = 0
    while True:
        today = today + f'_{cnt:02d}'
        dirname = os.path.join(data_dir, degg_id, measurement_type, today)
        if os.path.isdir(dirname):
            today = today[:-3]
            cnt += 1
        else:
            os.makedirs(dirname)
            print(f"Created directory {dirname}")
            break
    return dirname

def daq_wrapper(run_json, comment, measurement_type):

    ##setup path
    degg_id = get_deggID(run_json)
    dir_ref, dir_sig = setup_paths(degg_id, measurement_type)

    
    r_step = 3 ##mm
    r_max = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_max, r_step)

    z_step = 3 ##mm
    z_max = 135 ##mm (radius)
    z_scan_points = np.arange(0, z_max, z_step)

    #set LD voltage
    voltage = 4.42
    
    if(measurement_type=="bottom-r"):
        fStrength = 0                                                            
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg                                                                          
        theta_scan_points = np.arange(0, theta_max, theta_step)
        ##wf (waveform) or chargestamp (stamp)
        icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, 
        baselineFileList, baselineList, ignoreList = setup_degg_and_mb(run_json, dir_sig, comment, fStrength, n_jobs = 1, 
                                                                       overwrite = False,verbose = False, ALT_FITTING = False
                                                                       )
    
        measure_brscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_max, r_scan_points,
                    mtype=measure_mode, measure_side='bottom')
    
    elif(measurement_type=="top-r"):
        fStrength = 1
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        #theta_scan_points = theta_scan_points[54:]
        icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList = setup_degg_and_mb(run_json, dir_sig, comment, fStrength, 
     overwrite = False, n_jobs = 1, ALT_FITTING = False, verbose = False
     )
        
        measure_trscan(run_json, dir_sig, dir_ref, voltage,theta_step,theta_scan_points,
                       r_step, r_scan_points, icm_ports, deggNameList, deggList, sessionList, 
                       portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList
                       )
        
    elif(measurement_type=="top-z"):
        
        fStrength = 1
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        theta_scan_points = theta_scan_points[59:]
        icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList = setup_degg_and_mb(run_json, dir_sig, comment, fStrength, 
     overwrite = False, n_jobs = 1, ALT_FITTING = False, verbose = False
     )
        measure_tzscan(run_json, dir_sig, dir_ref, voltage,theta_step,theta_scan_points,
                       z_step, z_max, z_scan_points, icm_ports, deggNameList, deggList, sessionList, 
                       portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList
                       )
    
    elif(measurement_type=="bottom-z"):
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        measure_bzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    mtype=measure_mode, measure_side='bottom')
    
    else:
        print("Wrong measurement_type!!!")
        sys.exit()


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
    measurement_type = inquirer.prompt(questions)["type"]
    print(measurement_type)
    if(measurement_type=="exit"):
        print('bye bye')
        sys.exit()

    daq_wrapper(run_json, comment, measurement_type)

if __name__ == "__main__":
    main()
##END
