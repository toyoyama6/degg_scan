import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.cm as cm
import os, sys
import pandas as pd
from glob import glob
import click
import tables

from degg_measurements.utils import read_data
from degg_measurements.utils import load_degg_dict, load_run_json
from degg_measurements.utils import update_json
from degg_measurements.utils.load_dict import audit_ignore_list
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.analysis import Result
from degg_measurements.analysis import RunHandler
from degg_measurements import REMOTE_DATA_DIR
from degg_measurements import DB_JSON_PATH

from chiba_slackbot import send_warning

lws = [1.4,1.8,1.4,1.4,1.8,1.4,1.4,1.8,1.4,1.4,1.8,1.4] # downward bold

def signalPlots(df_off, df_on, degg_id, savedir, mode='all'):
    if mode == 'horizontal':
        label_list = ['0x0001', '0x0004', '0x0008', '0x0020',
                      '0x0040', '0x0100', '0x0200', '0x0800']
        mode_list = [1, 4, 8, 32, 64, 256, 512, 2048]
        df_signal = df_on.loc[df_on['Dir'] == 'horizontal']
        df_bkg = df_off.loc[df_off['Dir'] =='horizontal']
    elif mode == 'vertical':
        label_list = ['0x0002', '0x0010', '0x0080', '0x0400']
        mode_list = [2, 16, 128, 1024]
        df_signal = df_on.loc[df_on['Dir'] == 'vertical']
        df_bkg = df_off.loc[df_off['Dir'] == 'vertical']
    else:
        df_signal = df_on
        df_bkg = df_off
        label_list = ['0x0001', '0x0002', '0x0004', '0x0008', '0x0010',
                      '0x0020', '0x0040', '0x0080', '0x0100', '0x0200',
                      '0x0400', '0x0800']
        c0 = 'royalblue'
        c1 = 'goldenrod'
        color_list = [c0, c1, c0, c0, c1, c0, c0, c1, c0, c0, c1, c0]

    low_hv = df_signal["HVLowGain"].values[0]

    fig1, ax1 = plt.subplots()
    ax1.set_title(f'Flasher Scaler Test, HV={low_hv} V')
    ax1.set_ylabel('Rate [Hz]')
    ax1.set_xlabel(f'LED Configuration {degg_id} - {mode}')
    if mode == 'horizontal' or mode == 'vertical':
        ax1.plot(np.arange(df_signal.index.size), df_signal['Rate'],
                 marker='o', linewidth=0, color='royalblue', label=mode)
        ax1.legend()
    else:
        ax1.scatter(np.arange(df_signal.index.size), df_signal['Rate'], marker='o',
                 linewidth=0, color=color_list)

    fig1.tight_layout()
    fig1.savefig(savedir + f'signal_{degg_id}_{mode}.pdf')

def baselinePlots(df_0, df_off, degg_id, savedir):
    off_rate = df_off['Rate'].values
    null_rate = df_0['Rate'].values[0]
    diff = abs(off_rate - null_rate)
    low_hv = df_off["HVLowGain"].values[0]
    fig1, ax1 = plt.subplots()
    ax1.plot(np.arange(len(diff)), diff, marker='o', linewidth=0)
    ax1.set_xlabel(f'LED Configuration {degg_id}')
    ax1.set_title(f'Null Measurements, HV={low_hv} V')
    ax1.set_ylabel('Off - Baseline [Hz]')
    fig1.savefig(savedir + f'null_{degg_id}.pdf')

def flasher_plot(df, degg_id, savedir):
    df_on = df.loc[df['FlasherStatus'] == True]
    df_off = df.loc[(df['FlasherStatus'] == False) & (df['Config'] != 0)]

    ## calculate difference in the on/off rates, use config 0 for baseline
    df_0 = df.loc[df['Config'] == 0]

    #print(df_0)
    #print(df_off)
    #print(df_on)

    baselinePlots(df_0, df_off, degg_id, savedir)
    signalPlots(df_off, df_on, degg_id, savedir, mode='all')
    signalPlots(df_off, df_on, degg_id, savedir, mode='horizontal')
    signalPlots(df_off, df_on, degg_id, savedir, mode='vertical')

def read_scaler_data(filename, return_indiv_counts=False):
    with tables.open_file(filename) as open_file:
        if return_indiv_counts:
            data = open_file.get_node('/data')
            scaler_counts = data.col('scaler_count')
        parameters = open_file.get_node('/parameters')

        parameter_keys = parameters.keys[:]
        parameter_values = parameters.values[:]
        parameter_dict = {}
        for key, val in zip(parameter_keys, parameter_values):
            key = key.decode('utf-8')
            val = val.decode('utf-8')
            try:
                parameter_dict[key] = int(val)
            except ValueError:
                parameter_dict[key] = val
    if return_indiv_counts:
        return parameter_dict, scaler_counts
    else:
        return parameter_dict


def analyze_scaler_data(parameter_dict):
    try:
        # convert from microseconds to seconds
        total_duration = (parameter_dict['period'] / 1e6 *
            parameter_dict['n_runs'])
    except KeyError:
        total_duration = parameter_dict['period'] / 1e6
    # convert from FPGA clock cycles to seconds
    deadtime = parameter_dict['deadtime'] / 240e6

    scaler_count = parameter_dict['scaler_count']
    time = total_duration - (scaler_count * deadtime)

    rate = scaler_count / time
    error = np.sqrt(scaler_count / time)
    return rate, error, deadtime, time

def find_keys(dct, partial_key):
    keys = [key for key in dct.keys()
            if partial_key in key]
    return keys

def flasher_ana(degg_file, degg_dict, logbook, savedir, run_number, remote=False, offline=False):
    print('-' * 20)
    data_key = 'FlasherCheck'
    degg_id = degg_dict['DEggSerialNumber']
    pmt_id = degg_dict['LowerPmt']['SerialNumber']
    print(f"DEGG ID: {degg_id}, PMT ID: {pmt_id}")

    keys = find_keys(degg_dict['LowerPmt'], data_key)
    if len(keys) == 0:
        send_warning(f'Trying to run flasher ana for {degg_id} but no files found!')
        return
        #raise Exception(f'No valid keys found for: {degg_id}:{pmt_id} !')
    key = keys[-1]
    if audit_ignore_list(degg_file, degg_dict, key) == True:
        return

    if logbook != None:
        result = Result(pmt_id, logbook=logbook, run_number=run_number, remote_path=REMOTE_DATA_DIR)

    fig, ax = plt.subplots()

    if remote:
        folder = degg_dict['LowerPmt'][key]['RemoteFolder']
    else:
        folder = degg_dict['LowerPmt'][key]['Folder']
    #folder = degg_dict['LowerPmt'][key]['Folder']
    try:
        temperature = degg_dict['LowerPmt'][key]['Temperature']
    except:
        print('temperature data missing! Old data? (2022/05/12)')
        temperature = -999
    data_file = glob(os.path.join(folder, pmt_id + '*.hdf5'))[0]
    with tables.open_file(data_file) as f:
        data = f.get_node('/data')
        charge = data.col('chargestamp')
        ledbias = data.col('ledbias')
        ledmask = data.col('ledmask')

        _xvals = []
        _yvals = []

        numPass = 0
        maxChargeList = []
        fixedledmask = [2**i for i in range(12)]
        for i, _ledmask in enumerate(fixedledmask):
            thecharge = charge[ledmask==_ledmask]
            meanList = []
            thisMaxMedian = 0
            thisMax = 0
            for j, _ledbias in enumerate(ledbias[::12]):
                c = thecharge[j]
                #print(f'{_ledbias}: {np.max(c)}, {np.median(c)}, {np.mean(c)}, {np.std(c)}')
                if np.median(c) > thisMaxMedian:
                    thisMaxMedian = np.median(c)
                if np.max(c) > thisMax:
                    thisMax = np.max(c)

                meanList.append(np.mean(c))
            setcolor = cm.tab10(i/10) if i < 10 else cm.Set2((i-10)/8)
            ax.plot(ledbias[ledmask==_ledmask], meanList, label=f'LED{i+1}',color=setcolor,lw=lws[i])
            maxChargeList.append(np.max(thecharge))
            _xvals.append(ledbias[ledmask==_ledmask])
            _yvals.append(meanList)

            ##check if LED is reliably producing more than ~3 PE
            if thisMaxMedian >= (3 * 1.6):
                numPass += 1
            ##else check if LED is still bright sometimes
            elif thisMaxMedian >= (2 * 1.6) and thisMax >= (10 * 1.6):
                numPass += 1
            else:
                numPass += 0

        print(_xvals[0])
        print(type(_xvals[0]))
        print(_xvals[0].tolist())
        if logbook != None:
            json_filenames = result.to_json(
                meas_group='luminosity',
                raw_files=data_file,
                folder_name=DB_JSON_PATH,
                filename_add=data_key.replace('Folder', ''),
                ledmask=fixedledmask,
                ledbias=ledbias[::12],
                maxcharge=maxChargeList,
                numPass=numPass,
                xvals=_xvals[0],
                yvals=_yvals,
                temperature=temperature
            )

            run_handler = RunHandler(filenames=json_filenames)
            run_handler.submit_based_on_meas_class()

        print(f"Number of LEDs Passing: {numPass}")

        plot_dir = os.path.join(savedir, run_number)
        if offline:
            outpdf = os.path.join(plot_dir, f'{pmt_id}_offline')
        else:
            outpdf = os.path.join(plot_dir, f'{pmt_id}')
        #pdf = PdfPages(outpdf)
        ax.legend()
        ax.axhline(3*1.6,ls=':',lw=1,color='magenta')
        ax.set_title(f'PMT: {pmt_id}')
        ax.set_xlabel('LED Bias')
        ax.set_ylabel('Relative intensity')
        if not os.path.exists(plot_dir):
            print(f"Making {plot_dir}")
            os.mkdir(plot_dir)

        fig.savefig(os.path.join(plot_dir, f'{outpdf}.pdf'))
        #pdf.savefig()
        ax.set_yscale('log')
        fig.savefig(os.path.join(plot_dir, f'{outpdf}_log.pdf'))
        #pdf.savefig()
        #pdf.close()
        #fig.savefig(os.path.join(plot_dir, f'{pmt_id}.pdf'))
        #fig.tight_layout()
        plt.close(fig)


def analysis_wrapper(run_json, remote=False, offline=False):
    savedir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots')
    if not os.path.exists(savedir):
        os.mkdir(savedir)

    list_of_deggs = load_run_json(run_json)
    if offline is False:
        logbook = DEggLogBook()
    else:
        logbook = None
        print('Running offline for testing!')
    f = os.path.basename(run_json)
    run_number = f.split('_')[1]
    run_number = run_number.split('.')[0]
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        flasher_ana(degg_file, degg_dict, logbook, savedir,
                    run_number, remote=remote, offline=offline)

        degg_id = degg_dict['DEggSerialNumber']
        #flasher_plot(df, degg_id, savedir)


@click.command()
@click.argument('run_json')
@click.option('--remote', is_flag=True)
@click.option('--offline', is_flag=True)
def main(run_json, remote, offline):
    analysis_wrapper(run_json, remote, offline)
    print("Done")

if __name__ == "__main__":
    main()

##end
