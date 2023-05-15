import os, sys
from glob import glob
import click

from degg_measurements.utils import load_run_json, load_degg_dict
from degg_measurements.utils.load_dict import audit_ignore_list

from chiba_slackbot import send_message, send_warning

def camera_file_checker(run_json, skip_copy=False):
    ##check for the dark rate
    ##and pattern files

    meas_names = ['camera_darknoise', 'camera_pattern']

    valid_paths = ['', '']

    ignoreList = [0, 0]
    total_count = [0, 0]

    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        for i, measurement in enumerate(meas_names):
            ##get the latest one
            ##(should usually only be 1 or there was a problem)
            m_num = 0
            while True:
                data_key_to_use = measurement + f'_{m_num:02d}'
                try:
                    data_path = degg_dict[data_key_to_use]['Folder']
                    m_num += 1
                    if m_num >= 10:
                        print('Problem finding {data_path}')
                        exit(1)
                except:
                    break

            if audit_ignore_list(degg_file, degg_dict, data_key_to_use,
                                 analysis=True) == True:
                ignoreList[i] += 1
                continue

            if data_path != None:
                valid_paths[i] = data_path

            if measurement == 'camera_darknoise':
                glob_str = os.path.join(data_path, degg_dict['DEggSerialNumber'] + '*0_200.tar.gz')
            elif measurement == 'camera_pattern':
                glob_str = os.path.join(data_path, degg_dict['DEggSerialNumber'] + '*.tar.gz')

            fileList = glob(f'{glob_str}')
            if len(fileList) != 3:
                ##some or all files are missing
                ##if data_path is none, the measurement crashed/exited
                ##before updating the json file -- try and find it from another module
                if data_path == None:
                    for _degg_file in list_of_deggs:
                        _degg_dict = load_degg_dict(_degg_file)
                        data_path = _degg_dict[data_key_to_use]['Folder']
                        if data_path != None:
                            break
                    ##try finding the files again
                    if measurement == 'camera_darknoise':
                        glob_str = os.path.join(data_path,
                                                degg_dict['DEggSerialNumber'] + '*0_200.tar.gz')
                    elif measurement == 'camera_pattern':
                        glob_str = os.path.join(data_path,
                                                degg_dict['DEggSerialNumber'] + '*.tar.gz')
                    fileList = glob(f'{glob_str}')

                degg_name = degg_dict['DEggSerialNumber']
                warn_str = f'{degg_name} is missing files for camera (N_found={len(fileList)}).\n'
                if data_path == None:
                    warn_str = f'\t Path to files is none, error during data taking. \n '
                if data_path != None:
                    warn_str = warn_str + f'\t Check path: {data_path}.\n '
                warn_str = warn_str + f'\t See: {measurement}. \n'
                warn_str = warn_str + '\t Please log this event.'
                print(warn_str)
                send_warning(warn_str)
            total_count[i] += len(fileList)

    for j in [0, 1]:
        total_deggs = (16 - ignoreList[j])
        num_active_cams = (3 * total_deggs)
        if num_active_cams == total_count[j]:
            msg_str = f'{meas_names[j]} - All camera files found!'
            print(msg_str)
            send_message(msg_str)
        else:
            msg_str = f'{meas_names[j]} - {total_count[j]} / {num_active_cams} found'
            print(msg_str)
            send_message(msg_str)

    if skip_copy == True:
        print('Skipping Copying Files - Done')
        exit(1)

    ##upload files - DAQ will be briefly paused
    send_message('DAQ paused - uploading camera files')

    for data_path, measurement in zip(valid_paths, meas_names):
        script = '/home/scanbox/software/camera_helper/camera_copy_data.py'
        if measurement == 'camera_darknoise':
            arg = 'darknoise'
        if measurement == 'camera_pattern':
            arg = 'pattern'
        try:
            os.system(f'python3 {script} {data_path} {arg}')
            send_message(f'Copying finished: {measurement}')
        except:
            warn_str = f'Error copying camera files {measurement}. Copy manually. \n'
            warn_str = warn_str + f'Run python3 {script} {data_path} {arg}'
            print(warn_str)
            send_warning(warn_str)

    print('Done')

@click.command()
@click.argument('run_json')
@click.option('--skip_copy', '-s', is_flag=True)
def main(run_json, skip_copy):
    camera_file_checker(run_json, skip_copy)

if __name__ == "__main__":
    main()
##end
