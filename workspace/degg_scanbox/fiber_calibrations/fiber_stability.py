import click
import os
import sys
import datetime
import time
import csv

from fiber_mes_kai import setup_oscilloscape, measure_waveform
from analysis.fiber.fiber_ana_hdf5 import *

from src.kikusui import *

def analysis_waveform(data_dir, data_file, graph_dir, strdate, time_stamp):

    bin = 50

    charge_list = get_charge(data_file)
    mean_charge, std_charge = hist_charge(graph_dir, bin, strdate, charge_list)

    list = [time_stamp, mean_charge, std_charge]
    with open(f'{data_dir}time_charge.csv', 'a') as f:
        writer = csv.writer(f)
        writer.writerow(list)


def measure(data_dir, graph_dir):

    with open(f'{data_dir}time_charge.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(["time", "charge", "error"])

    LD = PMX70_1A('10.25.123.249')
    LD.connect_instrument()

    voltage = 8
    LD.set_volt_current(voltage, 0.02)

    scope = setup_oscilloscape(1)
    nwfm = 5000

    start = time.time()
    counter = 1

    while True:
        print(f'Loop {counter}')
        dt_now = datetime.datetime.now()
        strdate = dt_now.strftime('%Y_%m_%d_%H_%M')
        now = time.time()
        time_stamp = now - start
        data_file = os.path.join(data_dir, f'fiber_{strdate}.hdf5')
        measure_waveform(data_file, scope, 1, num_reference_wfs=nwfm)
        analysis_waveform(data_dir, data_file, graph_dir, strdate, time_stamp)
        counter += 1


@click.command()
@click.argument('folder_name')
def main(folder_name):
    data_dir = f'/home/icecube/Workspace/degg_scan/fiber_calibrations/data/{folder_name}/'
    graph_dir = f'/home/icecube/Workspace/degg_scan/fiber_calibrations/graph/{folder_name}/'
    try:
        os.mkdir(data_dir)
        os.mkdir(graph_dir)
    except:
        ans = input('Overwrite???? (y/n):  ')
        if(ans=='y'):
            print('OK!!')
        else:
            sys.exit()

    measure(data_dir, graph_dir)

if __name__ == "__main__":
    main()
#end