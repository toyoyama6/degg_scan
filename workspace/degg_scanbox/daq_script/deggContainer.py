import tables
import numpy as np
import os, sys
from infoContainer import infoContainer

class deggContainer(object):
    def __init__(self):
        self.port = -1
        self.lowerPMT = ''
        self.upperPMT = ''
        self.icm_port = -1
        self.threshold0 = -1
        self.threshold1 = -1
        self.peakHeight0 = -1
        self.peakHeight1 = -1
        self.dac_value = -1
        self.session = -1
        self.rapcals = -1
        self.files = []
        self.blFiles = []
        self.info0 = []
        self.info1 = []
        self.offset = -1
        self.hvSet0 = -1
        self.hvSet1 = -1
        self.period = -1
        self.rapcal_utcs = []
        self.rapcal_icms = []
        self.dac = -1

    def addInfo(self, infoContainer, channel):
        if channel == 0:
            self.info0.append(infoContainer)
        if channel == 1:
            self.info1.append(infoContainer)

    def resetInfo(self):
        self.info0 = []
        self.info1 = []
    def saveInfo(self, channel):
        if channel == 0:
            info = self.info0
            f = self.files[0]
        if channel == 1:
            info = self.info1
            f = self.files[1]
        with tables.open_file(f, 'a') as open_file:
            table = open_file.get_node('/data')
            for m, _info in enumerate(info):
                event = table.row
                event['timestamp']  = _info.timestamp
                event['charge']     = _info.charge
                event['channel']    = _info.channel
                event['eventNum']   = _info.event_number
                event['rVal']       = _info.r_point
                event['tVal']       = _info.t_point
                event.append()
                table.flush()


    def createInfoFiles(self, nevents, overwrite=False):
        for ch in [0, 1]:
            f = self.files[ch]
            if os.path.isfile(f):
                if not overwrite:
                    raise IOError(f'File name not unique! Risk overwriting file {f}')
                else:
                    print(f"Will overwrite file {f}")
                    time.sleep(0.1)
                    os.remove(f)
            dummy = [0] * nevents
            dummy = np.array(dummy)
            if not os.path.isfile(f):
                class Event(tables.IsDescription):
                    timestamp   = tables.Float128Col()
                    charge      = tables.Float64Col()
                    channel     = tables.Int32Col()
                    eventNum    = tables.Int32Col()
                    rVal        = tables.Float64Col()
                    tVal        = tables.Float64Col()
                with tables.open_file(f, 'w') as open_file:
                    table = open_file.create_table('/','data',Event)

##end
