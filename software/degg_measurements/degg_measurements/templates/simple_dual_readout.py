from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from optparse import OptionParser
from iceboot.test_waveform import parseTestWaveform
import os, sys
import numpy as np
from tqdm import tqdm
import time

from sensors import get_sensor_info

def main():
    parser = getParser()
    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)
    
    hv_ch0 = 1464
    hv_ch1 = 1374
    set_hv(session, hv_ch0, hv_ch1)

    wf_pre_padding = 1
    wf_size = 32
    configure_readout(session, 0, wf_pre_padding, wf_size)
    configure_readout(session, 1, wf_pre_padding, wf_size)

    dac_value = 30000
    set_dac(session, 0, dac_value)
    set_dac(session, 1, dac_value)

    ch0_baseline = 7913
    ch1_baseline = 8050
    ch0_threshold = 1000 + ch0_baseline
    ch1_threshold = 1000 + ch1_baseline
    start_dual_trigger_stream(session, ch0_threshold, ch1_threshold)
    
    num_waveforms = 1000
    name = "colton"
    f = open(os.path.expandvars(
        f"$HOME/workshop/{name}/dual_channel_output.txt"), "w+")
    take_data(session, num_waveforms, f)

    f.close()
    session.endStream()

def set_hv(session, hv_ch0=0, hv_ch1=0):
    session.setDEggHV(0, 0)
    session.setDEggHV(1, 0)
    session.enableHV(0)
    session.enableHV(1)
    session.setDEggHV(0, 0)
    session.setDEggHV(1, 0)

    ##use function from previous script
    get_sensor_info(session)

    session.setDEggHV(0, hv_ch0)
    session.setDEggHV(1, hv_ch1)

    time.sleep(10)

    get_sensor_info(session)

def configure_readout(session, channel=-1, wf_pre_padding=1, wf_size=16):
    ##wf_size max = 1024
    if wf_size > 1024:
        raise ValueError("Waveform Size cannot be larger than 1024")
    session.setDEggConstReadout(channel, wf_pre_padding, wf_size)

def set_dac(session, channel=-1, dac_value=30000):
    #DAC has channels A & B
    #mapping to PMT channels
    #A --> 0, B --> 1
    if channel == 0:
        session.setDAC('A', dac_value)
        return True
    if channel == 1:
        session.setDAC('B', dac_value)
        return True
    return False

def start_dual_trigger_stream(session, ch0_threshold=1000, ch1_threshold=1000):
    session.startDEggDualChannelTrigStream(ch0_threshold, ch1_threshold)

def take_data(session, num_waveforms, f):
    for num in tqdm(range(num_waveforms)):
        readout = parseTestWaveform(session.readWFMFromStream())
        wf = readout['waveform']
        chan = readout['channel']
        mb_timestamp = readout['timestamp']
        wf_max = np.max(wf)
        wf_baseline = np.median(wf)

        ##values have to be strings
        wf_max = str(wf_max)
        wf_baseline = str(wf_baseline)
        chan = str(chan)
        mb_timestamp = str(mb_timestamp)
        data_string = chan + ", " + wf_max + ", " + wf_baseline + ", " + mb_timestamp + '\n'
        f.write(data_string)

if __name__ == "__main__":
    main()

##end
