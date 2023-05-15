from degg_measurements.utils import startIcebootSession
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, wait

import click
import os
import subprocess
import numpy as np
from scipy import stats
import time
from tqdm import tqdm

from chiba_slackbot import send_message
from chiba_slackbot import send_warning

from degg_measurements.monitoring import readout_sensor
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import create_key
from degg_measurements.utils import DEggLogBook
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils.load_dict import add_default_calibration_meas_dict
from degg_measurements.utils.hv_check import checkHV

from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs

from degg_measurements.analysis import CameraResult

from degg_measurements import DATA_DIR

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

# Globals
V_SIZE = 993
H_SIZE = 1312
CAM_HEX = {1: 0x03, 2: 0x0c, 3: 0x30}


# Helper functions
def setup_cam(session, cam):
    '''
    Resets and readies camera for measurements
    '''
    session.enableCalibrationPower()
    time.sleep(1)
    session.setCalibrationSlavePowerMask(1)
    session.setCameraEnableMask(CAM_HEX[cam])
    session.initCamera(cam)
    session.setCameraCaptureMode(cam, 0)


def cam_setting(session, cam, gain, exposure):
    '''
    Change the image setting before a capture in a clean way.
    '''
    session.setCameraSensorStandby(cam, 1)
    session.setCameraExposureMs(cam, exposure)
    session.setCameraGain(cam, gain)
    session.setCameraSensorStandby(cam, 0)


def turnoff_cam(session, cam):
    '''
    Turns off cameras safely
    '''
    session.setCameraSensorStandby(cam, 1)
    # Disables all available cameras
    session.setCameraEnableMask(0)
    session.disableCalibrationPower()


def raw_2_array(filename):
    '''
    Convert the raw image to a numpy array and save it.
    Input : raw image filename
    '''
    image = np.fromfile(filename, dtype=np.uint16, count=H_SIZE * V_SIZE) >> 4
    image = np.reshape(image, (V_SIZE, H_SIZE), 'C')

    return image[16:, 3:]

def cam_pattern(session, s_folder, cam, run_number, degg_name, logbook):
    '''
    This test captures two images for a camera with its corresponging LED
    turned on

    Parameters:
    ----------------------------------------------------------------------------
    session: An iceboot session object
    s_folder: The basefolder path where the camera folder should be created
    cam: The camera number (for D-Egg between 1 and 3)

    Output:
    ----------------------------------------------------------------------------
    '''
    print("Starting Camera pattern test for Cam {}".format(cam))

    setup_cam(session, cam)
    time.sleep(1)
    camera_id = session.getCameraID(cam)
    s_path = os.path.join(s_folder, f'{degg_name}_{camera_id}')

    ##add redundant check if exception is not getting thrown
    if not os.path.exists(s_path):
        print(f"Creating folder for camera images: {s_path}")
        try:
            os.makedirs(s_path)
        except Exception as e:
            print("Folder could not be created because of ")
            print(e)
            send_warning(e)
            raise IOError(e)
        if not os.path.exists(s_path):
            raise FileNotFoundError(f'Directory: {s_path} does not exist!')

    print(f'{degg_name}: range of 33 to 1000 ms')
    for exposure_time in tqdm([33, 100, 200, 300, 500, 1000]):
        cam_setting(session, cam, 0, exposure_time)
        session.captureCameraImage(cam)
        img_name = f'{degg_name}_{camera_id}_{exposure_time}ms.RAW'
        session.sendCameraImage(cam, os.path.join(s_path, img_name))

    print(f'{degg_name}: turn off camera')
    turnoff_cam(session, cam)

    print(f'{degg_name}: make tarball')
    # Make a tarball of the camera files
    target_dir = os.path.dirname(s_path)
    target = os.path.basename(s_path)
    outputfile = os.path.join(target_dir, target + '.tar.gz')
    cmd = [f'tar -zvcf {outputfile} -C {target_dir} {target}']
    with open(os.devnull, 'w') as devnull:
        subprocess.Popen(cmd, stdout=devnull,
                         stderr=subprocess.STDOUT, shell=True).wait()

    ##required param for the database
    temperature = readout_sensor(session, 'temperature_sensor')

    print(f'{degg_name}: create camera results')
    # # Creating final results
    result = CameraResult(
        degg_name,
        camera_id,
        logbook=logbook,
     	run_number=run_number,
        remote_path='/data/exp/IceCubeUpgrade/commissioning/camera/chiba_fat')

    print(f'{degg_name}: result to json')
    result.to_json(meas_group='focus-and-alignment',
     		   folder_name='database_jsons',
     		   raw_files=[outputfile],
                   temperature=temperature)


def run_pattern_set(session, dirname, run_number, degg_name, logbook):
    for cam in [1,2,3]:
        cam_pattern(session, dirname, cam, run_number, degg_name, logbook)


def measure_degg(degg_file, degg_dict, dirname, run_number, key, logbook):

    host = 'localhost'
    port = degg_dict['Port']
    degg_name = degg_dict['DEggSerialNumber']
    print(f'Camera Pattern: Starting iceboot session with host={host}, port={port}')
    session = startIcebootSession(host=host, port=port)

    ##ramp down HV if it's on before LEDs fire
    hvOn = 0
    for channel in [0, 1]:
        hv_enabled = checkHV(session, channel, verbose=False)
        hvOn += hv_enabled
    if hvOn != 0:
        print(f'Ramping down HV for {port}')
        session.setDEggHV(0, 0)
        session.setDEggHV(1, 0)
        session.disableHV(0)
        session.disableHV(1)
        time.sleep(20)

    hvOn = 0
    for channel in [0, 1]:
        hv_enabled = checkHV(session, channel, verbose=False)
        hvOn += hv_enabled
    if hvOn == 0:
        send_message(f'Camera Pattern Test - HV is ramped down for {port}')
    else:
        raise IOError(f'Camera Pattern Test - HV was not ramped down! {port}')

    run_pattern_set(session, dirname, run_number, degg_name, logbook)

    print('Updating json file with folder location')
    degg_dict[key]['Folder'] = dirname
    update_json(degg_file, degg_dict)
    return degg_dict


def measure_pattern(run_json, comment, n_jobs=4):
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    n_jobs = int(n_jobs)
    print(f'Measuring Camera Pattern: running with n_jobs={n_jobs}')

    measure_type = 'camera_pattern'
    dirname = create_save_dir(DATA_DIR, measure_type)
    run_number = extract_runnumber_from_path(run_json)

    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
         list_of_deggs,
         key='Port',
         key_type=int,
         return_sorting_index=False)

    key = add_default_calibration_meas_dict(
         sorted_degg_dicts,
         sorted_degg_files,
         measure_type,
         comment,
    )

    logbook = DEggLogBook()

    results = run_jobs_with_mfhs(
         measure_degg,
         n_jobs,
         degg_file=sorted_degg_files,
         degg_dict=sorted_degg_dicts,
         dirname=dirname,
         run_number=run_number,
         key=key,
         logbook=logbook
    )

@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=4)
def main(run_json, comment, n_jobs):
    measure_pattern(run_json, comment, n_jobs)


if __name__ == "__main__":
    main()
