import time
import numpy as np


def set_dac(session, channel, dac_val):
    dac_channel_dict = {0:'A', 1:'B'}
    session.setDAC(dac_channel_dict[channel], dac_val)
    time.sleep(0.1)


def set_fepulser_dac(session, channel, dac_val_fepulser):
    session.enableFEPulser(channel,200)
    session.setDAC('D', dac_val_fepulser)
    time.sleep(0.1)
    

def get_baseline_waveform(session, channel):
    session.testDEggCPUTrig(channel)
    readout = session.testDEggWaveformReadout()
    return np.asarray(readout['waveform'])


def get_waveform(session, channel, baseline_wv):
    """ Enables FEPulser in appropriate channel and returns baseline-subtracted ADC waveform
    """
    baseline = np.mean(baseline_wv)
    std = np.std(baseline_wv)

    thres = baseline+std*20
    session.testDEggThresholdTrig(channel, int(thres))
    readout = session.testDEggWaveformReadout()
    return np.asarray(readout["waveform"])-baseline


def get_pulser_charge(session, channel, baseline_wv, bins_before_peak, bins_after_peak):
    """ Returns integrated ADC counts around peak of pulse
    """
    wf = get_waveform(session, channel, baseline_wv)
    return np.sum(wf[wf.argmax()-bins_before_peak:wf.argmax()+bins_after_peak+1])
