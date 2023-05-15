
from crc16 import calcCrcIBM
import struct
import os
import select


class XDOMAppException(Exception):
    pass


def checkErrorCode(ec):
    if ec == 0:
        return
    elif ec == 1:
        raise XDOMAppException("Opcode error")
    elif ec == 2:
        raise XDOMAppException("Hardware error")
    elif ec == 3:
        raise XDOMAppException("Value error")
    elif ec == 4:
        raise XDOMAppException("FIFO underflow error")
    elif ec == 5:
        raise XDOMAppException("Software error")
    elif ec == 6:
        raise XDOMAppException("Checksum/packet error")
    elif ec == 7:
        raise XDOMAppException("Interlock error")
    elif ec == 8:
        raise XDOMAppException("Timeout")
    elif ec == 9:
        raise XDOMAppException("No such channel/camera/device")
    elif ec == 10:
        raise XDOMAppException("FPGA required but not configured")
    elif ec == 11:
        raise XDOMAppException("Unsupported xDOM/device")
    elif ec == 12:
        raise XDOMAppException("No such file")
    elif ec == 13:
        raise XDOMAppException("Hardware not ready")
    elif ec == 14:
        raise XDOMAppException("Memory allocation failed")
    else:
        raise XDOMAppException("Unknown error: %s" % ec)


PKT_READ_REQ  = 1
PKT_WRITE_REQ = 2
PKT_POLL_REQ  = 3
PKT_ECHO_REQ  = 4

PKT_HEADER = 0x8F15
MAX_MSG_SIZE = 0x8000 # 32 KB

CLEAR_TIMEOUT = 0.1


class XDOMAppMsg(object):

    def __init__(self, comms, **kwargs):
        self.comms = comms
        self.options = kwargs
        self._clear()

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        self.comms.close()

    def _clear(self):
        while True:
            rdy = select.select([self.comms], [], [], CLEAR_TIMEOUT)
            if rdy[0]:
                recv_bytes = self.comms.recv(4096)
            else:
                return

    def _read_next(self, n_bytes, timeout):

        rdy = select.select([self.comms], [], [], timeout)

        if rdy[0]:
            recv_bytes = self.comms.recv(n_bytes)
            if len(recv_bytes) == 0:
                # Socket is closed
                raise IOError("Socket is closed")
            return recv_bytes
        else:
            raise IOError('Timeout')

    def _read_n(self, n_bytes, timeout):
        buf = bytearray()
        while len(buf) < n_bytes:
            buf.extend(self._read_next(n_bytes - len(buf), timeout=timeout))

        return buf

    def _send_next(self, data, timeout):

        rdy = select.select([], [self.comms], [], timeout)      

        if rdy[1]:
            sent_bytes = self.comms.send(data)
            if sent_bytes == 0:
                # Socket is closed
                raise IOError("Socket is closed")
            return sent_bytes
        else:
            raise IOError('Timeout')

    def _send_n(self, data, timeout):
        ptr = 0
        tot = len(data)
        while ptr < tot:
            ptr += self._send_next(data[ptr:tot], timeout)

    def _send_req_packet(self, pktCode, opcode, token1, token2, data, timeout):
        pkt = bytearray(9)
        payload = bytearray(data)
        pkt[0:2] = struct.pack("<H", PKT_HEADER)
        pkt[2:4] = struct.pack("<H", 11 + len(payload))
        pkt[4]   = struct.pack("<B", pktCode)
        pkt[5:7] = struct.pack("<H", opcode)
        pkt[7]   = struct.pack("<B", token1)
        pkt[8]   = struct.pack("<B", token2)
        self._send_n(pkt, timeout)
        self._send_n(payload, timeout)
        crc = calcCrcIBM(pkt)
        crc = calcCrcIBM(payload, crc)
        pkt = bytearray(2)
        # Write CRC as big-endian
        pkt[0:2] = struct.pack(">H", crc)
        self._send_n(pkt, timeout)

    def _recv_rep_packet1(self, timeout):
        hdr = bytearray(self._read_n(5, timeout))
        if struct.unpack("<H", hdr[0:2])[0] != PKT_HEADER:
            raise IOError("Checksum/packet error")
        msglen = struct.unpack("<H", hdr[2:4])[0]
        if msglen > MAX_MSG_SIZE:
            raise IOError("Checksum/packet error")
        checkErrorCode(hdr[4])
        remainder = bytearray(self._read_n(msglen - 5, timeout))
        crc = calcCrcIBM(hdr)
        crc = calcCrcIBM(remainder, crc)
        if crc != 0:
            raise IOError("Checksum/packet error")
        return remainder[:-2]

    def _recv_rep_packet(self, timeout):
        try:
            return self._recv_rep_packet1(timeout)
        except XDOMAppException:
            self._clear()
            raise

    def read(self, opcode, nbytes, token1=0, token2=0, timeout=1):
        self._send_req_packet(PKT_READ_REQ, opcode, token1, token2,
                              bytearray(struct.pack("<H", nbytes)), timeout)
        return self._recv_rep_packet(timeout)

    def write(self, opcode, data, token1=0, token2=0, timeout=1):
        payload = bytearray(data)
        self._send_req_packet(PKT_WRITE_REQ, opcode, token1, token2,
                              payload, timeout)
        # We still need to receive the response!
        return self._recv_rep_packet(timeout)

    def poll(self, opcode, token1=0, token2=0, timeout=1):
        self._send_req_packet(PKT_POLL_REQ, opcode, token1, token2,
                              bytearray(0), timeout)
        return (self._recv_rep_packet(timeout))

    def echo(self, data, timeout=1):
        self._send_req_packet(PKT_ECHO_REQ, 0, 0, 0, bytearray(data), timeout)
        return self._recv_rep_packet(timeout)
