import sys
from math import sqrt
import numpy as np
import time


def calibrateDAC(session, count=10, nSamples=256):
    fitparams = {}
    if nSamples < 16 or nSamples % 4 != 0:
        print("Number of samples must be at least 16 and divisible by 4")
        sys.exit(1)
    for channel in [0,1]:
        session.setDEggConstReadout(channel, 1, nSamples)
        dacChannel = 'A'
        if channel == 1:
            dacChannel = 'B'

        levels = range(0, 65000, 3000)
        avs = []
        rms = []
        for dac in levels:
            session.setDAC(dacChannel, dac)
            time.sleep(0.1)
            vals = []
            for _ in range(int(count+1)):
                session.testDEggCPUTrig(int(channel))
                readout = session.testDEggWaveformReadout()
                # toss out first waveform
                if readout is None or _==0:
                    continue
                wf = readout["waveform"]
                vals.extend(wf)

            vals = np.asarray(vals)
            avs.append(vals.mean())
            rms.append(vals.std())
        y = np.asarray(levels)
        x = np.asarray(avs)
        np.seterr(divide='ignore')
        w = 1./np.asarray(rms)
        _ = (x>100) & (x<16300)
        slope, intercept = np.polyfit(x[_], y[_], 1, w=w[_],)
        r2 = 1-np.sum((y[_]-slope*x[_]-intercept)**2)/np.sum((y[_]-y[_].mean())**2)
        ### DEBUG
        # from matplotlib import pyplot as plt
        # f, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
        # ax1.errorbar(x, y, yerr=1./w, fmt='.', color='k')
        # ax1.plot(x, slope*x+intercept,
        #          label=r'{:.2g}x+{:.2g}, R2={:.4g}'.format(slope, intercept, r2))
        # plt.ylabel('DAC')
        # ax2.plot(x[_], (y[_]-slope*x[_]-intercept)*w[_])
        # plt.ylabel('pull')
        # plt.xlabel('ADC')
        # plt.legend()
        # plt.show()
        ### END
        fitparams[channel] = {"slope":slope, "intercept":intercept, "r2":r2}
    return fitparams
