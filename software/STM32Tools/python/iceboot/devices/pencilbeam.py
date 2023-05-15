from .unmodified_mmb import UnmodifiedMMB


class PencilBeam(UnmodifiedMMB):
    def __init__(self, comms, **kwargs):
        super().__init__(comms, **kwargs)

    # define AM specific functions here..
