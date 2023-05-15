from .xdevice import xDevice
from ..iceboot_comms import IceBootComms
import struct


class UnmodifiedMMB(xDevice):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)

    def i2c2WriteReg(self, i2cAddr: int, register: int, value: int) -> None:
        self.cmd("%d %d %d i2c2WriteReg" % (i2cAddr, register, value))

    def i2c2ReadReg(self, i2cAddr: int, register: int) -> int:
        return int(self.cmd("%d %d i2c2ReadReg .s drop" % (i2cAddr, register),
                            strip_stack=True))

    def _sendData(self, data: list, cmdName: str) -> None:
        cmdStr = ""
        for s in data:
            cmdStr += "%s " % s
        cmdStr += "%d %s" % (len(data), cmdName)
        if len(cmdStr) > 1000:
            raise Exception("Command too long: %s" % cmdStr)
        self.cmd(cmdStr)

    def _recvData(self, nBytes: int, cmdName: str) -> list:
        cmdStr = "%d %s" % (nBytes, cmdName)
        return [int(s) for s in self.cmd(cmdStr).split()]

    def spi2Send(self, data: list) -> None:
        self._sendData(data, "spi2Send")

    def spi2Recv(self, nBytes: int) -> list:
        return self._recvData(nBytes, "spi2Recv")

    def spi4Send(self, data: list) -> None:
        self._sendData(data, "spi4Send")

    def spi4Recv(self, nBytes: int) -> list:
        return self._recvData(nBytes, "spi4Recv")

    def uart4Send(self, data: list) -> None:
        self._sendData(data, "uart4Send")

    def uart4Recv(self, nBytes: int) -> list:
        return self._recvData(nBytes, "uart4Recv")

    def uart7Send(self, data: list) -> None:
        self._sendData(data, "uart7Send")

    def uart7Recv(self, nBytes: int) -> list:
        return self._recvData(nBytes, "uart7Recv")

    def exampleInit(self) -> None:
        self.cmd("exampleInit")

    # SweCam routines
    def swecamInit(self) -> None:
        self.cmd("swecamInit")

    def swecamReset(self) -> None:
        self.cmd("swecamReset")

    def swecamPowerOn(self) -> None:
        self.cmd("swecamPowerOn")

    def swecamPowerOff(self) -> None:
        self.cmd("swecamPowerOff")

    def swecamPowerOK(self) -> bool:
        return bool(self.cmd("swecamPowerOK"))

    def swecamSend(self, data: list) -> None:
        self._sendData(data, "swecamSend")

    def swecamRecv(self, nBytes: int) -> list:
        return self._recvData(nBytes, "swecamRecv")

    def swecamBSend(self, data: list) -> None:
        cmd = ("%d swecamBSend\r\n" % len(data)).encode()
        self.comms.send(cmd)
        self.comms.send(bytes(data))
        self.comms._receiveRawPrompt()

    def swecamBRecv(self, maxBytes: int) -> bytes:
        cmd = ("%d swecamBRecv\r\n" % maxBytes).encode()
        self.comms.send(cmd)
        self.comms.read_n(len(cmd))
        repLen = struct.unpack("<H", self.comms.read_n(2))[0]
        out = bytes(self.comms.read_n(repLen))
        self.comms._receiveRawPrompt()
        return out
