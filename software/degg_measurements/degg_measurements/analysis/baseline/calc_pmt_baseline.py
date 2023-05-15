import numpy as np
import pandas as pd
import click
from datetime import datetime
from warnings import warn

from degg_measurements.utils import read_data
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json


def calc_baseline(filename):
    event_id, _, waveforms, _, _, datetime_timestamp, parameters = read_data(filename)
    df = pd.DataFrame()
    df['name'] = pd.Series(parameters['name'])
    df['baseline_filename'] = pd.Series(filename)
    df['baseline'] = np.mean(waveforms)
    df['baseline_std'] = np.std(waveforms)
    df['n_samples'] = np.prod(waveforms.shape)
    df['temp'] = parameters['degg_temp']
    if datetime_timestamp[0] < datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp():
        warning_str = filename + " does not include datetime timing information"
        warning_str = warning_str + "(file is probably older than 2022/05/11)."
        warn(warning_str)
        ##this was the start of FAT
        datetime_timestamp = datetime.strptime("2022/04/30", "%Y/%m/%d").timestamp()
        df['datetime_timestamp'] = datetime_timestamp
    else:
        df['datetime_timestamp'] = datetime_timestamp[0]
    return df


def make_baseline_df(filenames):
    total_df = pd.DataFrame()

    for file_i in filenames:
        df = calc_baseline(filename)
        total_df = total_df.append(df, ignore_index=True)
    print(total_df)
    return total_df


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
def main(run_json):
    baseline_filenames = []

    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)

        pmts = ['LowerPmt', 'UpperPmt']

        for pmt in pmts:
            file_i = degg_dict[pmt]['BaselineFilename']
            baseline_filenames.append(file_i)

    baseline_df = make_baseline_df(baseline_filenames)
    return baseline_df


if __name__ == '__main__':
    main()

