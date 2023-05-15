import os, sys
import click
import json
import requests
from glob import glob
import time
from tqdm import tqdm
import subprocess

from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils import create_key
from degg_measurements.utils import update_json
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import add_git_infos_to_dict
from degg_measurements.utils import uncommitted_changes
from degg_measurements.utils import MFH_SETUP_CONSTANTS

from multi_processing import run_jobs_with_mfhs

from degg_measurements import STF_PATH

sys.path.append(STF_PATH)
import stf
from scripts.sendresults import get_testgroup_id
from stf.util.config import get_config

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

def send_report(data, config, timeslug=None):
    url = '{scheme}://{host}/{basepath}/data/testsets/'.format_map(
        config)
    print(f'Sending to {url}')
    data = {'resultDoc': data, 'timeslug': timeslug,
            'user': config['user'],
            'password': config['password']}
    response = requests.post(url, json=data)
    print(response.json())


def send_stf_results(result_paths, database_config, mb_serial=None):
    with open(database_config, 'r') as open_file:
        config = json.load(open_file)

    for result_path in result_paths:
        files = glob(os.path.join(result_path,
                                  '*.json'))
        for file_i in files:
            with open(file_i, 'r') as open_file:
                resultDoc = json.load(open_file)

            timeslug = get_testgroup_id(file_i)
            if resultDoc['metadata'].get('test_group_id', False) is False:
                resultDoc['metadata']['test_group_id'] = timeslug

            # set the mainboard production ID to the STF result json file.
            if mb_serial is not None:
                resultDoc['metadata']['device']['dut_serial'] = mb_serial

            # Overwrite the STF result json file.
            with open(file_i, 'w') as write_file:
                json.dump(resultDoc, write_file, indent=4)

            send_report(resultDoc, config, timeslug)


def run_stf(port, host='localhost', set_name='DEgg-FAT', debug=False):
    stf.config.setIcebootOpts(host=host,
                              port=port,
                              debug=debug)
    print('Starting test run with iceboot settings:\n',
          f'\thost={host}\n',
          f'\tport={port}\n',
          f'\tdebug={debug}')

    # modify the STF config file...
    # we obtain the wire pair address & fieldHub address port.
    # getting from the D-Egg spreadsheet and evaluate each number.
    n_per_wp = MFH_SETUP_CONSTANTS.in_ice_devices_per_wire_pair
    WirePairAddr = (port - 5000) % n_per_wp
    CONFIG = get_config()
    CONFIG.settings.fieldHub['device'] = WirePairAddr
    CONFIG.settings.fieldHub['port'] = port - WirePairAddr + 1000
    result_paths = stf.run_set(set_name,
                               device_host=host,
                               device_port=port)
    return result_paths


def measure_degg(degg_file,
                 degg_dict,
                 set_name,
                 hercules_config,
                 comment,
                 run_number,
                 key):

    port = degg_dict['Port']

    mb_serial = degg_dict['MainboardNumber']
    print(f'mb_serial {mb_serial}')
    result_paths = run_stf(port, debug=False, set_name=set_name)

    meta_dict = {}
    meta_dict = add_git_infos_to_dict(meta_dict)
    meta_dict['Folder'] = result_paths[0]
    meta_dict['Comment'] = comment
    degg_dict[key] = meta_dict
    print(result_paths)
    for path in glob(f'{result_paths[0]}/*.json'):
        with open(path, 'r') as open_file:
            result = json.load(open_file)
        result['metadata']['run_number'] = int(run_number)
        print(f'Updated run_number info in {path}')
        update_json(path,result)
    update_json(degg_file, degg_dict)

    send_stf_results(result_paths, hercules_config, mb_serial)


def measure_stf(run_json, comment, n_jobs=1):
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    run_number = int(run_json.split('/')[-1].split('.json')[0].split('run_')[-1])
    print(f'run_number: {run_number}')
    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int)

    hercules_config = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../utils/configs/hercules.json'))

    set_name = 'DEgg-FAT'
    key_name = 'STF'

    for degg_dict, degg_file in zip(sorted_degg_dicts, sorted_degg_files):
        key = create_key(degg_dict, key_name)
        meta_dict = {}
        meta_dict['Folder'] = 'None'
        degg_dict[key] = meta_dict
        update_json(degg_file, degg_dict)

    aggregated_results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        set_name=set_name,
        hercules_config=hercules_config,
        comment=comment,
        run_number=run_number,
        key=key)

    for result in aggregated_results:
        print(result.result())

    for i in [6000,6004,6008,6012]:
        subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/mcu_flash_enable.py -p {i}'.split())
        subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/lid_enable.py -p {i}'.split())
        subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/pmt_hv_enable.py -p {i}'.split())


@click.command()
@click.argument('json_run_file')
@click.argument('comment')
@click.option('-j', '--n_jobs', default=4)
@click.option('--force', is_flag=True)
def main(json_run_file, comment, n_jobs, force):
    if uncommitted_changes and not force:
        raise Exception(
            'Commit changes to the repository before running a measurement! '
            'Or use --force to run it anyways.')

    if not os.path.isdir('tmp'):
        os.makedirs('tmp')
    measure_stf(json_run_file, comment, n_jobs)


if __name__ == "__main__":
    main()

##end
