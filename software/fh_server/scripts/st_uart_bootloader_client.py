
BOOTLOADER_GET                = 0x00
BOOTLOADER_GET_VERSION_AND_RP = 0x01
BOOTLOADER_GET_ID             = 0x02
BOOTLOADER_READ               = 0x11
BOOTLOADER_GO                 = 0x21
BOOTLOADER_WRITE              = 0x31
BOOTLOADER_ERASE              = 0x43
BOOTLOADER_EXTENDED_ERASE     = 0x44
BOOTLOADER_WRITE_PROTECT      = 0x63
BOOTLOADER_WRITE_UNPROTECT    = 0x73
BOOTLOADER_READOUT_PROTECT    = 0x82
BOOTLOADER_READOUT_UNPROTECT  = 0x92
BOOTLOADER_GET_CHECKSUM       = 0xA1

BOOTLOADER_ACK      = 0x79
BOOTLOADER_NACK     = 0x1F
BOOTLOADER_ABR_INIT = 0x7F

BOOTLOADER_MAX_WRITE_CHUNK_SIZE = 256

BOOTLOADER_DEFAULT_TIMEOUT            = 1
BOOTLOADER_DEFAULT_MASS_ERASE_TIMEOUT = 20

BOOTLOADER_STD_MASS_ERASE_BYTES = [0xFF, 0x00]
BOOTLOADER_EXT_MASS_ERASE_BYTES = [0xFF, 0xFF, 0x00]

BOOTLOADER_DEFAULT_BOOT_ADDRESS = 0x8000000

def computeBootloaderChecksum(data, ival):
    result = ival
    for x in data:
        result = result ^ x
    return result

class ST_UART_BootloaderClient(object):
    def __init__(self, send, recv):
        self.send = send
        self.recv = recv

    def receiveAck(self, timeout):
        ack = self.recv(1, timeout)[0]
        if ack != BOOTLOADER_ACK:
            raise Exception("Didn't receive ACK from bootloader. Got %x" % ack)

    def sendAndRecvAck(self, data, timeout):
        self.send(data, timeout)
        self.receiveAck(timeout)

    def bootloaderCmdInit(self, cmd, timeout):
        data = [cmd, 0xFF ^ cmd]
        self.sendAndRecvAck(data, timeout)

    def bootloaderSendWord(self, addr, timeout):
        mesg = [(addr >> 24) & 0xFF,
                (addr >> 16) & 0xFF,
                (addr >> 8) & 0xFF,
                 addr & 0xFF]
        mesg.append(computeBootloaderChecksum(mesg, 0))
        self.sendAndRecvAck(mesg, timeout)

    def bootloaderSendLen(self, length, timeout):
        txlen = (length - 1) & 0xFF # Bootloader adds 1 to length
        data = [txlen, 0xFF ^ txlen]
        self.sendAndRecvAck(data, timeout)

    def bootloaderInit(self, timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        # Need to try twice. First ABR_INIT byte may not work, depending on HW
        try:
            self.sendAndRecvAck([BOOTLOADER_ABR_INIT], timeout)
        except:
            self.sendAndRecvAck([BOOTLOADER_ABR_INIT], timeout)

    def bootloaderGet(self, timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        self.bootloaderCmdInit(BOOTLOADER_GET, timeout)
        nbytes = self.recv(1, timeout)[0]
        # The returned number of bytes is actually (nbytes - 1)
        nbytes += 1
        data = self.recv(nbytes, timeout)
        self.receiveAck(timeout)
        return data

    def bootloaderGetID(self, timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        self.bootloaderCmdInit(BOOTLOADER_GET_ID, timeout)
        data = self.recv(3, timeout)
        version = int(data[2] | (data[1] << 8))
        self.receiveAck(timeout)
        return version

    def bootloaderRead(self, address, length,
                       timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        if (length == 0 or length > 256):
            raise Exception("Bad length for read: %d" % length)
        self.bootloaderCmdInit(BOOTLOADER_READ, timeout)
        self.bootloaderSendWord(address, timeout)
        self.bootloaderSendLen(length, timeout)
        return self.recv(length, timeout)

    def bootloaderGo(self, address=BOOTLOADER_DEFAULT_BOOT_ADDRESS,
                     timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        self.bootloaderCmdInit(BOOTLOADER_GO, timeout)
        self.bootloaderSendWord(address, timeout)

    def bootloaderWrite(self, address, data,
                        timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        if (len(data) == 0 or (len(data) & 0x3) != 0 or
            len(data) > BOOTLOADER_MAX_WRITE_CHUNK_SIZE):
            raise Exception("Bad data length for write: %d" % len(data))
        self.bootloaderCmdInit(BOOTLOADER_WRITE, timeout)
        self.bootloaderSendWord(address, timeout)
        txlen = (len(data) - 1) & 0xFF # Bootloader adds 1 to length
        ck = txlen
        self.send([txlen], timeout)
        self.send(data, timeout)
        ck = computeBootloaderChecksum(data, ck)
        self.send([ck], timeout)
        self.receiveAck(timeout)

    def _bootloaderEraseStd(self, pages, timeout):
        if (len(pages) == 0 or len(pages) > 255):
            raise Exception("Bad pages length for eraseStd: %d" % len(pages))
        if (any(x > 255 for x in pages)):
            raise Exception("Page numbers for eraseStd must be less than 256")
        self.bootloaderCmdInit(BOOTLOADER_ERASE, timeout)
        txlen = (len(pages) - 1) & 0xFF # Bootloader adds 1 to length
        self.send([txlen], timeout)
        self.send(pages, timeout)
        ck = computeBootloaderChecksum(pages, 0)
        self.send([ck], timeout)
        self.receiveAck(timeout)

    def _bootloaderMassEraseStd(self, timeout):
        self.bootloaderCmdInit(BOOTLOADER_ERASE, timeout)
        self.send(BOOTLOADER_STD_MASS_ERASE_BYTES, timeout)
        self.receiveAck(timeout)

    def _bootloaderEraseExt(self, pages, timeout):
        if (len(pages) == 0 or len(pages) > 0xFFFC):
            raise Exception("Bad pages length for eraseExt: %d" % len(pages))
        if (any(x > 65535 for x in pages)):
            raise Exception("Page numbers for eraseExt must be < 65536")
        self.bootloaderCmdInit(BOOTLOADER_EXTENDED_ERASE, timeout)
        txlen = (len(pages) - 1) # Bootloader adds 1 to length
        txdata = [(txlen >> 8) & 0xFF, txlen & 0xFF]
        ck = 0
        ck = ck ^ txdata[0]
        ck = ck ^ txdata[1]
        self.send(txdata, timeout)
        for page in pages:
            txdata = [(page >> 8) & 0xFF, page & 0xFF]
            ck = ck ^ txdata[0]
            ck = ck ^ txdata[1]
            self.send(txdata, timeout)
        self.send([ck], timeout)
        self.receiveAck(timeout)

    def _bootloaderMassEraseExt(self, timeout):
        self.bootloaderCmdInit(BOOTLOADER_EXTENDED_ERASE, timeout)
        self.send(BOOTLOADER_EXT_MASS_ERASE_BYTES, timeout)
        self.receiveAck(timeout)

    def _useStandardErase(self, timeout):
        cmds = self.bootloaderGet(timeout)
        return (BOOTLOADER_ERASE in cmds)

    def bootloaderErase(self, pages, timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        # First we need to determine the proper erase command
        if self._useStandardErase(timeout):
            self._bootloaderEraseStd(pages, timeout)
        else:
            self._bootloaderEraseExt(pages, timeout)

    def bootloaderMassErase(self,
                            timeout=BOOTLOADER_DEFAULT_MASS_ERASE_TIMEOUT):
        # First we need to determine the proper erase command
        if self._useStandardErase(timeout):
            self._bootloaderMassEraseStd(timeout)
        else:
            self._bootloaderMassEraseExt(timeout)

    def bootloaderGetChecksum(self, address, length, poly, initValue,
                              timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        self.bootloaderCmdInit(BOOTLOADER_GET_CHECKSUM, timeout)
        self.bootloaderSendWord(address, timeout)
        nwords = (length + 3) / 4
        self.bootloaderSendWord(nwords, timeout)
        self.bootloaderSendWord(poly, timeout)
        self.bootloaderSendWord(initValue, timeout)
        ret = self.recv(5, timeout)
        ck = 0
        for i in range(4):
            ck = ck ^ ret[i]
        if ck != ret[4]:
            raise Exception("Transmission error")
        retval = (ret[0] << 24 | ret[1] << 16 | ret[2] << 8 | ret[3])
        return retval

    def bootloaderCRC32(self, address, length,
                        timeout=BOOTLOADER_DEFAULT_TIMEOUT):
        return self.bootloaderGetChecksum(address, length,
                                          0x04C11DB7, 0xFFFFFFFF, timeout)

    def bootloaderProgram(self, address, data, verify=True,
                          timeout=BOOTLOADER_DEFAULT_MASS_ERASE_TIMEOUT):
        data = bytearray(data)
        while (len(data) & 0x3) != 0:
            data.append(0)
        self.bootloaderMassErase(timeout=timeout)
        for offset in range(0, len(data), BOOTLOADER_MAX_WRITE_CHUNK_SIZE):
            chunk = data[offset:offset + BOOTLOADER_MAX_WRITE_CHUNK_SIZE]
            self.bootloaderWrite(address + offset, chunk, timeout)
            if verify:
                readback = self.bootloaderRead(address + offset, len(chunk))
                if readback != chunk:
                    raise Exception("Verify failure at "
                                    "address %s" % address + offset)

    def bootloaderProgramBootImage(self, data, verify=True,
                                   timeout=BOOTLOADER_DEFAULT_MASS_ERASE_TIMEOUT):
        self.bootloaderProgram(BOOTLOADER_DEFAULT_BOOT_ADDRESS,
                               data, verify, timeout=timeout)
