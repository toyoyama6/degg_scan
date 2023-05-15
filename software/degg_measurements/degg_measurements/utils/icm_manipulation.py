import time
import sys
import os
import click
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
import icm_command_script as ics

DUMMY_ARGS = 'dummy -p {command_port} --host localhost'
DUMMY_ARGS_RP = 'dummy -p {command_port} -w {wp_addr} --host localhost'


def run_rapcal_all(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="rapcal_all",
                       only_remote=True)

def run_rapcal(command_port, wp_addr):
    args = DUMMY_ARGS_RP.format(command_port=command_port,
                                wp_addr=wp_addr)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="rapcal",
                       only_remote=True)

def enable_gps(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="gps_enable",
                       only_remote=True)

def enable_external_osc(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="ext_osc_enable",
                       only_remote=True)

def enable_flash_interlock(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="mcu_flash_enable",
                       only_remote=True)

def enable_pmt_hv_interlock(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="pmt_hv_enable",
                       only_remote=True)


def enable_calibration_interlock(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd="lid_enable",
                       only_remote=True)


def mfh_power_status(command_port, option):
    if option.lower() not in ['voltage', 'current']:
        raise NotImplementedError(f'<mfh_power_status> {option.lower()} is not implemented!')
    if option.lower() == 'voltage':
        command = 'wp_voltage'
    if option.lower() == 'current':
        command = 'wp_current'

    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    info = ics.single_command(args_list,
                              cmd=command,
                              only_remote=True)
    return info


def mfh_power_on(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd='wp_on',
                       only_remote=True)
    #ics.single_command(args_list,
    #                   cmd='probe',
    #                   only_remote=True)


def mfh_power_off(command_port):
    args = DUMMY_ARGS.format(command_port=command_port)
    args_list = args.split(' ')
    ics.single_command(args_list,
                       cmd='wp_off',
                       only_remote=True)

def mfh_power_cycle(command_port):
    mfh_power_off(command_port)
    time.sleep(2)
    mfh_power_on(command_port)
    time.sleep(2)

@click.command()
@click.argument('command_port')
def main(command_port):
    terminate_cables(command_port)


if __name__ == '__main__':
    main()

