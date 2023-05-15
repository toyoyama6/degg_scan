from .unmodified_mmb import UnmodifiedMMB
from ..iceboot_comms import IceBootComms

class MMBTestSetup(UnmodifiedMMB):
    def __init__(self, comms, **kwargs):
        super().__init__(comms, **kwargs)

    def MMBTestInit(self) -> None:
        """
        Initialize MMB for testing
        """
        self.cmd("MMBTestInit")

    def readPin(self, socket, pin) -> int:
        """
        read the state of a pin

        """
        ret = self.cmd("%d %d readPin" % (pin, socket))
        return int(ret)

    def setSinglePin(self, socket, pin, state) -> None:
        """
        Set a single pin on the XTIO

        """
        self.cmd("%d %d %d setSinglePin" % (state, pin, socket))
