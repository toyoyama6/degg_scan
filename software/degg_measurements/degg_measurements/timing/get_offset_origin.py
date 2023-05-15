import sys, os
import click
import pandas as pd
import threading
import numpy as np
import time
from tqdm import tqdm
from datetime import datetime, timedelta

#########
from degg_measurements import FH_SERVER_SCRIPTS

sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet

from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.rapcalHelper import calculateTimingInfoAfterDataTaking
from degg_measurements.timing.setupHelper import recreateStreams
from degg_measurements.timing.setupHelper import makeBatches, getEventDataParallel
from degg_measurements.timing.setupHelper import infoContainer, deggContainer
from degg_measurements.timing.setupHelper import configureBaselines
from degg_measurements.timing.setupHelper import deggListInitialize, doInitialize
from degg_measurements.timing.setupHelper import recreateDEggStreams
from degg_measurements.timing.setupHelper import getTimeMFH


from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_run_json, load_degg_dict, add_default_meas_dict, update_json
from degg_measurements.utils.check_laser_freq import light_system_check
from degg_measurements.utils.hv_check import checkHV



def saveContainer(deggContainerList, filepath, method='charge_stamp', run_number='00000',
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
                filename = f'timing_info_{method}_{degg.port}_ALT_FITS.hdf5'
            else:
                filename = f'timing_info_{method}_{degg.port}.hdf5'
            df.to_hdf(os.path.join(filepath, filename), key='df', mode='w')
            dfList.append(df)

    df_total = pd.concat(dfList, sort=False)
    if ALT_FITTING == True:
        t_filename = f'total_{run_number}_{method}_ALT_FITS.hdf5'
    else:
        t_filename = f'total_{run_number}_{method}.hdf5'
    df_total.to_hdf(os.path.join(filepath, t_filename), key='df', mode='w')


def getWaveformTimestamp(xList, yList, threshold):
    below = []
    above = []
    for y in yList:
        if y < threshold:
            below.append(y)
        if y >= threshold:
            above.append(y)
            break

    ##get last point below and first point above
    just_below = [xList[len(below)-1], below[-1]]
    just_above = [xList[len(below)], above[0]]
    ##do simple linear interpolation between
    slope = (just_above[1] - just_below[1]) / (just_above[0] - just_below[0])
    offset = (slope * (0 - just_below[0])) + just_below[1]
    crossing_point = (threshold - offset) / slope
    return crossing_point

def prepare_metadata(run_file, comment, fStrength, laser_freq, nevents,
                     n_rapcals):
    data_dir = '/home/scanbox/data/fat_calibration/'
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
        print(f'Created directory {data_dir}')
    filepath = create_save_dir(data_dir, 'tts')
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

    return icm_ports, key, filepath, ignoreList

##hv should be ramped by this time - check
def verify_hv(deggBatches, verbose=False):
    hvOn = 0
    doRamp = True
    for deggBatch in deggBatches:
        for degg in deggBatch:
            if degg.port == 5007:
                continue
            session = degg.session
            hvList = [degg.hvSet0, degg.hvSet1]
            if hvList[0] == -1 or hvList[1] == -1:
                doRamp = False
            for _channel in [0, 1]:
                hv_enabled = checkHV(session, _channel, verbose=verbose)
                hvOn += hv_enabled
                if hv_enabled == False and doRamp == True:
                    session.enableHV(_channel)
                    session.setDEggHV(_channel, int(hvList[_channel]))
    if hvOn != 32:
        print(f'Only {hvOn} PMTs are ramped!')
        for i in tqdm(range(40), desc='HV Ramping'):
            time.sleep(1)


def run_timing(run_file, comment, n_jobs,
               method='charge_stamp', overwrite=False,
               verbose=False, ALT_FITTING=False):
    n_jobs = int(n_jobs)

    ##SPE level tests
    fStrength = 1 
    print(f'Total Filter Strength: {fStrength}')

    ##configure function generator
    laser_freq = 500 #Hz
    #light_system_check(laser_freq)
    tSleep = 40 ##seconds

    rapcal_ports = [6000, 6008]
    icmConnectList = []
    for rp_port in rapcal_ports:
        icms = ICMNet(rp_port, host='localhost')
        icmConnectList.append(icms)

    dac_value = 30000
    nevents = laser_freq ##charge block size
    ##already at 300 size is getting huge!
    n_rapcals = 5 ##number of repeats

    period = 100000 ##deprecated - only for scaler
    deadtime = 24 ##deprecated - only for scaler

    icm_ports, key, filepath, ignoreList = prepare_metadata(run_file, comment,
                                                fStrength, laser_freq,
                                                nevents, n_rapcals)

    ##this stage measures the PMT baselines
    deggNameList, deggList, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList = configureBaselines(
        run_file=run_file, n_jobs=n_jobs, fStrength=fStrength, tSleep=tSleep,
        overwrite=overwrite, key=key, ignoreList=ignoreList)

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


    ##create tabletop class too
    ##add to the lists to be run
    #tabletop = doInitialize(['tabletop', 'tabletop'], 10007, 11000, [0, 0], [9500, 14000],
    #                         dac_value, period, deadtime, [None, None], filepath=filepath,
    #                         baselines = [0, 0], _type='tabletop', createFile=False)
    ##NOTE - The threshold is lowered when the splitter is used!
    tabletop = doInitialize('tabletop', ['tabletop', 'tabletop'], 5011, 6008, [0, 0], [9000, 14000],
                            dac_value, period, deadtime, [None, None], filepath=filepath,
                            baselines = [0, 0], _type='tabletop', createFile=False,
                            ALT_FITTING=ALT_FITTING)
    recreateStreams(tabletop)
    deggBatches.append([tabletop])
    ##get the ICM seed times in parallel to reduce offset between them
    print("icmConnectList =",icmConnectList)
    print("deggBatches =", deggBatches)
    t_threads = []
    for icms, deggBatch in zip(icmConnectList, deggBatches):
        t_threads.append(threading.Thread(target=getTimeMFH, args=[icms, deggBatch]))
    for t in t_threads:
        t.start()
    for t in t_threads:
        t.join()

    print("Finished initialisation")
    # verify_hv(deggBatches, verbose=True)
    print("Verifying HV is OK")

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
    saveContainer(deggsList, filepath, method, run_number, ALT_FITTING)

@click.command()
@click.argument('run_file')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=1, help='number of parallel baseline tasks')
@click.option('--method', '-m', default='charge_stamp')
@click.option('--overwrite', '-o', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
@click.option('--alt_fit', is_flag=True)
def main(run_file, comment, n_jobs, method, overwrite, verbose, alt_fit):
    run_timing(run_file=run_file, comment=comment, n_jobs=n_jobs,
               method=method, overwrite=overwrite, verbose=verbose,
               ALT_FITTING=alt_fit)

if __name__ == "__main__":
    main()

##end
