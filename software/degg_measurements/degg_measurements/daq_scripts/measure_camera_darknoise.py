from degg_measurements.utils import startIcebootSession
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, wait
import matplotlib.pyplot as plt

import click
import os
import subprocess
import numpy as np
import pandas as pd
from scipy import stats
import time
from datetime import datetime
from tqdm import tqdm

from chiba_slackbot import send_warning

from degg_measurements import DB_JSON_PATH

from degg_measurements.daq_scripts.multi_processing import run_jobs_with_mfhs

from degg_measurements.monitoring import readout_sensor

from degg_measurements.utils import DEggLogBook
from degg_measurements.utils import create_save_dir
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import create_key
from degg_measurements.utils.load_dict import add_default_calibration_meas_dict
from degg_measurements.utils import sort_degg_dicts_and_files_by_key
from degg_measurements.utils import extract_runnumber_from_path
from degg_measurements.utils.hv_check import checkHV

from degg_measurements.analysis import CameraResult

from degg_measurements import DATA_DIR

try:
    from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101
except ImportError:
    raise ValueError('The library function_generators is missing! Go check!')# WARNING:

# Globals
V_SIZE = 993
H_SIZE = 1312
CAM_HEX = {1: 0x01, 2: 0x04, 3: 0x10}


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

##suggested fix from Christoph
def Get_Majority_camera_id(session, cam):
  camera_id = [session.getCameraID(cam) for i in range(10)]
  return max(set(camera_id), key = camera_id.count)

def cam_darknoise(session, degg_name, port, s_folder, cam, gain, exposure_time, n_images, run_number, key, logbook, plot=False):
    '''
    This test captures n_images for a specific gain and exposure time settings
    and saves them in the specified save folder and runs analysis on them.

    Parameters:
    ----------------------------------------------------------------------------
    session: An iceboot session object
    s_folder: The basefolder path where the camera folder should be created
    cam: The camera number (for D-Egg between 1 and 3)
    gain: The gain value in units of 0.1dB (between 0 and 300)
    exposure_time: The exposure time value in ms (between 33 and 3700)
    n_images: The amount of images to be captured (standard is 30)
    plot: Flag to set for debug histogram of all mean pixel values

    Output:
    ----------------------------------------------------------------------------
    darknoise_mean: The mean of all mean pixel values (also known as pedestal)
    darknoise_std: The mean of all pixel standard deviations
    hotpixel_amount: Amount of pixel that are above 5 sigma in 50% of images
    darknoise_mean_99pct: The 99 percentile of all pedestal values
    darknoise_std_99pct: The 99 percentile of all pixel standard deviations.
    '''
    print(f"Camera Darknoise test: Gain {gain}, Exposure time {exposure_time}")
    print(f"Setting up camera {cam} for port {port}")

    ##required param for the database
    temperature = readout_sensor(session, 'temperature_sensor')

    setup_cam(session, cam)
    cam_setting(session, cam, gain, exposure_time)

    session.setCalSPIFastMode()

    print("Sleep for 3 seconds after setup?")
    time.sleep(1)
    camera_id = Get_Majority_camera_id(session, cam)

    s_path = os.path.join(s_folder,
                          f'{degg_name}_{camera_id}_{gain}_{exposure_time}')
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

    img_array = np.zeros((n_images, 977, 1309), dtype=np.uint16)
    stamp = int(time.time())
    print("Taking {} images".format(n_images))

    transfer_times = []
    for i in tqdm(range(n_images), desc='Taking Images'):

        now = datetime.now().timestamp()
        session.captureCameraImage(cam)
        img_name = '{}_{}_{}_{}_{}ms_{}.RAW.gz'.format(degg_name, camera_id,
                                                       stamp, gain, exposure_time, i)
        img_name_path = os.path.join(s_path, img_name)
        session.sendCameraImage(cam, img_name_path)
        try:
            img_array[i, :, :] = raw_2_array(img_name_path)
        except ValueError:
            print(f'ValueError with Port:{port} Cam:{cam}, trying to recover')

        later = datetime.now().timestamp()
        transfer_times.append(later - now)

    session.setCalSPISlowMode()
    turnoff_cam(session, cam)

    print(f"Transfer times for port {port}, camera {cam}: {transfer_times}")
    data = {'Port': [port]*len(transfer_times),
            'Camera': [cam]*len(transfer_times),
            'TransferTimes': transfer_times}
    df = pd.DataFrame(data=data)
    df.to_hdf(os.path.join(s_path,
                           f'transfer_time_{port}_{cam}_{gain}_{exposure_time}.hdf5'),
              key='df', mode='w')

    mean_img = np.mean(img_array, axis=0)
    median_img = np.median(img_array, axis=0)
    std_img = np.std(img_array, axis=0)
    hp_mask = img_array > (np.mean(img_array, axis=(1, 2))[:, None, None]
                           + 5*np.std(img_array, axis=(1, 2))[:, None, None])
    hp_pos = np.where(np.sum(hp_mask, axis=0) > hp_mask.shape[0]*0.5)

    # Saving aggregate images to npy files for later upload
    savestr = '{}_{}_{}_{}_{}ms.npy'.format(degg_name, camera_id, stamp, gain, exposure_time)
    np.save(s_path + 'DN_mean_' + savestr, mean_img)
    np.save(s_path + 'DN_median_' + savestr, median_img)
    np.save(s_path + 'DN_std_' + savestr, std_img)

    # Creating pedestal hist
    brange = [max(0, np.mean(mean_img)-3*np.std(mean_img)), min(4096, np.mean(mean_img)+3*np.std(mean_img))]
    pedestal_hist_vals, pedestal_bins = np.histogram(mean_img.flatten(), bins="auto", range=brange)
    pedestal_hist = [pedestal_bins[0], pedestal_bins[-1], len(pedestal_bins)-1, pedestal_hist_vals, "Pixel pedestal value"]

    # Creating noise hist
    brange = [max(0, np.mean(std_img)-3*np.std(std_img)), min(4096, np.mean(std_img)+3*np.std(std_img))]
    noise_hist_vals, noise_bins = np.histogram(std_img.flatten(), bins="auto", range=brange)
    noise_hist = [noise_bins[0], noise_bins[-1], len(noise_bins)-1, noise_hist_vals, "Pixel darknoise value"]

    # Make a tarball of the camera files
    target_dir = os.path.dirname(s_path)
    target = os.path.basename(s_path)
    outputfile = os.path.join(target_dir, target + '.tar.gz')
    cmd = [f'tar -zvcf {outputfile} -C {target_dir} {target}']
    with open(os.devnull, 'w') as devnull:
        subprocess.Popen(cmd, stdout=devnull,
                         stderr=subprocess.STDOUT, shell=True).wait()

    # Creating final results
    result = CameraResult(
        degg_name,
        camera_id,
	logbook=logbook,
    	run_number=run_number,
    	remote_path='/data/exp/IceCubeUpgrade/commissioning/camera/chiba_fat')


    result.to_json(meas_group='darknoise',
                   filename_add=f'{degg_name}_{key}_Gain_{gain/10}dB_Exposure_time_{exposure_time}ms',
    		   raw_files=[outputfile],
                   folder_name=DB_JSON_PATH,
    		   mean_darknoise=np.mean(std_img),
    		   mean_pedestal=np.mean(mean_img),
                   darknoise_error=np.std(std_img),
    		   n_hotpixel=len(hp_pos[0]),
    		   mean_99pct=np.percentile(mean_img, 99),
    		   std_99pct=np.percentile(std_img, 99),
    		   gain=gain,
    		   exposure_time=exposure_time,
                   pedestal_hist=pedestal_hist,
                   noise_hist=noise_hist,
                   temperature=temperature)

def run_darknoise_set(session, degg_name, port, dirname, run_number, key, logbook, plot):
    ##time bottle-neck is transfer speeds, not taking the image
    ##estimated time is ~10 images for 5 min.
    #n_images = 20
    for cam in [1,2,3]:
        for setting in [(0,33),(0,200),(0,500),(0,3700),(120,3700),(30,3700)]:
            if setting[1] == 3700:
                n_images = 10
            else:
                n_images = 30
            cam_darknoise(session, degg_name, port, dirname, cam,
                          setting[0], setting[1], n_images,
                          run_number, key, logbook, plot)

def measure_degg(degg_file, degg_dict, dirname, run_number, key, logbook, plot):
    host = 'localhost'
    port = degg_dict['Port']
    degg_name = degg_dict['DEggSerialNumber']
    print(f'Camera Dark Noise Test: Starting iceboot sessions with host={host}, port={port}')
    now = datetime.now()
    print(f'Time: {now}')
    session = startIcebootSession(host=host, port=port)

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
        print('HV disabled!')

    hv0 = readout_sensor(session, 'voltage_channel0')
    hv1 = readout_sensor(session, 'voltage_channel1')
    if hv0 > 1000 or hv1 > 1000:
        raise ValueError(f'HV is still on! {hv0} V & {hv1} V!')

    run_darknoise_set(session, degg_name, port, dirname, run_number, key, logbook, plot)
    degg_dict[key]['Folder'] = dirname
    update_json(degg_file, degg_dict)
    return degg_dict


def measure_camera(run_json, comment, n_jobs=4, plot=False, test=False):
    ##get function generator - turn laser off
    fg = FG3101()
    fg.disable()

    n_jobs = int(n_jobs)

    measure_type = 'camera_darknoise'
    dirname = create_save_dir(DATA_DIR, measure_type)

    run_number = extract_runnumber_from_path(run_json)

    logbook = DEggLogBook()

    list_of_deggs = load_run_json(run_json)
    sorted_degg_files, sorted_degg_dicts = sort_degg_dicts_and_files_by_key(
        list_of_deggs,
        key='Port',
        key_type=int,
        return_sorting_index=False)

    key = add_default_calibration_meas_dict(
        degg_dicts=sorted_degg_dicts,
        degg_files=sorted_degg_files,
        meas_key=measure_type,
        comment=comment,
    )

    if test == True:
        print("RUNNING IN TEST MODE!")
        measure_degg(sorted_degg_files[0], sorted_degg_dicts[0], dirname, run_number, key, logbook, plot=True)
        exit(1)

    results = run_jobs_with_mfhs(
        measure_degg,
        n_jobs,
        degg_file=sorted_degg_files,
        degg_dict=sorted_degg_dicts,
        dirname=dirname,
        run_number=run_number,
        key=key,
        logbook=logbook,
        plot=plot
    )

    print("Done")

@click.command()
@click.argument('run_json')
@click.argument('comment')
@click.option('--n_jobs', '-j', default=4)
@click.option('--plot', '-p', is_flag=True)
@click.option('--test', is_flag=True)
def main(run_json, comment, n_jobs, plot, test):
    measure_camera(run_json, comment, n_jobs, plot, test)


if __name__ == "__main__":
    main()
