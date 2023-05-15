import numpy as np
import pandas as pd
import os, sys
import traceback
import time

##for interface with chiba-daq slack channel

SENSOR_TO_VALUE = {
    'light_sensor': 6,
    'temperature_sensor': 7,
    'pressure_sensor': np.nan,
    'voltage_channel0': 8,
    'voltage_channel1': 10,
    'reflash_count': -1,
    'current_channel0': 9,
    'current_channel1': 11,
    'magnetometer_x': -1,
    'magnetometer_y': -1,
    'magnetometer_z': -1,
    'accelerometer_x': -1,
    'accelerometer_y': -1,
    'accelerometer_z': -1,
    'magnetometer_temp': -1,
    'accelerometer_temp': -1
}


def readout_sensor(session, sensor):
    if sensor == 'reflash_count':
        return -1
    if sensor == 'magnetometer_x':
        try:
            return session.readMagnetometerXYZ()[0]
        except:
            print("Error reading magnetometer (x)")
            return -1
    if sensor == 'magnetometer_y':
        try:
            return session.readMagnetometerXYZ()[1]
        except:
            print("Error reading magnetometer (y)")
            return -1
    if sensor == 'magnetometer_z':
        try:
            return session.readMagnetometerXYZ()[2]
        except:
            print("Error reading magnetometer (z)")
            return -1
    if sensor == 'accelerometer_x':
        try:
            return session.readAccelerometerXYZ()[0]
        except:
            print("Error reading accelerometer (x)")
            return -1
    if sensor == 'accelerometer_y':
        try:
            return session.readAccelerometerXYZ()[1]
        except:
            print("Error reading accelerometer (y)")
            return -1
    if sensor == 'accelerometer_z':
        try:
            return session.readAccelerometerXYZ()[2]
        except:
            print("Error reading accelerometer (z)")
            return -1

    if sensor == 'magnetometer_temp':
        try:
            return session.readMagnetometerTemperature()
        except:
            print("Error reading magnetometer temp")
            return -1
    if sensor == 'accelerometer_temp':
        try:
            return session.readAcceleromterTemperature()
        except:
            print("Error reading acceleromter temp")
            return -1
    if sensor == 'pressure':
        try:
            return session.readPressure()
        except ValueError:
            return -1

    channel_no = SENSOR_TO_VALUE[sensor]
    if np.isfinite(channel_no):
        try:
            value = session.sloAdcReadChannel(channel_no)
        except IndexError:
            return -1
        except IOError as io_error:
            print(io_error)
            print(session.comms.__str__())
            string = session.comms.__str__()
            split = string.split(",")
            print(split[4])
            return -1
        except AttributeError:
            if session is None:
                print("session object is none! - cannot get sloAdcReadChannel()")
                return -1
            else:
                print("AttributeError!")
    return value


def readout(session, reflash_count, filename):
    '''
    Parameters
    ----------
    session : IceBoot Session
    filename : str
        Filename to save the sensor data to.

    Returns
    -------
    session : IceBoot Session
        Returns the given IceBoot Session.
    '''
    measured_values = dict()

    df = pd.DataFrame()
    index = pd.to_datetime([pd.Timestamp.now()])
    index.name = 'Local time'

    for key in SENSOR_TO_VALUE.keys():
        if key == 'reflash_count':
            val = reflash_count
            df[key] = pd.Series(val, index=index)
            continue
        try:
            val = readout_sensor(session, key)
        except ValueError:
            val = np.nan
        df[key] = pd.Series(val, index=index)

    if not os.path.isfile(filename):
        df.to_csv(filename, mode='w', header=True)
    else:
        existing_df = pd.read_csv(filename, index_col='Local time')
        df = existing_df.append(df)
        df.to_csv(filename, mode='w', header=True)
    return session


def reboot(session, firmware_version='degg_fw_v0x10e.rbf'):
    '''
    Reboot the DEgg and confirm the reboot by putting the FPGA
    version on the iceboot stack and check the stack after the
    reboot.
    '''
    session.cmd('fpgaVersion')
    before_reboot = session.cmd('.s')

    try:
        session.reboot()
        time.sleep(1)
    except:
        send_critical("@channel CRITICAL: Reboot failed!")
        print(traceback.format_exc())

    after_reboot = None
    reconfigured = False
    fails = 0
    while reconfigured == False:
        try:
            session.bypassBootloader()
            time.sleep(2)
            #session.cmd(f's" {firmware_version}" flashConfigureCycloneFPGA', timeout=10)
            output = session.flashConfigureCycloneFPGA(firmware_version)
            print(output)
            reconfigured = True
            session.cmd('fpgaVersion')
            after_reboot = session.cmd('.s')
        except TimeoutError:
            print("Timeout during FPGA flash from reboot!")
            fails += 1
        except:
            print("Error during FPGA flash from reboot!")
            print(traceback.format_exc())
            send_message(traceback.format_exc())
            fails += 1
        if fails >= 3:
            send_warning("Failed to reconfigure FPGA 3 (or more) times in a row!")
            break

    print(f"Starting Version:{before_reboot} \n Reconfigured Version:{after_reboot}")

    return fails


def get_fpga_version(session):
     out = session.cmd('fpgaVersion .s drop')
     print(out)
     return session


def set_degg_hv_zero(session):
    channels = [0, 1]
    for channel in channels:
        session.disableHV(channel)
        out = session.setDEggHV(channel, int(0))
    return session

