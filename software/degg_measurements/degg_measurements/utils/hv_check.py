import os, sys
import numpy as np
import click
import time
import pandas as pd
from tqdm import tqdm

from degg_measurements.monitoring import readout_sensor
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils import update_json
from degg_measurements.utils import create_save_dir

from degg_measurements import DATA_DIR

##utility function to check if HV is already enabled or not

def checkHV(session, channel, verbose=False):
    if channel not in [0, 1]:
        raise ValueError(f'Channel must be 0 or 1, NOT {channel} !')
    if session == None:
        raise ValueError('session object is none!')

    hv = 0
    for i in range(5):
        val = readout_sensor(session, f'voltage_channel{channel}')
        if verbose == True:
            print(f'CH:{channel}, {val}V')
        hv += val
    hv_ave = hv / 5
    if verbose == True:
        print('-'*20)

    if hv_ave > 1000:
        return True
    else:
        return False

class DEggCal():
    def __init__(self, name, port, session, hv1e7Gain0, hv1e7Gain1):
        self.name = name
        self.port = port
        self.session = session
        self.hv1e7Gain0 = hv1e7Gain0
        self.hv1e7Gain1 = hv1e7Gain1
        self.hvSet0 = []
        self.hvSet1 = []
        self.hvRead0 = []
        self.hvRead1 = []
        self.current0 = []
        self.current1 = []
        self.temperature = []

    def recordHV(self, hvSet):

        self.hvSet0.append(hvSet[0])
        self.hvSet1.append(hvSet[1])
        hv0 = readout_sensor(self.session, 'voltage_channel0')
        hv1 = readout_sensor(self.session, 'voltage_channel1')
        current0 = readout_sensor(self.session, 'current_channel0')
        current1 = readout_sensor(self.session, 'current_channel1')
        temperature = readout_sensor(self.session, 'temperature_sensor')
        self.hvRead0.append(hv0)
        self.hvRead1.append(hv1)
        self.current0.append(current0)
        self.current1.append(current1)
        self.temperature.append(temperature)

    def saveInfo(self, filename):
        nameL = [self.name] * len(self.hvSet0)
        portL = [self.port] * len(self.hvSet0)
        hv1e7Gain0L = [self.hv1e7Gain0] * len(self.hvSet0)
        hv1e7Gain1L = [self.hv1e7Gain1] * len(self.hvSet1)
        data = {'DEgg': nameL, 'Port':portL,
                'HV1e7Gain0': hv1e7Gain0L, 'HV1e7Gain1': hv1e7Gain1L,
                'HVSet0': self.hvSet0, 'HVSet1': self.hvSet1,
                'HVRead0': self.hvRead0, 'HVRead1': self.hvRead1,
                'Current0': self.current0, 'Current1': self.current1,
                'Temperature': self.temperature}

        df = pd.DataFrame(data=data)
        df.to_hdf(filename, key='df', mode='w')

##check how different the HVs are
##from the set point at a given HV1e7Gain
##and a particular temperature
def measure_hv(run_json):
    deggCalList = []

    ##should be an int
    nPoints = 120

    list_of_deggs = load_run_json(run_json)
    list_of_dicts = []
    for degg_file in list_of_deggs:
        list_of_dicts.append(load_degg_dict(degg_file))

    # filepath for saving data
    measurement_type = "hv_mon"
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)
    meas_key = 'HVMonitoring'
    comment = f'monitoring hv, N=+/-{nPoints}V'

    keysList = add_default_meas_dict(
        list_of_dicts,
        list_of_deggs,
        meas_key,
        comment
    )

    for degg_dict, keys in zip(list_of_dicts, keysList):
        name = degg_dict['DEggSerialNumber']
        port = degg_dict['Port']
        hvSet = [0, 0]
        scanRange = [[], []]
        for i, pmt in enumerate(['LowerPmt', 'UpperPmt']):
            hv_set = int(degg_dict[pmt]['HV1e7Gain'])
            hvSet[i] = hv_set
            scanRange[i] = np.arange(hv_set - nPoints, hv_set + nPoints)

        session = startIcebootSession(host='localhost', port=port)
        session.enableHV(0)
        session.enableHV(1)
        deggCal = DEggCal(name, port, session, hvSet[0], hvSet[1])
        deggCal.scanRange = scanRange
        deggCal.keys = keys
        deggCal.dirname = dirname
        deggCalList.append(deggCal)

        deggCal.session.setDEggHV(0, scanRange[0][0])
        deggCal.session.setDEggHV(1, scanRange[1][0])

    time.sleep(40)

    for i in tqdm(range(int(nPoints*2)), desc='Sample Point'):
        for deggCal in deggCalList:
            session = deggCal.session
            hv0 = deggCal.scanRange[0][i]
            hv1 = deggCal.scanRange[1][i]
            hvSet = [hv0, hv1]
            for channel in [0, 1]:
                session.setDEggHV(channel, hvSet[channel])
        time.sleep(1)
        for num in range(20):
            for deggCal in deggCalList:
                fname = f'hv_set_test_{deggCal.port}_{deggCal.name}.hdf5'
                deggCal.recordHV([hv0, hv1])
                deggCal.saveInfo(os.path.join(dirname, fname))
            time.sleep(0.3)

    ##update the jsons
    for degg_dict, keys, degg_file in zip(list_of_dicts, keysList, list_of_deggs):
        degg_dict['LowerPmt'][keys[0]]['Folder'] = dirname
        degg_dict['UpperPmt'][keys[1]]['Folder'] = dirname
        update_json(degg_file, degg_dict)

    ##close the sessions
    for deggCal in deggCalList:
        deggCal.session.close()

    print('Done')

@click.command()
@click.option('--run_file', '-r', default=None)
@click.option('--measure', is_flag=True)
def main(run_file, measure):
    if measure == True:
        if run_file == None:
            print('For measure mode, please provide the run file')
        measure_hv(run_file)
        print('Done measuring')
        return

    print('Monitoring the HV')
    verbose = True
    portList = np.arange(16)
    hvOn = 0
    nChecked = 0
    for port in portList:
        port = 5000 + port
        try:
            session = startIcebootSession(host='localhost', port=port)
            for channel in [0, 1]:
                hv_enabled = checkHV(session, channel, verbose)
                hvOn += hv_enabled
                nChecked += 1
            session.close()
            del session
        except:
            print(f'session on port {port} could not be started - skipping')
            continue

    print(f'HV is ON for: {hvOn} / {nChecked} moduels')
    if hvOn == 0 and nChecked > 0:
        print('HV is off for all checked modules.')

if __name__ == "__main__":
    main()

##end
