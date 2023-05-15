#!/usr/bin/env python

from iceboot.iceboot_session import getParser
from iceboot.test_waveform import parseTestWaveform
from optparse import OptionParser
import numpy as np
import tables
import matplotlib.pyplot as plt
import time
import sys
import os
import signal
import tqdm
from datetime import datetime

#################################################
from degg_measurements.utils import startIcebootSession
from degg_measurements.utils import flatten_dict
from degg_measurements.monitoring import readout_sensor
#################################################


def main():
    parser = getParser()
    parser.add_option("--channel", dest="channel",
                      help="Waveform ADC channel", default="0")
    parser.add_option("--samples", dest="samples", help="Number of samples "
                               "per waveform",  default=256)
    parser.add_option("--threshold", dest="threshold",
                      help="Apply threshold trigger instead of CPU trigger "
                           "and trigger at this level", default=None)
    parser.add_option("--adcMin", dest="adcMin",
                      help="Minimum ADC value to plot", default=None)
    parser.add_option("--adcRange", dest="adcRange",
                      help="Plot this many ADC counts above min",
                      default=None)
    parser.add_option("--filename", dest="filename", default=None)
    parser.add_option("--timeout", dest="timeout", default=10)
    parser.add_option("--nevents", dest="nevents", default=50000)
    parser.add_option("--debug", dest="debug", action="store_true",
                      help="Plot data stream", default=False)

    (options, args) = parser.parse_args()

    session = startIcebootSession(parser)
    session = initialize(session, options.channel, options.samples,
                         1400, options.threshold)
    fig, ax, line = setup_plot()

    i = 0
    while True:
        session, xdata, wf, timestamp, channel = take_waveform(session)
        time.sleep(0.2)
        if session is None:
            break
        if wf is None:
            continue
        # Fix for 0x6a firmware
        if len(wf) != options.samples:
            continue

        write_to_hdf5(options.filename, i, xdata, wf, timestamp)

        if options.debug:
            fig, ax, line = update_plot(fig, ax, line, xdata, wf)

        i += 1

        if i >= int(options.nevents):
            exit_gracefully(session)

# Define signal handler to end the stream on CTRL-C
def signal_handler(*args):
    print('\nEnding waveform stream...')
    session.endStream()
    print('Done')
    sys.exit(0)

##initialize dual PMT readout - doesn't break 1 channel inits
def initialize_dual(session, n_samples, dac_value,
                    high_voltage0, high_voltage1,
                    threshold0, threshold1, burn_in=0,
                    modHV=True):

    return initialize(session, 2, n_samples, dac_value,
                      high_voltage0, high_voltage1,
                      threshold0, threshold1, burn_in, modHV)

##generic initialize function
def initialize(session, channel, n_samples, dac_value,
               high_voltage0, high_voltage1=None,
               threshold0=None, threshold1=None, burn_in=0,
               modHV=True, verbose=True):
    burn_in = int(burn_in)
    # Number of samples must be divisible by 4
    n_samples = (int(n_samples) // 4) * 4
    if (n_samples < 16):
        raise ValueError('Number of samples must be at least 16')

    if threshold0 is None and threshold1 is not None:
        raise ValueError("Please set threshold0, or remove threshold1")

    ##FIXME - not needed anymore?
    session.cmd('.s drop')

    if int(channel) in [0, 1]:
        if verbose == True:
            print(f"Initialising readout for channel {channel}")
        session.setDEggConstReadout(int(channel), 1, int(n_samples))
        if modHV == True:
            session.enableHV(int(channel))
            session.setDEggHV(int(channel), int(high_voltage0))
        #else:
        #    print(f'<initialize> modHV == False ({channel})')
        if dac_value is not None:
            dac_channels = ['A', 'B']
            session.setDAC(dac_channels[channel], int(dac_value))
        if dac_value == None:
            raise ValueError(f'<initialize> Please configure the dac_value')

        if threshold0 is None:
            # If no threshold is passed, set the software trigger delay to 10
            session.startDEggSWTrigStream(int(channel),
                10)
        else:
            session.startDEggThreshTrigStream(int(channel),
                int(threshold0))

    if int(channel) == 2:
        if verbose == True:
            print(f"Initialising readout for PMT channels 0 & 1")
        session.setDEggConstReadout(0, 1, int(n_samples))
        session.setDEggConstReadout(1, 1, int(n_samples))
        if modHV == True:
            session.enableHV(0)
            session.setDEggHV(0, int(high_voltage0))
            session.enableHV(1)
            session.setDEggHV(1, int(high_voltage1))
        else:
            print(f'<initialize> modHV = {modHV} (DualChannel)')
        if dac_value is not None:
            session.setDAC('A', int(dac_value))
            session.setDAC('B', int(dac_value))
        if threshold0 is None or threshold1 is None:
            raise ValueError("Dual PMT readout requires 2 thresholds")
        session.startDEggDualChannelTrigStream(int(threshold0), int(threshold1))

    if int(channel) not in [0, 1, 2]:
        raise ValueError(f"Trying to initialise readout for channel {channel} - not valid.")

    if burn_in == 0:
        pass
    elif burn_in > 0:
        print(f"<initialize>: PMT burn in, waiting {burn_in} s")
        for t in tqdm.tqdm(range(burn_in), desc='Burning In'):
            time.sleep(1)
    else:
        raise ValueError("Burn in time should be a positive number (in seconds)")

    if modHV == True:
        print("<initialize> HV was enabled & set - waiting")
        time.sleep(40)
        if channel in [0, 1]:
            meas_hv = readout_sensor(session, f'voltage_channel{channel}')
            print(f'<initialize> HV measured to be: {meas_hv} V for channel {channel}')
        if channel == 2:
            meas_hv = readout_sensor(session, f'voltage_channel0')
            print(f'<initialize> HV measured to be: {meas_hv} V for channel 0')
            meas_hv = readout_sensor(session, f'voltage_channel1')
            print(f'<initialize> HV measured to be: {meas_hv} V for channel 1')
    return session


def sensibly_read_degg_charge_block(session,
                                    channel,
                                    nevents,
                                    n_per_chunk=400,
                                    n_bins_before_peak=10,
                                    n_bins_after_peak=15):
    nblocks = int(np.ceil(nevents/n_per_chunk))
    charges, timestamps = np.array([]), np.array([])
    for _ in range(nblocks):
        block = session.DEggReadChargeBlock(
            n_bins_before_peak,
            n_bins_after_peak,
            14*n_per_chunk,
            timeout=120)
        _charges = [(rec.charge * 1e12)
                    for rec in block[channel] if not rec.flags]
        _timestamps = [(rec.timeStamp)
                       for rec in block[channel] if not rec.flags]
        charges = np.append(charges, _charges)
        timestamps = np.append(timestamps, _timestamps)
    return charges, timestamps


def setup_fir_trigger(session,
                      channel,
                      dac_value,
                      threshold_over_baseline,
                      fir_coeffs=[0]*10+[1,1]+[0]*4):
    if channel not in [0, 1]:
        raise ValueError(f'Channel {channel} is not a valid option!')

    #dac_channels = ['A', 'B']
    #session.setDAC(dac_channels[channel], dac_value)
    print('Setting up the FIR trigger')
    fir_threshold = int(threshold_over_baseline*np.sum(fir_coeffs))*len(fir_coeffs)
    session.setFIRCoefficients(channel, fir_coeffs)
    session.setDEggFIRTriggerThreshold(channel, fir_threshold)
    session.enableDEggFIRTrigger(channel)

    return session

def setup_fir_dual_trigger(session,
                           n_samples,
                           dac_value,
                           threshold_over_baseline,
                           fir_coeffs=[0]*10+[1,1]+[0]*4):
    dac_channels = ['A', 'B']
    for ch in [0, 1]:
        session.setDAC(dac_channels[ch], dac_value)
        session.setFIRCoefficients(ch, fir_coeffs)
        ##TODO - I believe this is not needed here - 2022-09-16
        #session.setDEggConstReadout(ch, 1, 128)
        ##deprecated according to Jim B. 2022-08-16
        #session.enableDEggTrigger(ch)
        ##now use this 2022-09-13
        session.enableDEggADCTrigger(channel)
    threshold = int(threshold_over_baseline*np.sum(fir_coeffs))*len(fir_coeffs)
    session.startDEggDualChannelFIRTrigStream(threshold, threshold)
    return session


def setup_scalers(session, channel, high_voltage, dac_value,
                  threshold, period, deadtime, modHV=True):
    '''
    Setup scaler data taking for a given channel, period and deadtime.

    Parameters
    ----------
    session : Iceboot Session
        Iceboot session to use.
    channel : int (0, 1)
        Channel to read out.
    high_voltage : int
        High voltage to run the PMT at.
    dac_value : int
        DAC value to set the baseline.
    threshold : int
        Threshold in ADC counts to trigger the PMT.
    period : int
        Readout period in micro seconds.
    deadtime : int
        Deadtime in units of DEgg clock cycles (240 MHz).

    Returns
    -------
    session : IceBoot Session
        Returns the given Iceboot session.
    '''
    print(f'Enabling Scaler for channel {channel}, {period}microseconds, {deadtime}cycles deadtime')
    channel = int(channel)
    if channel not in [0, 1]:
        raise ValueError(f'Channel must be 0 or 1, not {channel}')
    high_voltage = int(high_voltage)
    threshold = int(threshold)
    period = int(period)
    deadtime = int(deadtime)
    dac_channels = ['A', 'B']
    if modHV == True:
        print(f'Enabling HV for channel {channel}')
        session.enableHV(channel)
        if high_voltage < 1000:
            raise ValueError(f'HV must be greater than 1000 V, not {high_voltage}')
        print(f'Setting HV for channel {channel} to {high_voltage}V')
        session.setDEggHV(channel, int(high_voltage))
        session.setDAC(dac_channels[channel], int(dac_value))

    session.setDEggTriggerConditions(channel, threshold)
    ##deprecated according to Jim B. 2022-08-16
    #session.enableDEggTrigger(channel)
    ##now use this 2022-09-13
    session.enableDEggADCTrigger(channel)
    session.enableScalers(channel, period, deadtime)
    if modHV == True:
        time.sleep(40)
    if modHV == False:
        time.sleep(0.1)

    ##check if the HV is on
    hv_read = readout_sensor(session, f'voltage_channel{channel}')
    if hv_read < 1000:
        raise ValueError(f'Readout HV is low: {hv_read} V')

    return session


def take_scalers(session, channel):
    '''
    Take scaler data for a given channel.
    Make sure to run setup_scalers() beforehand.

    Parameters
    ----------
    channel : int (0, 1)
        Channel to read out

    Returns
    -------
    session : IceBoot Session
        Returns the given Iceboot session.
    scaler_count : int
        Observed scaler count.
    '''
    n_tries_left = 3
    scaler_count = -1
    while n_tries_left >= 0:
        try:
            scaler_count = session.getScalerCount(channel)
        except ValueError as e:
            print(f'error observed in take_scalers (ch:{channel}) - {e}')
            n_tries_left -= 1
        else:
            break
    return session, scaler_count


def write_scaler_and_time_to_hdf5(filename, event_id, scaler_count, time, hv=-1, temp=-1):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            scaler_count = tables.Int32Col()
            time = tables.Float32Col()
            hv = tables.Float32Col()
            temp = tables.Float32Col()
            datetime_timestamp = tables.Float64Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/', 'data', Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        table = open_file.get_node('/data')
        event = table.row

        event['event_id'] = event_id
        event['scaler_count'] = scaler_count
        event['time'] = time
        event['hv'] = hv
        event['temp'] = temp
        event['datetime_timestamp'] = datetime.now().timestamp()
        event.append()
        table.flush()


def write_scaler_to_hdf5(filename, event_id, scaler_count):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            scaler_count = tables.Int32Col()
            datetime_timestamp = tables.Float64Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/', 'data', Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        table = open_file.get_node('/data')
        event = table.row

        event['event_id'] = event_id
        event['scaler_count'] = scaler_count
        event['datetime_timestamp'] = datetime.now().timestamp()
        event.append()
        table.flush()


def take_waveform(session):
    import traceback
    got_waveform = False
    for i in range(5):
        try:
            readout = parseTestWaveform(session.readWFMFromStream())
            pc_time = time.monotonic()
        except IOError:
            print(traceback.format_exc())
            print(f'Retry {i+1}')
            continue
        else:
            got_waveform = True
            break

    if not got_waveform:
        print('Timeout! Ending waveform stream and exiting')
        session.endStream()
        session.close()
        return None, None, None, None, None, None

    # Check for timeout
    if readout is None:
        print('Readout is None')
        return session, None, None, None, None, None
    else:
        wf = readout["waveform"]
        timestamp = readout["timestamp"]
        channel = readout["channel"]
        xdata = [x for x in range(len(wf))]
        return session, xdata, wf, timestamp, pc_time, channel


def take_waveform_block(session, name=''):
    import traceback
    got_waveform = False
    readouts = None
    for i in range(3):
        try:
            pc_time = time.monotonic()
            readouts = session.readWFBlock()
        except IOError:
            print(traceback.format_exc())
            print(f'Retry {i+1}: {name}')
            continue
        else:
            got_waveform = True
            break

    if not got_waveform:
        print('Timeout! Ending waveform stream and exiting')
        session.endStream()
        session.close()
        return None, None, None

    # Check for timeout
    if readouts is None:
        print('Readouts is None')
        return session, None, None
    else:
        return session, readouts, pc_time


def setup_plot():
    plt.ion()
    fig, ax = plt.subplots()
    ax.set_xlabel("Waveform Bin")
    ax.set_ylabel("ADC Count")
    line = None
    return fig, ax, line


def update_plot(fig, ax, line, xdata, wf):
    if not line:
        line, = ax.plot(xdata, wf, 'r-')
    else:
        line.set_ydata(wf)
    # if (options.adcMin is None or options.adcRange is None):
    wfrange = (max(wf) - min(wf))
    plt.axis([0, len(wf),
              max(wf) - wfrange * 1.2, min(wf) + wfrange * 1.2])
    # else:
    #     plt.axis([0, len(wf), int(options.adcMin),
    #               int(options.adcMin) + int(options.adcRange)])
    return fig, ax, line


def write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time):
    # Prepare hdf5 file
    if not os.path.isfile(filename):
        class Event(tables.IsDescription):
            event_id = tables.Int32Col()
            time = tables.Float32Col(
                shape=np.asarray(xdata).shape)
            waveform = tables.Float32Col(
                shape=np.asarray(wf).shape)
            timestamp = tables.Int64Col()
            pc_time = tables.Float32Col()
            datetime_timestamp = tables.Float64Col()

        with tables.open_file(filename, 'w') as open_file:
            table = open_file.create_table('/', 'data', Event)

    # Write to hdf5 file
    with tables.open_file(filename, 'a') as open_file:
        table = open_file.get_node('/data')
        #try:
        #    table = open_file.get_node('/data')
        #except:
        #    with tables.open_file(filename, 'w') as open_file:
        #        table = open_file.create_table('/', 'data', Event)
        #    table = open_file.get_node('/data')

        event = table.row
        event['event_id'] = i
        event['time'] = np.asarray(xdata, dtype=np.float32)
        event['waveform'] = np.asarray(wf, dtype=np.float32)
        event['timestamp'] = timestamp
        event['pc_time'] = pc_time
        event['datetime_timestamp'] = datetime.now().timestamp()
        event.append()
        table.flush()


def add_dict_to_hdf5(dct, filename, node_name='parameters'):
    dct = flatten_dict(dct)
    with tables.open_file(filename, 'a') as open_file:
        try:
            params = open_file.create_group(open_file.root, node_name,
                                        "Parameters used for this measurement")
        except:
            params = open_file.get_node(node_name)
        open_file.create_array(params, 'keys', list(dct.keys()))
        values = [val if not isinstance(val, list) else str(val)
                  for val in dct.values()]
        open_file.create_array(params, 'values', values)


def exit_gracefully(session):
    #print(datetime.now())
    print("Reached end of run - exiting...")
    try:
        session.endStream()
        session.close()
    except:
        print("Failed to exit cleanly...")
    else:
        print("Exiting...")
       # break


if __name__ == "__main__":
    main()
