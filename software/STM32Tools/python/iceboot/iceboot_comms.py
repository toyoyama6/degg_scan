"""
Iceboot core communications object
"""
import fcntl
import os
import select
import socket
import time
import struct
from abc import abstractmethod

import numpy as np
import ymodem

try:
    from serial import Serial
except ModuleNotFoundError:
    pass

EOL = '\r\n'
_PROMPT = '> '
PROMPT = EOL + _PROMPT
GZSTREAM_EOT = 0xFFFF


class _IceBootTransport(object):
    """ Iceboot physical transport API """

    @abstractmethod
    def send(self, data: bytes) -> int:
        pass

    @abstractmethod
    def recv(self, nbytes: int) -> bytes:
        pass

    @abstractmethod
    def fileno(self) -> int:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class _IcebootSocket(_IceBootTransport):
    """ Iceboot socket transport implementation """

    def __init__(self, *args, **kwargs):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Note heritage startIcebootSession() and STF may pass port as str
        self._sock.connect((kwargs['host'], kwargs['port']))
        fcntl.fcntl(self._sock, fcntl.F_SETFL, os.O_NONBLOCK)

    def __del__(self):
        self.close()

    def send(self, data: bytes) -> int:
        return self._sock.send(data)

    def recv(self, nbytes: int) -> bytes:
        return self._sock.recv(nbytes)

    def fileno(self) -> int:
        return self._sock.fileno()

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
        except OSError:
            pass


class _IcebootSerial(_IceBootTransport):
    """ Iceboot serial transport implementation """

    def __init__(self, *args, **kwargs):
        try:
            self._serial = Serial(kwargs['devFile'], kwargs['baudRate'],
                                  timeout=0, writeTimeout=10, xonxoff=0)
        except NameError:
            raise Exception('pySerial module needed for serial support')

    def send(self, data: bytes) -> int:
        return self._serial.write(data)

    def recv(self, nbytes: int) -> bytes:
        return self._serial.read(nbytes)

    def fileno(self) -> int:
        return self._serial.fileno()

    def close(self) -> None:
        self._serial.close()


class IceBootComms(object):
    def __init__(self, options: dict):
        if options.get('host') and options.get('port'):
            self._comms = _IcebootSocket(host=options['host'], port=options[
                'port'])
        elif options.get('devFile') and options.get('baudRate'):
            self._comms = _IcebootSerial(devFile=options['devFile'],
                                         baudRate=options['baudRate'])
        else:
            raise Exception("Set host and port for Ethernet or "
                            "devFile and baudRate for serial")
        self._debug = options['debug']
        self._logOutput = None
        if self._debug:
            print('IcebootSession: Start')

        # Get past bootloader if present.  This should be harmless if we're
        # already in iceboot
        self.bypassBootloader()
        self.cmd("true setecho" + EOL)
        # Save logging output enable status, then disable.
        self._logOutput = self.cmd("disableLogOutput")
        time.sleep(0.1)
        # Clear the buffer
        while True:
            try:
                if len(self._comms.recv(128)) == 0:
                    break

            except BlockingIOError:
                break
        # Clear the stack
        self.cmd("sdrop")

    def __del__(self):
        try:
            # Restore initial logging output enable status
            if self._logOutput == '0':
                self.cmd("disableLogOutput")
            elif self._logOutput == '1':
                # Print logging output queue and re-enable logging output
                print(self.cmd("printLogOutput"))
                self.cmd("enableLogOutput")
            self.close()
            if self._debug:
                print('IcebootSession: End')
        except (Exception,):
            pass

    def close(self) -> None:
        self._comms.close()

    def cmd(self, cmd_str: str, timeout: float = 1.0,
            strip_stack: bool = False) -> str:
        """
        Send cmd_str to Iceboot and return the response as a string

            Keyword Arguments:
            cmd_str      command to send
            timeout     floating point seconds
            strip_stack remove leading stack "<N> TOKEN " from output string
                example "<1> 65535 " -> "65535 " , note trailing whitespace
        """
        output = self.raw_cmd(cmd_str, timeout=timeout).decode()

        if self._debug:
            print("Received %s" % output)

        if strip_stack:
            ll = len(output.split()[0])
            return output[(ll + 1):]

        return output

    def uint16_cmd(self, cmd_str: str, n_words: int) -> np.ndarray:
        """ Send a command to Iceboot and return the response
        as a tuple of ints
        n_words is the number of expected words
        """

        # 2 bytes per 16 bit word
        buff = self.raw_cmd(cmd_str, 2 * n_words)

        unpacked_response = np.frombuffer(buff, np.uint16)

        if self._debug:
            print("Received %s" % str(unpacked_response))

        return unpacked_response

    def raw_cmd(self, cmd_str: str, n_bytes: int = None,
                timeout: float = 1) -> bytearray:
        """ Sends a command and returns the response as a binary buffer
            if n_bytes is not None, raw_cmd will not return unless
            n_bytes have been read from the socket
            (not including the echo or the prompt)

            Keyword Arguments:
            cmd_str      command to send
            n_bytes     see comment above
            timeout     floating point seconds
        """
        if self._debug:
            print("SENT: %s" % cmd_str)

        if not cmd_str.endswith(EOL):
            cmd_str += EOL

        self._comms.send(cmd_str.encode())

        # nbytes to read including the cmd_str and the prompt
        n_bytes_adj = None  # avoid 'use before set' warning
        if n_bytes is not None:
            n_bytes_adj = n_bytes + len(PROMPT) + len(cmd_str)

        reply = bytearray()
        while True:
            new_data = self.read_next(timeout=timeout)
            reply.extend(new_data)

            if n_bytes is None or len(reply) >= n_bytes_adj:
                try:
                    if reply[-len(PROMPT):].decode() == PROMPT:
                        break
                except UnicodeDecodeError:
                    pass

        # Strip original command and prompt and return the reply
        reply = reply[len(cmd_str):-len(PROMPT)]

        return reply

    def read_next(self, n_bytes: int = 128, timeout: float = 1.0) -> bytes:
        """ Read from socket.

            Keyword Arguments:
            n_bytes     read size
            timeout     floating point seconds

        """
        rdy = select.select([self._comms.fileno()], [], [], timeout)

        if rdy[0]:
            recv_bytes = self._comms.recv(n_bytes)
            return recv_bytes
        else:
            raise IOError('Timeout!')

    def read_n(self, n_bytes: int, timeout: float = 1.0) -> bytearray:
        buf = bytearray()
        while len(buf) < n_bytes:
            buf.extend(self.read_next(n_bytes - len(buf), timeout=timeout))

        return buf

    def bypassBootloader(self) -> None:
        try:
            self.cmd("boot", timeout=3)
        except IOError:
            # Send a second "boot" because a prompt may not immediately
            # appear, depending on the specific communications channel.
            self.cmd("boot", timeout=3)

    def fileno(self) -> int:
        return self._comms.fileno()

    def send(self, msg: bytes) -> int:
        return self._comms.send(msg)

    def getBoardType(self, unknown_value: int=0) -> int:
        try:
            return int(self.cmd("getBoardType .s drop", strip_stack=True))
        except ValueError:
            # Support session initialization for those not yet running
            # MCU software that supports the getBoardType call
            # Note a value of 0 is mapped to pDOM.
            return unknown_value

    def receiveRawCmd(self, cmd_str: str, n_bytes: int,
                      timeout: float = 1.0) -> bytearray:
        if not cmd_str.endswith(EOL):
            cmd_str += EOL
        encoded_cmd = cmd_str.encode()
        self.send(encoded_cmd)
        self.read_n(len(encoded_cmd), timeout)
        ret = self.read_n(n_bytes, timeout)
        self._receiveRawPrompt()
        return ret

    def _receiveRawPrompt(self) -> None:
        ret = ""
        while not ret.endswith(_PROMPT):
            try:
                ret += self.read_next(n_bytes=128, timeout=10).decode()
            except UnicodeDecodeError:
                pass

    def receiveGZDataTransfer(self, cmd: str) -> bytearray:
        if not cmd.endswith(EOL):
            cmd += EOL
        encoded_cmd = cmd.encode()
        self._comms.send(encoded_cmd)
        self.read_n(len(encoded_cmd))
        xfer = bytearray()
        while True:
            chunklen = struct.unpack("<H", self.read_n(2))[0]
            if chunklen == GZSTREAM_EOT:
                break
            xfer.extend(self.read_n(chunklen))
        self._receiveRawPrompt()
        return xfer

    def ymodemSend(self, infile: str, cmd: str) -> None:
        infile = os.path.expanduser(infile)
        if not os.path.exists(infile):
            print("File \"%s\" does not exist" % infile)
            return
        encoded_cmd = cmd.encode()
        self.send(encoded_cmd)
        self.read_n(len(encoded_cmd))
        ymodem.ymodemImpl(self.fileno(), infile, verbose=False)
        # Remove partial prompt
        self._receiveRawPrompt()

    def ymodemFlashUploadBytes(self, remote_filename: str, content: bytes) \
            -> None:
        # This exists mainly for the flash STF test
        cmd = ("s\" %s\" ymodemFlashUpload\r\n" % remote_filename).encode()
        self._comms.send(cmd)
        self.read_n(len(cmd))
        ymodem.ymodemSendContent(self._comms.fileno(), content,
                                 remote_filename, verbose=False)
        # Remove partial prompt
        prompt = _PROMPT
        ret = ""
        while not ret.endswith(prompt):
            try:
                ret += self.read_next(n_bytes=128, timeout=10).decode()
            except UnicodeDecodeError:
                pass
