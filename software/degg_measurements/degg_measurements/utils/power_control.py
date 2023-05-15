import sys, os, time
import json

##for interface with chiba-daq slack channel
from chiba_slackbot import send_message
from chiba_slackbot import send_warning
from chiba_slackbot import send_critical

from datetime import datetime

##coloured text
from termcolor import colored
import click
from tqdm import tqdm
from degg_measurements import FREEZER_CONTROL

sys.path.append(FREEZER_CONTROL)
try:
    from switchminFH import power_switch as switchMFH
except ModuleNotFoundError:
    raise ModuleNoFoundError(
        f'Mini-Fieldhub Control script expected at {switch_path}!')

from degg_measurements.utils.icm_manipulation import mfh_power_status, mfh_power_on
from degg_measurements.utils.icm_manipulation import mfh_power_off, mfh_power_cycle

POWER_SETTINGS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'configs/power_settings.json')


def get_config(create=False):
    if create == False:
        try:
            with open(POWER_SETTINGS, 'r') as open_file:
                info = json.load(open_file)
        except:
            print(f"Could not find file: {POWER_SETTINGS}")
    if create == True:
        print('Creating New Power Settings File')
        info = {str(6000): 'UNSET', str(6004): 'UNSET',
                str(6008): 'UNSET', str(6012): 'UNSET'}
        with open(POWER_SETTINGS, 'w+') as open_file:
            json.dump(info, open_file, indent=4)
        print(colored('Execute script again to run with'
                  + ' 6000 - 6012 or with specific port', 'green'))
        exit(1)

    control_ports = []
    status = []
    for (key, val) in info.items():
        control_ports.append(key)
        status.append(val)
    return control_ports, status


def do_reboot(command_port, reboot, verbose):
    if reboot.lower() == 'soft':
        soft_reboot(command_port, verbose)
        return 'ON'
    elif reboot.lower() == 'hard':
        mfh_reboot(verbose)
        return 'ON'
    else:
        raise NotImplementedError('<power_control> Type of reboot not specified!')


def do_control(command_port, setting, control, power, verbose):
    ## check current status in json
    if power == setting:
        print(colored(f"{command_port} is already set to {setting}!", 'yellow'))
        return
    if control == 'none' or power == 'none':
        raise NotImplementedError('<do_control> SET Control Method & Power Setting')
    ## icm
    if control == 'icm':
        if power == 'on':
            wp_on(command_port, verbose)
        if power == 'off':
            wp_off(command_port, verbose)
    ## switch
    if control == 'switch':
        if power == 'on':
            mfh_on(verbose)
        if power == 'off':
            mfh_off(verbose)
    ##only need to operate switch once
        exit(1)


def mfh_reboot(verbose):
    if verbose:
        send_message("<MFH REBOOT> TURNING OFF MFH")
    mfh_off(verbose)
    time.sleep(2)
    power = mfh_on(verbose)
    time.sleep(2)
    if verbose:
        send_message("<MFH REBOOT> MFH BACK ONLINE")
    return power


def mfh_on(verbose):
    if verbose:
        send_message("<MFH ON> TURNING ON MFH")
    power = switchMFH(option='on')
    send_message("<MFH ON> MFH ONLINE")
    return power


def mfh_off(verbose):
    send_message("<MFH OFF> TURNING OFF MFH")
    power = switchMFH(option='off')
    if verbose:
        send_message("<MFH OFF> MFH OFFLINE")
    return power


#enabling WP - always send to slack
def wp_on(command_port, verbose):
    if verbose:
        send_message(f"<WP ON> WIRE PAIR {command_port} ENABLING POWER")
    mfh_power_on(command_port)
    send_message(f"<WP ON> POWER ENABLED {command_port}")
    if verbose:
        get_status(command_port)


#disabling WP - always send to slack
def wp_off(command_port, verbose):
    send_message(f"<WP OFF> WIRE PAIR {command_port} DISABLING POWER")
    mfh_power_off(command_port)
    if verbose:
        send_message("<WP OFF> POWER DISABLED")


def soft_reboot(command_port, verbose):
    if verbose:
        send_message(f"<SOFT REBOOT> WIRE PAIR {command_port} REBOOTING")
    mfh_power_cycle(command_port)
    send_message("<SOFT REBOOT> WIRE PAIR {command_port} REBOOTED")


def get_status(command_port, verbose=True):
    print(f"Get Status {command_port}")
    voltage_info = mfh_power_status(command_port, 'voltage')
    current_info = mfh_power_status(command_port, 'current')
    send_message(f"<GET STATUS> WIRE PAIR {command_port}")
    send_message(f"<GET STATUS> VOLTAGE {voltage_info}")
    send_message(f"<GET STATUS> CURRENT {current_info}")


def print_help():
    print("================================================")
    print("Either give the command port (--port) & --setting (ON / OFF)")
    print("OR code runs for all commands ports (6000, 6004, 6008, 6012)")
    print("================================================")
    print("To get the wire pair status give --status as a flag")
    print("To turn on or off specify --control='icm' / 'switch'")
    print("And also the --power='ON'/'OFF'")
    print("To reboot use --reboot='soft'/'hard'")
    print("To create a new config file use --create")
    print("To send additional information to slack use --verbose/-v")


@click.command()
@click.option('--status', is_flag=True, default=False)
@click.option('--control', type=click.Choice(['icm', 'switch', 'none'],
                case_sensitive=False), default='none')
@click.option('--power', type=click.Choice(['ON', 'OFF'], case_sensitive=False))
@click.option('--reboot', type=click.Choice(['soft', 'hard', 'none'],
                case_sensitive=False), default='none')
@click.option('--port', type=click.Choice(['6000', '6004', '6008', '6012', '-1']),
                default='-1')
@click.option('--setting', type=click.Choice(['ON', 'OFF']), default='ON')
@click.option('--verbose', '-v', is_flag=True, default=False)
@click.option('--create', is_flag=True, default=False)
@click.option('--help', is_flag=True, default=False)
def main(status, control, power, reboot, port, setting, verbose, create, help):
    port = int(port)
    if help == True:
        print_help()
        return
    if port == -1:
        command_ports = [6000, 6004, 6008, 6012]
        settings = [setting, setting, setting, setting]
        #command_ports, settings = get_config(create)
        print(colored(f"Running for {command_ports} - Set:{settings}", 'green'))
    else:
        command_ports = [port]
        settings = [setting]
        if reboot != 'none':
            print(colored(f"Manual Settings: running for {port} - Pwr:{power}", 'yellow'))
        else:
            print(colored(f"Manual Settings: running for {port} - Reboot: {reboot}", 'yellow'))

    if status:
        for command_port, setting in zip(command_ports, settings):
            get_status(command_port, verbose)
        exit(1)

    ## update status in json
    with open(POWER_SETTINGS, 'w') as open_file:
        info = {}
        if reboot.lower() in ['soft', 'hard']:
            for command_port, setting in zip(command_ports, settings):
                ## check current status in json - must be on to reboot!
                if setting.lower() == 'on':
                    do_reboot(command_port, reboot.lower(), verbose)
                    info.update({str(command_port): 'ON'})

        elif control.lower() in ['icm', 'switch']:
            if power.lower() in ['on', 'off']:
                for command_port, setting in zip(command_ports, settings):
                    do_control(command_port, setting, control.lower(),
                               power.lower(), verbose)
                    info.update({str(command_port): power})
        json.dump(info, open_file, indent=4)

if __name__ == "__main__":
    main()

##end
