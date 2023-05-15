from iceboot.iceboot_session import startIcebootSession as iceboot_session
from degg_measurements.utils import rerun_after_exception


class OptparseWrapper(object):
    def __init__(self, **kwargs):
        self.options = OptionsWrapper(**kwargs)
        self.args = None

    def parse_args(self):
        return self.options, self.args


class OptionsWrapper(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@rerun_after_exception(BrokenPipeError, 2)
def startIcebootSession(parser=None,
                        fpgaConfigurationFile=None,
                        host=None,
                        port=None,
                        fpgaEnable=True,
                        **kwargs):

    if parser is not None:
        #print( "Trying to start iceboot session... (parser is not None)" )
        return iceboot_session(parser, host=host, port=port)

    else:
        #print( "Trying to start iceboot session... (parser is None)" )
        default_dict = {
            'fpgaConfigurationFile': fpgaConfigurationFile,
            'debug': False,
            'setBaseline': None,
            'fpgaEnable': fpgaEnable,
            'dacSettings': [],
            'host': host,
            'port': port
        }

        default_dict.update(kwargs)

        optparse_wrapper = OptparseWrapper(
            **default_dict)

        return iceboot_session(parser=optparse_wrapper,
                               host=host, port=port)


