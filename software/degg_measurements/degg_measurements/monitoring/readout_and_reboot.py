from degg_measurements.utils import startIcebootSession
import time
import click
import os
from copy import deepcopy
import json
from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_save_dir
from degg_measurements.monitoring import readout, reboot
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils.stack_fmt import stripStackSize

from datetime import datetime
from datetime import timedelta

from degg_measurements import DATA_DIR


@click.command()
@click.argument('json_file')
@click.argument('comment')
@click.argument('set_time', default=None)
def main(json_file, comment, set_time):
    readout_and_reboot(json_file, comment, set_time)

def readout_and_reboot(json_file, comment, set_time):

    measurement_type = 'ReadoutReboot'

    #load all degg files
    list_of_deggs = load_run_json(json_file)

    ##filepath for saving data
    dirpath = create_save_dir(DATA_DIR, measurement_type=measurement_type)

    session_list = []
    port_list = []
    filename_list = []
    firmware_version_list = []
    firmwarefilename_list = []

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        key = create_key(degg_dict, measurement_type)
        degg_dict[key] = dict()
        degg_id = degg_dict['DEggSerialNumber']
        filename = os.path.join(dirpath, degg_id + '.csv')
        degg_dict[key]['Filename'] = filename
        degg_dict[key]['Comment'] = comment
        degg_dict[key]['Time'] = set_time

        current_dict = deepcopy(degg_dict)
        port = current_dict['Port']
        port_list.append(port)
        session = startIcebootSession(host='localhost', port=port)
        try:
            fpgaVersion = session.cmd('fpgaVersion .s drop')
        except:
            print("Could not determine the fpgaVersion")
            fpgaVersion = -1
        firmware_version = stripStackSize(fpgaVersion)
        degg_dict[key]['FirmwareVersion'] = firmware_version

        ##will we have problems with sessions staying open?
        session_list.append(session)
        filename_list.append(filename)
        firmware_version_list.append(firmware_version)

        flashLS = session.flashLS()
        try:
            firmwarefilename = flashLS[len(flashLS)-1]['Name'] # latest uploaded file
            firmwarefilename_list.append(firmwarefilename)
        except KeyError:
            print(flashLS)
            raise
        print(f'Found valid firmware {firmwarefilename} in the flash memory.\n' +
            'Try to configure... ')

        update_json(degg_file, degg_dict)

        time.sleep(3)

    start = datetime.now()
    now = start
    stop = start + timedelta(seconds=float(set_time))
    while (stop - now).total_seconds() > 0:
        cnt = 0
        for session, port in zip(session_list, port_list):
            time.sleep(3)

            firmware_version = firmware_version_list[cnt]
            firmwarefilename = firmwarefilename_list[cnt]
            filename = filename_list[cnt]

            print(f"Port: {port}")
            print(f"FW Vers.: {firmwarefilename}")

            reflash_count = reboot(session, firmware_version=firmwarefilename)
            readout(session, reflash_count, filename)

        ##if no time - only run once
        if set_time is None:
            break
        now = datetime.now()
        cnt += 1

if __name__ == '__main__':
    main()

