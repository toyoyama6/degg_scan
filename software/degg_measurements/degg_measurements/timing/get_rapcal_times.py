##taken from DESYs setup - converting for D-Eggs

""" RapCal functional test."""

import datetime
import logging
import numpy as np
import threading
import time
import click
import numpy as np
import matplotlib.pyplot as plt

##needed for icmregs
import sys
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
from icmregs import Address
from icmnet import ICMNet

from RapCal import rapcal as rp

### D-Egg specific functions #######
from degg_measurements.utils.icm_manipulation import enable_external_osc, run_rapcal
from degg_measurements.utils.icm_manipulation import enable_pmt_hv_interlock
from degg_measurements.utils.icm_manipulation import enable_gps
from degg_measurements.utils import startIcebootSession
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.utils.control_data_charge import write_chargestamp_to_hdf5
from degg_measurements.utils import MFH_SETUP_CONSTANTS

DO_RUN = False


def icm_request(icm_port, req):
    icms = ICMNet(icm_port, host='localhost')
    reply = icms.request(req)
    if reply['status'] != 'OK':
        raise RuntimeError(f'Received status "{reply["status"]}" on request "{req}"')
    if 'value' in reply:
        return int(reply['value'], 0)

def get_utc_icm_times(icm_port):
    icm_request(icm_port, f'write 8 {Address["CTRL1"]} 0x0100')
    icm_request(icm_port, 'gps_enable')
    time.sleep(1.1) # let the next PPS pass to update GPS registers
    try:
        if icm_request(icm_port, 'get_gps_ctrl') != 0x0002:
            raise RuntimeError('GPS data not valid')
        if icm_request(icm_port, 'get_gps_status') != 0x000E:
            raise RuntimeError('GPS not properly locked')
    except RuntimeError:
        print('GPS not connected! Use default settings')

    utc_time = list()
    for reg in [0x2E, 0x2D, 0x2C]:
        utc_time.append(icm_request(icm_port, f'read 8 {reg}'))
    icm_time = icm_request(icm_port, 'get_icm_time 8')
    return utc_time, icm_time


def collect_rapcal(session, lock, icm_port, rapcal_time):
    with lock:
        print("RapCal")
        rp_pair = None
        timestamps = None
        disc_offsets = None

        all_rapcals = rp.RapCalCollection()

        global DO_RUN
        while DO_RUN:
            ##this runs rapcal for all connected devices
            run_rapcal(icm_port)
            rapcal_hdr = session._read_n(4)
            header_info = rp.RapCalEvent.parse_rapcal_header(rapcal_hdr)
            packet_size = header_info.get('size')
            if packet_size:
                rapcal_pkt = session._read_n(packet_size)
            else:
                raise Exception(header_info['error'])
            event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
            event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
            all_rapcals.add_rapcal(event)

            '''
            if len(mDOM.all_rapcals.rapcals) >= 2:
                rp_pair = rp.RapCalPair(mDOM.all_rapcals.rapcals[-2], mDOM.all_rapcals.rapcals[-1], utc=mDOM.ref_utc_times[0], icm=mDOM.ref_utc_times[1])
                timestamps = mDOM.timestamps.copy()
                disc_offsets = mDOM.disc_offsets.copy()
                mDOM.timestamps = list()
                mDOM.disc_offsets = list()
            '''

            if timestamps != None:
                assert len(timestamps) == len(disc_offsets)
                for t_dom, offset in zip(timestamps, disc_offsets):
                    converted_time = rp_pair.dom2surface(t_dom, device_type='DEGG')
                    #converted_time = rp_pair.dom2surface(t_dom) + offset / (8 * rp.FPGA_CLOCK_FREQ)
                    #mDOM.timestamps_utc_sec.append(converted_time)
            time.sleep(rapcal_time)


def collect_timestamps(session, lock, filename):
    with lock:
        print("Timestamps")
        endBlock = 24
        nevents=20
        global DO_RUN
        while DO_RUN:
            block = session.DEggReadChargeBlock(0, endBlock, 14*nevents, timeout=60)
            time.sleep(10.0e-6) # TODO: sleep for 10us to give the collect_rapcal() thread a chance to run. Should eventually be replaced by a non-blocking version of mDOMReadChargeBlock()

        channels = [x for x in block.keys()]
        for channel in channels:
            records = block[channel]
            charges = [(rec.charge * 1e12) for rec in block[channel] if not rec.flags]
            timestamps = [(rec.timeStamp) for rec in block[channel] if not rec.flags]
            #deltaT = np.array([records[j+1].preciseTime() - records[j].preciseTime() for j in range(len(records)-1)])
            timestamps = np.array(timestamps)
            #timestamps = timestamps - (endBlock * 4.2e-9)
            deltaT = np.diff(timestamps)
            deltaT = deltaT / 240e6
            deltaT = np.around(deltaT, decimals=7)

        print(f"Size: {len(deltaT)}, Mean: {np.mean(deltaT)}")

        fig, ax = plt.subplots()
        ax.hist(deltaT, histtype='step')
        ax.set_xlabel('Delta T [s]')
        ax.set_ylabel('Entries')
        fig.savefig('test.pdf')

        fig2, ax2 = plt.subplots()
        ax2.plot(np.arange(len(deltaT)), deltaT, 'o')
        ax2.set_xlabel('Entry')
        ax2.set_ylabel('Delta T [s]')
        ax2.set_ylim(-8e-5, 2e-4)
        fig2.savefig('entry_vs_dt.png')

        fig3, ax3 = plt.subplots()
        ax3.plot(np.arange(len(timestamps))[:150], timestamps[:150], 'o')
        ax3.set_xlabel('Entry')
        ax3.set_ylabel('Timestamp / 240Mhz')
        fig3.savefig('entry_vs_timestamp.png')


def run(run_time, rapcal_time, make_plots=False):

    icm_ports = [6000]
    #n_per_wp = MFH_SETUP_CONSTANTS.in_ice_devices_per_wire_pair
    #n_wire_pairs = MFH_SETUP_CONSTANTS.n_wire_pairs

    ##for all relevant WPs, enable external oscillator
    for icm_port in icm_ports:
        enable_external_osc(icm_port)
        enable_gps(icm_port)
        enable_pmt_hv_interlock(icm_port)
        time.sleep(1.1) ##for PPS to send new signal
        ref_utc_times = get_utc_icm_times(icm_port)

    ## measure baseline
    #measure_baseline(run_json, constants=constants, n_jobs=n_jobs)
    #baseline_filename = degg_dict[pmt]['BaselineFilename']
    #baseline_val = float(calc_baseline(baseline_filename)['baseline'].values[0])

    filename = "test.hdf5"
    active_sessions = []

    list_of_deggs = [5007]
    for degg in list_of_deggs:
        #timestamps = list()
        #timestamps_utc_sec = list()
        #disc_offsets = list()
        #charges = list()
        port = degg
        session = startIcebootSession(host='localhost', port=port)
        ## setup channel 0
        ## injecting signal directly into MB
        pmt_threshold0 = 9000
        samples = 128
        dac_value = 30000
        session = initialize_dual(session, n_samples=samples, dac_value=dac_value,
                    high_voltage0=0, high_voltage1=0, threshold0=pmt_threshold0,
                    threshold1=10000)
        active_sessions.append(session)

    lock = threading.RLock()

    global DO_RUN
    DO_RUN = True
    #logging.info(f'Starting threads for {run_time} seconds')
    print(f'Starting threads for {run_time} seconds')
    threads = list()
    for i, session in enumerate(active_sessions):
        threads.append(threading.Thread(
                target=collect_timestamps,
                args=[session, lock, filename]))
        threads.append(threading.Thread(
                target=collect_rapcal,
                args=[session, lock, icm_ports[0], rapcal_time]))
    for t in threads:
        t.start()
    time.sleep(run_time)
    DO_RUN = False
    for t in threads:
        t.join()

    for i, session in enumerate(active_sessions):
        session.endStream()

    if make_plots:
        import matplotlib.pyplot as plt
        if len(mDOMs.mDOMs) > 1:
            for i in range(1, len(timestamps_utc_sec)):
                min_len = min(len(timestamps_utc_sec[i]), len(timestamps_utc_sec[0]))
                delta_t = (timestamps_utc_sec[i][:min_len] - timestamps_utc_sec[0][:min_len]) * 1e9
                logging.info(f'Delta-t mDOM[{i}] - mDOM[0]: mean = {np.mean(delta_t):.2f}ns, std = {np.std(delta_t):.2f}ns')

                fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
                plt.hist(delta_t, bins=500)
                plt.title(f'Time difference: mean={np.mean(delta_t):.2f}ns \n std={np.std(delta_t):.2f}ns')
                plt.xlabel('Time (in ns)')
                plt.savefig(f'delta_t_mdom{i}-mdom0.png')

                for i, mDOM in enumerate(mDOMs.mDOMs):
                    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
                    plt.hist(mDOM.charges, bins=40)
                    plt.xlabel('Charge')
                    plt.savefig(f'charge_mb{i}.png')

@click.command()
@click.argument('run_time', default=10)
@click.argument('rapcal_time', default=1)
@click.option('--make_plots', is_flag=True)
def main(run_time, rapcal_time, make_plots):
    run(run_time, rapcal_time, make_plots)

if __name__ == "__main__":
    main()

##end
