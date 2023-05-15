import numpy as np
from degg_measurements.utils import startIcebootSession
from iceboot.iceboot_session import getParser
import time
import click


def main():
    parser = getParser()
    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)

    channel = 0
    hv = 1434
    dac_value = 30000
    threshold = 8120
    period = 100000
    deadtime = 24

    session = setup_scalers(session, channel, hv,
                            dac_value, threshold,
                            period, deadtime)

    for i in range(0, 5):
        session, scaler_count = take_scalers(session, channel)
        session.endStream()
        print(f'Observed {scaler_count} triggers in a {period}µs time window ' +
             f'with a {deadtime / 240e6 * 1e9}ns deadtime.')


def setup_scalers(session, channel, high_voltage,
                  dac_value, threshold, period, deadtime):
    session.setDEggHV(channel, int(0))
    session.enableHV(channel)
    session.setDEggHV(channel, int(high_voltage))

    dac_channels= ['A', 'B']
    session.setDAC(dac_channels[channel], int(dac_value))

    session.setDEggTriggerConditions(channel, threshold)
    session.enableDEggTrigger(channel)

    session.enableScalers(channel, period, deadtime)
    time.sleep(5)
    return session


def take_scalers(session, channel):
    scaler_count = session.getScalerCount(channel)
    return session, scaler_count


if __name__ == '__main__':
    main()


