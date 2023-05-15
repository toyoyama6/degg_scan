import os, sys
import click
import json
import requests
import numpy as np
import time
import tables
from tqdm import tqdm
from termcolor import colored
from glob import glob
from copy import deepcopy
from datetime import datetime
from chiba_slackbot import send_message
from chiba_slackbot import send_warning

from iceboot import iceboot_session_cmd

from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import flatten_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import log_crash
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_git_infos_to_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils import DEVICES
from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.utils import add_default_meas_dict
from degg_measurements.utils.load_dict import check_dirname_in_pmt_dict
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.flash_fpga import loadFPGA
from degg_measurements.utils.control_data_charge import write_chargestamp_to_hdf5

from degg_measurements.daq_scripts.master_scope import initialize
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.daq_scripts.master_scope import add_dict_to_hdf5
from degg_measurements.daq_scripts.master_scope import setup_fir_trigger
from degg_measurements.daq_scripts.master_scope import sensibly_read_degg_charge_block
from degg_measurements.daq_scripts.measure_pmt_baseline import measure_baseline
from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs

from degg_measurements.monitoring import readout_sensor
from degg_measurements.monitoring import readout_temperature

#from degg_measurements.analysis.baseline.calc_pmt_baseline import calc_baseline
from degg_measurements.analysis import calc_baseline

from degg_measurements import DATA_DIR

KEY_NAME = 'DeltaTMeasurement'

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:


def min_delta_t(session,
                channel,
                hv0,
                hv1,
                filename,
                threshold,
                threshold_over_baseline,
                dac_value,
                burn_in,
                nevents,
                use_fir,
                port):
    params = {}
    params['filename'] = filename
    null_threshold = 15000
    modHV = False

    if use_fir == False:
        threshold = int(threshold)
        if threshold < 6000 or threshold > 10000:
            raise ValueError(f'threshold (total) should be around ~8000 ADC')

        if channel == 0:
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                              high_voltage0=hv0, high_voltage1=0,
                              threshold0=threshold, threshold1=null_threshold,
                              burn_in=burn_in, modHV=modHV)
        if channel == 1:
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                              high_voltage0=0, high_voltage1=hv1,
                              threshold0=null_threshold, threshold1=threshold,
                              burn_in=burn_in, modHV=modHV)
    if use_fir == True:
        dac_channels = ['A', 'B']
        fir_coeffs=[0]*10+[1,1]+[0]*4
        threshold = int(threshold_over_baseline * np.sum(fir_coeffs)) * len(fir_coeffs)

        '''
        print(f'Rebooting board {port}')
        session.reboot()
        time.sleep(3)
        session.comms.bypassBootloader()
        time.sleep(0.5)
        print(f'Flashing FPGA {port}')
        flashLS = session.flashLS()
        firmwarefilename = flashLS[len(flashLS)-1]['Name']
        session.flashConfigureCycloneFPGA(firmwarefilename)
        time.sleep(1)
        print(f'Setup Done {port}')
        send_message(f'Finished rebooting {port}:{channel}')

        ##just set to the same HV so I don't have to pass individual values
        session.enableHV(0)
        session.enableHV(1)
        session.setDEggHV(0, hv0)
        session.setDEggHV(1, hv1)
        for _i in tqdm(range(40), desc=f'HV Ramping {port}:{channel}'):
            time.sleep(1)
        '''

        session.setDAC(dac_channels[0], dac_value)
        session.setDAC(dac_channels[1], dac_value)

        for ch in [0, 1]:
            session.disableDEggTriggers(ch)
        idx0 = channel
        idx1 = (channel + 1) % 2
        tList = [threshold, null_threshold]
        session.startDEggDualChannelFIRTrigStream(tList[idx0], tList[idx1])
        session.setDEggConstReadout(0, 1, 128)
        session.setDEggConstReadout(1, 1, 128)
        session.setFIRCoefficients(0, fir_coeffs)
        session.setFIRCoefficients(1, fir_coeffs)
        session.setDEggFIRTriggerThreshold(0, tList[idx0])
        session.setDEggFIRTriggerThreshold(1, tList[idx1])
        session.enableDEggFIRTrigger(channel)
        #for ch in [0, 1]:
        #    session.setDAC(dac_channels[ch], dac_value)
        #    session.setDEggConstReadout(ch, 1, 128)
        #    session.setFIRCoefficients(ch, fir_coeffs)
        #if channel == 0:
        #    session.startDEggDualChannelFIRTrigStream(threshold, null_threshold)
        #    session.setDEggFIRTriggerThreshold(0, threshold)
        #    session.setDEggFIRTriggerThreshold(1, null_threshold)
        #if channel == 1:
        #    session.startDEggDualChannelFIRTrigStream(null_threshold, threshold)
        #    session.setDEggFIRTriggerThreshold(0, null_threshold)
        #    session.setDEggFIRTriggerThreshold(1, threshold)
        #for ch in [0, 1]:
        #    session.enableDEggFIRTrigger(ch)

    for t in tqdm(range(burn_in), desc='Burning in'):
        time.sleep(1)

    charges, timestamps = sensibly_read_degg_charge_block(session,
                                                          channel,
                                                          nevents)

    write_chargestamp_to_hdf5(filename, charges, timestamps)
    temp = np.nan
    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
    if session is None:
        send_message(f"None session object in min_delta_t for Port {port}")
        print(colored(f"None session object for Port: {port}!"), 'yellow')

    params['degg_temp'] = temp
    add_dict_to_hdf5(params, params['filename'])
    session.endStream()
    return session


def measure(session, params):
    host = 'localhost'
    port = params['Port']
    channel = params['channel']
    threshold_over_bl = params['threshold_over_baseline']
    if threshold_over_bl > 20 or threshold_over_bl < 0:
        raise ValueError(f'threshold over the baseline should be about 13 ADC')

    nevents = params['Constants']['Events']
    dac_value = params['Constants']['DacValue']
    filename = params['filename']
    pmt = params['pmt']
    hv = params['hv']
    pmt_id = params[pmt]['SerialNumber']
    use_fir = params['use_fir']
    dac_channels = ['A', 'B']

    print(f'Start Measurement for {port}, on channel {channel}')

    burn_in = 0 #s
    modHV = False
    null_threshold = 15000

    if use_fir == False:
        threshold = int(params['threshold'])
        if threshold < 6000 or threshold > 10000:
            raise ValueError(f'threshold (total) should be around ~8000 ADC')

        if channel == 0:
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                              high_voltage0=hv, high_voltage1=0,
                              threshold0=threshold, threshold1=null_threshold,
                              burn_in=burn_in, modHV=modHV)
        if channel == 1:
            session = initialize_dual(session, n_samples=128, dac_value=dac_value,
                              high_voltage0=0, high_voltage1=hv,
                              threshold0=null_threshold, threshold1=threshold,
                              burn_in=burn_in, modHV=modHV)
    if use_fir == True:
        fir_coeffs=[0]*10+[1,1]+[0]*4
        threshold = int(threshold_over_bl * np.sum(fir_coeffs)) * len(fir_coeffs)
        for ch in [0, 1]:
            session.setFIRCoefficients(ch, fir_coeffs)
            session.setDAC(dac_channels[ch], dac_value)
        if channel == 0:
            session.setDEggFIRTriggerThreshold(0, threshold)
            session.setDEggFIRTriggerThreshold(1, null_threshold)
        if channel == 1:
            session.setDEggFIRTriggerThreshold(0, null_threshold)
            session.setDEggFIRTriggerThreshold(1, threshold)
        for ch in [0, 1]:
            session.setDEggConstReadout(ch, 1, 128)
            session.enableDEggFIRTrigger(ch)
        if channel == 0:
            session.startDEggDualChannelFIRTrigStream(threshold, null_threshold)
        if channel == 1:
            session.startDEggDualChannelFIRTrigStream(null_threshold, threshold)

    n_pts = 5
    hv_mon_pre = np.full(n_pts, np.nan)
    if session is not None:
        if pmt == 'LowerPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel0')
        if pmt == 'UpperPmt':
            for pt in range(n_pts):
                hv_mon_pre[pt] = readout_sensor(session, 'voltage_channel1')

    print(f'{port}:{channel} HV (pre) {hv_mon_pre} V')

    ref_time = time.monotonic()
    prev_pc_time = ref_time

    n_retry = 0
    NTRIAL = 3
    while(True):
        setup_time = datetime.now()
        try:
            charges, timestamps = sensibly_read_degg_charge_block(session,
                                                                  channel,
                                                                  nevents)
            write_chargestamp_to_hdf5(filename, charges, timestamps)

        except IOError:
            except_time = datetime.now()
            send_warning(f"TIMEOUT: measure_dt.py read_charge_block: {port} {pmt_id}," \
                         f"{hv} V, retry {n_retry+1}")
            temp = np.nan
            if session is not None:
                temp = readout_sensor(session, 'temperature_sensor')

            readout_hv = readout_sensor(session, f'voltage_channel{channel}')

            log_crash(
                "{}_delta_t_crash.csv".format(pmt),
                setup_time,
                except_time,
                port,
                channel,
                temp, #temp
                readout_hv, #hv_readback
                hv,
                0.0, #darkrate
                threshold,
                0.0, ## spe peak height
                use_fir)

            n_retry += 1
            if n_retry == 3:
                print(f'Timeout! {port}')
                send_warning(f"PMT {pmt_id} charge SPE meas failed. Skip. ###")
                break
            continue
        break


    temp = np.nan
    hv_mon = np.full(n_pts, np.nan)

    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
        if pmt == 'LowerPmt':
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel0')
        if pmt == 'UpperPmt':
            for pt in range(n_pts):
                hv_mon[pt] = readout_sensor(session, 'voltage_channel1')
    if session is None:
        print(colored(f"None session object for Port: {port}!"), 'yellow')

    params['degg_temp'] = temp
    params['hv_mon_pre'] = str(hv_mon_pre)
    params['hv_mon'] = str(hv_mon)
    add_dict_to_hdf5(params, params['filename'])
    time.sleep(1)


def measure_degg(session,
                 degg_file,
                 degg_dict,
                 dirname,
                 constants,
                 keys,
                 use_fir):

    if audit_ignore_list(degg_file, degg_dict, keys[0]) == True:
        return

    adc_to_volts = CALIBRATION_FACTORS.adc_to_volts
    degg_dict['Constants'] = constants

    # Do some setup and json file bookkeeping
    pe_threshold = 0.25
    temperature_ch1 = readout_temperature(device=DEVICES.thermometer, channel=1)
    temperature_ch2 = readout_temperature(device=DEVICES.thermometer, channel=2)
    for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
        spe_peak_height = degg_dict[pmt]['SPEPeakHeight']
        degg_name = degg_dict["DEggSerialNumber"]
        port = degg_dict["Port"]
        ##peak height should usually be around 3 mV --> 40 ADC
        ##if this is wrong, raise an error
        if spe_peak_height > 0.01 or spe_peak_height < 0.001:
            msg_str = 'There was an error during the peak height calculation!'
            msg_str = msg_str + f'{port}:{channel} ({degg_name}), with {spe_peak_height} V!'
            msg_str = msg_str + ' The script will now exit!'
            send_warning(msg_str)
            raise ValueError(f'Issue with SPE Peak Height, cannot accuartely determine \
                             threshold! {spe_peak_height}')
        threshold_over_baseline = np.ceil(spe_peak_height * pe_threshold / adc_to_volts)
        name = degg_dict[pmt]['SerialNumber']

        # dirname_exists = check_dirname_in_pmt_dict(dirname,
        #                                            degg_dict[pmt],
        #                                            KEY_NAME)
        # if dirname_exists:
        #     continue

        meta_dict = degg_dict[pmt][keys[channel]]
        # Before measuring check the D-Egg surface temp
        meta_dict['DEggSurfaceTemp'] = temperature_ch1
        meta_dict['BoxSurfaceTemp']  = temperature_ch2
        meta_dict['Folder'] = dirname
        meta_dict['use_fir'] = use_fir

        baseline_filename = degg_dict[pmt]['BaselineFilename']
        meta_dict['BaselineFilename'] = baseline_filename
        meta_dict['Baseline'] = float(calc_baseline(baseline_filename)['baseline'].values[0])

        current_dict = deepcopy(degg_dict)
        current_dict['Constants'] = constants
        current_dict['channel'] = channel
        current_dict['pmt'] = pmt
        current_dict['measurement'] = keys[channel]
        current_dict['threshold'] = int(meta_dict['Baseline'] + threshold_over_baseline)
        current_dict['threshold_over_baseline'] = threshold_over_baseline
        current_dict['hv'] = int(degg_dict[pmt]['HV1e7Gain'])
        current_dict['use_fir'] = use_fir

        filename = os.path.join(dirname, name + '.hdf5')
        valid_file_found = False
        counter = 0
        while not valid_file_found:
            if not os.path.isfile(filename):
                break
            else:
                if counter == 0:
                    counter += 1
                    filename = filename.replace('.hdf5',
                                                 f'_{counter:02d}.hdf5')
                else:
                    counter += 1
                    filename = filename.replace('_{counter-1:02d}.hdf5',
                                                f'_{counter:02d}.hdf5')

        current_dict['filename'] = filename
        measure(session, current_dict)

    session.endStream()
    session.close()

    update_json(degg_file, degg_dict)


def measure_spe(run_json, comment, n_jobs, n_events=10000, use_fir=False):
    print(f'n_jobs: {n_jobs}')
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    constants = {
        'Events': int(n_events),
        'DacValue': 30000
    }
    measurement_type = 'dt_measurement'
    dirname = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    session_list = measure_baseline(run_json, high_voltage=None,
                     constants=constants,
                     modHV=False,
                     return_sessions=True)

    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts, sorted_index = \
        sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int,
        return_sorting_index=True)

    keys = add_default_meas_dict(
        sorted_degg_dicts,
        sorted_degg_files,
        KEY_NAME,
        comment
    )

    sorted_session_list = np.array(session_list)[sorted_index]

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        session=sorted_session_list,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        constants=constants,
        keys=keys,
        use_fir=use_fir)

    for result in aggregated_results:
        print(result.result())


@click.command()
@click.argument('json_run_file')
@click.argument('comment')
@click.option('-j', '--n_jobs', default=1)
@click.option('--force', is_flag=True)
@click.option('--n_events', default=10000)
@click.option('--use_fir', is_flag=True)
def main(json_run_file, comment, n_jobs, force, n_events, use_fir):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')

    measure_spe(json_run_file, comment, n_jobs, n_events, use_fir)


if __name__ == "__main__":
    main()

##end
