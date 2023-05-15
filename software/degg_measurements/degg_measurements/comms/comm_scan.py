##scan adc thresholds and dac amplitudes in domnet
##to find configuration
import click
import numpy as np
import configparser
import os, sys
from tqdm import tqdm
import pandas as pd
import matplotlib.pyplot as plt

from degg_measurements.utils.setup_degg import DomnetRunner

def do_scan(in_file, dac_range, adc_range, usb_list, port_list):
    config = configparser.ConfigParser()
    config.read(in_file)
    print("Starting Scan")

    n_per_wp = 4

    df_len = len(dac_range) * len(adc_range) * len(usb_list) * 100
    dac_list = np.zeros(df_len)
    adc_list = np.zeros(df_len)
    device_list = np.zeros(df_len, dtype=str)
    port_list_out = np.zeros(df_len)
    return_list = np.zeros(df_len)
    
    index = 0
    for dac in tqdm(dac_range):
        for adc in tqdm(adc_range):
            config['fieldhub']['dac_amp'] = hex(dac)
            config['fieldhub']['adc_thresh'] = hex(adc)
            with open(in_file, 'w') as configfile:
                config.write(configfile)

            for usb_device, port in zip(usb_list, port_list):
                for rep in range(80):
                    with DomnetRunner(usb_device, port, n_per_wp, path_to_config=in_file) as runner:
                        if not runner.is_connected:
                            raise ValueError(f'Could not create DomnetRunner (port: {port})')
                        ret = runner.success
                
                    dac_list[index] = dac
                    adc_list[index] = adc
                    device_list[index] = usb_device
                    port_list_out[index] = port
                    return_list[index] = ret
                    index += 1

    d = {'DAC': dac_list,
         'ADC': adc_list,
         'Device': device_list,
         'Port': port_list_out,
         'Return': return_list}

    df = pd.DataFrame(data=d)

    return df

def do_ana(df_file):
    df = pd.read_hdf(df_file)

    vals = df['Return']
    vals0 = vals[::4]
    vals1 = vals[1::4]
    vals2 = vals[2::4]
    vals3 = vals[3::4]
    adc_pts = df['ADC']
    adc_pts = adc_pts[::4]
    dac_pts = df['DAC']
    dac_pts = dac_pts[::4]

    total_vals = vals0.values+vals1.values+vals2.values+vals3.values

    fig1, ax1 = plt.subplots()
    h = ax1.scatter(adc_pts, dac_pts, c=total_vals)
    ax1.set_xlabel('ADC Threshold')
    ax1.set_ylabel('DAC Offset')
    fig1.colorbar(h, label='Successful Wire Pairs')
    ax1.set_title('Comm. Scan')
    fig1.savefig('comm_scan.pdf')

@click.command()
@click.option('--scan', is_flag=True)
@click.option('--ana', is_flag=True)
@click.option('--in_file', '-f', required=True)
def main(scan, ana, in_file):
    if not os.path.exists(in_file):
        raise IOError(f'Could not find file {in_file}!')

    usb_list = ['/dev/ttyUSB2', '/dev/ttyUSB3', '/dev/ttyUSB4', '/dev/ttyUSB5']
    port_list = [5000, 5004, 5008, 5012]

    dac_max = 0x005a
    dac_min = 0x000a
    dac_step = 10
    #dac_step = 100
    dac_range = np.arange(dac_min, dac_max, dac_step)

    adc_max = 0x00fa
    adc_min = 0x0019
    adc_step = 25
    #adc_step = 100
    adc_range = np.arange(adc_min, adc_max, adc_step)
    
    print(len(dac_range))
    print(len(adc_range))

    if scan == True:
        df = do_scan(in_file, dac_range, adc_range, usb_list, port_list)
        print(df)
        df.to_hdf('scan_results.hdf5', 'mfh_scan')

    if ana == True:
        do_ana('scan_results.hdf5')

if __name__ == "__main__":
    main()

##end
