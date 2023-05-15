import time
from optparse import OptionParser

from . import ads4149
from . import dac_cal
from . import iceboot_session_cmd
from . import ltc2600

modules = [ltc2600, ads4149]


def getParser():
    parser = OptionParser()

    iceboot_session_cmd.configureOptions(parser)
    for m in modules:
        m.configureOptions(parser)

    return parser


def calibrateSession(session, baseline):
    fitparams = dac_cal.calibrateDAC(session)
    for channel in fitparams:
        print("Calibrating channel {} to baseline of {}".format(channel,
                                                                baseline))
        dacChannel = 'A'
        if channel == 1:
            dacChannel = 'B'
        slope, intercept = fitparams[channel]['slope'], fitparams[channel][
            'intercept']
        print("DAC set to {}".format(slope * baseline + intercept))
        session.setDAC(dacChannel, slope * baseline + intercept)
        time.sleep(0.1)


def getIcebootSession(**kwargs):
    """
    Public factory method to return a connected Iceboot session.
    This is the only official public method for receiving an Iceboot session.

    For kwargs see iceboot_session.configureOptions()
    """
    parser = kwargs.get('parser') or getParser()
    (options, args) = parser.parse_args()
    session = iceboot_session_cmd.init(options, **kwargs)

    # Additional initialization for DEgg, pDOM with configured FPGA
    if session.isDEgg() or session.isPDOM():
        if session.fpgaVersion() != 0xFFFF:
            if options.setBaseline is not None:
                calibrateSession(session, options.setBaseline)
    return session


def startIcebootSession(parser=None, host=None, port=None):
    """
    Legacy public factory method to return a connected Iceboot session.
    """
    return getIcebootSession(parser=parser, host=host, port=port)
