import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import click
import os, sys
import tqdm

###########
from degg_measurements.utils import read_data

###########


#flasher_off_path = '/home/scanbox/data/fat_calibration/pmt_residual/20210705_00/'
#flasher_on_path  = '/home/scanbox/data/fat_calibration/pmt_residual/20210706_01/'

#valid_pmts = ['SQ0295', 'SQ0421', 'SQ0485', 'SQ0573', 'SQ0578', 'SQ0648', 'SQ0649', 'SQ0737']

def run_analysis(wf_trim, fpath=None, old=False):

    print('This script looks at the limited waveforms collected')
    print('during the waveform stream for specific runs!')

    if old == True:
        valid_pmts = ['SQ0295', 'SQ0300', 'SQ0307', 'SQ0313', 'SQ0322',
                      'SQ0379', 'SQ0406', 'SQ0414', 'SQ0418', 'SQ0422', 'SQ0434',
                      'SQ0296', 'SQ0303', 'SQ0309', 'SQ0314', 'SQ0323', 'SQ0403',
                      'SQ0407', 'SQ0415', 'SQ0420', 'SQ0423', 'SQ0438',
                      'SQ0298', 'SQ0306', 'SQ0310', 'SQ0315', 'SQ0378', 'SQ0405',
                      'SQ0411', 'SQ0417', 'SQ0421', 'SQ0429']
        fpath = '/home/scanbox/dvt/data/dark_waveforms/20210527_01/'
        fig_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_wf_run114')

    else:
        valid_pmts = ['SQ0295', 'SQ0421', 'SQ0480', 'SQ0489', 'SQ0525', 'SQ0555', 'SQ0573', 
                      'SQ0578', 'SQ0607', 'SQ0642', 'SQ0686', 'SQ0309', 'SQ0466', 'SQ0482',
                      'SQ0507', 'SQ0531', 'SQ0556', 'SQ0575', 'SQ0580', 'SQ0626', 'SQ0648', 
                      'SQ0737', 'SQ0418', 'SQ0467', 'SQ0485', 'SQ0522', 'SQ0545', 'SQ0558', 
                      'SQ0576', 'SQ0604', 'SQ0628', 'SQ0649']
        if fpath == None:
            fpath = '/home/scanbox/dvt/data/dark_waveforms/20210714_01/'
        fig_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_wf')

    for pmt in valid_pmts:
        print(pmt)
        make_plots(wf_trim, fpath, fig_path, pmt)


def make_plots(wf_trim, fpath, fig_path, pmt):

    fig, ax = plt.subplots()
    figStart, axStart = plt.subplots()

    on_filename = fpath + pmt + '_1500V.hdf5'
    event_id, time, waveforms, timestamp, pc_time, parameter_dict = read_data(on_filename)
    num_events = len(event_id)
    peak_vals = []
    integrals = []
    for i, wf in enumerate(waveforms):
        if i < 10:
            axStart.plot(time[0][:wf_trim]*4.2, wf[:wf_trim], label=str(i), alpha=0.8)
        peak_vals.append(np.max(wf))
        integrals.append(np.sum(wf))

    j = 0
    for wf_rnd in waveforms[::200]:
        ax.plot(time[0][:wf_trim]*4.2, wf_rnd[:wf_trim])
        figSingle, axSingle = plt.subplots()
        axSingle.plot(time[0][:wf_trim]*4.2, wf_rnd[:wf_trim])
        axSingle.set_xlabel('Time [ns]')
        axSingle.set_ylabel('ADC')
        axSingle.set_title(f'{pmt} ({parameter_dict["DEggSerialNumber"]}, {parameter_dict["pmt"]})')
        figSingle.savefig(os.path.join(fig_path, f'wfs_{j}_{pmt}.pdf'))
        j += 1
        plt.close(figSingle)

    ax.set_title(f'{pmt} ({parameter_dict["DEggSerialNumber"]}, {parameter_dict["pmt"]})')
    ax.set_xlabel('Time [ns]')
    ax.set_ylabel('ADC')
    #ax.legend()
    fig.savefig(os.path.join(fig_path, f'wfs_{pmt}.png'), dpi=300)
    plt.close(fig)
    
    axStart.set_title(f'{pmt} ({parameter_dict["DEggSerialNumber"]}, {parameter_dict["pmt"]})')
    axStart.set_xlabel('Time [ns]')
    axStart.set_ylabel('ADC')
    #axStart.legend()
    figStart.savefig(os.path.join(fig_path, f'wfs_start_{pmt}.png'), dpi=300)
    plt.close(figStart)

    wf_num = np.arange(0, i+1)
    fig1, ax1 = plt.subplots()
    ax1.plot(wf_num, peak_vals, 'o')
    ax1.set_xlabel('WF Number')
    ax1.set_ylabel('WF Peak Amplitude [ADC]')
    fig1.savefig(os.path.join(fig_path, f'peak_amp_{pmt}.pdf'))
    plt.close(fig1)
    
    fig1b, ax1b = plt.subplots()
    ax1b.plot(wf_num, integrals/np.max(integrals), 'o', label=f'Norm Factor={np.max(integrals)}')
    ax1b.set_xlabel('WF Number')
    ax1b.set_ylabel('Integrated ADC (Norm)')
    ax1b.legend()
    fig1b.savefig(os.path.join(fig_path, f'integrated_adc_{pmt}.pdf'))
    plt.close(fig1b)

    '''
    dtype = [('num', int), ('peak', float)]
    wf_num = np.array(wf_num, dtype=[dtype[0]])
    peak_vals = np.array(peak_vals, dtype=[dtype[1]])
    
    p = peak_vals.argsort()
    sorted_peak = np.sort(peak_vals, order='peak')
    sorted_num = wf_num[p]

    fig2, ax2 = plt.subplots()
    ax2.plot(sorted_peak, sorted_num, 'o')
    ax2.set_xlabel('WF Peak Amplitude [ADC]')
    ax2.set_ylabel('WF Number')
    fig2.savefig(os.path.join(fig_path, f'sorted_peak_amp_{pmt}.pdf'))
    plt.close(fig2)
    '''

@click.command()
@click.argument('fpath')
@click.option('--wf_trim', '-t', default=-1)
@click.option('--old', is_flag=True)
def main(fpath, wf_trim, old):
    wf_trim = int(wf_trim)
    run_analysis(wf_trim, fpath, old)

if __name__ == "__main__":
    main()

