#!/usr/bin/env python

# This is a test for FieldHub data corruption using an echo server.

from __future__ import print_function
import select
import os
import socket
import fcntl
import sys
import copy
from optparse import OptionParser

# FieldHub uses ASK/8b10b to encode data. Choose symbols without
# consecutive ones to minimize error rates on framing symbols
FRAME_STRT_CHR = 0x4A # 0101010101 in 8b10b
FRAME_STOP_CHR = 0xB5 # 1010101010 in 8b10b
FRAME_BDRY_LEN = 8 # Chance collisions will not happen in our lifetime

FRAME_BEGIN = bytearray([FRAME_STRT_CHR] * FRAME_BDRY_LEN)
FRAME_END = bytearray([FRAME_STOP_CHR] * FRAME_BDRY_LEN)

TIMEOUT = 3
MAX_CONSEC_FRAME_ERR = 2
CLEAR_TIMEOUT = 0.1

def encodeFrame(data):
    out = copy.deepcopy(FRAME_BEGIN)
    out.extend(data)
    out.extend(copy.deepcopy(FRAME_END))
    return out

class FrameException(Exception):
    pass

def decodeFrame(data):
    if len(data) < (2 * FRAME_BDRY_LEN):
        raise FrameException()
    if data[:FRAME_BDRY_LEN] != FRAME_BEGIN:
        raise FrameException()
    if data[(-1 * FRAME_BDRY_LEN):] != FRAME_END:
        raise FrameException()
    return data[FRAME_BDRY_LEN:(-1 * FRAME_BDRY_LEN)]

def _read_next(comms, n_bytes, timeout):

    rdy = select.select([comms], [], [], timeout)

    if rdy[0]:
        recv_bytes = comms.recv(n_bytes)
        if len(recv_bytes) == 0:
            # Socket is closed
            raise IOError("Socket is closed")
        return recv_bytes
    else:
        raise IOError('Timeout')

def _read_n(comms, n_bytes, timeout):
    buf = bytearray()
    while len(buf) < n_bytes:
        buf.extend(_read_next(comms, n_bytes - len(buf), timeout=timeout))

    return buf

def _send_next(comms, data, timeout):

    rdy = select.select([], [comms], [], timeout)      

    if rdy[1]:
        sent_bytes = comms.send(data)
        if sent_bytes == 0:
            # Socket is closed
            raise IOError("Socket is closed")
        return sent_bytes
    else:
        raise IOError('Timeout')

def _send_n(comms, data, timeout):
    ptr = 0
    tot = len(data)
    while ptr < tot:
        ptr += _send_next(comms, data[ptr:tot], timeout)

def _clear(comms):
    while True:
        rdy = select.select([comms], [], [], CLEAR_TIMEOUT)
        if rdy[0]:
            recv_bytes = comms.recv(4096)
        else:
            return

def sendFrame(comms, data):
    frame = encodeFrame(data)
    _send_n(comms, frame, TIMEOUT)

def recvFrame(comms, datalen):
    framelen = datalen + 2 * FRAME_BDRY_LEN
    data = _read_n(comms, framelen, TIMEOUT)
    return decodeFrame(data)

def exchangeFrame(comms, data):
    sendFrame(comms, data)
    return recvFrame(comms, len(data))

def markError(errorMap, expbyte, rcvbyte):
    if expbyte not in errorMap:
        errorMap[expbyte] = {}
    if rcvbyte not in errorMap[expbyte]:
        errorMap[expbyte][rcvbyte] = 1
    else:
        errorMap[expbyte][rcvbyte] += 1

def echoTest(comms, chunkSize, errorMap):
    chunk = bytearray(os.urandom(chunkSize))
    retChunk = exchangeFrame(comms, chunk)
    for i in range(len(chunk)):
        if chunk[i] != retChunk[i]:
            markError(errorMap, chunk[i], retChunk[i])

def printErrMapLine(c, data):
    print("0x%02x: {" % c, end = "")
    for ce in sorted(data):
        print("0x%02x: %d " % (ce, data[ce]), end = "")
    print("}")

def main():
    parser = OptionParser()
    parser.add_option("-s", "--framesize", dest="framesize", default=1024,
                      help="Number of bytes to transmit in each frame. ")
    parser.add_option("-c", "--framecnt", dest="framecnt", default=1024,
                      help="Number of frames to exchange. ")
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default="localhost")
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default="5012")
    (options, args) = parser.parse_args()
    comms = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    comms.connect((options.host, int(options.port)))
    fcntl.fcntl(comms, fcntl.F_SETFL, os.O_NONBLOCK)
    _clear(comms)

    frErrCnt = 0
    errMap = {}
    consFrErrCnt = 0
    for _ in range(int(options.framecnt)):
        try:
            echoTest(comms, int(options.framesize), errMap)
            consFrErrCnt = 0
        except FrameException:
            frErrCnt += 1
            _clear(comms)
        except IOError:
            frErrCnt += 1
            consFrErrCnt += 1
            if consFrErrCnt == MAX_CONSEC_FRAME_ERR:
                print("%s cosecutive I/O errors.  Aborting." % consFrErrCnt)
                sys.exit(1)
            _clear(comms)

    totalBytes = int(options.framecnt) * int(options.framesize)
    totalErrors = sum(sum(errMap[c][x] for x in errMap[c]) for c in errMap)
    errorRate = float(totalErrors) / totalBytes
    print("")
    
    if totalErrors > 0:
        print("Map of character errors:")
        for c in sorted(errMap):
            printErrMapLine(c, errMap[c])
        print("")

    print("Total frames: %s" % options.framecnt)
    print("Total frame errors: %s" % frErrCnt)
    print("Total bytes: %s" % totalBytes)
    print("Total errors: %s" % totalErrors)
    print("Byte error rate: %g" % errorRate)


if __name__ == "__main__":
    main()
    
    