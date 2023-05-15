''' An example of how to use the HitBufReader class

    Contains assert statements to verify that the HitBufReader is working
'''

from iceboot.iceboot_session import getParser, startIcebootSession
from iceboot.hitbuf_reader import HitBufReader
from fpga_reg import fpga_write
import time


def main():
    parser = getParser()

    parser.add_option("--startPage", dest="startPage", type=int,
                      help="start page for the hit buffer", default="0")
    parser.add_option("--nPages", dest="nPages", type=int,
                      help="number of pages for the hit buffer", default=10000)
    parser.add_option("--nTriggers", dest="nTriggers", type=int,
                      help="Number of triggers for the sw trigger test",
                      default=100)
    parser.add_option("--samples", dest="samples", type=int,
                      help="Number of samples per waveform",
                      default=256)
    parser.add_option("--pulserPeriod", dest="pulserPeriod", type=int,
                      help="Pulser period in microseconds",
                      default=5000)
    parser.add_option("--pulserDACSetting", dest="pulserDACSetting", type=int,
                      help="Pulser DAC setting",
                      default=32000)
    parser.add_option("--trigThreshold", dest="trigThreshold", type=int,
                      help="Trigger threshold for the periodic pulser test",
                      default=8170)
    parser.add_option("--pulseTestLen", dest="pulseTestLen", type=int,
                      help="Length of the periodic pulser test (in seconds)",
                      default=5)

    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)

    # reset the waveform buffers
    fpga_write(session, 'dig_logic_reset', 0x3)
    fpga_write(session, 'wvb_overflow_ack', 0x3)

    # set dpram mode
    fpga_write(session, 'dpram_mode', 0x1)

    time.sleep(0.1)

    # initialize the hitbuffer reader;
    # start the hit buffer controller and the wvb reader
    hbufReader = HitBufReader(session, options.startPage, options.nPages,
                              reset=True, startController=True,
                              startReader=True)

    assert hbufReader.empty()

    print(f'Initial test: Sending {options.nTriggers} sw triggers...')

    for i in range(options.nTriggers):
        fpga_write(session, f'sw_trigger[{i%2}]', 0x1)

    assert not hbufReader.empty()

    print(f'Reading waveforms from the hit buffer...')

    hbufReader.flush()

    nWfmsRead = 0
    # we can read waveforms by iterating over hbufReader
    for i, wfm in enumerate(hbufReader):
        assert wfm['channel'] == i % 2
        nWfmsRead += 1

    print(f'Found {nWfmsRead} waveforms')
    assert nWfmsRead == options.nTriggers

    print('SW trigger test passed.\n')

    print(f'Setting FE pulser DAC to {options.pulserDACSetting}')
    session.setDAC('D', options.pulserDACSetting)

    print('Setting trigger threshold for each channel to '
          f'{options.trigThreshold}')
    for channel in range(2):
        fpga_write(session, f'trig_thresh[{channel}]', options.trigThreshold)

    nSamples = (int(options.samples) / 4) * 4
    print(f'Setting waveform length to {nSamples} samples')
    for channel in range(2):
        session.setDEggConstReadout(channel, 1, int(nSamples))

    print(f'Enabling FE pulser with a period of {options.pulserPeriod} us')
    for channel in range(2):
        session.enableFEPulser(channel, options.pulserPeriod)

    print(f'Enabling triggers and starting the pulser test')
    start = time.time()
    for channel in range(2):
        fpga_write(session, f'trig_settings[{channel}]', 0x7)

    nWfms = [0, 0]
    seenLtcs = [set(), set()]
    while True:
        for wfm in hbufReader:
            updateRecords(wfm, nWfms, seenLtcs, nSamples)

        if time.time() - start > options.pulseTestLen:
            break

    print('Stopping the pulser')
    for channel in range(2):
        session.disableFEPulser(channel)

    end = time.time()

    tElapsed = end - start
    print(f'The pulser ran for {tElapsed:.2f} seconds with a period of'
          f' {options.pulserPeriod} us.')

    # read the last waveforms
    print(f'Current memory page: {hbufReader.currentPage()}')

    print('Flushing and reading final waveforms')
    hbufReader.flush()
    for wfm in hbufReader:
        updateRecords(wfm, nWfms, seenLtcs, nSamples)

    nExpected = int(tElapsed*1e6/options.pulserPeriod)
    print(f'Expected number of pulses: ~{nExpected:.1f}')

    for channel in range(2):
        print(f'Number of pulses found from channel {channel} '
              f': {nWfms[channel]}')

    # disable the hit buffer controller and the wvb_reader
    hbufReader.stopController(stopReader=True)

    assert hbufReader.empty()

    print(f'Current memory page: {hbufReader.currentPage()}')


def updateRecords(wfm, nWfms, seenLtcs, nSamples):
    chan = wfm["channel"]
    ltc = wfm["timestamp"]

    # check that we decoded the right number of samples
    assert wfm["waveformLength"] == nSamples
    # check that we are reading unique waveforms
    assert ltc not in seenLtcs[chan]

    seenLtcs[chan].add(ltc)
    nWfms[chan] += 1


if __name__ == '__main__':
    main()
