#!/usr/bin/env python

# ymodem.py: YModem send over TCP socket

from __future__ import print_function
import socket
import os
import ctypes
from select import select
from optparse import OptionParser
from contextlib import contextmanager
import sys


# crctab calculated by Mark G. Mendel, Network Systems Corporation
crctab = [
    0x0000,  0x1021,  0x2042,  0x3063,  0x4084,  0x50a5,  0x60c6,  0x70e7,
    0x8108,  0x9129,  0xa14a,  0xb16b,  0xc18c,  0xd1ad,  0xe1ce,  0xf1ef,
    0x1231,  0x0210,  0x3273,  0x2252,  0x52b5,  0x4294,  0x72f7,  0x62d6,
    0x9339,  0x8318,  0xb37b,  0xa35a,  0xd3bd,  0xc39c,  0xf3ff,  0xe3de,
    0x2462,  0x3443,  0x0420,  0x1401,  0x64e6,  0x74c7,  0x44a4,  0x5485,
    0xa56a,  0xb54b,  0x8528,  0x9509,  0xe5ee,  0xf5cf,  0xc5ac,  0xd58d,
    0x3653,  0x2672,  0x1611,  0x0630,  0x76d7,  0x66f6,  0x5695,  0x46b4,
    0xb75b,  0xa77a,  0x9719,  0x8738,  0xf7df,  0xe7fe,  0xd79d,  0xc7bc,
    0x48c4,  0x58e5,  0x6886,  0x78a7,  0x0840,  0x1861,  0x2802,  0x3823,
    0xc9cc,  0xd9ed,  0xe98e,  0xf9af,  0x8948,  0x9969,  0xa90a,  0xb92b,
    0x5af5,  0x4ad4,  0x7ab7,  0x6a96,  0x1a71,  0x0a50,  0x3a33,  0x2a12,
    0xdbfd,  0xcbdc,  0xfbbf,  0xeb9e,  0x9b79,  0x8b58,  0xbb3b,  0xab1a,
    0x6ca6,  0x7c87,  0x4ce4,  0x5cc5,  0x2c22,  0x3c03,  0x0c60,  0x1c41,
    0xedae,  0xfd8f,  0xcdec,  0xddcd,  0xad2a,  0xbd0b,  0x8d68,  0x9d49,
    0x7e97,  0x6eb6,  0x5ed5,  0x4ef4,  0x3e13,  0x2e32,  0x1e51,  0x0e70,
    0xff9f,  0xefbe,  0xdfdd,  0xcffc,  0xbf1b,  0xaf3a,  0x9f59,  0x8f78,
    0x9188,  0x81a9,  0xb1ca,  0xa1eb,  0xd10c,  0xc12d,  0xf14e,  0xe16f,
    0x1080,  0x00a1,  0x30c2,  0x20e3,  0x5004,  0x4025,  0x7046,  0x6067,
    0x83b9,  0x9398,  0xa3fb,  0xb3da,  0xc33d,  0xd31c,  0xe37f,  0xf35e,
    0x02b1,  0x1290,  0x22f3,  0x32d2,  0x4235,  0x5214,  0x6277,  0x7256,
    0xb5ea,  0xa5cb,  0x95a8,  0x8589,  0xf56e,  0xe54f,  0xd52c,  0xc50d,
    0x34e2,  0x24c3,  0x14a0,  0x0481,  0x7466,  0x6447,  0x5424,  0x4405,
    0xa7db,  0xb7fa,  0x8799,  0x97b8,  0xe75f,  0xf77e,  0xc71d,  0xd73c,
    0x26d3,  0x36f2,  0x0691,  0x16b0,  0x6657,  0x7676,  0x4615,  0x5634,
    0xd94c,  0xc96d,  0xf90e,  0xe92f,  0x99c8,  0x89e9,  0xb98a,  0xa9ab,
    0x5844,  0x4865,  0x7806,  0x6827,  0x18c0,  0x08e1,  0x3882,  0x28a3,
    0xcb7d,  0xdb5c,  0xeb3f,  0xfb1e,  0x8bf9,  0x9bd8,  0xabbb,  0xbb9a,
    0x4a75,  0x5a54,  0x6a37,  0x7a16,  0x0af1,  0x1ad0,  0x2ab3,  0x3a92,
    0xfd2e,  0xed0f,  0xdd6c,  0xcd4d,  0xbdaa,  0xad8b,  0x9de8,  0x8dc9,
    0x7c26,  0x6c07,  0x5c64,  0x4c45,  0x3ca2,  0x2c83,  0x1ce0,  0x0cc1,
    0xef1f,  0xff3e,  0xcf5d,  0xdf7c,  0xaf9b,  0xbfba,  0x8fd9,  0x9ff8,
    0x6e17,  0x7e36,  0x4e55,  0x5e74,  0x2e93,  0x3eb2,  0x0ed1,  0x1ef0]


def calcCrc(buf):
    crc = 0
    for b in buf:
        crc = (crctab[((crc >> 8) & 255)] ^ (crc << 8) ^ b) & 0xFFFF
    return crc


SOH = 0x01
STX = 0x02
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
SYNC = 0x43
SOH_DATASZ = 128
STX_DATASZ = 1024


def getBlockSize(blkType):
    datasz = STX_DATASZ
    if blkType == SOH:
        datasz = SOH_DATASZ
    return datasz


def quit(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    raise Exception()


def getChar(fd, timeout):
    # Read the first character from the device
    # If no data is available, return None
    (rarr, warr, xarr) = select([fd], [], [], timeout)
    if len(rarr) == 0:
        return None
    # We have at least one byte
    try:
        ret = os.read(fd, 1)        
        if ret is None or len(ret) == 0:
            return None
        c = ret[0]
        try:
            # this will raise a TypeError in Python3
            c = ord(c)
        except TypeError:
            pass
        return c
    except:
        return None
    
    
def getAck(fd, ch, skipSync=False):
    c = getChar(fd, 10)

    if skipSync and c == SYNC:
        return getAck(fd, ch, skipSync)
    if c == CAN:
        quit("Fatal error in file transfer")
    if c != ch:
        quit("Did not get expected char %s" % hex(ch))
        
        
def sendBlock(fd, blkType, blkno, data, verbose):

    blk = bytearray()
    blk.append(blkType)
    blkNoByte = blkno & 0xFF
    blk.append(blkNoByte)
    blk.append((~blkNoByte) & 0xFF)
    # Pad the data with zeroes to fill the block.  Include zeroes for CRC16
    data.extend(bytearray([0x0]) * (getBlockSize(blkType) + 2 - len(data)))

    blk.extend(data)

    # Calculate CRC
    crc16 = calcCrc(data)
    blk[-2] = (crc16 >> 8) & 0xFF
    blk[-1] = crc16 & 0xFF
    if verbose:
        print("Sending block %d" % blkno)
    if os.write(fd, bytearray(blk)) < len(blk):
        quit("Error sending block")
    if blkno == 0:
        # First block may contain a stray SYNC or two
        getAck(fd, ACK, True)
    else:
        getAck(fd, ACK)


def sendByte(fd, b):
    o = bytearray()
    o.append(b)
    if os.write(fd, o) != 1:
        quit("Error sending data")


@contextmanager
def getSocketFD(host, port):
    print("Opening socket to %s:%s" % (host, port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    sock.setblocking(0)
    try:
        yield sock.fileno()
    finally:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()


@contextmanager
def getFileFD(devFile):
    print("Opening file %s" % devFile)
    with open(devfile, os.O_RDWR|os.O_NONBLOCK) as f:
        yield f.fileno()


def loadFile(infile):
    if not os.path.exists(infile):
        quit("File %s does not exist" % infile)
    content = None
    with open(infile, "rb") as f:
        fsz = os.fstat(f.fileno()).st_size
        print("Opening file %s: %s bytes" % (os.path.basename(infile), fsz))
        # Don't send anything over 32 MB
        if fsz > (32 * 1024 * 1024):
            quit("File %s is too large" % infile)
        return f.read()


@contextmanager
def getFD(device, host, port):
    if device is None:
        with getSocketFD(host, port) as fd:
            yield fd
    else:
        with getFileFD(devFile) as fd:
            yield fd


def ymodemSendContent(fd, content, filename, verbose=True):

    # Drain any data in input buffer:
    while True:
        try:    
            read = os.read(fd, 4096)
            if len(read) == 0:
                break
        except (IOError, OSError):
            break
    
    # Do handshake
    getAck(fd, SYNC)

    # OK, receiver is listening (probably).  Send the first block
    # containing filename and data size
    data = bytearray()
    data.extend(filename[:100].encode())
    data.append(0x0)
    data.extend(("%d " % len(content)).encode())
    blkno = 0
    sendBlock(fd, SOH, blkno, data, verbose)
    blkno += 1

    # YModem will send another 'C'
    getAck(fd, SYNC)

    # Send the remainder
    while True:
        data = bytearray(content[(blkno - 1) * STX_DATASZ : blkno * STX_DATASZ])
        if len(data) == 0:
            break
        sendBlock(fd, STX, blkno, data, verbose)
        blkno += 1

    # End transmission
    sendByte(fd, EOT)
    getAck(fd, NAK)
    sendByte(fd, EOT)
    getAck(fd, ACK)
    getAck(fd, SYNC)
    sendBlock(fd, SOH, 0, [], verbose)
    getAck(fd, SYNC)

    return 0


def ymodemImpl(fd, infile, verbose=True):

    content = loadFile(infile)
    return  ymodemSendContent(fd, content, os.path.basename(infile), verbose)


def main():
    
    p = OptionParser()
    p.add_option("--host", dest="host",
                 default="192.168.0.10", help="Remote host IP address")
    p.add_option("--port", dest="port",
                 default="5012", help="Remote port number")
    p.add_option("--device", dest="device",
                 default=None, help="Serial device file")
    (ops, args) = p.parse_args()
    if len(args) != 1:
        print("No program file specified")
        p.print_help()
        print("Usage: ymodem.py <--host=host> <--port=port> program_file")
        print("Default: host=192.168.0.10 port=5012")
        sys.exit(1)
    
    infile = args[0]

    ret = -1
    with getFD(ops.device, ops.host, int(ops.port)) as fd:
        
        ret = ymodemImpl(fd, infile)
       
    return ret



if __name__ == "__main__":
    main()

