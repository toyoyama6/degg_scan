from .degg import DEgg
from ..iceboot_comms import IceBootComms

class pDOM(DEgg):
    def __init__(self, comms: IceBootComms, **kwargs):
        super().__init__(comms, **kwargs)
