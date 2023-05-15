
import struct

CHARGE_STAMP_SIZE = 14
MDOM_DISCRIMINATOR_SAMPLING_FREQ_MHZ = 120 * 8
MDOM_PRECISE_TIME_TO_NS = 1000. / MDOM_DISCRIMINATOR_SAMPLING_FREQ_MHZ

CHARGE_STAMP_BAD_WAVEFORM_FLAG           = 0x20
CHARGE_STAMP_BAD_CHARGE_FLAG             = 0x40
CHARGE_STAMP_BAD_DISCRIMINATOR_TIME_FLAG = 0x80

DEGG_CHARGE_STAMP_FLAG                   = 0x10


class mDOMChargeStamp(object):

    def __init__(self, buf):
        if len(buf) != CHARGE_STAMP_SIZE:
            raise Exception("Unexpected buffer size: %d" % len(buf))
        self.version = int(buf[0] & 0x0F)
        if (self.version == 0):
            self.parseVersion0(buf)
        else:
            raise Exception("Unknown charge stamp version: %d" % self.version)

    def parseVersion0(self, buf):
        self.channel = int(buf[1] & 0x1F)
        self.flags = int(buf[1] & 0xE0)
        self.discriminatorOffset = struct.unpack("<H", buf[2:4])[0]
        self.timeStamp = ((int(buf[4]))       |
                          (int(buf[5]) << 8)  |
                          (int(buf[6]) << 16) |
                          (int(buf[7]) << 24) |
                          (int(buf[8]) << 32) |
                          (int(buf[9]) << 40) |
                          (int(buf[0] & 0x80) << 41))
        self.charge = struct.unpack("f", buf[10:])[0]

    def preciseTime(self):
        return (self.timeStamp << 3) + self.discriminatorOffset


class DEggChargeStamp(object):

    def __init__(self, buf):
        if len(buf) != CHARGE_STAMP_SIZE:
            raise Exception("Unexpected buffer size: %d" % len(buf))
        self.version = int(buf[0] & 0x0F)
        if (self.version == 0):
            self.parseVersion0(buf)
        else:
            raise Exception("Unknown charge stamp version: %d" % self.version)

    def parseVersion0(self, buf):
        self.channel = int(buf[1] & 0x03)
        self.flags = int(buf[1] & 0xE0)
        self.discriminatorOffset = struct.unpack("<H", buf[2:4])[0]
        self.timeStamp = ((int(buf[4]))       |
                          (int(buf[5]) << 8)  |
                          (int(buf[6]) << 16) |
                          (int(buf[7]) << 24) |
                          (int(buf[8]) << 32) |
                          (int(buf[9]) << 40) |
                          (int(buf[0] & 0xC0) << 42))
        self.charge = struct.unpack("f", buf[10:])[0]


def parseChargeStampBlock(buf):
    idx = 0
    ret = {}
    while idx + CHARGE_STAMP_SIZE <= len(buf):
        rec = buf[idx:idx + CHARGE_STAMP_SIZE]
        cs = None
        if rec[0] & DEGG_CHARGE_STAMP_FLAG:
            cs = DEggChargeStamp(rec)
        else:
            cs = mDOMChargeStamp(rec)
        if cs.channel not in ret:
            ret[cs.channel] = []
        ret[cs.channel].append(cs)
        idx += CHARGE_STAMP_SIZE
    return ret