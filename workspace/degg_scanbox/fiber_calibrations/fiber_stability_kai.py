import click
import os
import sys
import time
import pandas as pd


from fiber_mes_kai import setup_oscilloscape, convert_wf
from analysis.fiber.fiber_ana_hdf5 import *

from src.kikusui import *


def measure_waveform(scope, reference_pmt_channel=1):
    raw_wf = scope.acquire_waveform(reference_pmt_channel)
    times, wfm = convert_wf(raw_wf)

    start_point = int(len(times)/2)
    end_point = int(start_point + len(times)//6)

    base = np.mean(wfm[0:200])
    times = times[start_point:end_point]
    wfm = -wfm[start_point:end_point]+base
    charge = find_charge(times, wfm)
    
    return charge
    



def measure(data_dir):


    column = pd.DataFrame(columns=['time', 'charge'])
    column.to_csv(f'{data_dir}time_charge.csv', mode='w')

    LD = PMX70_1A('10.25.123.249')
    LD.connect_instrument()

    voltage = 8
    LD.set_volt_current(voltage, 0.02)

    scope = setup_oscilloscape(1)

    start = time.time()
    counter = 0

    while True:
        print(f'Loop {counter}')
        now = time.time()
        time_stamp = now - start
        charge = measure_waveform(scope, 1)
        df = pd.DataFrame([[time_stamp, charge]])
        df.to_csv(f'{data_dir}time_charge.csv', mode='a', header=False)
        counter += 1
        time.sleep(5)


@click.command()
@click.argument('folder_name')
def main(folder_name):
    data_dir = f'/home/icecube/Workspace/degg_scan/fiber_calibrations/data/{folder_name}/'
    try:
        os.mkdir(data_dir)
    except:
        ans = input('Overwrite???? (y/n):  ')
        if(ans=='y'):
            print('OK!!')
        else:
            sys.exit()

    measure(data_dir)

if __name__ == "__main__":
    main()
#end
