from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

from termcolor import colored
from tqdm import tqdm
import time
import os
import pandas as pd
import threading


####
from read_waveform import set_DAQ
from deggContainer import *
from icmnet import ICMNet

####

#########
import skippylab as sl
from degg_measurements.daq_scripts.master_scope import write_to_hdf5
from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.setupHelper import getEventDataParallel
from degg_measurements.timing.rapcalHelper import calculateTimingInfoAfterDataTaking
from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.rapcalHelper import calculateTimingInfoAfterDataTaking
from degg_measurements.timing.setupHelper import infoContainer, deggContainer
from degg_measurements.timing.setupHelper import recreateDEggStreams
from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.timing.setupHelper import makeBatches
from degg_measurements.timing.setupHelper import deggListInitialize, doInitialize
from degg_measurements.timing.setupHelper import recreateDEggStreams
from degg_measurements.timing.setupHelper import getTimeMFH






#########

def run(filepath, run_file, r_point, t_point, icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList,
         baselineFileList, baselineList, ignoreList, method='charge_stamp', 
        overwrite=True, verbose=False, ALT_FITTING=False):
    
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
                            filepath=filepath, overwrite=overwrite, ignoreSession=True,
                            sessionList=sessionList, ignoreList=ignoreList,
                            ALT_FITTING=ALT_FITTING)


    print('1')
    # verify_hv([deggsList], verbose=True)
    #from IPython import embed
    #embed()
    ##mainly just calling initialize_dual for all DEggs
    recreateDEggStreams(deggsList)

    ##setup batches of 4 to avoid launching jobs
    ##simultaneously on same wire pair
    deggBatches = makeBatches(deggsList)

    if verbose:
        print("Checking Batching:")
        for deggBatch in deggBatches:
            for degg in deggBatch:
                print(f'Port: {degg.port}')


    ##NOTE - The threshold is lowered when the splitter is used!
    tabletop = doInitialize('tabletop', ['tabletop', 'tabletop'], 5011, 6008, [0, 0], [9000, 14000],
                            dac_value, period, deadtime, [None, None], filepath=filepath,
                            baselines = [0, 0], _type='tabletop', createFile=False,
                            ALT_FITTING=ALT_FITTING)
    recreateStreams(tabletop)
    deggBatches.append([tabletop])
    print("deggbatches1", deggBatches)
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

    run_number = os.path.basename(run_file)
    run_number = run_number.split('.')[0]
    run_number = run_number.split('_')[-1]
    saveContainer(deggsList, filepath, r_point, t_point, method, run_number, ALT_FITTING)






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




def measure_r_steps(data_dir, run_file, r_stage, slave_address, t_point, r_step, r_scan_points, 
                    icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList, ignoreList,
                    forward_backward='forward'):
    
    print(f'Measuring: {forward_backward}\n{r_scan_points}')
    for event_num, r_point in enumerate(r_scan_points):
        print("r_point =", r_point, "t_point =", t_point)
        ##take DEgg data
        try:
            run(data_dir, run_file, r_point, t_point, icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, 
                baselineFileList, baselineList, ignoreList,
                method='charge_stamp', verbose=False, ALT_FITTING=False)
        except:
            print("don't mind") 

        if forward_backward == 'forward':
            r_stage.moveRelative(slave_address, r_step)
            time.sleep(5)
        elif forward_backward == 'backward':
            r_stage.moveRelative(slave_address, -r_step)
            time.sleep(5)
        else:
            raise ValueError(f'option for scan direction: {forward_backward} not valid')



def setup_reference(reference_pmt_channel):
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
    LD = PMX70_1A('10.25.101.60')
    LD.connect_instrument()
    LD.set_volt_current(voltage, 0.02)
    #Warm up LD
    print('Warm up LD (10 min)')
    # for i in tqdm(range(600)):
    #     time.sleep(1)
    



def setup_bottom_devices(slave_address, voltage):
    print(colored("Setting up motors...", 'green'))
    rotate_stage = None
    ##USB3 - THORLABS
    try:
        rotate_stage = HDR50(serial_port="/dev/ttyUSB3", serial_number="40106754", home=True, swap_limit_switches=True)
        rotate_stage.wait_up()
    except:
        print(colored('Error in connecting to Thorlabs Motor!', 'red'))
    ##USB2 - ORIENTAL MOTORS
    try:
        r_stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    rotate_stage.move_relative(-90)
    rotate_stage.wait_up()

    r_stage.moveToHome(slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))
    setup_LD(voltage)
    return rotate_stage, r_stage

def setup_top_devices(rotate_slave_address, r_slave_address, voltage):
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

def measure_brscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_scan_points,
                    ):
    print('brscan')
    slave_address = 1
    rotate_stage, r_stage, LD = setup_bottom_devices(slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:
        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point, r_step, 
                        r_scan_points, forward_backward='forward')
        ##when finished, return motor to home
        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(20)

        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()
    rotate_stage.move_relative(-270)
    rotate_stage.wait_up()



def measure_bzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    ):
    print('bzscan')
    slave_address = 2
    rotate_stage, r_stage, LD = setup_bottom_devices(slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point, z_step, 
                        z_scan_points, forward_backward='forward')
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(10)
        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()
    rotate_stage.move_relative(-270)
    rotate_stage.wait_up()



def measure_trscan(run_file, dir_sig, dir_ref, voltage,
                    theta_step,theta_scan_points, r_step, 
                    r_scan_points, icm_ports, deggNameList, 
                    deggList, sessionList, portList, hvSetList, 
                    thresholdList, baselineFileList, baselineList, ignoreList
                    ):

    print('trscan')
    rotate_slave_address = 5
    r_slave_address = 3
    stage = setup_top_devices(rotate_slave_address, r_slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    stage.moveToHome(r_slave_address)
    print('r_stage homing')
    time.sleep(10)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')

        measure_r_steps(dir_sig, run_file, stage, r_slave_address, theta_point, r_step, r_scan_points, 
                        icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, 
                        baselineFileList, baselineList, ignoreList,
                        forward_backward='forward')


        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(10)
        stage.moveRelative(rotate_slave_address, -theta_step)
        time.sleep(10)
    stage.moveRelative(rotate_slave_address, 360)
    print('stage homing')
    for i in tqdm(range(120)):
        time.sleep(1)
    

    

def measure_tzscan(run_file, dir_sig, dir_ref, voltage,
                    theta_step,theta_scan_points, z_step, 
                    z_max, z_scan_points, icm_ports, deggNameList, 
                    deggList, sessionList, portList, hvSetList, 
                    thresholdList, baselineFileList, baselineList, ignoreList
                    ):
    print('tzscan')
    rotate_slave_address = 5
    r_slave_address = 4
    stage = setup_top_devices(rotate_slave_address, r_slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    #r_stage is homing
    stage.moveToHome(r_slave_address)
    print('r_stage homing')
    time.sleep(10)


    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, run_file, stage, r_slave_address, theta_point, z_step, z_scan_points, 
                        icm_ports, deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, 
                        baselineFileList, baselineList, ignoreList,
                        forward_backward='forward')
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)
        stage.moveRelative(rotate_slave_address, -theta_step)
        time.sleep(10)
    stage.moveRelative(rotate_slave_address, 360)
    print('stage homing')
    for i in tqdm(range(120)):
        time.sleep(1)

##################################################################################
