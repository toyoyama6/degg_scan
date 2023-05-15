
import struct
from numpy import record

LOGIC_CAPTURE_N_WORDS   = 0x4000
LOGIC_CAPTURE_WORD_SIZE = 2

LOGIC_CAPTURE_RECORD_LEN = 1 + (LOGIC_CAPTURE_N_WORDS * LOGIC_CAPTURE_WORD_SIZE)
LOGIC_CAPTURE_FREQ_MHZ = 25.

bankNumbers = {"A": 0, 
               "B": 1,
               "C": 2,
               "D": 3,
               "E": 4,
               "F": 5,
               "G": 6,
               "H": 7}

def bankNumber(bankName):
    return bankNumbers[bankName]

def bankName(bankNumber):
    for (name, number) in bankNumbers.items():
        if number == bankNumber:
            return name
    raise KeyError(bankNumber)

def parseLogicCapture(buf):

    if len(buf) != LOGIC_CAPTURE_RECORD_LEN:
        raise Exception("Bad logic record length: %d" % len(buf))

    waveforms = {}
    for channel in range(16):
        waveforms[channel] = []

    for i in range(LOGIC_CAPTURE_N_WORDS):
        word = struct.unpack("<H", buf[1 + (2*i): 3 + (2*i)])[0]
        for channel in range(16):
            waveforms[channel].append(word & 0x1)
            word = word >> 1

    rec = {}
    for channel in range(16):
        pinName = "P%s%d" % (bankName(buf[0]), channel)
        rec[pinName] = waveforms[channel]
    return rec

def pinsortFunction(s):
    return int(''.join(ch for ch in s if ch.isdigit()))

def displayLogicCapture(record, pins=None):

    import matplotlib.pyplot as plt
    plotPins = record
    if pins is not None:
        plotPins = {}
        for pin in pins:
            plotPins[pin] = record[pin]

    xdata = [(float(i) / LOGIC_CAPTURE_FREQ_MHZ) for i in range(LOGIC_CAPTURE_N_WORDS)]
    cnt = len(plotPins.keys())
    fig = plt.figure()
    fig.patch.set_facecolor('w')
    ax1 = None
    for pin in sorted(plotPins.keys(), reverse=True, key=pinsortFunction):
        if ax1 is None:
            ax = plt.subplot(len(plotPins.keys()), 1, cnt)
            plt.xlabel("Time (us)")
            ax1 = ax
        else:
            axn = plt.subplot(len(plotPins.keys()), 1, cnt, sharex=ax1)
            plt.setp(axn.get_xticklabels(), visible=False)
        cnt -= 1
        plt.plot(xdata, plotPins[pin], 'b')
        plt.ylabel(pin, fontsize=10)
        axes = plt.gca()
        axes.set_ylim([-0.1,1.1])
        axes.get_yaxis().set_ticks([])
    plt.show()
