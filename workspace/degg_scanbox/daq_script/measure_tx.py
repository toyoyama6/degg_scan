import click
import time

from daq_script.measure_bx import *


def setup_top_motors():
    print(colored("Setting up motors...", 'green'))
    stage = None
    ##USB2 - ORIENTAL MOTORS
    try:
        stage = AZD_AD(port="/dev/ttyUSB2")
    except:
        print(colored('Error in connecting to Oriental Motor!', 'red'))

    # rotate_stage.home()
    # rotate_stage.wait_up()

    print(colored("Motor setup finished", 'green'))

    return stage


def daq_wrapper(run_json, comment):
    measurement_type = "scanbox"
    dir_ref, dir_sig = setup_paths(measurement_type)

    theta_step = 6 ##deg
    theta_max = 180 ##deg
    theta_scan_points = np.arange(0, theta_max, theta_step)

    r_step = 3 ##mm
    r_range = 141 ##mm (radius)
    r_scan_points = np.arange(0, r_range, r_step)

    rotate_slave_address = 5
    r_slave_address = 3
    stage = setup_top_motors()
    stage.moveToHome(3)
    time.sleep(5)
    stage.moveToHome(r_slave_address)
    time.sleep(rotate_slave_address)

    LD = PMX70_1A('10.25.123.249')
    LD.connect_instrument()

    reference_pmt_channel = 1
    scope = setup_reference(reference_pmt_channel)

    ##initialise DEgg settings
    config_threshold0 = 6000 ##units of ADC
    config_threshold1 = 100 ##units of ADC
    ##wf/chargestamp per scan point
    nevents = 3000
    ##wf (waveform) or chargestamp (stamp)
    measure_mode = 'stamp'
    degg, degg_dict, degg_file = setup_degg(run_json, dir_sig, measure_mode, 
                                    nevents, config_threshold0, config_threshold1)

    for pmt in ['LowerPmt', 'UpperPmt']:
        key = create_key(degg_dict[pmt], measurement_type)
        meta_dict = dict()
        meta_dict['Folder']     = dir_sig
        meta_dict['threshold0'] = config_threshold0
        meta_dict['threshold1'] = config_threshold1
        meta_dict['nevents']    = nevents
        meta_dict['mode']       = measure_mode
        meta_dict['Comment']    = comment
        degg_dict[pmt][key] = meta_dict
    update_json(degg_file, degg_dict)

    voltage = 6
    LD.set_volt_current(voltage, 0.02)

    for theta_point in theta_scan_points:

        print(r'-- $\theta$:' + f'{theta_point} --')

        measure_r_steps(dir_sig, degg, nevents, stage, r_slave_address, theta_point, r_step, 
                        r_scan_points, mtype=measure_mode, forward_backward='backward')

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)

        measure_r_steps(dir_sig, degg, nevents, stage, r_slave_address, theta_point+180, r_step, 
                        r_scan_points, mtype=measure_mode, forward_backward='forward') 

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(20)
        reference_pmt_file = os.path.join(dir_ref, f'ref_{theta_point}.hdf5')
        measure_reference(reference_pmt_file, scope, reference_pmt_channel)

        stage.moveToHome(r_slave_address)
        print('r_stage homing')
        time.sleep(10)
        stage.moveRelative(rotate_slave_address, theta_step)
        time.sleep(10)
    ##save data
    save_degg_data(degg, measure_mode, dir_sig)



@click.command()
@click.argument('run_json')
@click.argument('comment')
def main(run_json, comment):
    daq_wrapper(run_json, comment)

if __name__ == "__main__":
    main()
