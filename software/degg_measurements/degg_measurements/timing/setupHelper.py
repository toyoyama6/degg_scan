##helper functions
import tables
import os, sys
import threading
import time
import numpy as np
from tqdm import tqdm
from datetime import datetime, timedelta

from RapCal import rapcal as rp

from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.analysis import calc_baseline
from degg_measurements import DATA_DIR
from degg_measurements.utils import CALIBRATION_FACTORS

from degg_measurements.monitoring import readout_sensor

from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import enable_pmt_hv_interlock
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import update_json

from degg_measurements.daq_scripts.master_scope import setup_fir_dual_trigger


class deggContainer(object):
    def __init__(self, ALT_FITTING=False):
        self.port = -1
        self.deggName = ''
        self.lowerPMT = ''
        self.upperPMT = ''
        self.icm_port = -1
        self.threshold0 = -1
        self.threshold1 = -1
        self.peakHeight0 = -1
        self.peakHeight1 = -1
        self.dac_value = -1
        self.session = -1
        self.rapcals = -1
        self.files = []
        self.blFiles = []
        self.info0 = []
        self.info1 = []
        self.offset = -1
        self.hvSet0 = -1
        self.hvSet1 = -1
        self.period = -1
        self.rapcal_utcs = []
        self.rapcal_icms = []
        self.dac = -1
        self.seedTimeICM = -1
        self.seedTimeUTC = -1
        self.temperature = -999
        self.fitResult = []

        if ALT_FITTING == True:
            self.rapcals_LINEAR   = -1
            self.rapcals_QUAD     = -1
            self.rapcals_QUAD_MOD = -1
            self.rapcals_RICHARD  = -1

    def addInfo(self, infoContainer, channel):
        if channel == 0:
            self.info0.append(infoContainer)
        if channel == 1:
            self.info1.append(infoContainer)

    def resetInfo(self):
        self.info0 = []
        self.info1 = []
    def saveInfo(self, channel):
        if channel == 0:
            info = self.info0
            f = self.files[0]
        if channel == 1:
            info = self.info1
            f = self.files[1]
        with tables.open_file(f, 'a') as open_file:
            table = open_file.get_node('/data')
            for m, _info in enumerate(info):
                event = table.row
                event['timestamp']   = _info.timestamp
                event['charge']      = _info.charge
                event['channel']     = _info.channel
                event['mfhTime']     = _info.mfh_t
                event['delta']       = _info.delta
                event['offset']      = _info.datetime_offset
                event['blockNum']    = _info.i_pair
                event['triggerNum']  = _info.triggerNum
                event['cableDelay0'] = _info.cable_delay0
                event['cableDelay1'] = _info.cable_delay1
                event['clockDrift']  = _info.clock_drift
                event.append()
                table.flush()

    def createInfoFiles(self, nevents, overwrite=False):
        for ch in [0, 1]:
            f = self.files[ch]
            if os.path.isfile(f):
                if not overwrite:
                    raise IOError(f'File name not unique! Risk overwriting file {f}')
                else:
                    print(f"Will overwrite file {f}")
                    time.sleep(0.1)
                    os.remove(f)
            dummy = [0] * nevents
            dummy = np.array(dummy)
            if not os.path.isfile(f):
                class Event(tables.IsDescription):
                    mfhTime     = tables.Float128Col()
                    delta       = tables.Float128Col()
                    timestamp   = tables.Float128Col()
                    charge      = tables.Float64Col()
                    offset      = tables.Float128Col()
                    channel     = tables.Int32Col()
                    blockNum    = tables.Int32Col()
                    triggerNum  = tables.Int32Col()
                    cableDelay0 = tables.Float64Col()
                    clockDrift  = tables.Float64Col()
                    cableDelay1 = tables.Float64Col()
                with tables.open_file(f, 'w') as open_file:
                    table = open_file.create_table('/','data',Event)

class infoContainer(object):
    def __init__(self, timestamp, charge, channel, i_pair, triggerNum,
                 ALT_FITTING=False):
        self.timestamp = timestamp
        self.charge = charge
        self.channel = channel
        self.i_pair = i_pair
        self.triggerNum = triggerNum
        self.mfh_t = -1
        self.mfh_t2 = -1
        self.delta = -1
        self.datetime_offset = -1
        self.cable_delay0 = -1
        self.cable_delay1 = -1
        self.clock_drift = -1

        if ALT_FITTING == True:
            self.mfh_LINEAR = -1
            self.mfh_QUAD   = -1
            self.mfh_QUAD_MOD = -1
            self.mfh_RICHARD = -1
            self.clockDrift_LINEAR = -1
            self.clockDrift_QUAD = -1
            self.clockDrift_QUAD_MOD = -1
            self.clockDrift_RICHARD = -1
            self.delay0_LINEAR = -1
            self.delay0_QUAD = -1
            self.delay0_QUAD_MOD = -1
            self.delay0_RICHARD = -1
            self.delay1_LINEAR = -1
            self.delay1_QUAD = -1
            self.delay1_QUAD_MOD = -1
            self.delay1_RICHARD = -1

def parseRunFile(run_file, loop_val, gainMeasurement):
    degg_list = []
    hvSetList = []
    thresholdList = []
    blList = []
    peakHeightList = []
    #load all degg files
    list_of_deggs = load_run_json(run_file)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        degg_list.append([degg_dict['LowerPmt']['SerialNumber'], degg_dict['UpperPmt']['SerialNumber']])
        try:
            hvSet0 = getNewHV(degg_dict, 'LowerPmt', loop_val, gainMeasurement)
        except KeyError:
            print(f"-- No GainFitNorm or GainFitExp - {degg_dict['Port']} Ch0 --")
            hvSet0 = 1500
        try:
            hvSet1 = getNewHV(degg_dict, 'UpperPmt', loop_val, gainMeasurement)
        except KeyError:
            print(f"-- No GainFitNorm or GainFitExp - {degg_dict['Port']} Ch1 --")
            hvSet1 = 1500

        baselineFile0 = degg_dict['LowerPmt']['BaselineFilename']
        baselineFile1 = degg_dict['UpperPmt']['BaselineFilename']

        try:
            spe_peak_height0 = (degg_dict['LowerPmt']['SPEPeakHeight'])
        except KeyError:
            print(f"Estimating Peak height for {degg_dict['LowerPmt']['SerialNumber']}")
            spe_peak_height0 = 0.004
        try:
            spe_peak_height1 = (degg_dict['UpperPmt']['SPEPeakHeight'])
        except KeyError:
            print(f"Estimating Peak height for {degg_dict['UpperPmt']['SerialNumber']}")
            spe_peak_height1 = 0.004

        blList.append([baselineFile0, baselineFile1])
        hvSetList.append([hvSet0, hvSet1])
        thresholdList.append([0, 0])
        peakHeightList.append([spe_peak_height0, spe_peak_height1])

    return degg_list, hvSetList, thresholdList, blList, peakHeightList

def overwriteCheck(f, overwrite):
    if not overwrite:
        raise IOError(f'File name not unique! Risk overwriting file {f}')
    else:
        #print(f"Will overwrite file {f}")
        time.sleep(0.01)
        os.remove(f)


def makeBatches(deggsList):
    batch = []
    # batch2 = []
    # batch3 = []
    # batch4 = []

    for degg in deggsList:
        batch.append(degg)
        # if degg.port <= 5003:
        #     batch1.append(degg)
            # continue
        # elif degg.port <= 5007:
        #     batch2.append(degg)
        #     continue
        # elif degg.port <= 5011:
        #     batch3.append(degg)
        #     continue
        # else:
        #     batch4.append(degg)

    batchList = [batch]
    return batchList

def configureDEggHV(deggsList):
    threads = []
    for degg in deggsList:
        configureHV(degg)

    ##verify ramping is finished
    print("For now just waiting enough time (40s)")
    time.sleep(40)

    for degg in deggsList:
        print(f'{degg.port}:')
        print(f'{degg.session.sloAdcReadAll()}')
        time.sleep(0.25)


def configureHV(degg, info='Ramping'):
    session = degg.session
    hv_set0 = degg.hvSet0
    hv_set1 = degg.hvSet1
    print(f'{degg.port}: {hv_set0}, {hv_set1}')
    session.enableHV(0)
    session.enableHV(1)
    session._ramped_channel0 = True
    session._ramped_channel1 = True
    ##ramping handled in firmware
    session.setDEggHV(0, int(hv_set0))
    session.setDEggHV(1, int(hv_set1))

def getICMPort(port):
    if port == 5007:
        return 6000
    elif port == 5011:
        return 6008
    else:
        raise ValueError(f'<getICMPort>: {port} not valid')

def verifyInputs(degg_list, portList, icm_ports, hvSetList, thresholdList,
                 baselineFileList, baselineList):
    return
    #for a in [degg_list, portList, icm_ports, hvSetList, thresholdList, baselineFileList, baselineList]:
        #if len(a) != 16:
            #raise ValueError(f'Length of inputs should be 16! Not {len(a)}')

##NOTE - tabletop port numbers are ASSUMED, in the future grab from the config
def deggListInitialize(deggNameList, degg_list, portList, icm_ports, hvSetList, thresholdList,
                       dacValue, period, deadtime,
                       baselineFileList, baselineList, _type, nevents,
                       overwrite, filepath, loop=0, tabletop=False,
                       ignoreSession=False, sessionList=None, ignoreList=[],
                       ALT_FITTING=False):

    ##just checking book keeping, if 16 D-Eggs are present
    verifyInputs(degg_list, portList, icm_ports, hvSetList, thresholdList, baselineFileList, baselineList)

    deggsList = []

    if sessionList == None:
        sessionList = [None] * len(degg_list)

    for deggName, degg, port, hv_set, thresholds, baselineFs, baselines, session in zip(
                                deggNameList, degg_list,
                                portList, hvSetList, thresholdList,
                                baselineFileList, baselineList, sessionList):
        icm_port = getICMPort(port)
        _degg = doInitialize(deggName, degg, port, icm_port, hv_set,
                             thresholds, dacValue, period, deadtime,
                             baselineFs, baselines, _type, filepath, nevents,
                             overwrite, loop, ignoreSession, session,
                             ALT_FITTING=ALT_FITTING)
        ##this is AFTER initialize to make sure that the sessions are enabled
        ##this is important for the RapCal stability
        if port in ignoreList:
            continue

        deggsList.append(_degg)

    return deggsList

##NOTE - tabletop port numbers are ASSUMED, in the future grab from the config
def doInitialize(deggName, degg, port, icm_port, hv_set, thresholds, dac_value, period, deadtime,
                 baselineFs, baselines, _type, filepath, nevents=0, overwrite=False,
                 loop=0, ignoreSession=False,
                 session=None, createFile=True,
                 ALT_FITTING=False):

    print(f"<doInitialize>: Initialising {port}")

    port = int(port)
    icm_port = int(icm_port)

    ##this is set in setup.py - not needed here anymore
    #if port == 10007 and _type=='tabletop':
    #    print("Enabling tabletop HV interlock")
    #    enable_pmt_hv_interlock(icm_port)

    if ignoreSession != True:
        session = startIcebootSession(host='localhost', port=port)
    if ignoreSession == True and session == None:
        print("If ignoreSession == True, must pass in valid session as argument!")
        print(f"If not, there is a stability risk from RapCal - {port}")
        exit(1)
    rapcals = rp.RapCalCollection()
    time.sleep(0.1)

    hv_set0, hv_set1 = hv_set
    threshold0 = thresholds[0]
    threshold1 = thresholds[1]
    files = []
    pmt_name0 = degg[0]
    f0 = os.path.join(filepath, f'{pmt_name0}_charge_stamp_{hv_set0}v_{thresholds[0]}_{loop}.hdf5')
    files.append(f0)
    pmt_name1 = degg[1]
    f1 = os.path.join(filepath, f'{pmt_name1}_charge_stamp_{hv_set1}v_{thresholds[1]}_{loop}.hdf5')
    files.append(f1)

    _degg = deggContainer(ALT_FITTING)
    _degg.port = port
    _degg.deggName = deggName
    _degg.lowerPMT = pmt_name0
    _degg.upperPMT = pmt_name1
    _degg.icm_port = icm_port
    _degg.rapcals = rapcals
    if ALT_FITTING == True:
        _degg.rapcals_LINEAR   = rp.RapCalCollection()
        _degg.rapcals_QUAD     = rp.RapCalCollection()
        _degg.rapcals_QUAD_MOD = rp.RapCalCollection()
        _degg.rapcals_RICHARD  = rp.RapCalCollection()
    _degg.session = session
    _degg.files = files
    _degg.blFiles = baselineFs
    _degg.baselines = baselines
    _degg.period = period
    _degg.deadtime = deadtime
    _degg.hvSet0 = hv_set0
    _degg.hvSet1 = hv_set1
    _degg.dac = dac_value
    _degg.period = period
    _degg.threshold0 = int(threshold0)
    _degg.threshold1 = int(threshold1)
    _degg.lock = threading.RLock()
    _degg.condition = threading.Condition()
    _degg.type = _type
    _degg.loop = loop
    _degg.temperature = readout_sensor(session, 'temperature_sensor')

    if createFile == True:
        _degg.createInfoFiles(nevents, overwrite)

    if ALT_FITTING == True:
        if _degg.rapcals_LINEAR == -1:
            raise AttributeError(_degg.port)
        if _degg.rapcals_QUAD == -1:
            raise AttributeError(_degg.port)
        if _degg.rapcals_QUAD_MOD == -1:
            raise AttributeError(_degg.port)
        if _degg.rapcals_RICHARD == -1:
            raise AttributeError(_degg.port)

    return _degg

##NOTE: recreateStreams does not enable the HV anymore!
def recreateStreams(degg, use_fir=False):
    with degg.lock:
        if degg.session != None:
            session = degg.session
            if use_fir == True:
                threshold_over_baseline = degg.threshold0 - degg.baselines[0]
                session = setup_fir_dual_trigger(session, n_samples=128,
                                                 dac_value=degg.dac,
                                         threshold_over_baseline=threshold_over_baseline)
            else:
                session = initialize_dual(session, n_samples=128, dac_value=degg.dac,
                                  high_voltage0=degg.hvSet0, high_voltage1=degg.hvSet1,
                                  threshold0=degg.threshold0, threshold1=degg.threshold1,
                                  burn_in=0, modHV=False)

    time.sleep(0.1)

def recreateDEggStreams(deggsList, use_fir=False):
    threads = []
    for degg in deggsList:
        threads.append(threading.Thread(target=recreateStreams, args=[degg, use_fir]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

def getEventDataParallel(degg, nevents=100, method='charge_stamp', i_pair=0, ALT_FITTING=False):
    with degg.lock:
        session = degg.session
        #v0 = readout_sensor(session, 'voltage_channel0')
        #v1 = readout_sensor(session, 'voltage_channel1')
        #print(degg.port, v0, v1)
        ##configure number of events in a block (up to some limit)
        if method == 'charge_stamp':
            block = session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=60)
            channels = list(block.keys())
            for channel in channels:
                charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
                timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
                triggerNum = 0
                for ts, q in zip(timestamps, charges):
                    info = infoContainer(ts, q, channel, i_pair, triggerNum,
                                         ALT_FITTING=ALT_FITTING)
                    degg.addInfo(info, channel)
                    triggerNum += 1

def getNewHV(degg_dict, pmt, gain_factor, gainMeasurement):
    gainFitNorm = degg_dict[pmt][gainMeasurement]['GainFitNorm']
    gainFitExp  = degg_dict[pmt][gainMeasurement]['GainFitExp']

    ##gain func: gain = norm * hv^exp
    ##inverse: hv = (gain / norm)^(1/exp)
    new_hv = (1e7 * gain_factor / gainFitNorm)**(1/gainFitExp)
    return new_hv

def configureBaselines(run_file, n_jobs, fStrength, tSleep, key=None, overwrite=False,
                       ignoreList=[]):

    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
    if not os.path.exists(tmp_file):
        os.mkdir(tmp_file)

    measure_baseline(run_file, n_jobs=n_jobs, modHV=False, return_sessions=False, ignoreList=ignoreList)

    degg_list = []
    hvSetList = []
    thresholdList = []
    baselineFileList = []
    baselineList = []
    sessionList = []
    usingDEggFileList = []
    portList = []
    deggNameList = []
    #load all degg files
    list_of_deggs = load_run_json(run_file)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        port = int(degg_dict['Port'])
        degg_list.append([degg_dict['LowerPmt']['SerialNumber'],
                          degg_dict['UpperPmt']['SerialNumber']])
        hvSetList.append([degg_dict['LowerPmt']['HV1e7Gain'], degg_dict['UpperPmt']['HV1e7Gain']])
        session = startIcebootSession(host='localhost', port=degg_dict['Port'])
        baselineFiles = []
        for channel, pmt in zip([0, 1], ['LowerPmt', 'UpperPmt']):
            bl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   f'tmp/{degg_dict[pmt]["SerialNumber"]}_baseline_get_offset_{channel}.hdf5')
            baselineFiles.append(bl_file)
            if os.path.isfile(bl_file):
                if overwrite:
                    time.sleep(0.5)
                    os.remove(bl_file)
                else:
                    raise IOError(f'File {bl_file} already exists!')
        baselineFileList.append(baselineFiles)
        sessionList.append(session)
        usingDEggFileList.append(degg_file)
        portList.append(port)
        deggNameList.append(degg_dict['DEggSerialNumber'])

    i = 0
    for degg_file, session in zip(usingDEggFileList, sessionList):
        degg_dict = load_degg_dict(degg_file)
        port = int(degg_dict['Port'])
        if port in ignoreList:
            thresholdList.append([0, 0])
            baselineList.append([0, 0])
            continue
        baselineFileList[i][0] = degg_dict['LowerPmt']['BaselineFilename']
        baselineFileList[i][1] = degg_dict['UpperPmt']['BaselineFilename']
        baseline0 = calc_baseline(baselineFileList[i][0])['baseline'].values[0]
        baseline1 = calc_baseline(baselineFileList[i][1])['baseline'].values[0]
        baselineList.append([baseline0, baseline1])

        ##these are in Volts
        spePeakHeight0 = degg_dict['LowerPmt']['SPEPeakHeight']
        spePeakHeight1 = degg_dict['UpperPmt']['SPEPeakHeight']
        speThresh0 = (spePeakHeight0/CALIBRATION_FACTORS.adc_to_volts) * 0.5
        speThresh1 = (spePeakHeight1/CALIBRATION_FACTORS.adc_to_volts) * 0.5

        ##SPE setting
        if fStrength == 0.005 or fStrength == 0.0005:
            #threshold0 = baseline0 + 24
            #threshold1 = baseline1 + 24

            threshold0 = baseline0 + speThresh0
            threshold1 = baseline1 + speThresh1

        elif fStrength == 0.25:
            threshold0 = baseline0 + 1600
            threshold1 = baseline1 + 1600

            #threshold0 = baseline0 + 700
            #threshold1 = baseline1 + 700
            #threshold0 = baseline0 + 24
            #threshold1 = baseline1 + 24
        elif fStrength == 0.1:
            threshold0 = baseline0 + 500
            threshold1 = baseline1 + 500
            #check threshold when it's the same as the linearity

            #threshold0 = baseline0 + 700
            #threshold1 = baseline1 + 700
        elif fStrength == 0.01:
            threshold0 = baseline0 + 12
            threshold1 = baseline1 + 12
        elif fStrength == 0.05:
            threshold0 = baseline0 + 24
            threshold1 = baseline1 + 24
        elif fStrength == 0.5:
            threshold0 = baseline0 + 20
            threshold1 = baseline1 + 20
        
        elif fStrength == 1:
            threshold0 = baseline0 + 6000
            threshold1 = baseline1 + 100
        elif fStrength == 0:
            threshold0 = baseline0 + 100
            threshold1 = baseline1 + 6000
        
        
        else:
            raise ValueError(f'No threshold configured for strength of {fStrength}! Please set one!')

        thresholdList.append([threshold0, threshold1])

        print(f'Thresholds - {port}: {threshold0}, {threshold1} ADC')

        if key != None:
            degg_dict['LowerPmt'][key]['Threshold'] = float(threshold0)
            degg_dict['UpperPmt'][key]['Threshold'] = float(threshold1)
            degg_dict['LowerPmt'][key]['BaselineFilename'] = baselineFileList[i][0]
            degg_dict['UpperPmt'][key]['BaselineFilename'] = baselineFileList[i][1]
            degg_dict['LowerPmt'][key]['Baseline'] = float(baseline0)
            degg_dict['UpperPmt'][key]['Baseline'] = float(baseline1)
            try:
                update_json(degg_file, degg_dict)
            except:
                print("use this to recover the file")
                print(degg_dict)
                exit(1)
        i += 1
    print(f"baselinelist = {baselineList}")
    return deggNameList, degg_list, sessionList, portList, hvSetList, thresholdList, baselineFileList, baselineList

def getTimeMFH(icms, deggBatch):

    icms.request('write 8 0 0x0100')
    # icms.request('gps_enable')
    ##THIS IS NEEDED FOR PPS TO UPDATE SETTINGS
    ##DO NOT REMOVE
    time.sleep(1.1)
    icm_time = icms.request('get_icm_time 8')['value']
    # utc_time_str = icms.request('read 8 0x2B')['value']
    icms.request('write 8 0 0x0100')
    # icms.request('gps_enable')
    ##THIS IS NEEDED FOR PPS TO UPDATE SETTINGS
    ##DO NOT REMOVE
    time.sleep(1.1)
    icm_time = icms.request('get_icm_time 8')['value']
    # utc_time_str = icms.request('read 8 0x2B')['value']
    # utc_time_str = datetime.now()

    #icm_time = icms.request('get_icm_time 8')['value']
    #utc_time_str = icms.request('read 8 0x2B')['value']
    # utc_time_str = utc_time_str.split('T')
    #Years, days, hours, min, sec
    # years   = int(utc_time_str[0].split('-')[0])
    # days    = int(utc_time_str[0].split('-')[1])
    # days    = utc_time_str.day
    # hours   = int(utc_time_str[1].split(':')[0])
    # minutes = int(utc_time_str[1].split(':')[1])
    # seconds = int(utc_time_str[1].split(':')[2])
    # dt = datetime(years, 1, 1, hours, minutes, seconds) + timedelta(days=(days-1))
    # dt = datetime(utc_time_str.year, 1, 1, utc_time_str.hour, utc_time_str.minute, utc_time_str.second) + timedelta(days=(days-1))
    utc_time = datetime.now().timestamp()
    # utc_time = datetime.now.timestamp()


    # print(f'GPS datetime read from ICM: {dt}')
    print(f'GPS timestamp: {utc_time}')
    print(f'MFH ICM Time: {icm_time}')

    for degg in deggBatch:
        degg.seedTimeICM = icm_time
        degg.seedTimeUTC = utc_time

##end
