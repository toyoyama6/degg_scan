from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from optparse import OptionParser

from sensors import get_sensor_info

def main():
    parser = getParser()
    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)

    session.enableHV(0)
    session.enableHV(1)

    session.setDEggHV(0, 0)
    session.setDEggHV(1, 0)

    ##use function from previous script
    get_sensor_info(session)

    session.setDEggHV(0, 1400)
    session.setDEggHV(1, 1500)

    get_sensor_info(session)

if __name__ == "__main__":
    main()

##end
