#!/usr/bin/env python

from iceboot.iceboot_session import  startIcebootSession
from RapCal import rapcal as rp
import signal
import numpy as np
import time
import matplotlib.pyplot as plt
import sys
from icmnet import ICMNet
import datetime

set_bit_clock = {'command':'write', 'device':'8', 'register': '0x00', 'value':'256'}
check_ready_for_read = {'command':'read', 'device':'8', 'register': '0x2A'}
request_utc_time = {'command':'write', 'device':'8', 'register': '0x2A', 'value':'1'}
read_utc = {'command':'read', 'device':'8', 'register': '0x2E'}
read_icm_pps = {'command':'read', 'device':'8', 'register': '0x2F'}
utc_registers = ['0x2E', '0x2D', '0x2C', '0x2B']   
icm_pps_registers = ['0x2F', '0x30', '0x31']

          
# Signal handler
def signal_handler(sig, frame):
    sys.exit(0)

            
baseline = 3600
nsamples = 64
nmeas = 500
channels_mdoms = 22
channel_mb = 0
read_timeout = 1.0


def get_utc_icm_times(icm):
    
    reply = icm.request(set_bit_clock)
    reply = icm.request(request_utc_time)

    time.sleep(1)
    reply = icm.request(check_ready_for_read)
    
    utc_time = []
    icm_time = 0
    
    if(reply['value']=='0x0002'):
        for reg in utc_registers:
                read_utc['register'] = reg
                reply = icm.request(read_utc)
                utc_time.append(int(reply['value'], 16))
                
        for cnt, reg in enumerate(icm_pps_registers):
            read_icm_pps['register'] = reg
            reply  = icm.request(read_icm_pps)
            icm_time += int(reply['value'],16)* pow(2,cnt*16)
        
        return utc_time, icm_time
    

def main():

    signal.signal(signal.SIGINT, signal_handler)
    
    
    # Start an IceBoot session for each MFH/device
    session1 = startIcebootSession(host="localhost", port=5007)
    session2 = startIcebootSession(host="localhost", port=5015)
    
    # Start an ICMNet to talk to each MFH ICM

    icm1 = ICMNet(port=6000, host="localhost")
    icm2 = ICMNet(port=6001, host="localhost")

        
    # Turn on HV for the mDOM PMT illuminated by the LED light
    session1.mDOMEnableHV()
    time.sleep(0.1)     
    session1.mDOMUBaseQuickscan(channels_mdoms,104)
    time.sleep(20)
    print(session1.mDOMUBaseStatus(channels_mdoms))      
    
    
    #  Use MCU calibration of ADC and discriminator's baseline
    session1.mDOMCalibrateBaselines()
    session1.mDOMSetBaselines(baseline)
    # set the discriminator to 10 mV above its
    session1.mDOMSetDiscriminatorThresholds(0.01)

    session2.mDOMCalibrateBaselines()
    session2.mDOMSetBaselines(baseline)
    # set the discriminator to 10 mV above its
    session2.mDOMSetDiscriminatorThresholds(0.01)
    
    
    #  List arrays to hold timestamps
    
    utc_times_mdom = []
    icm_times_mdom = []
    utc_times_mb = []
    icm_times_mb = []  

    wfms_mdom = []
    timestamps_mdom = []
    wfms_mb = []
    timestamps_mb = []
    
    
    #  Call on the RapCal class to hold results from all the RapCal pulses
    all_rapcals_mdom = rp.RapCalCollection()
    all_rapcals_mb = rp.RapCalCollection()

    # Loop over n number of RapCal sequences / waveform acquisition
    for meas in range(nmeas):
        
        
        # Read the RAPCal for mDOM
        reply = icm1.request('rapcal 7')
        if reply['status'] != 'OK':
            raise Exception('request RapCal packet failed')
        rapcal_hdr_mDOM = session1.read_n(4, read_timeout)
        
        reply = icm2.request('rapcal 7')
        if reply['status'] != 'OK':
            raise Exception('request RapCal packet failed')
            
        # Read the RAPCal for mainboard
        rapcal_hdr_mb = session2.read_n(4, read_timeout)

        header_info = rp.RapCalEvent.parse_rapcal_header(rapcal_hdr_mDOM)
        packet_size = header_info.get('size')
        if packet_size:
            rapcal_pkt = session1.read_n(packet_size)
        else:
            raise Exception(header_info['error'])
        event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
        event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
        all_rapcals_mdom.add_rapcal(event)
        
        header_info = rp.RapCalEvent.parse_rapcal_header(rapcal_hdr_mb)
        packet_size = header_info.get('size')
        if packet_size:
            rapcal_pkt = session2.read_n(packet_size)
        else:
            raise Exception(header_info['error'])
        event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
        event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
        all_rapcals_mb.add_rapcal(event)        
        
        
        
        
        icm1_reg = get_utc_icm_times(icm1)
        icm2_reg = get_utc_icm_times(icm2)
        
        # Read the UTC time registers for each MFH's ICM
        utc_times_mdom.append(icm1_reg[0])    
        utc_times_mb.append(icm2_reg[0])
        
        # Read the internal ICM clock for each MFH's ICM
        icm_times_mdom.append(icm1_reg[1])
        icm_times_mb.append(icm2_reg[1])
      
        
        # Now acquire waveforms / timestamp for the mDOM PMT + tabletop mainboard
        session1.mDOMSetConstReadout(nsamples)
        session1.mDOMTestDiscTrigger(channels_mdoms)
        session2.mDOMSetConstReadout(nsamples)
        session2.mDOMTestDiscTrigger(channel_mb)

        readout_mdom = session1.testDEggWaveformReadout()
        readout_mb = session2.testDEggWaveformReadout()
        
        wfm_mdom  = readout_mdom['waveform']
        timestamp_mdom = readout_mdom['timestamp']
        wfm_mb  = readout_mb['waveform']
        timestamp_mb = readout_mb['timestamp']    
        
        wfms_mdom.append(wfm_mdom)
        timestamps_mdom.append(timestamp_mdom)
        wfms_mb.append(wfm_mb)
        timestamps_mb.append(timestamp_mb)           
            

    
    timestamps_utc_sec_mdom = []
    timestamps_utc_sec_mb = []
    
    # Call the RapCal class and implement equation [3.7] from IceCube-Gen1 instrumentation paper
    # https://arxiv.org/pdf/1612.05093.pdf
    # Translate a DOM timestamp -> surface timestamp -> UTC timestamp
    
    for rc0, rc1, utc, icm, t_dom in zip(all_rapcals_mdom.rapcals,all_rapcals_mdom.rapcals[1:],utc_times_mdom, icm_times_mdom,timestamps_mdom):          
        rp_pair = rp.RapCalPair(rc0,rc1,utc,icm)
        converted_time = rp_pair.dom2surface(t_dom)
        timestamps_utc_sec_mdom.append(converted_time)
        utc = datetime.datetime.fromtimestamp(converted_time)
        print(f'mDOM timestamps is {converted_time} UTC seconds, or {utc}')

    for rc0, rc1, utc, icm, t_dom in zip(all_rapcals_mb.rapcals,all_rapcals_mb.rapcals[1:],utc_times_mb, icm_times_mb,timestamps_mb):          
        rp_pair = rp.RapCalPair(rc0,rc1,utc,icm)
        converted_time = rp_pair.dom2surface(t_dom)
        utc = datetime.datetime.fromtimestamp(converted_time)

        timestamps_utc_sec_mb.append(converted_time)
        print(f'Mainboard timestamps give is {converted_time} UTC seconds, or {utc}')        
        
    timestamps_utc_sec_mb  = np.array(timestamps_utc_sec_mb) 
    timestamps_utc_sec_mdom  = np.array(timestamps_utc_sec_mdom) 
    
    
    # Now look at the time difference between the mainboard and the mDOM timestamp
    delta_t = timestamps_utc_sec_mb - timestamps_utc_sec_mdom
    
    
    # Plot the results, if you will
    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    for wfm in wfms_mdom:
        plt.plot(wfm)
    plt.title(f'Full mDOM Channel {channels_mdoms}')
    plt.xlabel('Sample number')
    plt.ylabel("ADC count")
    plt.savefig(f'wfm_pmt_{channels_mdoms}_mdom.png')
    
    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    for wfm in wfms_mb:
        plt.plot(wfm)
    plt.title(f'Full mDOM Channel {channel_mb} ')
    plt.xlabel('Sample number')
    plt.ylabel("ADC count")
    plt.savefig(f'wfm_{channel_mb}_mb.png')   
    
    
    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    plt.hist(delta_t, bins=50, range=[0,0.02])
    plt.xlim(0.0,0.02)
    plt.title('Time difference between LED trigger and photon discriminator trigger: mean=%1.3e \n std=%1.3e' %(np.mean(delta_t),np.std(delta_t)))
    plt.xlabel('Time (in s)')
    plt.ylabel("Entries")
    plt.savefig(f'delta_t_timing_setup.png')    
    
    time.sleep(3)
    session1.mDOMDisableHV()
    session1.endStream()
    session2.endStream()
    
    np.savez(file='timing_mesurement.npz', delta_t = delta_t)
    
if __name__ == "__main__":
    main()


