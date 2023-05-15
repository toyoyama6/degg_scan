from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

from termcolor import colored
from tqdm import tqdm
import time
import os
import pandas as pd

####
from read_waveform import init as reference_init
from read_waveform import set_DAQ
from infoContainer import infoContainer
from deggContainer import *
from measure_scan_origin import *
####

#########
import skippylab as sl
from degg_measurements.daq_scripts.master_scope import write_to_hdf5

#########

def measure_degg_charge_stamp(degg, nevents=100, event_num=0, r_point=0, t_point=0, data_dir=''):
    infoval = []
    num_retry = 0
    retry = True
    while retry == True:
        try:
            block = degg.session.DEggReadChargeBlock(10, 15, 14*nevents, timeout=200)
            channels = list(block.keys())
            for channel in channels:
                charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
                timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
                for ts, q in zip(timestamps, charges):
                    info = infoContainer(ts, q, channel, event_num, r_point, t_point)
                    try:
                        infoval.append([ts, q, channel, event_num, r_point, t_point])
                    except:
                        continue
                    degg.addInfo(info, channel)
            try:
                dfs = pd.read_hdf(f'{data_dir}/charge_stamp.hdf5')
                df = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                df_total = pd.concat([dfs, df])
            except:
                df_total = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
            df_total.to_hdf(f'{data_dir}/charge_stamp.hdf5', key='df')
            retry = False

        except:
            print(f'no measure {r_point}: {t_point} - retry {num_retry}')
            retry = True
            num_retry += 1

            if num_retry > 5:
                info = infoContainer(-1, -1, -1, -1, r_point, t_point)
                infoval.append([-1, -1, -1, -1, r_point, t_point])
                degg.addInfo(info, -1)
                try:
                    dfs = pd.read_hdf(f'{data_dir}/charge_stamp.hdf5')
                    df = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                    df_total = pd.concat([dfs, df])
                except:
                    df_total = pd.DataFrame(data=infoval, columns=["timestamp", "charge", "channel", "event_num", "r_point", "t_point"])
                df_total.to_hdf(f'{data_dir}/charge_stamp.hdf5', key='df')
                retry = False

def measure_r_steps(data_dir, degg, nevents, r_stage, slave_address, t_point, r_step, r_scan_points,
                    mtype='stamp', forward_backward='forward', measure_side='bottom'):
    print(f'Measuring: {forward_backward}\n{r_scan_points}')
    for event_num, r_point in enumerate(r_scan_points):
        print(r_point)
        ##take DEgg data
        if mtype == 'stamp':
            measure_degg_charge_stamp(degg, nevents, event_num, r_point, t_point, data_dir)
        elif mtype == 'waveform':
            raise NotImplementedError('Not ready yet!')
            #measure_degg_waveform()
        else:
            raise ValueError(f'option for measurement type: {mtype} not valid')

        if forward_backward == 'forward':
            r_stage.moveRelative(slave_address, r_step)
            time.sleep(5)
        elif forward_backward == 'backward':
            r_stage.moveRelative(slave_address, -r_step)
            time.sleep(5)
        else:
            raise ValueError(f'option for scan direction: {forward_backward} not valid')

def setup_reference(reference_pmt_channel):
    print(colored("Setting up reference pmt readout (scope)...", 'green'))
    scope_ip = "10.25.101.2"
    scope = sl.instruments.RohdeSchwarzRTM3004(ip=scope_ip)
    scope.ping()
    return scope

def convert_wf(raw_wf):
    times, volts = raw_wf
    return times, volts


def measure_reference(filename, scope, reference_pmt_channel=1, num_reference_wfs=1000):
    print(colored(f"Reference Measurement - {num_reference_wfs} WFs", 'green'))
    for i in range(num_reference_wfs):
        raw_wf = scope.acquire_waveform(reference_pmt_channel)
        times, wf = convert_wf(raw_wf)
        write_to_hdf5(filename, i, times, wf, 0, 0)

def setup_bottom_devices(slave_address, voltage):
    print(colored("Setting up motors...", 'green'))
    rotate_stage = None
    ##USB3 - THORLABS
    try:
        rotate_stage = HDR50(serial_port="/dev/ttyUSB3", serial_number="40106754", home=True, swap_limit_switches=True)
        rotate_stage.wait_up()
    except:
        print(colored('Error in connecting to Thorlabs Motor!', 'red'))
    ##USB2 - ORIENTAL MOTORS
    try:
        r_stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    rotate_stage.move_relative(-90)
    rotate_stage.wait_up()

    r_stage.moveToHome(slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))
    # LD = PMX70_1A('10.25.101.60')
    # LD.connect_instrument()
    # LD.set_volt_current(voltage, 0.02)
    # #Warm up LD
    print('Warm up LD (10 min)')
    # for i in tqdm(range(600)):
    #     time.sleep(1)
    return rotate_stage, r_stage, LD

def setup_top_devices(rotate_slave_address, r_slave_address, voltage):
    print(colored("Setting up motors...", 'green'))
    stage = None
    ##USB2 - ORIENTAL MOTORS
    try:
        stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    stage.moveToHome(rotate_slave_address)
    time.sleep(5)
    stage.moveToHome(r_slave_address)
    time.sleep(5)
    print(colored("Motor setup finished", 'green'))
    # LD = PMX70_1A('10.25.101.60')
    # LD.connect_instrument()
    # LD.set_volt_current(voltage, 0.02)
    # #Warm up LD
    print('Warm up LD (10 min)')
    # for i in tqdm(range(600)):
    #     time.sleep(1)
    return stage

#############################################################################

def measure_brscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_max, r_scan_points,
                    mtype='stamp', measure_side='bottom'):
    print('brscan')
    slave_address = 1
    rotate_stage, r_stage, LD = setup_bottom_devices(slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:
        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point, r_step, 
                        r_scan_points, mtype=mtype, forward_backward='forward')
        ##when finished, return motor to home
        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(20)

        # measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point+180, r_step, 
        #                 r_scan_points, mtype=mtype, forward_backward='backward') 

        # r_stage.moveToHome(slave_address)
        # print('r_stage homing')
        # time.sleep(20)
        
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()
    rotate_stage.move_relative(-270)
    rotate_stage.wait_up()



def measure_bzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    mtype='stamp', measure_side='bottom'):
    print('bzscan')
    slave_address = 2
    rotate_stage, r_stage, LD = setup_bottom_devices(slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, r_stage, slave_address, theta_point, z_step, 
                        z_scan_points, mtype=mtype, forward_backward='forward')
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        r_stage.moveToHome(slave_address)
        print('r_stage homing')
        time.sleep(10)
        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()
    rotate_stage.move_relative(-270)
    rotate_stage.wait_up()



def measure_trscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    r_step, r_max, r_scan_points,
                    mtype='stamp', measure_side='top'):
    print('trscan')
    rotate_slave_address = 5
    r_slave_address = 3
    stage = setup_top_devices(rotate_slave_address, r_slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')

        measure_r_steps(dir_sig, degg, nevents, stage, r_slave_address, theta_point, r_step, 
                        r_scan_points, mtype=mtype, forward_backward='backward')

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)

        # measure_r_steps(dir_sig, degg, nevents, stage, r_slave_address, theta_point+180, r_step, 
        #                 r_scan_points, mtype=mtype, forward_backward='forward') 

        # stage.moveToHome(r_slave_address)
        # print('r_stage homing')
        # time.sleep(20)
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)
        stage.moveRelative(rotate_slave_address, -theta_step)
        time.sleep(10)
    stage.moveRelative(rotate_slave_address, 360)
    print('stage homing')
    for i in tqdm(range(120)):
        time.sleep(1)
    

    

def measure_tzscan(dir_sig, dir_ref, degg, nevents, voltage,
                    theta_step, theta_max, theta_scan_points,
                    z_step, z_max, z_scan_points,
                    mtype='stamp', measure_side='top'):
    print('tzscan')
    rotate_slave_address = 5
    r_slave_address = 4
    stage = setup_top_devices(rotate_slave_address, r_slave_address, voltage)
    ##initialize reference settings
    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')
        measure_r_steps(dir_sig, degg, nevents, stage, r_slave_address, theta_point, z_step, 
                        z_scan_points, mtype=mtype, forward_backward='forward')
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)
        stage.moveRelative(rotate_slave_address, -theta_step)
        time.sleep(10)
    stage.moveRelative(rotate_slave_address, 360)
    print('stage homing')
    for i in tqdm(range(120)):
        time.sleep(1)

##################################################################################
