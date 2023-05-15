
from optparse import OptionParser, Option, OptionValueError
import re


def _checkDAC(option, opt, value):
    match = re.match('([A-H]),(\d+)', value)
    if match:
        return (match.groups()[0], int(match.groups()[1]))
    else:
        raise OptionValueError("Can't parse a DAC channel/value pair out of"
                               " '%s'. Use e.g. --setDAC=A,16000 to set "
                               "DAC channel A to 16000" % value)


Option.TYPES = Option.TYPES + ("dac",)
Option.TYPE_CHECKER["dac"] = _checkDAC


def configureOptions(parser):

    parser.add_option("--setDAC", dest="dacSettings", type="dac",
                      default=[], action="append",
                      help="Set DAC channel to the specified value, "
                      "e.g. --setDAC=A,16000.  Valid channels are A-H")


def init(options, session):
    session.resetDAC()
    for setting in options.dacSettings:
        session.setDAC(setting[0], setting[1])