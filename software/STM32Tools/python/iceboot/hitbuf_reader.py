''' Provides a class to facilitate reading waveforms out of
the DDR3 hit buffer

Wraps the HBufReader iceboot functions
handles assembling and unpacking complete waveforms

See DEggTest/HBufReaderExample.py for example code using this class

dpram abort mode MUST be set to 1 for the logic of this reader to function
'''

import numpy as np
from .test_waveform import parseTestWaveform, waveformNWords

WVB_READER_ENABLE_REG_ADDR = 0xdf4
DPRAM_ABORT_MODE_REG = 0xdf2


class HitBufReader:
    def __init__(self, session, startPage, nPages, lane=0, reset=False,
                 startController=False, startReader=False):
        self._session = session
        self._evtBuf = np.array([], dtype=np.uint16)

        if reset:
            ret = session.resetHBufReader(startPage, nPages, lane)
        else:
            ret = session.initHBufReader(StartPage, nPages, lane)

        if ret != 0:
            raise RuntimeError(f'HitBufReader init error! Return code: {ret}')

        if startController:
            self.startController()

        if startReader:
            session.fpgaWrite(DPRAM_ABORT_MODE_REG, [0x1])
            session.fpgaWrite(WVB_READER_ENABLE_REG_ADDR, [0x1])

    def stopController(self, stopReader=False):
        if stopReader:
            self._session.fpgaWrite(WVB_READER_ENABLE_REG_ADDR, [0x0])

        self._session.stopHBufController()

    def startController(self, startReader=True):
        self._session.startHBufController()

        if startReader:
            self._session.fpgaWrite(DPRAM_ABORT_MODE_REG, [0x1])
            self._session.fpgaWrite(WVB_READER_ENABLE_REG_ADDR, [0x1])

    def flush(self):
        self._session.flushHBuf()

    def empty(self):
        ''' this checks whether the page buffer is empty
        it does not guarantee that a full new waveform is available.
        A flush may be required.
        '''
        return self._session.HBufReaderEmpty() == 1

    def currentPage(self):
        return self._session.HBufReaderCurrentPage()

    def popWfm(self):
        ''' raises StopIteration if no new waveform is available '''
        return self._getNextWfm()

    def __iter__(self):
        return self

    def __next__(self):
        return self.popWfm()

    def _getNextWfm(self):
        while True:
            wfm = self._stripWfmFromBuf()

            if wfm is None:
                self._readNextPage()
            else:
                break

        return wfm

    def _stripWfmFromBuf(self):
        # strip leading zeros (from HBufFlushes)
        nonzeroArgs = np.argwhere(self._evtBuf != 0)
        if len(nonzeroArgs) != 0:
            self._evtBuf = self._evtBuf[nonzeroArgs[0][0]:]
        # handle case where we have a full page of zeros
        # (can occur from calling flush when there is no data to flush)
        elif len(self._evtBuf) > 0 and self._evtBuf[0] == 0:
            self._evtBuf = np.array([], dtype=np.uint16)

        # get wfm len (from waveform header)
        if len(self._evtBuf) < 2:
            return None

        version = (int(self._evtBuf[0]) >> 8) & 0xFF
        nWords = waveformNWords(self._evtBuf[1], version)

        # full waveform not available in self._evtBuf
        if len(self._evtBuf) < nWords:
            return None

        newWfm = parseTestWaveform(self._evtBuf[:nWords])

        self._evtBuf = self._evtBuf[nWords:]

        return newWfm

    def _readNextPage(self):
        retcode, newData = self._session.HBufReaderPop()
        if retcode < 0:
            raise RuntimeError('HBufReaderPop() failure!'
                               f' Return code {retcode}')
        elif retcode == 0:
            raise StopIteration

        self._evtBuf = np.hstack((self._evtBuf, newData))
