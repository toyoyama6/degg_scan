import skippylab as sl
from termcolor import colored
import os
from src.kikusui import *
import numpy as np
import tables
import click

def setup_oscilloscape(reference_pmt_channel):
    print(colored("Setting up reference pmt readout (scope)...", 'green'))
    scope_ip = "10.25.121.219"
    scope = sl.instruments.RohdeSchwarzRTM3004(ip=scope_ip)
    scope.ping()
    return scope

def measure_waveform(filename, scope, reference_pmt_channel=1, num_reference_wfs=1000):
    print(colored(f"Reference Measurement - {num_reference_wfs} WFs", 'green'))
    for i in range(num_reference_wfs):
        raw_wf = scope.acquire_waveform(reference_pmt_channel)
        times, wf = convert_wf(raw_wf)
        write_to_hdf5(filename, i, times, wf, 0, 0)

def convert_wf(raw_wf):
    times, volts = raw_wf
    #times_and_volts = np.array(raw_wf.split(','), dtype=float)
    #times = times_and_volts[::2]
    #volts = times_and_volts[1::2]
    return times, volts

def write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            time = tables.Float32Col(
                shape=np.asarray(xdata).shape)
            waveform = tables.Float32Col(
                shape=np.asarray(wf).shape)
            timestamp = tables.Int64Col()
            pc_time = tables.Float32Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/', 'data', Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        try:
            table = open_file.get_node('/data')
        except:
            with tables.open_file(filename, 'w') as open_file:
                table = open_file.create_table('/', 'data', Event)
            table = open_file.get_node('/data')

        event = table.row

        event['event_id'] = i
        event['time'] = np.asarray(xdata, dtype=np.float32)
        event['waveform'] = np.asarray(wf, dtype=np.float32)
        event['timestamp'] = timestamp
        event['pc_time'] = pc_time
        event.append()
        table.flush()


def fiber_mes(data_dir):

    LD = PMX70_1A('10.25.123.249')
    LD.connect_instrument()

    

    voltage_points = np.arange(3.2, 10.4, 0.4)

    scope = setup_oscilloscape(1)

    nwfm = 3000

    for i in voltage_points:

        print(f'Measuring {i}V')

        voltage_point = i

        LD.set_volt_current(i, 0.02)

        data_file = os.path.join(data_dir, f'fiber_{voltage_point}.hdf5')
        measure_waveform(data_file, scope, 1, num_reference_wfs=nwfm)

@click.command()
@click.argument('dir_name')
def main(dir_name):
    data_dir = f'/home/icecube/Workspace/degg_scan/fiber_calibrations/data/fiber_calibration/{dir_name}/'
    os.mkdir(data_dir)
    fiber_mes(data_dir)

if __name__ == "__main__":
    main()
##end
