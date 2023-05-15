#!/usr/bin/env python
# Measure mock packet bandwidth from a remote IceBoot session.

from iceboot.iceboot_session import getParser, startIcebootSession
from optparse import OptionParser
from bandwidth import Bandwidth, BandwidthException
import time


def main():
    parser = getParser()
    parser.add_option("--pktSize", help="Packet size, bytes", default=600)
    parser.add_option("--nPkts", help="Number of packets", default=1)
    parser.add_option("--delay", help="Inter packet delay, usec", default=0)
    parser.add_option("--timeout", help="Inter packet timeout, usec", default=10)
    parser.add_option("--frequency", help="Packet frequency, Hz", type=float)
    parser.add_option("--quiet", help="No console output")
    
    (options, args) = parser.parse_args()
    pktSize = int(options.pktSize)
    nPkts = int(options.nPkts)
    delay = int(options.delay)
    timeout = int(options.timeout)

    start = time.time()
    session = startIcebootSession(parser)
    bw = Bandwidth(session)
    freq_pkts = 0
    period = None
    if options.frequency:
        period = 1.0 / options.frequency

    try:
        while (True):
            # Request and read packets
            pkt_time = time.time()
            results = bw.reader(pktSize=pktSize,nPkts=nPkts,delay=delay,timeout=timeout)


            freq_pkts += 1
            if not options.quiet and not options.frequency:
                print('CONFIG nPkts:%d pktSize:%dB delay:%dusec' % (nPkts,pktSize,delay))
                print('STATISTICS elapsed time:%gs bytes:%d bits:%d B/W:%f Mbps' %
                    (results["elapsed"], results["nBytes"], results["nBits"],
                    results["Mbps"]))

            if period:
                now = time.time()
                delay = period - (now - pkt_time)
                print(f'FIXME freq {options.frequency} period {period} meas {now - pkt_time} delay {delay}')
                if delay < 0.0:
                    print(f'WARNING slipping frequency {options.frequency} by '
                          f'{delay} s')
                    delay = 0.0
                time.sleep(delay)
            else:
                break

    except  KeyboardInterrupt:
        pass
    finally:
        if freq_pkts:
            end = time.time()
            freq = freq_pkts/(end-start)
            bw = freq * pktSize * 8.0 / 1.0e6
            print(f'frequency {freq} target {options.frequency} pktSize {pktSize} bandwidth {bw} Mbps')


if __name__ == "__main__":
    main()

