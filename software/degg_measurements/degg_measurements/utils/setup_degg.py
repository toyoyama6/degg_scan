##setup a DEgg since the mini-fieldhub has been power cycled

import os, sys, subprocess
import signal
from traceback import print_tb
import time
from tqdm import tqdm
import numpy as np
import json
import click
from tempfile import TemporaryFile
from termcolor import colored
import configparser
from datetime import datetime

######################################################################
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils.flash_fpga import fpga_set
from degg_measurements.utils import MFH_SETUP_CONSTANTS
from degg_measurements.utils import enable_pmt_hv_interlock
from degg_measurements.utils import enable_flash_interlock
from degg_measurements.utils import enable_calibration_interlock
from degg_measurements.utils import ICMController
from degg_measurements.utils import mfh_power_on

from concurrent.futures import ProcessPoolExecutor, wait

from degg_measurements import FW_PATH
from degg_measurements import MCU_DEV_PATH
from degg_measurements import USB_BAN_LIST
from degg_measurements import FH_SERVER_SCRIPTS
from degg_measurements import MFH_PATH00
from degg_measurements import MFH_PATH01
from degg_measurements import MFH_PATH10
from degg_measurements import MFH_PATH11
from degg_measurements import MFH_PATH20
from degg_measurements import MFH_PATH21

OPEN_PORTS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'configs/open_ports.json')


def rethink_life():
    choice = input("Only run this script domnet is not already running." +
                   "\n Do you want to proceeed? [y/n] ")

    logfile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'restart_logging.txt')

    if choice.lower() not in ["y", "yes"]:
        print("Go home and rethink your life")
        exit(1)
    else:
        print("Setting up D-Eggs")
        print(f"This will be logged: {logfile}")
        print("------------------")

    file_obj = open(logfile, 'a')
    file_obj.write(datetime.today().strftime('%Y-%m-%d-%H-%M'))
    file_obj.close()



def establish_connection_domnet(usb_device_list):
    n_per_wp = 8
    # wire_pairs = [1]
    n_tries_per_icm = 4

    port_start_list = [5000]

    domnet_runners = []
    successes = []

    flash_interlock_choice = input('Enable the flash interlock? \
                                    (required for STF) [y/n]: ')
    if flash_interlock_choice.lower() in ['y', 'yes']:
        write_flash_interlock = True
    else:
        write_flash_interlock = False

    domnet_runner = DomnetRunner(usb_device_list[0],
                                    port_start_list[0],
                                    n_per_wp)
    domnet_runner.__connect__()
    # n_tries = 0
    # while not domnet_runner.success:
    #     n_tries += 1
    #     domnet_runner.__disconnect__()
    #     domnet_runner.__connect__()
    #     if n_tries > n_tries_per_icm:
    #         break

    successes.append(domnet_runner.success)
    # terminate_cables(domnet_runner.command_port)
    time.sleep(0.5)
    enable_pmt_hv_interlock(domnet_runner.command_port)
    enable_calibration_interlock(domnet_runner.command_port)
    if write_flash_interlock == True:
        enable_flash_interlock(domnet_runner.command_port)


    # if np.sum(domnet_runners) == 0:
    #     print("No vaid connections were opened, exiting...")
    #     exit(1)

  
    ports = [5007]
    return [domnet_runners], ports, np.asarray(successes)


class DomnetRunner():
    def __init__(self, usb_device, port, n_per_wp,
                 path_to_config=None):
        self.usb_device = usb_device
        self.port = port
        self.command_port = port + 1000
        self.n_per_wp = n_per_wp
        if path_to_config is not None:
            self.config = path_to_config
        else:
            self.config = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'configs/domnet.ini')
        self.file = TemporaryFile()
        self.connected = False
        self.success = False
        self.pid = None

    @property
    def is_connected(self):
        return self.connected

    def __enter__(self):
        self.__connect__()
        return self

    def __exit__(self, type, value, traceback):
        self.__disconnect__()

    def __add__(self, other):
        if isinstance(other, int):
            return int(self.connected) + other
        elif isinstance(other, DomnetRunner):
            return int(self.connected) + int(other.connected)

    def __radd__(self, other):
        if isinstance(other, int):
            return other + int(self.connected)
        elif isinstance(other, DomnetRunner):
            return int(self.connected) + int(other.connected)

    def __was_successful__(self):
        MFH_ICM = 8
        lines = self.domnet_out
        for line in lines:
            if line.startswith("ICMs detected at address"):
                splitted = line.split(':')[-1].split(' ')
                detected_icms = [int(s) for s in splitted if s.isnumeric()]
                if MFH_ICM not in detected_icms:
                    raise ValueError(
                        f'MFH_ICM not found in domnet output! '
                        ' '.join(lines))
                if len(detected_icms) - 1 == self.n_per_wp:
                    return True
                else:
                    return False
        return False

    def __connect__(self):
        print(f" --- Establishing connection for ports "
              f"{self.port}:{self.port+self.n_per_wp-1} ---\n"
              f" --- Using config at {self.config} ---")
        process = subprocess.Popen([
            "domnet",
            self.usb_device,
            "-c", f"{self.config}",
            "-p", f"{self.port}",
            "-n", f"{self.n_per_wp}"],
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        self.domnet_out = []
        for _ in range(3):
            line = process.stderr.readline().decode()
            self.domnet_out.append(line)

        print(''.join(self.domnet_out))
        self.connected = True
        self.success = self.__was_successful__()
        self.pid = process.pid
        time.sleep(0.5)
        return self.connected, self.pid

    def __disconnect__(self):
        if self.pid is not None:
            os.kill(self.pid, signal.SIGTERM)
            self.connected = False
            self.success = False
            print(f'Killed domnet session with pid {self.pid}')
            self.pid = None
        else:
            raise ValueError(
                "Can't disconnect, when not connected!")
        time.sleep(0.5)


def check_connection(port):
    print("-" * 20)
    print(f"localhost - {port}")
    try:
        session = startIcebootSession(host='localhost', port=port)
    except:
        print('Could not start Iceboot Session')
        return False

    try:
        output = session.cmd("sloAdcReadAll")
        if output == 'sloAdcReadChannel: FAIL':
            print(' --- FPGA is not configured --- ')
            print(output)
            return False
        else:
            print(output)
            return True
    except:
        print(' --- Error reading sloAdc ---')
        return False


def time_func(func):
    def wrapper(*args, **kwargs):
        t0 = time.monotonic()
        func(*args, **kwargs)
        t1 = time.monotonic()
        print(f'Function {func.__name__} ran {(t1-t0)/3600.:.2f} hours!')
    return wrapper


def reboot_from_image_and_terminate(usb_devices, mfh_image_id=2, ignore=False):
    inice_image_id = 2
    #choice = input(
    #    f'Reboot from MFH image {mfh_image_id}, InIce image {inice_image_id} '
    #    f'and terminate all ICMs?')
    #if choice.lower() in ['y', 'yes']:
    print(f"Rebooting from MFH image {mfh_image_id}, InIce image {inice_image_id} and terminating.")
    if True == True:
        connected_devices = [7]
        for usb_device in usb_devices:
            icm_ctrl = ICMController(usb_device, connected_devices)
            #icm_ctrl.setup_icms(mfh_image_id=mfh_image_id,
            #                    inice_image_id=inice_image_id,
            #                    ignore=ignore)
            #icm_ctrl.close()

            icm_ctrl.setup_mfh_icm(mfh_image_id=mfh_image_id, ignore=ignore)
            icm_ctrl.close()

            ##start domnet now that icm is rebooted
            ##enable HV to detect D-Eggs
            #domnet_runner = DomnetRunner(usb_device, 20000, 4)
            #domnet_runner.__connect__()
            #time.sleep(1)
            #os.system(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/wp_on.py -p {domnet_runner.command_port}')
            #mfh_power_on(domnet_runner.command_port)
            #print(domnet_runner)
            #domnet_runner.__disconnect__()

            with DomnetRunner(usb_device, 5000, 8) as domnet_runner:
                time.sleep(0.5)
                os.system(f'python3 {FH_SERVER_SCRIPTS}/wp_on.py -p {domnet_runner.command_port}')
                #os.system(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/wp_on.py -p {domnet_runner.command_port}')
                #mfh_power_on(domnet_runner.command_port) ##complains about remote only, but it's enabled...

            icm_ctrl = ICMController(usb_device, connected_devices)
            icm_ctrl.setup_inice_icm(inice_image_id=inice_image_id, ignore=ignore)
            icm_ctrl.close()

    return

##make it convenient for parallel jobs
def get_sorted_ports():
    sorted_ports = [5007]
    return sorted_ports



@click.command()
@click.argument('usb_devices', nargs=-1)
@time_func
def setup_deggs(usb_devices):
    rethink_life()
    if not os.path.isfile(FW_PATH):
        raise ValueError(f'Firmware file {FW_PATH} does not exist!')


    print(f"Using the given devices: {usb_devices}.")

    reboot_from_image_and_terminate(usb_devices)

    print("\n" + "-" * 45 + "\n")
    domnet_runners, ports, successes = establish_connection_domnet(
        usb_devices)

    print("\n")
    print(f"Ports: {ports}")
    print(f"{np.sum(~successes)} Domnet Initializations were unsuccessful!")
    flash_choice = input("Automatically flash FPGA for all ports? [y/n]")
    if flash_choice.lower() in ['y', 'yes']:
        auto_flash = True
        parallel_choice = input("Flash in parallel? [y/n]")
        if parallel_choice.lower() in ['y', 'yes']:
            n_parallel_tasks = 4
            with ProcessPoolExecutor(max_workers=n_parallel_tasks) as executor:
                futures = []
                sorted_ports = get_sorted_ports()
                for port in sorted_ports:
                    futures.append(
                        executor.submit(
                            fpga_set,
                            port_num=port,
                            auto_flash=auto_flash
                        )
                    )
            results = wait(futures)
            for result in results.done:
                print(result.result())
        else:
            for port in ports:
                flashed = fpga_set(port, auto_flash)
                time.sleep(0.5)
    else:
        auto_flash = False
        n_parallel_tasks = 1
        for port in ports:
            flashed = fpga_set(port, auto_flash)
            time.sleep(0.5)

    ###for tabletop mainboard integration
    #tabletop_usb = '/dev/ttyUSB8'
    # tabletop_usb = os.path.join('/dev/serial/by-path/', MFH_PATH20)
    # print(f'Assuming that tabletop board is on {tabletop_usb}!')
    # port_start = 10000
    # port_board = 10007
    # setup_choice, tabletop_runner = setup_tabletop(tabletop_usb, port_start, port_board)
    # if setup_choice.lower() in ['yes', 'y']:
    #     domnet_runners.append(tabletop_runner)

    setup_results = []
    for port in ports:
        output = check_connection(port)
        time.sleep(0.5)
        setup_results.append(([port,output]))

    with open(OPEN_PORTS, 'w+') as open_file:
        open_ports = {}
        for result in setup_results:
            open_ports.update({str(result[0]): result[1]})
        json.dump(open_ports, open_file, indent=4)

    print('-' * 20)
    print('Setup Summary: ')
    print(setup_results)
    print('-' * 20)

    print(colored("--- Setup Completed ---", 'green'))
    print(colored("Press Ctrl+C to exit and close domnet processes!", 'green'))
    while True:
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            for runner in domnet_runners:
                runner.__disconnect__()
            break


if __name__ == "__main__":
    setup_deggs()
