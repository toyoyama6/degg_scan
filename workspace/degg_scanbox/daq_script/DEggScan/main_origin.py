import os
import click
import sys
import json
import inquirer
from datetime import datetime
from termcolor import colored
from tqdm import tqdm

from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

import skippylab as sl

####
from read_waveform import init as reference_init
from read_waveform import set_DAQ
from infoContainer import infoContainer
from deggContainer import *
from measure_scan_origin import *
####

####
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import write_to_hdf5
from degg_measurements.utils import update_json, create_key
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.monitoring import readout_sensor
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.analysis import calc_baseline
####

def setup_degg(run_file, filepath, measure_mode, nevents, config_threshold0, config_threshold1):
    tSleep = 40 #seconds
    list_of_deggs = load_run_json(run_file)
    degg_file = list_of_deggs[0]
    degg_dict = load_degg_dict(degg_file)

    port = degg_dict['Port']
    hv_l = degg_dict['LowerPmt']['HV1e7Gain']
    hv_u = degg_dict['UpperPmt']['HV1e7Gain']

    pmt_name0 = degg_dict['LowerPmt']['SerialNumber']
    pmt_name1 = degg_dict['UpperPmt']['SerialNumber']

    ##connect to D-Egg mainboard
    session = startIcebootSession(host='localhost', port=port)

    ##turn on HV - ramping happens on MB, need about 40s
    session.enableHV(0)
    session.enableHV(1)
    session.setDEggHV(0, int(hv_l))
    session.setDEggHV(1, int(hv_u))
    
    ##make temporary directory for baseline files
    if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')):
        os.mkdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp'))
    
    baselineFiles = []
    for channel, pmt in zip([0, 1], ['LowerPmt', 'UpperPmt']):
        bl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                f'tmp/{degg_dict[pmt]["SerialNumber"]}_baseline_{channel}.hdf5')
        baselineFiles.append(bl_file)
        if os.path.isfile(bl_file):
            os.remove(bl_file)

    ##wait for HV to ramp
    for i in tqdm(range(tSleep)):
        time.sleep(1)

    v0 = readout_sensor(session, 'voltage_channel0')
    v1 = readout_sensor(session, 'voltage_channel1')
    print(f"Voltage is currently: {v0}, {v1}")
    time.sleep(0.25)

    ##measure baseline for both PMTs
    session = min_measure_baseline(session, 0, baselineFiles[0], 
                                1024, 30000, 0, nevents=50, modHV=False)
    session = min_measure_baseline(session, 1, baselineFiles[1], 
                                1024, 30000, 0, nevents=50, modHV=False)
    
    baseline0 = calc_baseline(baselineFiles[0])['baseline'].values[0]
    baseline1 = calc_baseline(baselineFiles[1])['baseline'].values[0]

    threshold0 = int(baseline0 + config_threshold0)
    threshold1 = int(baseline1 + config_threshold1)
    thresholdList = [threshold0, threshold1]

    dac_value = 30000
    session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                             high_voltage0=hv_l, high_voltage1=hv_u,
                             threshold0=threshold0, threshold1=threshold1,
                             modHV=False)

    f0_string = f'{pmt_name0}_{measure_mode}_{hv_l}.hdf5'
    f1_string = f'{pmt_name1}_{measure_mode}_{hv_u}.hdf5'
    f0 = os.path.join(filepath, f0_string)
    f1 = os.path.join(filepath, f1_string)
    files = [f0, f1]

    _degg = deggContainer()
    _degg.port = port
    _degg.session = session
    _degg.files = files
    _degg.lowerPMT = pmt_name0
    _degg.upperPMT = pmt_name1
    _degg.createInfoFiles(nevents, overwrite=False)
    return _degg, degg_dict, degg_file

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

    ##wf/chargestamp per scan point
    nevents = 3000

    ##initialise DEgg settings
    if(measurement_type=="bottom-r" or measurement_type=="bottom-z"):
        config_threshold0 = 100 ##units of ADC
        config_threshold1 = 6000 ##units of ADC
    elif(measurement_type=="top-r" or measurement_type=="top-z"):
        config_threshold0 = 6000 ##units of ADC
        config_threshold1 = 100 ##units of ADC
    else:
        print("Wrong measurement_type!!!")
        sys.exit()
    
    ##wf (waveform) or chargestamp (stamp)
    measure_mode = 'stamp'
    degg, degg_dict, degg_file = setup_degg(run_json, dir_sig, measure_mode, 
                                    nevents, config_threshold0, config_threshold1)
    for pmt in ['LowerPmt', 'UpperPmt']:
        key = create_key(degg_dict[pmt], measurement_type)
        meta_dict = dict()
        meta_dict['Folder']     = dir_sig
        meta_dict['threshold0'] = config_threshold0
        meta_dict['threshold1'] = config_threshold1
        meta_dict['nevents']    = nevents
        meta_dict['mode']       = measure_mode
        meta_dict['Comment']    = comment
        degg_dict[pmt][key] = meta_dict
    update_json(degg_file, degg_dict)

    
    r_step = 3 ##mm
    r_max = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_max, r_step)

    z_step = 3 ##mm
    z_max = 135 ##mm (radius)
    z_scan_points = np.arange(0, z_max, z_step)

    #set LD voltage
    voltage = 6
    
    if(measurement_type=="bottom-r"):
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)

        measure_brscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_max, r_scan_points,
                    mtype=measure_mode, measure_side='bottom')
    elif(measurement_type=="top-r"):
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        measure_trscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_max, r_scan_points,
                    mtype=measure_mode, measure_side='top')
    elif(measurement_type=="bottom-z"):
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        measure_bzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    mtype=measure_mode, measure_side='bottom')
    elif(measurement_type=="top-z"):
        #setup step-size
        theta_step = 6 ##deg
        theta_max = 360 ##deg
        theta_scan_points = np.arange(0, theta_max, theta_step)
        measure_tzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    mtype=measure_mode, measure_side='top')
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