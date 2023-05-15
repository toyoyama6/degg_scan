import numpy as np
import os
import json
from glob import glob
import click
from matplotlib import pyplot as plt
import matplotlib.transforms as tx
from matplotlib.collections import LineCollection

import pandas as pd

from degg_measurements.utils import extract_runnumber_from_path

PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_summ')

def load_jsons(json_paths):
    df = pd.DataFrame()
    for f in json_paths:
        with open(f, 'r') as open_file:
            json_ = json.load(open_file)
        df_ = pd.json_normalize(json_, sep='.')
        flat_meas_data = pd.json_normalize(df_['meas_data'][0][0])
        df_.drop(columns='meas_data')
        result = pd.concat([df_, flat_meas_data], axis=1)
        df = df.append(result)
    return df

def analyse_gain_jsons(gain_json_paths, run_number):
    gain_df = load_jsons(gain_json_paths)

    bins = np.linspace(1400, 1800, 13)

    fig, ax = plt.subplots()
    ax.hist(gain_df['value'], histtype='step', lw=2, bins=bins)
    trans = tx.blended_transform_factory(ax.transData, ax.transAxes)
    xy_pairs = np.column_stack([
        np.repeat(gain_df['value'], 2), np.tile([0, 0.075], gain_df.shape[0])])
    line_segments = xy_pairs.reshape([gain_df.shape[0], 2, 2])
    ax.add_collection(LineCollection(
        line_segments, transform=trans, lw=1.))
    ax.set_xlabel(r'HV @ $10^7$ gain')
    fig.savefig(os.path.join(PLOT_DIR, f'hv_hist_run_{run_number}.pdf',
                bbox_inches='tight'))

    bot_mask = gain_df['device_uid'].str.contains('degg-bot')
    fig, ax = plt.subplots()
    ax.hist([gain_df.loc[bot_mask, 'value'], gain_df.loc[~bot_mask, 'value']],
            color=[(94/255, 129/255, 172/255), (191/255, 97/255, 106/255)],
            label=['Bottom PMT', 'Top PMT'],
            stacked=True,
            bins=bins)
    trans = tx.blended_transform_factory(ax.transData, ax.transAxes)
    xy_pairs = np.column_stack([
        np.repeat(gain_df['value'], 2), np.tile([0, 0.075], gain_df.shape[0])])
    line_segments = xy_pairs.reshape([gain_df.shape[0], 2, 2])
    ax.add_collection(LineCollection(
        line_segments, transform=trans, lw=1., color='k'))
    ax.set_xlabel(r'HV @ $10^7$ gain')
    ax.legend(loc='best')
    fig.savefig(os.path.join(PLOT_DIR, f'hv_hist_split_run_{run_number}.pdf',
                bbox_inches='tight'))


@click.command()
@click.argument('run_json')
def main(run_json):
    run_number = extract_runnumber_from_path(run_json)

    import degg_measurements
    json_base_path = os.path.join(degg_measurements.__path__[0],
                                  'analysis',
                                  'database_jsons')
    database_jsons = glob(os.path.join(
        json_base_path, f'run_{run_number:05d}',
        '*.json'))

    gain_jsons = [json_f for json_f in database_jsons
                  if json_f.endswith('01.json') and 'GainMeasurement' in json_f]

    analyse_gain_jsons(gain_jsons, run_number)


if __name__ == '__main__':
    main()
