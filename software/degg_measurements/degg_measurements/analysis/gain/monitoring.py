import os, sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from glob import glob
import click

#############################
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import load_run_json
from degg_measurements.utils import extract_runnumber_from_path

E_CONST = 1.60217662e-7

##This script checks for the cache created from
##analyze_gain.py with --save_df enabled
##by default it looks through all caches for
##a given run

def get_cache(run_number, pmt_id):
    dfs = []
    glob_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
    glob_str = f'{run_number}_GainMeasurement_*_gain_check_{pmt_id}.hdf5'
    pd_files = glob(os.path.join(glob_dir, glob_str))
    if len(pd_files) == 0:
        print(f'No files found at: {glob_str} !')
        print('If you did not run analyze_gain.py with --save_df, please do so')
        raise ValueError()
    for f in pd_files:
        _df = pd.read_hdf(f)
        for hv_str in ['hv_mon_b4_wf', 'hv_mon']:
            for hv_s in _df[hv_str]:
                hv_s = hv_s[1:-1]
                hv_s = hv_s.split(' ')
                hv_aves = []
                for hv in hv_s:
                    if hv == '':
                        continue
                    try:
                        val = float(hv)
                    except ValueError:
                        val = int(hv)
                    hv_aves.append(val)
                hv_ave = np.mean(hv_aves)
                _df[hv_str] = hv_ave
        dfs.append(_df)

    df = pd.concat(dfs)

    ##this should be for monitoring
    ##check that set HV is always constant
    n_set_hv = len(df['high_voltages'].unique())
    if n_set_hv != 1:
        raise ValueError(f'Monitoring data - why are set HV values: {n_set_hv} ?')

    return df

def monitoring_plots(df, pmt_id, plot_dir):

    temperature = df['temps'].values
    hv_mon1 = df['hv_mon_b4_wf'].values
    hv_mon2 = df['hv_mon'].values
    hv_set = df['high_voltages'].values[0]
    gain = df['spe_peak_pos'].values / E_CONST
    m_order = np.arange(len(gain))

    fig1, ax1 = plt.subplots()
    ax1.plot(m_order, gain, 'o', linewidth=0, color='royalblue')
    ax1.set_xlabel('Measurement Number')
    ax1.set_ylabel('Gain')
    fig1.savefig(os.path.join(plot_dir, f'{pmt_id}_gain_mon.pdf'))
    plt.close(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot(m_order, temperature, 'o', linewidth=0, color='royalblue')
    ax2.set_xlabel('Measurement Number')
    ax2.set_ylabel('Temperature [C]')
    fig2.savefig(os.path.join(plot_dir, f'{pmt_id}_temperature_mon.pdf'))
    plt.close(fig2)

    fig3, ax3 = plt.subplots()
    ax3.plot(m_order, hv_mon1, 'o', linewidth=0, color='royalblue', label='Before WF', alpha=0.8)
    ax3.plot(m_order, hv_mon2, 'o', linewidth=0, color='goldenrod', label='After WF', alpha=0.8)
    ax3.plot([m_order[0], m_order[-1]], [hv_set, hv_set], '--', color='black', label='Set')
    ax3.set_xlabel('Measurement Number')
    ax3.set_ylabel('HV Readback [V]')
    ax3.legend()
    fig3.tight_layout()
    fig3.savefig(os.path.join(plot_dir, f'{pmt_id}_readback_mon.pdf'))
    plt.close(fig3)

    fig4, ax4 = plt.subplots()
    ax4.plot(temperature, hv_mon1, 'o', linewidth=0, color='royalblue', label='Before WF', alpha=0.8)
    ax4.plot(temperature, hv_mon2, 'o', linewidth=0, color='goldenrod', label='After WF', alpha=0.8)
    ax4.set_xlabel('Temperature [C]')
    ax4.set_ylabel('HV Readback [V]')
    ax4.legend()
    fig4.tight_layout()
    fig4.savefig(os.path.join(plot_dir, f'{pmt_id}_temperature_readback.pdf'))
    plt.close(fig4)


def summary_plots(df, pmt_id_list, plot_dir):

    gains = df.gain.values / 1e7

    fig1, ax1 = plt.subplots()
    ax1.hist(gains, histtype='step', color='royalblue')
    ax1.set_xlabel('Gain  / 1e7')
    ax1.set_ylabel('Entries')
    fig1.savefig(os.path.join(plot_dir, 'all_gains.pdf'))

@click.command()
@click.argument('run_json')
def main(run_json):
    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)

    plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_check')
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)

    pmt_id_list = []
    df_total = []

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        for pmt in ['LowerPmt', 'UpperPmt']:
            pmt_dict = degg_dict[pmt]
            pmt_id = pmt_dict['SerialNumber']
            print(f'--- {pmt_id} ---')
            pmt_id_list.append(pmt_id)

            df_pmt = get_cache(run_number, pmt_id)
            monitoring_plots(df_pmt, pmt_id, plot_dir)
            df_total.append(df_pmt)

    print('Summary Plots')
    df = pd.concat(df_total)
    summary_plots(df, pmt_id_list, plot_dir)

    print('Done')

if __name__ == "__main__":
    main()
##end
