from boardtype import getBoardName
from .iceboot_comms import IceBootComms, PROMPT
# Board classes needed by _get_board_cls() below.
from .devices.acoustic import Acoustic
from .devices.degg import DEgg
from .devices.mdom import mDOM
from .devices.pdom import pDOM
from .devices.pencilbeam import PencilBeam
from .devices.pocam import POCAM
from .devices.swedencam import SwedenCam
from .devices.unmodified_mmb import UnmodifiedMMB
from .devices.mmb_test_setup import MMBTestSetup
from .devices.xdevice import xDevice
from .devices.xdom import xDOM


def configureOptions(parser):
    # Only support Ethernet host/port at the moment
    parser.add_option("--host",
                      help="Ethernet host name or IP")
    parser.add_option("--port", type=int,
                      help="Ethernet port")
    parser.add_option("--debug", action="store_true",
                      help="Print board I/O stdout")
    parser.add_option("--setBaseline", type=float,
                      help="Set ADC baseline")
    parser.add_option("--class_name",
                      help="Device class name, default: <probed>")
    parser.add_option("--baudRate", type=int, default=1000000,
                      help="Serial port baud rate, default: 1000000")
    parser.add_option("--devFile",
                      help="Serial port special device file")


def _get_board_cls(name: str):
    """ Return board class corresponding to board name. """
    return globals()[name]

def init(defaults, **kwargs):
    """
    Internal Iceboot session device type factory.
    All public clients should use icebootsession.startIcebootSession() instead.
    """

    options = {}
    for option in defaults.__dict__:
        if len(option) > 4 and option.isascii() and \
                option.startswith('__') and option.endswith('__'):
            # skip stfv1 __dunder__ attributes TODO remove for stfv2
            continue
        # Backwards compat to optparse options
        options[option] = kwargs[option] if kwargs.get(option) is not \
                                            None else defaults.__dict__[option]

    comms = IceBootComms(options)
    board_cls = options.get('class_name')
    if board_cls is None:
        # Probe board type and class name.
        board_cls = getBoardName(comms.getBoardType(), whitespace=False)
    return _get_board_cls(board_cls)(comms, **options)
