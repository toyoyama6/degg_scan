#! /usr/bin/env python3

from goldschmidt.magnetometer import ThermometerTM947SD
import pandas as pd
import os
import click
import time


@click.command()
@click.argument('device')
@click.argument('channel', nargs=-1, type=int)
@click.argument('filename', type=click.Path())
@click.option('sleep_time', '--s', type=float, default=0)
def main(device, channel, filename, sleep_time):
    if sleep_time == 0:
        record_temp(device, channel, filename)
    else:
        while True:
            record_temp(device, channel, filename)
            time.sleep(sleep_time)


def record_temp(device, channel, filename):
    if not isinstance(channel, list):
        channel = list(channel)

    meter = ThermometerTM947SD(device=device)
    df = pd.DataFrame()

    index = pd.to_datetime([pd.Timestamp.now()])
    index.name = 'Local time'

    for channel_i in channel:
        meter.select_channel(channel_i)
        temp_i = meter.measure()
        df['Temp Channel {}'.format(channel_i)] = pd.Series(temp_i,
                                                            index=index)

    if not os.path.isfile(filename):
        df.to_csv(filename, mode='w', header=True)
    else:
        existing_df = pd.read_csv(filename, index_col='Local time')
        df = existing_df.append(df)
        df.to_csv(filename, mode='w', header=True)


if __name__ == '__main__':
    main()
