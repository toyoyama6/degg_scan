
import struct

# Hardware type ID
PDOM_BOARD_TYPE      = 0x0
DEGG_REV3_BOARD_TYPE = 0x1B00
DEGG_BOARD_TYPE      = 0x0100
MDOM_BOARD_TYPE      = 0x0200

# Interlock flags
FLASH_INTERLOCK_BIT = 0x10
FPGA_INTERLOCK_BIT  = 0x20
LID_INTERLOCK_BIT   = 0x40
HV_INTERLOCK_BIT    = 0x80


def decodeString(ba):
    for i in range(len(ba)):
        if ba[i] == 0:
            return ba[:i].decode()
    raise Exception("Error: Received non-terminated string: %s" % ba)


# Parse a binary flash LS record into a dictionary
def parseFlashLSRecord(data):
    datalen = struct.unpack("<H", data[0:2])[0]
    if datalen != len(data):
        raise Exception("Received FlashLS record with incorrect length.  "
                        "Got %d bytes, expected %d" % (len(data), datalen))
    ptr = 2
    out = []
    while ptr < len(data):
        filename = decodeString(data[ptr:ptr + 32])
        ptr += 32
        fsize = struct.unpack("<I", data[ptr:ptr + 4])[0]
        ptr += 4
        fsector = struct.unpack("<B", data[ptr:ptr + 1])[0]
        ptr += 1
        out.append({"Name": filename, "Size": fsize, "Sector": fsector})
    return out

# Parse an accelerometer record into a dictionary
ACCELEROMETER_RECORD_SIZE = 28
def parseAccelerometerRecord(data):
    if len(data) != ACCELEROMETER_RECORD_SIZE:
        raise Exception("Accelerometer record: expected %d bytes, got %d" % (
                                        ACCELEROMETER_RECORD_SIZE, len(data)))
    out = {}
    out["x"] = struct.unpack("<d", data[0:8])[0]
    out["y"] = struct.unpack("<d", data[8:16])[0]
    out["z"] = struct.unpack("<d", data[16:24])[0]
    out["temperature"] = struct.unpack("<f", data[24:28])[0]
    return out

# Parse a magnetometer record into a dictionary
MAGNETOMETER_RECORD_SIZE = 28
def parseMagnetometerRecord(data):
    if len(data) != MAGNETOMETER_RECORD_SIZE:
        raise Exception("Magnetometer record: expected %d bytes, got %d" % (
                                        MAGNETOMETER_RECORD_SIZE, len(data)))
    out = {}
    out["x"] = struct.unpack("<d", data[0:8])[0]
    out["y"] = struct.unpack("<d", data[8:16])[0]
    out["z"] = struct.unpack("<d", data[16:24])[0]
    out["temperature"] = struct.unpack("<f", data[24:28])[0]
    return out

# Parse a pressure sensor record into a dictionary
PRESSURE_SENSOR_RECORD_SIZE = 12
def parsePressureSensorRecord(data):
    if len(data) != PRESSURE_SENSOR_RECORD_SIZE:
        raise Exception("Pressure record: expected %d bytes, got %d" % (
                                        PRESSURE_SENSOR_RECORD_SIZE, len(data)))
    out = {}
    out["pressure"] = struct.unpack("<d", data[0:8])[0]
    out["temperature"] = struct.unpack("<f", data[8:12])[0]
    return out

# Format a uint16 data array as a little-endian byte array
def LE16Pack(data):
    pkt = bytearray()
    for x in data:
        pkt.extend(struct.pack("<H", x))
    return pkt

# Format a little-endian byte array as a uint16 data array
def LE16Unpack(ba):
    data = []
    for i in range(0, len(ba), 2):
        data.append(struct.unpack("<H", ba[i:i+2])[0])
    return data