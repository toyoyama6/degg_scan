from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from iceboot import iceboot_session_cmd
from tqdm import tqdm
import time
from copy import deepcopy
from termcolor import colored
import click
import time, os
import numpy as np

from degg_measurements import DATA_DIR

from master_scope import initialize
from master_scope import add_dict_to_hdf5
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import create_key
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_git_infos_to_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils.flasherLED import enableLEDs, setContinuousFlashing, disableLEDs
from degg_measurements.utils.control_data_charge import write_flasher_chargestamp_to_hdf5
from degg_measurements.utils.hv_check import checkHV
from degg_measurements.utils.load_dict import audit_ignore_list

from degg_measurements.monitoring import readout_sensor

from multi_processing import run_jobs_with_mfhs

from chiba_slackbot import send_message

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise IOError('Cannot import function generator Agilent3101CFunctionGenerator - Exiting')# WARNING:

def measure(session, params):
    channel = 0 #params['channel']
    dac_value = params['dac_val']
    samples = params['samples']
    events = params['Constants']['Events']
    filename = params['filename']
    meas_key = params['measurement']
    pmt = params['pmt']
    period = params['period']
    deadtime = params['deadtime']
    led_mask = params['led_mask']
    led_flash_rate = params['led_flash_rate']
    wf_debug = params['wf_debug']
    wf_filename = params['wf_filename']
    bias_power = params['led_bias_power']
    serialnumber = params[pmt]['SerialNumber']
    port = params['Port']
    hv = params['HV']

    session.setDEggConstReadout(0,1,256)
    session.setDEggExtTrigSourceICM()
    session.startDEggExternalTrigStream(channel)

    if led_mask < 0:
        print("=== Null Measurement ===")
    if led_mask > 0:
        #print(f"=== Enabling LEDs {led_mask:#x} ===")
        session = enableLEDs(session, biasPower=bias_power)
        setContinuousFlashing(session, rate=led_flash_rate, led_mask=led_mask)

    n_retry = 0
    MAXNTRIAL = 10
    while(True):
        try:
            block = session.DEggReadChargeBlockFixed(135,160,14*events,timeout=10)
        except OSError:
            print(f'{serialnumber}({port}): Timeout! Ending the session at {n_retry+1}.')
            #send_message(f"### TIMEOUT in measure_flasher_caltrig_chargestamp.py in reading charge blocks for {pmt} {serialnumber}({port}) with HV {hv:.3f} V [Mask:{led_mask:#x}, Bias:{bias_power:#x}] at trial {n_retry+1}.###")
            session.endStream()
            disableLEDs(session)
            time.sleep(1)
            session = enableLEDs(session, biasPower=bias_power)
            setContinuousFlashing(session, rate=led_flash_rate, led_mask=led_mask)
            session.setDEggExtTrigSourceICM()
            session.startDEggExternalTrigStream(channel)
            n_retry += 1
            if n_retry == MAXNTRIAL:
                send_message(f"### {pmt} {serialnumber}({port}) with HV {hv:.3f} V chargestamp was failed. Skip.###")
                disableLEDs(session)
                session.endStream()
                session.close()
                return None
            else:
                continue
        break

    charges = [(rec.charge*1e12) for rec in block[channel] if not rec.flags]
    timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
    print(f'[{serialnumber}({port}): {hv:.3f} V] Observed mean charge LED [Mask:{led_mask:#x}, Bias:{bias_power:#x}]: {np.mean(np.array(charges)):.3f}pC')
    ledbias = bias_power
    ledmask = led_mask
    ledrate = led_flash_rate
    write_flasher_chargestamp_to_hdf5(filename=filename,
                                      chargestamps=charges,
                                      timestamps=timestamps,
                                      led_bias=ledbias,
                                      led_mask=ledmask,
                                      led_rate=ledrate)

    disableLEDs(session)
    try:
        session.endStream()
    except:
        print("Failed to exit cleanly...")
    else:
        pass

    return np.mean(np.array(charges))

def led_loop(degg_dict, degg_file, dirname,
             led_configs, led_frequency, bias_power_list,
             sleep_time, key):

    if audit_ignore_list(degg_file, degg_dict, key) == True:
        return

    pmt = 'LowerPmt'
    channel = 0
    wf_debug = True
    degg_dict['Constants']['Events'] = 500

    port = degg_dict['Port']
    dac_value = 2000
    hv = degg_dict[pmt]['HV1e7Gain']
    if hv<0:
        hv = 1500
        print('WARN - Running with default setting of {hv} V !')
        time.sleep(2)

    print(f"Start Iceboot Session for {port} - {pmt}")
    session = startIcebootSession(host='localhost', port=port)
    session = initialize(session, channel=channel,
                       high_voltage0=hv, n_samples=256,
                       dac_value=dac_value, burn_in=0,
                       modHV=False)

    hvOn = 0
    for _channel in [0, 1]:
        hv_enabled = checkHV(session, _channel, verbose=False)
        hvOn += hv_enabled
        if hv_enabled == False:
            session.enableHV(_channel)
            session.setDEggHV(_channel, hv)
    if hvOn != 0:
        print(f'Ramping HV for {port}')
        time.sleep(40)


    temperature = readout_sensor(session, 'temperature_sensor')

    meta_dict = dict()
    meta_dict = add_git_infos_to_dict(meta_dict)
    meta_dict['Folder'] = dirname
    meta_dict['Period'] = 10 #~10*17.0666 us
    meta_dict['Deadtime'] = 24 #~100 ns
    meta_dict['Threshold'] = "None"
    meta_dict['HV'] = hv
    meta_dict['DacValue'] = dac_value
    meta_dict['LEDFrequency'] = led_frequency
    meta_dict['Temperature'] = temperature
    degg_dict[pmt][key] = meta_dict
    charges = []
    name = degg_dict[pmt]['SerialNumber']
    for led_bias_power in bias_power_list:
        #meta_dict['LEDBiasPower'] = led_bias_power

        ##measurement is 1 LED by 1 LED
        for i, led_config in enumerate(led_configs):
            current_dict = deepcopy(degg_dict)
            current_dict['period'] = current_dict[pmt][key]['Period']
            current_dict['deadtime'] = current_dict[pmt][key]['Deadtime']
            current_dict['channel'] = channel
            current_dict['dac_val'] = current_dict[pmt][key]['DacValue']
            current_dict['pmt'] = pmt
            current_dict['samples'] = 640 #~1 us
            current_dict['measurement'] = key
            current_dict['wf_debug'] = wf_debug
            current_dict['threshold_over_baseline'] = 'None'
            current_dict['led_flash_rate'] = led_frequency
            current_dict['led_bias_power'] = led_bias_power
            current_dict['led_mask'] = led_config
            current_dict['filename'] = os.path.join(dirname, name + '.hdf5')
            current_dict['wf_filename'] = os.path.join(dirname, name + '_WFs.hdf5')
            current_dict['HV'] = degg_dict[pmt][key]['HV']

            ##do the measurement
            charge = measure(session, current_dict)

            charges.append(charge)
            time.sleep(1)

    meta_dict['led_bias_power'] = bias_power_list
    meta_dict['led_mask'] = led_configs
    degg_dict[pmt][key] = meta_dict
    update_json(degg_file, degg_dict)

    session.close()
    del session
    #print(f'Result for {name}({port}): {charges}')

def measure_baseline_flasher(run_json, comment, n_jobs=4):
    ##grab function generator - make sure laser is off
    try:
        fg = FG3101()
        fg.disable()
    except:
        print(colored("Unable to confirm laser status - Exiting", 'yellow'))
        exit(1)

    constants = {
        'DacValue': 2000,
        'Events': 500,
        'Samples': 256
    }

    measure_type = 'flasher_chargestamp'
    dirname = create_save_dir(DATA_DIR, measure_type)

    sleep_time = 1 #3 * 60

    ##LED configurations
    ##scanning sequentially from 0-->11
    ##between each LED is a null measurement
    led_configs = [0x0001,
                   0x0002,
                   0x0004,
                   0x0008,
                   0x0010,
                   0x0020,
                   0x0040,
                   0x0080,
                   0x0100,
                   0x0200,
                   0x0400,
                   0x0800]



    ##multi-wire pair parallelisation
    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    bias_power_list = [int('5000',16)+1024*i for i in range(10)]
    print(f'Range of bias voltages: {bias_power_list}')

    led_frequency = 10 # 1/(led_frequency*17.0666) MHz

    ##not using standard function as only results for bottom PMT!!
    meas_key = 'FlasherCheck'
    channel = 0
    pmt ='LowerPmt'
    keys = []
    for _degg_dict in sorted_degg_dicts:
        key = create_key(_degg_dict[pmt], meas_key)
        meta_dict = dict()
        meta_dict['Folder'] = 'None'
        _degg_dict[pmt][key] = meta_dict
        keys.append(key)

    aggregated_results = run_jobs_with_mfhs(
            led_loop,
            n_jobs,
            force_static=['led_configs','bias_power_list'],
            degg_dict=sorted_degg_dicts,
            degg_file=sorted_degg_files,
            dirname=dirname,
            led_configs=led_configs,
            led_frequency=led_frequency,
            bias_power_list=bias_power_list,
            sleep_time=sleep_time,
            key=keys)

    print('Flasher test done.')

@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=2)
@click.option('--force', is_flag=True)
def main(run_json, comment, n_jobs, force):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')
    measure_baseline_flasher(run_json, comment, n_jobs)


if __name__ == "__main__":
    main()

##end
