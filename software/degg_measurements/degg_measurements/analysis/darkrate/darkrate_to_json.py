import tables
import numpy as np
from glob import glob
import os
import pandas as pd
import click
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d

from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils import DEggLogBook
from degg_measurements.analysis import Result

from loading import make_darkrate_df
from loading import make_scaler_darkrate_df


def extract_darkrate_values_from_df(df, pmt_name, pe_threshold):
    mask = df['pmt'] == pmt_name
    df = df.loc[mask]
    interp_darkrates = interp1d(df['thresh'], df['darkrate'])
    interp_darkrate_errors = interp1d(df['thresh'],
                                      df['darkrate_err'])
    dr = interp_darkrates(pe_threshold)
    dr_error = interp_darkrate_errors(pe_threshold)
    # Check if all the deadtimes are the same
    deadtimes = df['deadtime'].values
    if len(np.unique(deadtimes)) == 1:
        deadtime = deadtimes[0]
    else:
        raise NotImplementedError('Not all deadtimes are the same '
                                  'over the course of this measurement!')
    return dr, dr_error, deadtime


def darkrate_to_json(df, pe_threshold=0.25, temp=None):
    if temp is None:
        extract_temp = True
    else:
        extract_temp = False

    import degg_measurements
    db_path = os.path.join(degg_measurements.__path__[0],
                           'analysis',
                           'database_jsons')

    logbook = DEggLogBook()
    for pmt_name in np.unique(df['pmt']):
        darkrate, darkrate_error, deadtime = \
            extract_darkrate_values_from_df(df, pmt_name, pe_threshold)

        if extract_temp:
            mask = df['pmt'] == pmt_name
            u_temps = np.unique(df.loc[mask, 'DEggSurfaceTemp'])
            if len(u_temps) != 1:
                raise ValueError('Multiple temperatures found!')

        result = Result(pmt_name, logbook=logbook,
                        test_type='dvt')
        result.to_json(test_name='darknoise',
                       folder_name=db_path,
                       darkrate=float(darkrate),
                       darkrate_error=float(darkrate_error),
                       deadtime=float(deadtime),
                       temp=temp,
                       pe_threshold=pe_threshold)
        result.to_database()


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.argument('meas_key')
@click.option('--temperature', '-t', type=float, default=None)
def main(run_json, meas_key, temperature):
    print(run_json)
    key = meas_key

    scaler_df = pd.DataFrame()

    run_base = os.path.basename(run_json)
    run_number = int(run_base.split('.')[0].split('_')[-1])
    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)

        pmts = ['LowerPmt', 'UpperPmt']

        for pmt in pmts:
            pmt_id = degg_dict[pmt]['SerialNumber']
            folder = degg_dict[pmt][key]['Folder']
            temp = degg_dict[pmt][key]['DEggSurfaceTemp']
            files = glob(os.path.join(folder, pmt_id + '*.hdf5'))
            scaler_df_i = make_scaler_darkrate_df(files,
                                                  DEggSurfaceTemp=temp,
                                                  key=key,
                                                  run_number=run_number)
            scaler_df = scaler_df.append(scaler_df_i, ignore_index=True)

    darkrate_to_json(scaler_df, pe_threshold=0.25, temp=temperature)


if __name__ == '__main__':
    main()

