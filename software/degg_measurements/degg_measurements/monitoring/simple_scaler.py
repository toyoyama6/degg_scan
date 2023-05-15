import os, sys
from tqdm import tqdm
import time
import click
import pandas as pd
import numpy as np
import threading

from degg_measurements.utils.stack_fmt import stripStackSize

from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.monitoring import readout_sensor
from degg_measurements.daq_scripts.master_scope import initialize
from degg_measurements.daq_scripts.master_scope import take_waveform
import traceback
from chiba_slackbot import send_message, send_warning

class Info():
    def __init__(self, session, port, channel):
        self.session = session
        self.channel = channel
        self.port = port
        self.baseline = -1

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

class deggInfo():
    def __init__(self, port):
        self.scaler0 = []
        self.scaler1 = []
        self.darkrate0 = []
        self.darkrate1 = []
        self.port = port


def remeasure_baseline(info, n_wfs=50):
    session = info.session
    channel = info.channel
    session = initialize(session, channel=channel, n_samples=1024,
                         high_voltage0=0, dac_value=30000, modHV=False)
    wf_aves = []
    for j in range(n_wfs):
        session, x, wf, t, pc_t, wf_channel = take_waveform(session)
        if session is None:
            break
        if wf is None:
            print("WF is none!")
            continue
        if len(wf) != 1024:
            print(f"BUFF ERR?? - len(wf) {len(wf)} != samples 1024")
            continue
        wf_ave = np.mean(wf)
        wf_aves.append(wf_ave)
    updated_baseline = np.median(wf_aves)
    session.endStream()
    info.baseline = updated_baseline

@click.command()
@click.argument('run_json')
@click.option('--enablehv', is_flag=True)
def main(run_json, enablehv):

    period = 10000 #us
    deadtime = 24 #bins
    dac_channels = ['A', 'B']

    sessionList = []
    infoList = []
    cInfoList = []
    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        port = degg_dict['Port']
        session = startIcebootSession(host='localhost', port=port)
        sessionList.append(session)
        hvs = [degg_dict['LowerPmt']['HV1e7Gain'], degg_dict['UpperPmt']['HV1e7Gain']]
        info = deggInfo(port)
        infoList.append(info)
        for channel in [0, 1]:
            if enablehv == True:
                session.enableHV(channel)
                session.setDEggHV(channel, int(hvs[channel]))
            cInfo = Info(session, port, channel)
            cInfoList.append(cInfo)

    if enablehv == True:
        for i in tqdm(range(40), desc='HV Ramp'):
            time.sleep(1)

    for session in sessionList:
        print(f'HV0: {readout_sensor(session, "voltage_channel0")}')
        print(f'HV1: {readout_sensor(session, "voltage_channel1")}')

    ##measure ch0 then ch1
    threads = []
    for i, session in enumerate(sessionList):
        channel = 0
        info = cInfoList[channel+(2*i)]
        threads.append(threading.Thread(target=remeasure_baseline, args=[info]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(1)

    threads = []
    for i, session in enumerate(sessionList):
        channel = 1
        info = cInfoList[channel+(2*i)]
        threads.append(threading.Thread(target=remeasure_baseline, args=[info]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, session in enumerate(sessionList):
        for channel in [0, 1]:
            info = cInfoList[channel+(2*i)]
            threshold = info.baseline + 15
            print(int(threshold))
            #session.setDAC(dac_channels[channel], 30000)
            session.setDEggTriggerConditions(channel, int(threshold))
            session.enableDEggADCTrigger(channel)
            session.enableScalers(channel, period, deadtime)

    time.sleep(0.1)

    n_reps = 100
    duration = period / 1e6
    FPGA_CLOCK_TO_S = 1. / 240e6
    _deadtime = deadtime * FPGA_CLOCK_TO_S
    for i, rep in enumerate(range(n_reps)):
        for j, session in enumerate(sessionList):
            info = infoList[j]
            info.scaler0.append(session.getScalerCount(0))
            info.scaler1.append(session.getScalerCount(1))
            mtime0 = duration - (info.scaler0[-1] * _deadtime)
            darkrate0 = info.scaler0[-1] / mtime0
            mtime1 = duration - (info.scaler1[-1] * _deadtime)
            darkrate1 = info.scaler1[-1] / mtime1
            info.darkrate0.append(darkrate0)
            info.darkrate1.append(darkrate1)
        time.sleep(period / 1e6)

    for session in sessionList:
        session.close()

    dfList = []
    for info in infoList:
        d = {'Port': [info.port]*len(info.scaler0),
             'Scaler0': info.scaler0, 'DarkRate0': info.darkrate0,
             'Scaler1': info.scaler1, 'DarkRate1': info.darkrate1}
        df = pd.DataFrame(data=d)
        dfList.append(df)
        print(f'Median Dark Rates for Port {df.Port.values[0]}')
        print(f'Ch0: {np.median(df.DarkRate0.values)}')
        print(f'Ch1: {np.median(df.DarkRate1.values)}')

    dfTotal = pd.concat(dfList)
    dfTotal.to_hdf('scaler_data.hdf5', 'df', 'w')

if __name__ == "__main__":
    main()
##end
