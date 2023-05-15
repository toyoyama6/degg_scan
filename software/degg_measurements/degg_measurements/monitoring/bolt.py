import os, sys
import click
import numpy as np
import pandas as pd
from tqdm import tqdm
import time
from datetime import datetime
import threading

from iceboot import iceboot_session_cmd

from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils import add_git_infos_to_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.monitoring import readout_sensor
from degg_measurements import DATA_DIR
from degg_measurements.daq_scripts.master_scope import setup_fir_trigger
from degg_measurements.daq_scripts.master_scope import take_waveform
from degg_measurements.daq_scripts.master_scope import initialize

from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101

from chiba_slackbot import send_message
from chiba_slackbot import send_warning
from chiba_slackbot import send_critical

class mbPowerInfo():
    def __init__(self, session, n_reads, port, degg_name, key, verbose=False):
        self.start_time = np.float128(datetime.now().timestamp())
        self.verbose = verbose
        self.degg_name = degg_name
        self.port = port
        self.meas_key = key
        self.n_reads = n_reads
        self.i1v1  = np.zeros(n_reads)
        self.i1v35 = np.zeros(n_reads)
        self.i1v8  = np.zeros(n_reads)
        self.i2v5  = np.zeros(n_reads)
        self.i3v3  = np.zeros(n_reads)
        self.v1v8  = np.zeros(n_reads)
        self.v1v1  = np.zeros(n_reads)
        self.v1v35 = np.zeros(n_reads)
        self.v2v5  = np.zeros(n_reads)
        self.v3v3  = np.zeros(n_reads)
        self.power = -1
        self.session = session
        self.channelList = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15]
        self.verdict = [True] * 5 #5 current monitors
        self.powerIsValid = True
        ##pmt hv readback
        self.hv0 = -1
        self.hv1 = -1
        self.hv1e7gain0 = -1
        self.hv1e7gain1 = -1
        ##internal pressure
        self.pressure = -1
        ##mainboard temperature
        self.temperature = -1

        ##for the scalers
        self.period = 100000
        self.deadtimeBins = 24
        self.dac_value = 30000
        self.baseline0 = 0
        self.baseline1 = 0
        self.scaler0 = 0
        self.scaler1 = 0
        self.dark_rate0 = 0
        self.dark_rate1 = 0


        ##include also previous data
        ##hv values and temperature

        #[mA]
        self.maxi1v1  = 1000
        self.maxi1v35 = 400
        self.maxi1v8  = 400
        self.maxi2v5  = 500
        self.maxi3v3  = 300

    def getHV1e7Gain(self, degg_dict):
        for pmt in ['LowerPmt', 'UpperPmt']:
            hv1e7gain = degg_dict[pmt]['HV1e7Gain']
            if hv1e7gain == 1500 or hv1e7gain == None or hv1e7gain == -1:
                if pmt == 'LowerPmt':
                    self.hv1e7gain0 = -1
                if pmt == 'UpperPmt':
                    self.hv1e7gain1 = -1
            else:
                if pmt == 'LowerPmt':
                    self.hv1e7gain0 = hv1e7gain
                if pmt == 'UpperPmt':
                    self.hv1e7gain1 = hv1e7gain

    def returnValues(self, channel):
        if channel == 0:
            return self.i1v1
        elif channel == 1:
            return self.i1v35
        elif channel == 2:
            return self.i1v8
        elif channel == 3:
            return self.i2v5
        elif channel == 4:
            return self.i3v3
        elif channel == 5:
            return self.v1v8
        elif channel == 12:
            return self.v1v1
        elif channel == 13:
            return self.v1v35
        elif channel == 14:
            return self.v2v5
        elif channel == 15:
            return self.v3v3

    def returnRange(self, channel):
        if channel == 0:
            return self.maxi1v1
        elif channel == 1:
            return self.maxi1v35
        elif channel == 2:
            return self.maxi1v8
        elif channel == 3:
            return self.maxi2v5
        elif channel == 4:
            return self.maxi3v3
        elif channel in [5, 12, 13, 14, 15]:
            return True
        else:
            raise ValueError(f'Channel invalid: {channel}')

    def checkValid(self):
        valList = [self.i1v1, self.i1v35, self.i1v8, self.i2v5, self.i3v3,
                   self.v1v8, self.v1v1, self.v1v35, self.v2v5, self.v3v3]
        for channel, vals in zip(self.channelList, valList):
            ret = self.returnRange(channel)
            if vals.any() == None:
                print(f'None read on channel: {channel}')
                try:
                    self.verdict[channel] = False
                except IndexError:
                    pass
                return False
            if ret == True:
                return True
            elif np.mean(vals) > ret:
                self.verdict[channel] = False
                return False
            else:
                self.verdict[channel] = True
                return True

    def mapToChannel(self, val, i, channel):
        if channel == 0:
            self.i1v1[i] = val
        elif channel == 1:
            self.i1v35[i] = val
        elif channel == 2:
            self.i1v8[i] = val
        elif channel == 3:
            self.i2v5[i] = val
        elif channel == 4:
            self.i3v3[i] = val
        elif channel == 5:
            self.v1v8[i] = val
        elif channel == 12:
            self.v1v1[i] = val
        elif channel == 13:
            self.v1v35[i] = val
        elif channel == 14:
            self.v2v5[i] = val
        elif channel == 15:
            self.v3v3[i] = val
        else:
            raise ValueError(f'{channel} for reading sloAdc is not valid!')

    def calcPower(self):
        if np.sum(self.verdict) != 5:
            self.powerIsValid = False
        power = (np.mean(self.i1v1)  * np.mean(self.v1v1) +
                np.mean(self.i1v35) * np.mean(self.v1v35) +
                np.mean(self.i1v8)  * np.mean(self.v1v8)  +
                np.mean(self.i2v5)  * np.mean(self.v2v5)  +
                np.mean(self.i3v3)  * np.mean(self.v3v3))
        power = power / 1e3 #[W]
        self.power = power
        if self.verbose:
            print(f'Power={power} W, {5-np.sum(self.verdict)} Imon out of range')

    def getVal(self, channel):
        if self.session != None:
            return float(self.session.sloAdcReadChannel(channel))
        else:
            raise ValueError(f'Session is none for {self.port}!')

    def getHighVoltage(self):
        if self.session != None:
            self.hv0 = readout_sensor(self.session, 'voltage_channel0')
            self.hv1 = readout_sensor(self.session, 'voltage_channel1')
        else:
            send_warning(f'quick_monitoring - session for {self.port} is none!')
            raise ValueError(f'Session is none for {self.port}!')

    ##this is best checked after sampling several times
    def checkHighVoltage(self, hvVal, hvStd, channel):
        if np.array(hvVal).any() == -1:
            raise ValueError(f'{hvVal} sees values of -1 V! This is a problem!')
        if channel not in [0, 1]:
            raise ValueError(f'HV Channel must be 0 or 1 not {channel}!')
        if channel == 0:
            hv1e7gain = self.hv1e7gain0
        if channel == 1:
            hv1e7gain = self.hv1e7gain1

        ##val & std
        verdict = [False, False]

        if hvVal <= 0 or hvVal > 2000:
            verdict[0] = False
        elif hv1e7gain == -1:
            print(f'NOTE: No HV1e7Gain yet assigned for {self.port}')
            verdict[0] = True
        else:
            ##try to find range to cover different temperatures
            if abs(hvVal - hv1e7gain) > 150:
                verdict[0] = False
            else:
                verdict[0] = True

        ##hvStd should be within 2% of each other
        rel_std = hvStd/hvVal
        if rel_std <= 0.02:
            verdict[1] = True
        else:
            verdict[1] = False

        return verdict

    def getPressure(self):
        if self.session != None:
            try:
                self.pressure = readout_sensor(self.session, 'pressure')
            except Exception as e:
                _msg = f'Pressure Read warn {e}'
                send_warning(_msg)
                self.pressure = -1
        else:
            send_warning(f'quick_monitoring - session for {self.port} is none!')
            raise ValueError(f'Session is none for {self.port}!')

    def getTemperature(self):
        if self.session != None:
            self.temperature = readout_sensor(self.session, 'temperature_sensor')
        else:
            send_warning(f'quick_monitoring - session for {self.port} is none!')
            raise ValueError(f'Session is none for {self.port}!')

    def getBaselines(self):
        if self.session != None:
            for channel, hv in zip([0, 1], [self.hv1e7gain0, self.hv1e7gain1]):
                session = initialize(self.session, channel=channel, n_samples=514,
                                     dac_value=self.dac_value, high_voltage0=hv,
                                     modHV=False, verbose=False)
                blList = []
                for i in range(10):
                    session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
                    blList.append(np.median(wf))
                if channel == 0:
                    self.baseline0 = np.mean(blList)
                if channel == 1:
                    self.baseline1 = np.mean(blList)
                self.session.endStream()
            time.sleep(1)
        else:
            raise ValueError(f'Session is none for {self.port}!')


    ##use fir trigger
    def getScalers(self):
        #threshold_over_baseline = 15
        threshold_over_baseline = 20
        if self.session == None:
            raise ValueError(f'Session is none for {self.port}!')
        duration = self.period / 1e6
        FPGA_CLOCK_TO_S = 1. / 240e6
        deadtime = self.deadtimeBins * FPGA_CLOCK_TO_S
        fir_coeffs=[0]*10+[1,1]+[0]*4
        for channel in [0, 1]:
            if channel == 0:
                threshold_total = int(self.baseline0 + threshold_over_baseline)
            if channel == 1:
                threshold_total = int(self.baseline1 + threshold_over_baseline)
            ##fir settings
            fir_threshold = int(threshold_over_baseline*np.sum(fir_coeffs))*len(fir_coeffs)
            self.session.setFIRCoefficients(channel, fir_coeffs)
            self.session.setDEggFIRTriggerThreshold(channel, fir_threshold)
            self.session.enableDEggFIRTrigger(channel)
            self.session.enableScalers(channel, self.period, self.deadtimeBins)
            ##non-fir settings
            # self.session.setDEggTriggerConditions(channel, int(threshold_total))
            # self.session.enableDEggADCTrigger(channel)
            # self.session.enableScalers(channel, self.period, self.deadtime)

        time.sleep(duration*2)
        for channel in [0, 1] :
            scaler = self.session.getScalerCount(channel)
            mtime = duration - (scaler * deadtime)
            darkrate = scaler / mtime
            if channel == 0:
                self.scaler0 = scaler
                self.dark_rate0 = darkrate
            if channel == 1:
                self.scaler1 = scaler
                self.dark_rate1 = darkrate

        self.session.endStream()
        time.sleep(0.01)

    def exportVals(self):
        data = {}
        for d in self.__dict__:
            vals = self.__dict__[d]
            if d in ['i1v1', 'i1v35', 'i1v8', 'i2v5', 'i3v3',
                 'v1v8', 'v1v1', 'v1v35','v2v5', 'v3v3']:
                _dict = {f'{d}': [np.mean(vals)]}
            elif d in ['power', 'powerIsValid', 'port',
                     'degg_name', 'n_reads', 'meas_key', 'baseline0',
                     'baseline1', 'hv0', 'hv1',
                     'hv1e7gain0', 'scaler0', 'dark_rate0',
                     'hv1e7gain1', 'scaler1', 'dark_rate1',
                     'pressure', 'start_time', 'temperature']:
                _dict = {f'{d}': [vals]}
            else:
                continue
            data.update(_dict)
        df = pd.DataFrame(data=data)
        return df

def sloAdcReadChannels(info):
    ##collect the monitoring data
    ##channels list is the sloAdc channels
    ##values can be a bit noisy - so read n times
    for channel in info.channelList:
        channel = int(channel)
        for i in range(info.n_reads):
            val = info.getVal(channel)
            info.mapToChannel(val, i, channel)

    ##get the high voltage
    info.getHighVoltage()

    ##get the internal pressure
    info.getPressure()

    ##get the mainboard temperature
    info.getTemperature()

    ##get the dark rate w/ scalers
    info.getBaselines()
    info.getScalers()
    print(f'{info.port}-0: {info.dark_rate0} Hz')
    print(f'{info.port}-1: {info.dark_rate1} Hz')

    ##check values - to be reported later
    info.checkValid()
    info.calcPower()

    ##collect data and create pandas dataframe
    df = info.exportVals()

    ##return the modified class and df
    return info, df

def convertToString(verdict):
    if verdict == True:
        return 'OK'
    if verdict == False:
        return 'FAILED'

##summed over a few runs for 1 D-Egg! i.e. dfTotal is still 1 module
def reportStatus(dfTotal, infoList):
    n_pass = 0
    chSummary = []
    valSummary = []
    msg_str = f'{infoList[0].degg_name} ({infoList[0].port}) '
    for info in infoList:
        if np.sum(info.verdict) == 5:
            n_pass += 1
        else:
            for i, v in enumerate(info.verdict):
                if v == False:
                    ch = info.channelList[i]
                    chSummary.append(ch)
                    val = np.mean(info.returnValues(ch))
                    valSummary.append(val)

    meanVerdictList = [False, False]
    stdVerdictList  = [False, False]
    highDarkRates   = [False, False]
    for hvch in [0, 1]:
        if hvch == 0:
            _hv = dfTotal.hv0.values
        if hvch == 1:
            _hv = dfTotal.hv1.values
        #_hv = dfTotal[f'hv{hvch}'].values
        hv_mean = np.mean(_hv)
        hv_std  = np.std(_hv)
        meanVerdict, stdVerdict = infoList[0].checkHighVoltage(hv_mean, hv_std, hvch)
        msg_str = msg_str + f' \n HV{hvch} Val: {convertToString(meanVerdict)} '
        msg_str = msg_str + f' \n HV{hvch} Std: {convertToString(stdVerdict)} '
        msg_str = msg_str + f' \n HV = {hv_mean:.2f} +/- {hv_std:.2f} V'

        meanVerdictList[hvch] = meanVerdict
        stdVerdictList[hvch]  = stdVerdict
        if meanVerdict == True and stdVerdict == True:
            if hvch == 0:
                voltage0_ok = 1
            if hvch == 1:
                voltage1_ok = 1
        else:
            if hvch == 0:
                voltage0_ok = 0
            if hvch == 1:
                voltage1_ok = 0


        ##check scalers
        dr_lim = 2600 #Hz
        if hvch == 0:
            s_cnt = dfTotal.dark_rate0.values
        if hvch == 1:
            s_cnt = dfTotal.dark_rate1.values
        mask = s_cnt >= dr_lim
        n_high = np.sum(mask)
        msg_str = msg_str + f' \n Dark Rate {hvch}: (N > {dr_lim} = {n_high} / {len(mask)}):'
        msg_str = msg_str + f' {np.mean(s_cnt):.2f} +/- {np.std(s_cnt):.2f} Hz'
        highDarkRates[hvch] = True

    if n_pass == len(infoList):
        current_ok = 1
    else:
        current_ok = 0

    msg_str = msg_str + f' \n I_Mon N Checks: {n_pass}/{len(infoList)} OK'

    if n_pass == len(infoList):
        if np.sum(meanVerdictList) == 2 and np.sum(stdVerdictList) == 2:
            send_message(msg_str)
        else:
            send_warning(msg_str)
    else:
        for ch, val in zip(chSummary, valSummary):
            maxI = infoList[0].returnRange(ch)
            msg_str = msg_str + f' \n FAILS: Ch={ch}, Val={val} (Max={maxI}) mA'
            current_ok = 0
        send_warning(msg_str)
    return current_ok, voltage0_ok, voltage1_ok

def wrapper(degg_file, session, passInfo, n_repeat, n_reads, key, save_dir, dfHolder):
    degg_dict = load_degg_dict(degg_file)
    degg_name = degg_dict['DEggSerialNumber']
    port = degg_dict['Port']

    if audit_ignore_list(degg_file, degg_dict, key):
        session.close()
        return

    dfList = []
    infoList = []
    for i in range(n_repeat):
        info = mbPowerInfo(session, n_reads, port, degg_name, key)
        info.getHV1e7Gain(degg_dict)
        info, df = sloAdcReadChannels(info)
        infoList.append(info)
        dfList.append(df)

    dfTotal = pd.concat(dfList)
    #print(dfTotal.keys())
    #for _key in dfTotal.keys():
    #    print(dfTotal[f'{_key}'].values)
    #time.sleep(1)
    #dfTotal.to_hdf(os.path.join(save_dir, f'mon_{port}.hdf5'), key=f'df{port}', mode='w')
    #time.sleep(1)
    dfHolder.df = dfTotal
    degg_dict[key]['Folder'] = save_dir

    ##report overall status to slack
    imon_passed, hv0_passed, hv1_passed = reportStatus(dfTotal, infoList)

    degg_dict[key]['IMONResult'] = imon_passed
    degg_dict[key]['HV0Result']  = hv0_passed
    degg_dict[key]['HV1Result']  = hv1_passed
    update_json(degg_file, degg_dict)

    passInfo[0] = imon_passed
    passInfo[1] = hv0_passed
    passInfo[2] = hv1_passed

    session.close()

class DFHolder():
    def __init__(self, port):
        self.df = None
        self.port = port

def makeBatches(deggsList, sessionList, portList):
    batch1 = []
    batch2 = []
    batch3 = []
    batch4 = []
    sbatch1 = []
    sbatch2 = []
    sbatch3 = []
    sbatch4 = []
    p1 = []
    p2 = []
    p3 = []
    p4 = []
    dfbatch1 = []
    dfbatch2 = []
    dfbatch3 = []
    dfbatch4 = []

    for degg, session, port in zip(deggsList, sessionList, portList):
        if port <= 5003:
            batch1.append(degg)
            sbatch1.append(session)
            p1.append([0, 0, 0])
            dfbatch1.append(DFHolder(port))
            continue
        elif port <= 5007:
            batch2.append(degg)
            sbatch2.append(session)
            p2.append([0, 0, 0])
            dfbatch2.append(DFHolder(port))
            continue
        elif port <= 5011:
            batch3.append(degg)
            sbatch3.append(session)
            p3.append([0, 0, 0])
            dfbatch3.append(DFHolder(port))
            continue
        else:
            batch4.append(degg)
            sbatch4.append(session)
            p4.append([0, 0, 0])
            dfbatch4.append(DFHolder(port))

    passInfoList = [p1, p2, p3, p4]
    batchList = [batch1, batch2, batch3, batch4]
    sessionList = [sbatch1, sbatch2, sbatch3, sbatch4]
    dfList = [dfbatch1, dfbatch2, dfbatch3, dfbatch4]
    return batchList, sessionList, passInfoList, dfList

def online_mon(run_file, comment, n_repeat, hv_status='moving'):
    ##hv_status is if the hv is constant, and in what part of FAT
    status_opts = ['moving', 'very_cold0', 'very_cold1', 'kinda_cold0',
                   'very_cold0_postIllumination', 'very_cold1_postIllumination',
                   'kinda_cold0_postIllumination']
    if hv_status not in status_opts:
        raise ValueError(f'hv_status argument must be one of {status_opts}!')
    print(f'Status is set to: {hv_status}')

    ##disable the function generator
    fg = FG3101()
    fg.disable()

    n_reads = 5 ##repeats per sensor to average over
    #n_repeat = 5 ##new set of re-samples
    n_repeat = int(n_repeat)
    if n_repeat <= 0:
        print('n_repeat must be 1 or greater!')
        exit(1)
    meas_name = 'OnlineMon'
    measure_type = 'online_monitoring'

    list_of_deggs = load_run_json(run_file)
    list_of_dicts = []
    for degg_file in list_of_deggs:
        list_of_dicts.append(load_degg_dict(degg_file))

    for degg_dict, degg_file in zip(list_of_dicts, list_of_deggs):
        key = create_key(degg_dict, meas_name)
        meta_dict = {}
        meta_dict['Folder'] = 'None'
        meta_dict['Comment'] = comment
        meta_dict['HVStatus'] = hv_status
        meta_dict = add_git_infos_to_dict(meta_dict)
        degg_dict[key] = meta_dict
        update_json(degg_file, degg_dict)

    sessionList = []
    passInfoList = []
    portList = []
    dac_channels = ['A', 'B']
    hvOn = 0
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        port = degg_dict['Port']
        session = startIcebootSession(host='localhost', port=port)
        for i, pmt in enumerate(['LowerPmt', 'UpperPmt']):
            hv1e7gain = degg_dict[pmt]['HV1e7Gain']
            hv_enabled = checkHV(session, i)
            hvOn += hv_enabled
            if hv_enabled == False:
                session.enableHV(i)
                session.setDEggHV(i, int(hv1e7gain))
                session.setDAC(dac_channels[i], 30000)

        sessionList.append(session)
        portList.append(port)
    if len(sessionList) == 0:
        raise ValueError('List of sessions is 0!')

    save_dir = create_save_dir(DATA_DIR, measure_type)

    if hvOn < (2 * len(list_of_deggs)):
        for i in tqdm(range(40), desc='HV Ramping'):
            time.sleep(1)
    else:
        for session in sessionList:
            print('-'*20)
            print(readout_sensor(session, 'voltage_channel0'))
            print(readout_sensor(session, 'voltage_channel1'))

    threads = []
    batchDeggs, batchSessions, batchInfoLists, batchdfLists = makeBatches(list_of_deggs,
                                                            sessionList,
                                                            portList)
    for batchDegg, batchSession, batchInfoList, batchdfList in zip(batchDeggs,
                                                      batchSessions,
                                                      batchInfoLists,
                                                      batchdfLists):
        for degg_file, session, passInfo, df in zip(batchDegg,
                                                batchSession,
                                                batchInfoList,
                                                batchdfList):
            #wrapper(degg_file, session, passInfo, n_repeat, n_reads, key, save_dir)
            threads.append(threading.Thread(target=wrapper, args=[degg_file,
                                                                  session,
                                                                  passInfo,
                                                                  n_repeat,
                                                                  n_reads,
                                                                  key,
                                                                  save_dir,
                                                                  df]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for batchdfList in batchdfLists:
        for dfHolder in batchdfList:
            if dfHolder.df is None: # skipped DEgg, we don't need to save this
                continue
            else:
                dfHolder.df.to_hdf(os.path.join(save_dir, f'mon_{dfHolder.port}.hdf5'),
                                key=f'df{port}', mode='w')

    ##check that all modules are there (if they're supposed to be)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        port = degg_dict['Port']
        if not audit_ignore_list(degg_file, degg_dict, key):
            if not os.path.exists(os.path.join(save_dir, f'mon_{port}.hdf5')):
                warn_str = f'After quick_monitoring, file for port {port} was not found! \n'
                warn_str = f'Check {save_dir} on scanbox.'
                send_warning(warn_str)

    n_passed_deggs     = 0
    n_passed_deggs_hv0 = 0
    n_passed_deggs_hv1 = 0
    for batchInfo in batchInfoLists:
        for passInfo in batchInfo:
            n_passed_deggs += passInfo[0]
            n_passed_deggs_hv0 += passInfo[1]
            n_passed_deggs_hv1 += passInfo[2]

    for session in sessionList:
        try:
            session.close()
        except Exception as e:
            send_warning(str(e))

    print(f'Saved file to: {save_dir}')
    print(f'{n_passed_deggs}/{len(list_of_deggs)} Passed I_MON Checks')
    print(f'{n_passed_deggs_hv0}/{len(list_of_deggs)} Passed HV0 Checks')
    print(f'{n_passed_deggs_hv1}/{len(list_of_deggs)} Passed HV1 Checks')
    print('Done')

@click.command()
@click.argument('run_file')
@click.argument('comment')
@click.argument('n_repeat')
@click.argument('hv_status')
def main(run_file, comment, n_repeat, hv_status):
    online_mon(run_file, comment, n_repeat, hv_status)

if __name__ == "__main__":
    main()
##end
