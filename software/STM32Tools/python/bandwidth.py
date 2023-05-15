''' Provides a class to measure communication bandwidth
'''

import time

class BandwidthException(BaseException):
    pass

class Bandwidth:

    def __init__(self, session):
        self.session = session


    def reader(self, nPkts=1, pktSize=600, delay=0, timeout=10):
        start = time.time()
        bytes = self.session.raw_cmd('%d %d %d pktWriter' %
            (nPkts, pktSize, delay), timeout=timeout)
        elapsed = time.time() - start

        if len(bytes) != nPkts * pktSize:
            raise BandwidthException('%d/%d short read' %
                (len(bytes),nPkts * pktSize))
        
        # Verify readback content
        index = 0
        for byte in bytes:
            if byte != index % 256:
                raise BandwidthException(
                    'Packet d offset %d value 0x%02x should be 0x%02x' %
                    (index, byte, index % 255))
            index = index + 1
            if index == pktSize:
                index = 0

        # Calculate statistics
        nBytes = len(bytes)
        nBits = nBytes * 8
        Bps = nBytes / elapsed
        bps = nBits / elapsed
        Mbps = bps / 1.0e6

        return {
            "elapsed":      elapsed,
            "nBytes":       nBytes,
            "nBits":        nBits,
            "Bps":          Bps,
            "bps":          bps,
            "Mbps":         Mbps,
        }

