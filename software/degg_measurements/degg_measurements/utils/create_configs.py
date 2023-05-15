##code for getting unique flashID and matching to port number
##then acquiring the D-Egg info from the ID via database

import time
import json
import click
import numpy as np
import os, sys
from datetime import datetime
from termcolor import colored

from degg_measurements.utils.stack_fmt import stripStackSize
from degg_measurements.utils.parser import startIcebootSession
from degg_measurements.utils.setup_degg import OPEN_PORTS
#from degg_measurements.utils import short_sha
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils.degg import DEgg
from degg_measurements import RUN_DIR
from degg_measurements.utils import SOFTWARE_VERSIONS


def import_box_port_map(box_map_file):
    if not os.path.isfile(box_map_file):
        print("Could not find box-port map file")
        exit(1)
    try:
        with open(box_map_file, 'r') as open_file:
            box_map = json.load(open_file)
            return box_map
    except:
        print("Could not open box-port map")
        exit(1)


def get_box(box_map, _port, degg):
    for (box, port) in box_map.items():
        if int(port) == _port:
            degg.setBoxNumber(box)


def get_flash_id(session, degg):
    try:
        flashID = session.cmd('flashID')
    except:
        print("Could not determine the flashID")
        flashID = -1
    degg.setFlashID(str(flashID))
    return flashID


def get_icm_id(session, degg):
    try:
        icm_id = session.cmd('icmID')
    except:
        print("Could not determine the icmID")
        icm_id = -1
    degg.setICMID(str(icm_id))
    return icm_id


## only call this function once -
## do not overload spreadsheet API
def logbook_instance():
    try:
        print("Connecting to D-Egg Log Book Spreadsheet")
        logbook_dataframes = DEggLogBook()
    except IndexError:
        print("Unable to construct dataframe from logbook")
    return logbook_dataframes


def get_degg_info(logbook_dataframes,
                  icm_id,
                  spread_sheet_names,
                  sub_sheet_names, port,
                  degg):
    df_row = logbook_dataframes.get_degg_from_ID(icm_id, 'Serial number', 'Label number',
                                                 'icm', spread_sheet_names)

    if len(df_row) > 1:
        print(f"Found duplicate ID! (ICM Serial Number {icm_id}) in get_degg_info")
        print('Congratulations, this error is coming up for the first time!')
        print(df_row)
        print('Please consider how this error should be resolved! (sort by re-sealing date?)')
        exit(1)

    if df_row is None:
        raise ValueError(f"Can't find icmID {icm_id} in the logbook!")

    ##D-Egg Logbook Page
    degg.setDEggName(df_row['Nickname'].values[0])
    degg.setDEggSerialNumber(df_row['Serial number'].values[0])
    degg.setArrivalDate(df_row['Arrival date(to Chiba)'].values[0])
    degg.setGlassSerialNumber(df_row['Serial number (Upper D-Egg half)'].values[0], "upper")
    degg.setGlassSerialNumber(df_row['Serial number (Lower D-Egg half)'].values[0], "lower")
    degg.setSealingDate(df_row['Sealing date'].values[0])
    degg.setICMID(df_row['ICMID'].values[0])
    degg.setFlasherNumber(df_row['Flasher board'].values[0])
    degg.setCameraNumber(df_row['Camera ring'].values[0])
    degg.setElectricalInspectionNME(df_row['Electrical inspection\n@NME'].values[0])
    degg.setMainboardNumber(df_row['Mainboard'].values[0])
    degg.setICMNumber(df_row['ICM'].values[0])

    ##use glass S/N to find on other page
    ##upper half
    degg_u = df_row['Serial number (Upper D-Egg half)'].values[0]
    df_row_u = logbook_dataframes.get_degg_from_string(degg_u, 'Serial number', sub_sheet_names)
    degg.setGlassNumber(df_row_u['Glass'].values[0], "upper")
    degg.setPmtSerialNumber(df_row_u['PMT'].values[0], "upper")
    degg.setHVB(df_row_u['HVB'].values[0], "upper")

    ##lower half, don't repeat entries
    degg_l = df_row['Serial number (Lower D-Egg half)'].values[0]
    df_row_l = logbook_dataframes.get_degg_from_string(degg_l, 'Serial number', sub_sheet_names)
    degg.setGlassNumber(df_row_l['Glass'].values[0], "lower")
    degg.setPmtSerialNumber(df_row_l['PMT'].values[0], "lower")
    degg.setHVB(df_row_l['HVB'].values[0], "lower")
    degg.setPenetratorNumber(df_row_l['Penetrator'].values[0])


def get_fpga_version(session, degg):
    try:
        fpgaVersion = session.cmd('fpgaVersion .s drop')
    except:
        print("Could not determine the fpgaVersion")
        fpgaVersion = -1
    fpgaVersion = stripStackSize(fpgaVersion)
    degg.setFpgaVersion(fpgaVersion)


def get_iceboot_version(session, degg):
    icebootVersion = -1
    try:
        icebootVersion = session.cmd('softwareVersion .s drop')
    except:
        print("Could not determine the iceboot version")
        icebootVersion = -1
    icebootVersion = stripStackSize(icebootVersion)
    degg.setIcebootVersion(icebootVersion)


def start_session(_port):
    session = startIcebootSession(host='localhost', port=_port)
    time.sleep(3)
    return session


def get_used_ports():
    print("Checking open ports.")
    if os.path.isfile(OPEN_PORTS):
        with open(OPEN_PORTS, 'r') as open_file:
            ports_dict = json.load(open_file)
    else:
        print(f"Path to open_ports.json: {OPEN_PORTS}")
        print("First open connections using setup_degg.py")
        exit(1)

    open_ports = []
    for (key, val) in ports_dict.items():
        if val != False:
            open_ports.append(int(key))

    print(f"Connections via ports {open_ports} are already open, ",
          "available iceboot session.")
    if len(open_ports) == 0:
        print("No open ports properly configured")
        exit(1)
    return open_ports


def construct_dict(degg):
    if degg.getFpgaVersion()!=SOFTWARE_VERSIONS.FPGA:
        raise ValueError("Wrong FPGA Version Number! Found {}, expected {}".format(degg.getFpgaVersion(), SOFTWARE_VERSIONS.FPGA))
    #if degg.getIcebootVersion()!=SOFTWARE_VERSIONS.ICEBOOT:
       # raise ValueError("Wrong Iceboot Version Number! Found {}, expected {}".format(degg.getIcebootVersion(), SOFTWARE_VERSIONS.ICEBOOT))
        #continue
    degg_dict = {
        "DEggSerialNumber": degg.getDEggSerialNumber(),
        "UpperGlassSerialNumber": degg.getGlassSerialNumber("upper"),
        "LowerGlassSerialNumber": degg.getGlassSerialNumber("lower"),
        "UpperGlass": degg.getGlassNumber("upper"),
        "LowerGlass": degg.getGlassNumber("lower"),
        "UpperPmt": {
            "SerialNumber": degg.getPmtSerialNumber("upper"),
            "HVB": degg.getHVB("upper"),
            "HV1e7Gain": degg.getPmtHV("upper"),
            "HV1e7GainDefault": degg.getPmtHV("default")
        },
        "LowerPmt": {
            "SerialNumber": degg.getPmtSerialNumber("lower"),
            "HVB": degg.getHVB("lower"),
            "HV1e7Gain": degg.getPmtHV("lower"),
            "HV1e7GainDefault": degg.getPmtHV("default")
        },
        "PenetratorType": degg.getPenetratorType(),
        "PenetratorNumber": degg.getPenetratorNumber(),
        "SealingDate": degg.getSealingDate(),
        "ArrivalDate": degg.getArrivalDate(),
        "flashID": degg.getFlashID(),
        "ICMID": degg.getICMID(),
        "fpgaVersion": degg.getFpgaVersion(),
        "IcebootVersion": degg.getIcebootVersion(),
        "BoxNumber": degg.getBoxNumber(),
        "Port": degg.getPort(),
        "ICM": degg.getICMNumber(),
        "FlasherID": degg.getFlasherNumber(),
        "MainboardNumber": degg.getMainboardNumber(),
        "ElectricalInspectionNME": degg.getElectricalInspectionNME(),
        "FlasherNumber": degg.getFlasherNumber(),
        "CameraNumber": degg.getCameraNumber(),
        "Constants": {
            "Samples": 128,
            "AdcMin": 7600,
            "AdcRange": 9000,
            "Events": 10000,
            "DacValue": 30000
        },
       # "GitShortSHA": short_sha
    }
    return degg_dict


def set_file_path(degg, run_number):
    degg_id = degg.getDEggSerialNumber()
    today = datetime.today()
    today = today.strftime("%Y-%m-%d")
    run_number = int(run_number)
    run = f'{run_number:05d}'

    file_path = os.path.join(RUN_DIR, f"run_{run}")
    if not os.path.exists(file_path):
        try:
            os.makedirs(file_path)
        except:
            print(colored("Could not create directory for writing json files", 'red'))
            exit(1)

    file_name = degg_id + ".json"
    json_file_path = os.path.join(file_path, file_name)

    if not os.path.isfile(json_file_path):
        return json_file_path

    if os.path.isfile(json_file_path):
        print("-----")
        print(f"{json_file_path} already exists!")
        choice = input(f"Do you want to override {json_file_path}? [y/n]")
        print("-----")
        if choice.lower() in ["y", "yes"]:
            return json_file_path
        elif choice.lower() in ["n", "no"]:
            time_now = datetime.now()
            time_now = time_now.strftime("%H-%M")
            json_file_path = json_file_path.replace(".json", f"_{time_now}.json")
            return json_file_path
        else:
            print("Yes or No not given -- exiting")
            exit(1)


def update_json(file_path, new_dict):
    if os.path.isfile(file_path):
        with open(file_path, 'r') as open_file:
            try:
                current_dict = json.load(open_file)
            except json.JSONDecodeError:
                print("Error loading json file during update!")
                current_dict = {}
    else:
        current_dict = {}

    current_dict.update(new_dict)

    # Make sure to not write a corrupted json file if
    # the new dict is not json serializable
    try:
        json.dumps(current_dict)
    except TypeError:
        raise

    with open(file_path, 'w') as open_file:
        json.dump(current_dict, open_file, indent=4)


def get_run_number(run_dir):
    if not os.path.exists(run_dir):
        print("-----")
        print(f"{run_dir} does not exist yet!")
        choice = input(f"Do you want to create {run_dir}? [y/n]")
        print("-----")
        if choice.lower() in ["y", "yes"]:
            os.makedirs(run_dir)
        else:
            raise IOError("Could not find run directory!")

    number_list = []

    file_list = os.listdir(run_dir)
    if len(file_list) == 0:
        return 1

    for f in file_list:
        number = f.split("_")[1]
        number = number.split(".")[0]
        number = int(number)
        number_list.append(number)

    max_number = np.max(number_list)
    run_number = max_number + 1
    return run_number


def update_run_json(json_reference, filepath, run_number):
    json_dict = {}
    for reference in json_reference:
        json_dict.update(reference)

    comment = input("Please provide a short comment about this run:")
    json_dict.update({'comment': comment})

    #check for previous run files
    today = datetime.today()
    today = today.strftime("%Y-%m-%d")

    json_dict.update({'date': today})
    run_number = int(run_number)

    num = f'{run_number:05d}'
    filename = os.path.join(filepath, f"run_{num}.json")
    with open(filename, 'w+') as open_file:
        json.dump(json_dict, open_file, indent=4)
    print(f"Created run summary file: {filename}")
    print(colored(f'New Run Number is: {run_number}. Add this to the FAT logbook', 'green'))
    print(colored(f'List of D-Eggs to add to FAT logbook:', 'green'))
    for key in json_dict.keys():
        print(key)

@click.command()
@click.option('--per_wp_run', is_flag=True)
def main(per_wp_run):
    ##check configured USB devices and open ports
    ports = sorted(get_used_ports())

    ##set which spreadsheets to check - lower case
    #spread_sheets = ['d-egg_for_dvt', 'rev4mb_tests']
    spread_sheets = [
        'd-egg_batch#1',
        'd-egg_batch#2',
        'd-egg_batch#3'
    ]
    sub_sheets = [
        'half_d-egg_batch#1',
        'half_d-egg_batch#2',
        'half_d-egg_batch#3'
    ]

    ##initialise empty D-Egg class
    generic_degg = DEgg()

    ##load hard-coded association of port<-->box
    box_map_file = os.path.join(os.path.dirname(__name__),
                                'configs/box_port_map.json')
    box_map = import_box_port_map(box_map_file)

    ##connect to google API and return dataframes
    logbook_dataframes = logbook_instance()

    run_dir = os.path.join(RUN_DIR, 'run')

    if per_wp_run:
        from degg_measurements.utils import MFH_SETUP_CONSTANTS
        devices_per_wp = MFH_SETUP_CONSTANTS.in_ice_devices_per_wire_pair
    else:
        devices_per_wp = len(ports)

    for i in range(devices_per_wp//len(ports)):
        sliced_ports = ports[i*devices_per_wp:(i+1)*devices_per_wp]
        print(f'Selected ports {sliced_ports} for Subrun {i}')
        json_reference = []
        run_number = get_run_number(run_dir)

        ##loop over all ports (i.e. D-Eggs)
        failed_sessions = False
        for port in sliced_ports:
            print("-" * 20)
            try:
                session = start_session(port)
            except:
                failed_sessions = True
                print("Could not start Iceboot session!")
                print(f"No connection to {port}")
                ##wait for serial connections
                ##they are a bit slow...
                time.sleep(5)
                continue

            temp_degg = DEgg()
            temp_degg.setPort(port)
            icm_id = get_icm_id(session, temp_degg)
            get_fpga_version(session, temp_degg)
            get_iceboot_version(session, temp_degg)

            ##removing formatting during input
            del session

            get_box(box_map, port, temp_degg)
            get_degg_info(logbook_dataframes,
                          icm_id,
                          spread_sheets,
                          sub_sheets,
                          port,
                          temp_degg)
            ##then create json file
            degg_dict = construct_dict(temp_degg)
            file_path = set_file_path(temp_degg, run_number)
            update_json(file_path, degg_dict)

            temp_dict = {str(temp_degg.getDEggSerialNumber()): file_path}
            json_reference.append(temp_dict)

        if failed_sessions:
            choice = input(
                "Some DEggs failed to start an iceboot session, " +
                "do you want to exit? [y/n]")
            if choice.lower() in ['y', 'yes']:
                exit(1)

        #then create run json file summary
        print("-" * 20)
        update_run_json(json_reference, run_dir, run_number)

    import degg_measurements
    db_path = os.path.join(degg_measurements.__path__[0], 'database_jsons')
    if not os.path.exists(db_path):
        os.mkdir(db_path)
        print(f'Created directory: {db_path}!')

if __name__ == "__main__":
    main()

