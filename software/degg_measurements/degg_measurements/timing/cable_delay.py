from tqdm import tqdm
from datetime import datetime, timedelta
import time
import sys
import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

#sys.path.append("/home/icecube/Workspace/Software/fh_server_cmake/scripts")
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet
from degg_measurements.utils import startIcebootSession
from RapCal import rapcal as rp
from degg_measurements.utils.icm_manipulation import enable_external_osc
from degg_measurements.utils.icm_manipulation import run_rapcal, run_rapcal_all

###If you run with independent, the RapCal pairs will be separated
##like (0, 1) (2, 3) (4, 5)
##If you run normally, they are paired (0, 1) (1, 2) (2, 3)

@click.command()
@click.option("--plotting", "-p", is_flag=True)
@click.option("--independent", "-i", is_flag=True)
@click.option('--richards', '-r', is_flag=True)
def main(independent, plotting, richards):
    device = input('which? DEgg/MB:')
    ports = []
    if device == 'DEgg':
        COMMAND_PORT=6000
        ports.append(5007)
        data_dir = '~/data/cable_delay/DEgg/'        
    elif device == 'MB':
        COMMAND_PORT=6008
        ports.append(5011)
        data_dir = '~/data/cable_delay/MB/'        
    icms = ICMNet(COMMAND_PORT, host='localhost')

    sessions = []
    for port in ports:
        session = startIcebootSession(port=port, host='localhost')
        sessions.append(session)
        time.sleep(0.25)

    icms.request('write 8 0 0x0100')
    time.sleep(1.1) # let the next PPS pass to update GPS registers
    icms.request('write 8 0 0x0100')
    time.sleep(1.1) # let the next PPS pass to update GPS registers

    icm_time = icms.request('get_icm_time 8')['value']


    ##do you only want to measure on 1 module?
    print('Measuring on only 1 module')
    i = 0
    for port, session in zip(ports, sessions):
        measure(icms, 10, data_dir, tag="int", session=session, port=port,
                rapcal_icm=icm_time, plotting=plotting, independent=independent,
                richards=richards)
        i += 1
        if i > 0:
            break

    for session in sessions:
        session.endStream()
        session.close()
        del session
        time.sleep(0.25)

    print("Finished")

def measure(icms, n_rapcal, data_dir, tag, session, port, rapcal_icm, plotting, independent,
            richards=False):

    sleep_time = 1.0 #s

    all_rapcals = rp.RapCalCollection()

    dom_wfs = []
    dor_wfs = []
    dom_tx = []
    dor_tx = []
    dom_rx = []
    dor_rx = []
    dom_trigger = []
    dor_trigger = []
    fit_type_list = []

    rapcal_utc = [datetime.now().timestamp(), 0, 0]

    if independent == False:
        for i in tqdm(range(n_rapcal)):
            icms.request("rapcal_all")
            if len(all_rapcals.rapcals) >= 2:
                rp_pair = rp.RapCalPair(all_rapcals.rapcals[-2], all_rapcals.rapcals[-1],
                            utc=rapcal_utc, icm=rapcal_icm)

            ##get rapcal info
            header_info = rp.RapCalEvent.parse_rapcal_header(session.read_n(4))
            rapcal_pkt = session.read_n(header_info['size'])
            if not header_info.get('size'):
                raise Exception(header_info['error'])
            event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
            if richards == True:
                event.analyze(rp.RapCalEvent.ALGO_RICHARD_FIT)
            else:
                event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
            all_rapcals.add_rapcal(event)

            dom_wfs.append(event.dom_waveform)
            dom_tx.append(event.T_tx_dom/60e6)
            dom_rx.append(event.T_rx_dom/60e6)
            dom_trigger.append(event.dom_trigger)
            dor_wfs.append(event.dor_waveform)
            dor_tx.append(event.T_tx_dor/60e6)
            dor_rx.append(event.T_rx_dor/60e6)
            dor_trigger.append(event.dor_trigger)
            time.sleep(sleep_time)

        stats = all_rapcals.get_rapcal_stats(gaussian_fit=False)
        cable_delay = all_rapcals.delays
        unpaired_delays = []
        for i, d in enumerate(cable_delay):
            if i == 0:
                unpaired_delays.append(d)
            if i % 2 == 0 and i != 0:
                unpaired_delays.append(d)

        epsilons = all_rapcals.epsilons
        np.append(epsilons, np.nan)
        data = {'cableDelay': unpaired_delays, 'clockDrift': epsilons}
        df = pd.DataFrame(data=data)
        df.to_hdf(f'{data_dir}/rapcal_ana_{port}.hdf5', key='df', mode='w')
        print("Created RapCal Ana Information HDF5 File")

    if independent == True:
        epsilons = []
        delays = []
        these_rapcals = rp.RapCalCollection()
        for i in tqdm(range(n_rapcal)):
            icms.request("rapcal_all")
            ##get rapcal info
            header_info = rp.RapCalEvent.parse_rapcal_header(session.read_n(4))
            rapcal_pkt = session.read_n(header_info['size'])
            if not header_info.get('size'):
                raise Exception(header_info['error'])
            event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
            if richards == True:
                event.analyze(rp.RapCalEvent.ALGO_RICHARD_FIT)
                fit_type = event.fitResult
            else:
                event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
                fit_type = 'lienar'
            fit_type_list.append(fit_type)

            these_rapcals.add_rapcal(event)
            if len(these_rapcals.rapcals) == 2:
                rp_pair = rp.RapCalPair(these_rapcals.rapcals[-2], these_rapcals.rapcals[-1],
                            utc=rapcal_utc, icm=rapcal_icm,
                            utc_is_seconds=True,
                            icm_is_base16=True)
                these_rapcals = rp.RapCalCollection()
                epsilons.append(rp_pair.epsilon)
                delays.append([rp_pair.cable_delays[0], rp_pair.cable_delays[1]])

            dom_wfs.append(event.dom_waveform)
            dom_tx.append(event.T_tx_dom/60e6)
            dom_rx.append(event.T_rx_dom/60e6)
            dom_trigger.append(event.dom_trigger)
            dor_wfs.append(event.dor_waveform)
            dor_tx.append(event.T_tx_dor/60e6)
            dor_rx.append(event.T_rx_dor/60e6)
            dor_trigger.append(event.dor_trigger)
            time.sleep(sleep_time)

        data = {'cableDelay': delays, 'clockDrift': epsilons}
        df = pd.DataFrame(data=data)
        if richards == True:
            df.to_hdf(f'{data_dir}/rapcal_ana_independent_richard_{port}.hdf5', key='df', mode='w')
        else:
            df.to_hdf(f'{data_dir}/rapcal_ana_independent_linear_{port}.hdf5', key='df', mode='w')
        print("Created RapCal Ana Information HDF5 File")

    data = {'dom_wf': dom_wfs, 'dor_wf': dor_wfs, 'dom_tx': dom_tx, 'dor_tx': dor_tx,
            'dom_rx': dom_rx, 'dor_rx': dor_rx, 'dom_trig': dom_trigger, 'dor_trig': dor_trigger,
            'fit': fit_type_list}
    df = pd.DataFrame(data=data)
    if independent == True:
        df.to_hdf(f'{data_dir}/rapcal_dom_dor_wfs_independent_{port}.hdf5', key='df', mode='w')
    else:
        df.to_hdf(f'{data_dir}/rapcal_dom_dor_wfs_{port}.hdf5', key='df', mode='w')
    print("Created RapCal WF Information HDF5 File")

    if plotting == True:

        fig_wf_dom, ax_wf_dom = plt.subplots()
        fig_wf_dor, ax_wf_dor = plt.subplots()
        min_plotted = False
        mid_plotted = False
        max_plotted = False

        for i, delay in enumerate(cable_delay):
            #min range
            if abs(delay) <= 18.5e-9 and min_plotted == False:
                ax_wf_dom.plot(np.arange(len(dom_wfs[i]))/60e6, dom_wfs[i], label=f'Min')
                ax_wf_dor.plot(np.arange(len(dor_wfs[i]))/60e6, dor_wfs[i], label=f'Min')
                min_plotted = True
            #mid range
            if abs(delay) > 20.5e-9 and abs(delay) < 21e-9 and mid_plotted == False:
                ax_wf_dom.plot(np.arange(len(dom_wfs[i]))/60e6, dom_wfs[i], label=f'Mid')
                ax_wf_dor.plot(np.arange(len(dor_wfs[i]))/60e6, dor_wfs[i], label=f'Mid')
                mid_plotted = True
            #high range
            if abs(delay) >= 22.6e-9 and max_plotted == False:
                ax_wf_dom.plot(np.arange(len(dom_wfs[i]))/60e6, dom_wfs[i], label=f'Max')
                ax_wf_dor.plot(np.arange(len(dor_wfs[i]))/60e6, dor_wfs[i], label=f'Max')
                max_plotted = True

            if min_plotted == True and mid_plotted == True and max_plotted == True:
                break

        fig1, ax1 = plt.subplots()
        ax1.hist(cable_delay, bins=50, histtype='step')
        ax1.set_xlabel('Cable Delay [s]')
        ax1.set_ylabel('Entries')
        fig1.savefig(f'cable_delay_{port}_{tag}.pdf')
        plt.close(fig1)

        fig1a, ax1a = plt.subplots()
        ax1a.hist(epsilons, bins=50, histtype='step')
        ax1a.set_xlabel('Clock Drift [s]')
        ax1a.set_ylabel('Entries')
        fig1a.savefig(f'clock_drift_{port}_{tag}.pdf')
        plt.close(fig1a)

        fig1b, ax1b = plt.subplots()
        ax1b.hist(dom_rx, bins=50, histtype='step', color='royalblue', label='DOM')
        ax1b.hist(dor_rx, bins=50, histtype='step', color='goldenrod', label='DOR')
        ax1b.set_xlabel('Receive Time [s]')
        ax1b.set_ylabel('Entries')
        ax1b.legend()
        fig1b.savefig(f'dom_dor_rx_{port}_{tag}.pdf')
        plt.close(fig1b)

        fig1c, ax1c = plt.subplots()
        ax1c.hist(dom_tx, bins=50, histtype='step', color='royalblue', label='DOM')
        ax1c.hist(dor_tx, bins=50, histtype='step', color='goldenrod', label='DOR')
        ax1c.set_xlabel('Transmit Time [s]')
        ax1c.set_ylabel('Entries')
        ax1c.legend()
        fig1c.savefig(f'dom_dor_tx_{port}_{tag}.pdf')
        plt.close(fig1c)

        fig2, ax2 = plt.subplots()
        ax2.plot(np.arange(len(cable_delay)), cable_delay, 'o')
        ax2.set_xlabel('Event #')
        ax2.set_ylabel('Cable Delay [s]')
        fig2.savefig(f'cable_delay_event_{port}_{tag}.png')
        plt.close(fig2)

        fig2a, ax2a = plt.subplots()
        ax2a.plot(np.arange(len(epsilons)), epsilons, 'o')
        ax2a.set_xlabel('Event #')
        ax2a.set_ylabel('Clock Drift [s]')
        fig2a.savefig(f'clock_drift_event_{port}_{tag}.png')
        plt.close(fig2a)

        fig2b, ax2b = plt.subplots()
        ax2b.plot(np.arange(len(dom_rx)), dom_rx, 'o', color='royalblue', label='DOM')
        ax2b.plot(np.arange(len(dor_rx)), dor_rx, 'o', color='goldenrod', label='DOR', alpha=0.6)
        ax2b.set_xlabel('Event #')
        ax2b.set_ylabel('Receive Time [s]')
        ax2b.legend()
        fig2b.savefig(f'dom_dor_rx_event_{port}_{tag}.png')
        plt.close(fig2b)

        fig2c, ax2c = plt.subplots()
        ax2c.plot(np.arange(len(dom_rx))[:100], dom_rx[:100], 'o', color='royalblue', label='DOM')
        ax2c.plot(np.arange(len(dor_rx))[:100], dor_rx[:100], 'o', color='goldenrod', label='DOR', alpha=0.6)
        ax2c.set_xlabel('Event #')
        ax2c.set_ylabel('Receive Time [s]')
        ax2c.legend()
        fig2c.savefig(f'dom_dor_rx_event_zoom_{port}_{tag}.png')
        plt.close(fig2c)

        fig2bi, ax2bi = plt.subplots()
        ax2bi.plot(np.arange(len(dom_tx)), dom_tx, 'o', color='royalblue', label='DOM')
        ax2bi.plot(np.arange(len(dor_tx)), dor_tx, 'o', color='goldenrod', label='DOR', alpha=0.6)
        ax2bi.set_xlabel('Event #')
        ax2bi.set_ylabel('Transmit Time [s]')
        ax2bi.legend()
        fig2bi.savefig(f'dom_dor_tx_event_{port}_{tag}.png')
        plt.close(fig2bi)

        fig2ci, ax2ci = plt.subplots()
        ax2ci.plot(np.arange(len(dom_tx))[:100], dom_tx[:100], 'o', color='royalblue', label='DOM')
        ax2ci.plot(np.arange(len(dor_tx))[:100], dor_tx[:100], 'o', color='goldenrod', label='DOR', alpha=0.6)
        ax2ci.set_xlabel('Event #')
        ax2ci.set_ylabel('Transmit Time [s]')
        ax2ci.legend()
        fig2ci.savefig(f'dom_dor_tx_event_zoom_{port}_{tag}.png')
        plt.close(fig2ci)

        fig3, ax3 = plt.subplots()
        ax3.plot(np.arange(len(dom_wfs[0]))/60e6, dom_wfs[10], 'o', label='DOM')
       #ax3.plot(np.arange(len(dor_wfs[0]))/60e6, dor_wfs[10], 'o', label='DOR')
        ax3.set_xlabel('Time [s]')
        ax3.set_ylabel('ADC')
        ax3.legend()
        fig3.savefig(f'dom_dor_wf_{port}_{tag}.png')
        plt.close(fig3)

        ax_wf_dom.set_xlabel('Time [s]')
        ax_wf_dor.set_xlabel('Time [s]')
        ax_wf_dom.set_ylabel('ADC')
        ax_wf_dor.set_ylabel('ADC')
        ax_wf_dom.legend(title='Delay Time')
        ax_wf_dor.legend(title='Delay Time')
        fig_wf_dom.savefig(f'dom_wfs_{port}_{tag}.png')
        fig_wf_dor.savefig(f'dor_wfs_{port}_{tag}.png')
        plt.close(fig_wf_dom)
        plt.close(fig_wf_dor)

if __name__ == "__main__":
    main()

##end
