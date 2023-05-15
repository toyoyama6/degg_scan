from .test_waveform import parseTestWaveform, waveformNWords
import sys
import numpy as np
import time


def make_hist(session,
              channel,
              nbins,
              start,
              width,
              threshold_over_baseline,
              bins_before_peak,
              bins_after_peak,
              enable_fepulser=True):
    nSamples = 256
    nCounts = 1000
    adc_to_v = lambda a: (2 * a) / (16384.)
    v_to_c = lambda v: v/50./(240e6)
    c_to_picoc = lambda c: c/1e-12
    c_to_pe = lambda c: c/1.60217733e-19
    
    session.setDEggConstReadout(channel, 1, nSamples)
    # measure baseline
    session.testDEggCPUTrig(channel)
    readout = session.testDEggWaveformReadout()
    baseline = np.mean(readout['waveform'])

    if enable_fepulser:
        print('Enabling FEPulser for channel {}'.format(channel))
        session.enableFEPulser(channel,2)

    charges = []
    thres = baseline+threshold_over_baseline
    for _ in range(nCounts):
        session.testDEggThresholdTrig(channel, int(thres))
        readout = session.testDEggWaveformReadout()
        wf = np.asarray(readout["waveform"])-baseline
        ### DEBUG
        # plt.plot(range(len(wf)), wf-baseline)
        # plt.show()
        ### END
        charges.append(v_to_c(adc_to_v(
            np.sum(wf[wf.argmax()-bins_before_peak:wf.argmax()+bins_after_peak+1]))))
    ### DEBUG
    # from matplotlib import pyplot as plt
    # plt.figure()
    # plt.hist(c_to_picoc(np.asarray(charges)), bins=nbins,
    #          range=(start, start+width*nbins), histtype='step')
    # plt.xlabel('pC')
    # plt.show()
    ## end
    h, _ = np.histogram(c_to_picoc(np.asarray(charges)), bins=nbins,
                        range=(start, start+width*nbins))
    return {'hist':h, 'nbins':nbins, 'min':start, 'width':width}
