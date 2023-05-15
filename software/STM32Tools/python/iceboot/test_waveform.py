import json
import numpy as np

class Rev90Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 2
    FPGA_TEST_WF_HEADER_WORDS     = 6
    FPGA_TEST_WF_FOOTER_WORDS     = 2

class Rev91Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 2
    FPGA_TEST_WF_HEADER_WORDS     = 8
    FPGA_TEST_WF_FOOTER_WORDS     = 2

class Rev92Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 2
    FPGA_TEST_WF_HEADER_WORDS     = 8
    FPGA_TEST_WF_FOOTER_WORDS     = 2

class Rev82Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 1
    FPGA_TEST_WF_HEADER_WORDS     = 17
    FPGA_TEST_WF_FOOTER_WORDS     = 2

class Rev81Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 1
    FPGA_TEST_WF_HEADER_WORDS     = 13
    FPGA_TEST_WF_FOOTER_WORDS     = 2

class Rev80Stats():
    FPGA_TEST_WF_WORDS_PER_SAMPLE = 2
    FPGA_TEST_WF_HEADER_WORDS     = 6
    FPGA_TEST_WF_FOOTER_WORDS     = 2

def getStats(version):
    if version == 0x80:
        return Rev80Stats()
    if version == 0x81:
        return Rev81Stats()
    if version == 0x82:
        return Rev82Stats()
    if version == 0x90:
        return Rev90Stats()
    if version == 0x91:
        return Rev91Stats()
    if version == 0x92:
        return Rev92Stats()
    raise Exception("Unknown waveform version: %s" % version)

def waveformNWords(l, version):
    stats = getStats(version)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    return (l * stats.FPGA_TEST_WF_WORDS_PER_SAMPLE + overhead)

def waveformLength(nw, version):
    stats = getStats(version)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    return int((nw - overhead) // stats.FPGA_TEST_WF_WORDS_PER_SAMPLE)

def parse80(args):
    stats = getStats(0x80)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["waveformLength"] = waveformLength(len(args), 0x80)
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["header1"] = int(args[1])
    wf["header0"] = int(args[2])
    wf["timestamp"] = (int(args[5]) | 
                           (int(args[4]) << 16) | (int(args[3]) << 32))
    wf["waveform"] =  np.array(args[7:-2:2])  >> 2
    wf["thresholdFlags"] = (np.array(args[7:-2:2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parse81(args):
    stats = getStats(0x81)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["waveformLength"] = waveformLength(len(args), 0x81)

    wf["header1"] = int(args[1])
    wf["header0"] = int(args[2])
    wf["timestamp"] = (int(args[5]) |
                           (int(args[4]) << 16) | (int(args[3]) << 32))
    wf["patternLenWord"] = int(args[6])
    wf["patternValid"] = bool(args[7] & 0x8000)
    wf["pattern"] = [0]*4
    wf["pattern"][0] = int(args[7] & 0x7FFF) << 8
    wf["pattern"][0] |= int(args[8] & 0xFF00) >> 8
    wf["pattern"][1] = int(args[8] & 0x00FF) << 15
    wf["pattern"][1] |= int(args[9] & 0xFFFE) >> 1
    wf["pattern"][2] = int(args[9] & 0x0001) << 22
    wf["pattern"][2] |= int(args[10]) << 6
    wf["pattern"][2] |= int(args[11] & 0xFC00) >> 10
    wf["pattern"][3] = int(args[11] & 0x03FF) << 13
    wf["pattern"][3] |= int(args[12]) >> 3
    wf["waveform"] =  np.array(args[13:-2]) >> 2
    wf["thresholdFlags"] = (np.array(args[13:-2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parse82(args):
    stats = getStats(0x82)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["waveformLength"] = waveformLength(len(args), 0x82)

    wf["header1"] = int(args[1])
    wf["header0"] = int(args[2])
    wf["syncReady"] = bool(args[2] & 0x100)
    wf["timestamp"] = ( ((int(args[2]) >> 6) & 0x3) | int(args[5]) << 2 |
                           (int(args[4]) << 18) | (int(args[3]) << 34))
    wf["chargeStamp"] = (int(args[7]) | int(args[6]) << 16)
    wf["chargeStampTime"] = (int(args[9]) | int(args[8]) << 16)
    wf["patternLenWord"] = int(args[10])
    wf["patternValid"] = bool(args[11] & 0x8000)
    wf["pattern"] = [0]*4
    wf["pattern"][0] = int(args[11] & 0x7FFF) << 8
    wf["pattern"][0] |= int(args[12] & 0xFF00) >> 8
    wf["pattern"][1] = int(args[12] & 0x00FF) << 15
    wf["pattern"][1] |= int(args[13] & 0xFFFE) >> 1
    wf["pattern"][2] = int(args[13] & 0x0001) << 22
    wf["pattern"][2] |= int(args[14]) << 6
    wf["pattern"][2] |= int(args[15] & 0xFC00) >> 10
    wf["pattern"][3] = int(args[15] & 0x03FF) << 13
    wf["pattern"][3] |= int(args[16]) >> 3
    wf["waveform"] =  np.array(args[17:-2]) >> 2
    wf["thresholdFlags"] = (np.array(args[17:-2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parse90(args):
    stats = getStats(0x90)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["waveformLength"] = waveformLength(len(args), 0x90)
    wf["header1"] = int(args[1])
    wf["preConfigCnt"] = (int(args[2]) & 0xF800) >> 11
    wf["const"] = bool(int(args[2]) & 0x400)
    wf["syncReady"] = bool(args[2] & 0x8)
    wf["triggerSource"] = int(args[2]) & 0x3
    wf["timestamp"] = ((int(args[2]) & 0x0004) >> 2 |
                               (int(args[5]) << 1) |
                               (int(args[4]) << 17) |
                               (int(args[3]) << 33))
    wf["waveform"] =  np.array(args[6:-2:2]) & 0xFFF
    wf["discWords"] =  np.array(args[7:-2:2]) >> 8
    wf["thresholdFlags"] =  (np.array(args[7:-2:2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parse91(args):
    stats = getStats(0x91)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["waveformLength"] = waveformLength(len(args), 0x91)
    wf["header1"] = int(args[1])
    wf["preConfigCnt"] = (int(args[2]) & 0xF800) >> 11
    wf["const"] = bool(int(args[2]) & 0x400)
    wf["syncReady"] = bool(args[2] & 0x8)
    wf["triggerSource"] = int(args[2]) & 0x3
    wf["timestamp"] = ((int(args[2]) & 0x0004) >> 2 |
                               (int(args[5]) << 1) |
                               (int(args[4]) << 17) |
                               (int(args[3]) << 33))
    wf["baselineSumValid"] = bool(int(args[6]) & 0x8000)
    wf["baselineSumLength"] = 1 << ((int(args[6]) & 0x7000) >> 12)
    wf["baselineSum"] = ((int(args[6]) & 0x0007) << 16 | int(args[7]))
    wf["waveform"] =  np.array(args[8:-2:2]) & 0xFFF
    wf["discWords"] =  np.array(args[9:-2:2]) >> 8
    wf["thresholdFlags"] =  (np.array(args[9:-2:2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parse92(args):
    stats = getStats(0x92)
    overhead = (stats.FPGA_TEST_WF_HEADER_WORDS +
                stats.FPGA_TEST_WF_FOOTER_WORDS)
    if len(args) < overhead:
        return None
    wf = {}
    wf["version"] = (int(args[0]) >> 8) & 0xFF
    wf["channel"] = int(args[0]) & 0xFF
    wf["waveformLength"] = waveformLength(len(args), 0x92)
    wf["header1"] = int(args[1])
    wf["preConfigCnt"] = (int(args[2]) & 0xF800) >> 11
    wf["const"] = bool(int(args[2]) & 0x400)
    wf["lc"] = bool(int(args[2]) & 0x200)
    wf["syncReady"] = bool(args[2] & 0x8)
    wf["triggerSource"] = int(args[2]) & 0x3
    wf["timestamp"] = ((int(args[2]) & 0x0004) >> 2 |
                               (int(args[5]) << 1) |
                               (int(args[4]) << 17) |
                               (int(args[3]) << 33))
    wf["baselineSumValid"] = bool(int(args[6]) & 0x8000)
    wf["baselineSumLength"] = 1 << ((int(args[6]) & 0x7000) >> 12)
    wf["baselineSum"] = ((int(args[6]) & 0x0007) << 16 | int(args[7]))
    wf["waveform"] =  np.array(args[8:-2:2]) & 0xFFF
    wf["discWords"] =  np.array(args[9:-2:2]) >> 8
    wf["thresholdFlags"] =  (np.array(args[9:-2:2]) >> 1) & 0x1
    wf["footer1"] = int(args[-2])
    wf["footer0"] = int(args[-1])
    return wf

def parseTestWaveform(args):
    if len(args) == 0:
        return None
    version = (int(args[0]) >> 8) & 0xFF
    if version == 0x80:
        return parse80(args)
    if version == 0x81:
        return parse81(args)
    if version == 0x82:
        return parse82(args)
    if version == 0x90:
        return parse90(args)
    if version == 0x91:
        return parse91(args)
    if version == 0x92:
        return parse92(args)
    raise Exception("Unknown waveform version: %s" % version)


def applyPatternSubtraction(wf):
    if wf["version"] not in [0x81, 0x82]:
        raise Exception("Pattern subtraction not supported for "
                        "version %s" % wf["version"])
    pattern = [0]*4
    for i in range(4):
        pattern[i] = float(wf["pattern"][i]) / (1 << wf["patternLenWord"])
    correctedWF = [0.] * len(wf["waveform"])
    patternStart = wf["timestamp"] % 4
    for i in range(len(wf["waveform"])):
        correctedWF[i] = (float(wf["waveform"][i]) -
                                  pattern[(patternStart + i) % 4])
    wf["waveform"] = np.array(correctedWF)


def deNumpy(wf):
    wf["waveform"] = [int(x) for x in wf["waveform"]]
    wf["thresholdFlags"] = [int(x) for x in wf["thresholdFlags"]]
    return wf


def reNumpy(wf):
    wf["waveform"] = np.array(wf["waveform"])
    wf["thresholdFlags"] = np.array(wf["thresholdFlags"])
    return wf


def writeWaveformFile(wfs, fileName):
    with open(fileName, "w") as f:
        json.dump([deNumpy(x) for x in wfs], f)
    
def loadWaveformFile(fileName):
    with open(fileName, "r") as f:
        return [reNumpy(x) for x in json.load(f)]
