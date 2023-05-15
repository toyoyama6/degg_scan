from glob import glob
import matplotlib.pyplot as plt
import numpy as np
import sys, os
import click

###################
from degg_measurements.analysis.darkrate.loading import make_scaler_darkrate_df
from degg_measurements.utils import load_run_json, load_degg_dict, extract_runnumber_from_path
###################

PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
TAPING_CORR_FACTOR = 2.375
FPGA_CLOCK_TO_S = 1. / 240e6
T_OFFSET = 3600 * 1

def run_analysis(key, degg_dict, pmt, run_number, run_plot_dir, scaler=False, multi=False):
    folder = degg_dict[pmt][key]['Folder']
    pmt_id = degg_dict[pmt]['SerialNumber']


    #valid_pmts = ['SQ0295', 'SQ0555', 'SQ0309', 'SQ0573', 'SQ0418', 'SQ0578', 'SQ0421', 
    #              'SQ0607', 'SQ0480', 'SQ0648', 'SQ0482', 'SQ0649', 'SQ0485', 'SQ0686', 
    #              'SQ0522', 'SQ0737']
    #if pmt_id not in valid_pmts:
    #    return 0, 0, False

    files = sorted(glob(os.path.join(folder, pmt_id + '*.hdf5')))
    if len(files) > 1 and run_number == 114:
        print("Trimming only 18 ADC Threshold for scalers!")
        files = files[1]
    if scaler == True:
        for f in files:
            df, dfr, plotting, thr = inner_analysis(f, key, degg_dict, pmt, run_number, run_plot_dir, scaler, multi)
            if plotting == True and thr == '0.3_0' and multi == True:
                _df30 = df
                _dfr30 = dfr
            elif plotting == True and thr == '0.25_0':
                _df = df
                _dfr = dfr
    else:
        inner_analysis(files, key, degg_dict, pmt, run_number, run_plot_dir)

    if multi == True:
        try:
            t = np.arange(0, len(_df30.meas_t.values))
            deadtime = _df30.deadtime * FPGA_CLOCK_TO_S
            time = (_df30.period / 1e6) - (_df30.indv_cnt * deadtime)
            return t, _df30.indv_cnt / time, True
        except:
            return 0, 0, False
    else:
        try:
            return _df['adcThresh'].values[0], _dfr, True
        except:
            return 0, 0, False

def inner_analysis(files, key, degg_dict, pmt, run_number, run_plot_dir, scaler=False, multi=False):
    print("----------")
    dac_value = degg_dict['Constants']['DacValue']
    pmt_id = degg_dict[pmt]['SerialNumber']
    if scaler == True:
        darkrate_df = make_scaler_darkrate_df(files, use_quantiles=True, get_time=False,
                        key=key,
                        run_number=run_number,
                        dac_value=dac_value)
    else:
        darkrate_df = make_scaler_darkrate_df(files, use_quantiles=False, get_time=True,
                        key=key,
                        run_number=run_number,
                        dac_value=dac_value)

    deadtime = darkrate_df.deadtime * FPGA_CLOCK_TO_S
    time = (darkrate_df.period / 1e6) - (darkrate_df.indv_cnt * deadtime)
    dark_rate = darkrate_df.indv_cnt / time

    port = degg_dict['Port']
    degg_id = degg_dict['DEggSerialNumber']
    try:
        tag = degg_dict[pmt][key]['Mode']
    except KeyError:
        tag = 'scaler'
    print(degg_id, port)
    #print(darkrate_df.meas_t.values)
    dr_cor = dark_rate / TAPING_CORR_FACTOR
    dr_err = np.sqrt(dr_cor) / dr_cor

    threshold = files.split("/")[-1]
    threshold = threshold[:-5]
    threshold = threshold[7:]


    max_time = np.max(darkrate_df.meas_t.values)
    time = darkrate_df.meas_t.values

    fig1, ax1 = plt.subplots()
    if np.sum(darkrate_df.meas_t.values) / len(darkrate_df.meas_t.values) == -1:
        print(len(darkrate_df.meas_t.values)-1, len(dr_cor[1:]))
        ax1.errorbar(np.arange(1, len(darkrate_df.meas_t.values)), dr_cor[1:], linewidth=0, marker='o')
        ax1.set_xlabel('Measurement #')
    else:
        ax1.errorbar(max_time-time[1:], dr_cor[1:], linewidth=0, marker='o')
        ax1.set_xlabel('Time [s]')
    ax1.set_title(f'{pmt_id} ({degg_id}, {port})')
    ax1.set_ylabel('Dark Rate (Corr.) [Hz]')
    fig1.tight_layout()
    if scaler == True:
        fig1.savefig(os.path.join(run_plot_dir, f'dark_rate_vs_time_{pmt_id}_{port}_{tag}_{threshold}.png'), dpi=300)
    else:
        fig1.savefig(os.path.join(run_plot_dir, f'dark_rate_vs_time_{pmt_id}_{port}_{tag}.png'), dpi=300)
    plt.close(fig1)
    
    fig1b, ax1b = plt.subplots()
    if np.sum(darkrate_df.meas_t.values) / len(darkrate_df.meas_t.values) == -1:
        print(len(darkrate_df.meas_t.values)-1, len(dr_cor[1:]))
        ax1b.errorbar(np.arange(1, len(darkrate_df.meas_t.values)), dr_cor[1:], linewidth=0, marker='o')
        ax1b.set_xlabel('Measurement #')
    else:
        ax1b.errorbar(max_time-time[1:], dr_cor[1:], linewidth=0, marker='o')
        ax1b.set_xlabel('Time [s]')
    ax1b.set_ylim(500, 2500)
    ax1b.set_title(f'{pmt_id} ({degg_id}, {port})')
    ax1b.set_ylabel('Dark Rate (Corr.) [Hz]')
    fig1b.tight_layout()
    if scaler == True:
        fig1b.savefig(os.path.join(run_plot_dir, f'dark_rate_vs_time_zoom_{pmt_id}_{port}_{tag}_{threshold}.png'), dpi=300)
    else:
        fig1b.savefig(os.path.join(run_plot_dir, f'dark_rate_vs_time_zoom_{pmt_id}_{port}_{tag}.png'), dpi=300)
    plt.close(fig1b)

    fig2, ax2 = plt.subplots()
    ax2.hist(dr_cor, bins=50, histtype='step')
    ax2.plot([np.mean(dr_cor), np.mean(dr_cor)], [0, 100], color='goldenrod')
    ax2.set_ylabel('Entries')
    ax2.set_xlabel(f'Dark Rate [Hz] (T={darkrate_df.period[0]} [us])')
    ax2.set_title(f'{pmt_id} ({degg_id}, {port})')
    if scaler == True:
        fig2.savefig(os.path.join(run_plot_dir, f'dark_rate_hist_{pmt_id}_{port}_{tag}_{threshold}.pdf'))
    else:
        fig2.savefig(os.path.join(run_plot_dir, f'dark_rate_hist_{pmt_id}_{port}_{tag}.pdf'))
    plt.close(fig2)
    print(f'{pmt_id} Ave: {np.mean(dr_cor)}')
    print(f'{pmt_id} Median: {np.median(dr_cor)}')
    
    ##calculate number of pts are above or below 2500 Hz
    mask = dr_cor <= 2500
    print(f'{pmt_id} Npts: {len(mask)}')
    print(f'{pmt_id} Normal Pts: {np.sum(mask)}')
    print(f'{pmt_id} Frac <= 2500 Hz: {np.sum(mask) / len(mask)}')

    if scaler != True:
        temp = darkrate_df.tempScaler.values
        hv = darkrate_df.highVoltage.values
    
        fig3, ax3 = plt.subplots()
        ax3.plot(max_time-time[1:], temp[1:], linewidth=0, marker='o')
        ax3.set_xlabel('Time [s]')
        ax3.set_ylabel('MB Temperature [C]')
        ax3.set_title(f'{pmt_id} ({degg_id}, {port})')
        fig3.tight_layout()
        if scaler == True:
            fig3.savefig(os.path.join(run_plot_dir, f'temp_{pmt_id}_{port}_{tag}_{threshold}.png'), dpi=300)
        else:
            fig3.savefig(os.path.join(run_plot_dir, f'temp_{pmt_id}_{port}_{tag}.png'), dpi=300)
        plt.close(fig3)
    
        fig4, ax4 = plt.subplots()
        ax4.plot(max_time-time[1:], hv[1:], linewidth=0, marker='o')
        ax4.set_xlabel('Time [s]')
        ax4.set_ylabel('High Voltage [V]')
        ax4.set_title(f'{pmt_id} ({degg_id}, {port})')
        fig4.tight_layout()
        if scaler == True:
            fig4.savefig(os.path.join(run_plot_dir, f'hv_{pmt_id}_{port}_{tag}_{threshold}.png'), dpi=300)
        else:
            fig4.savefig(os.path.join(run_plot_dir, f'hv_{pmt_id}_{port}_{tag}.png'), dpi=300)
        plt.close(fig4)

    if multi == True and threshold == '0.3_0':
        print("returning for 30%!")
        return darkrate_df, (np.sum(mask) / len(mask)), True, '0.3_0'
    elif threshold == '0.25_0':
        print("returning for 25!")
        return darkrate_df, (np.sum(mask) / len(mask)), True, '0.25_0'
    else:
        return 0, 0, False, 0

def analysis_wrapper(run_json, measurement_number,
                     scaler=False):

    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)
    #data_key = 'PostFlashRegularization'
    #data_key = 'PostFlashRegularizationHigh'
    if run_number == 114:
        data_key = 'DarkrateScalerMeasurement'
    elif scaler == True:
        data_key = 'DarkrateScalerMeasurement'
    else:
        data_key = 'PostFlashRegularizationnull'

    keys_list = []
    thresholds = []
    #ratio of events below 2500 Hz / total
    dfrs = []

    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        if run_number == 114 or scaler == True:
            pmts = ['LowerPmt', 'UpperPmt']
        else:
            pmts = ['LowerPmt']
        for pmt in pmts:
            if measurement_number == 'latest':
                eligible_keys = [key for key in degg_dict[pmt].keys()
                                 if key.startswith(data_key)]
                cts = [int(key.split('_')[1]) for key in eligible_keys]
                if len(cts) == 0:
                    print(f'No measurement found for '
                          f'{degg_dict[pmt]["SerialNumber"]} '
                          f'in DEgg {degg_dict["DEggSerialNumber"]}. '
                          f'Skipping it!')
                    continue
                measurement_number = np.max(cts)
            if type(measurement_number) == np.int64:
                measurement_number = [measurement_number]
            print(measurement_number)
            #loop over all configured measurements
            for num in measurement_number:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                print(data_key_to_use)
                if data_key_to_use not in keys_list:
                    keys_list.append(data_key_to_use)
                run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key_to_use}')
                if not os.path.isdir(run_plot_dir):
                    os.mkdir(run_plot_dir)

                threshold, dfr, valid = run_analysis(data_key_to_use, degg_dict,
                         pmt, run_number, run_plot_dir, scaler)
                if valid == True:
                    thresholds.append(int(float(threshold)))
                    dfrs.append(dfr)

    fig0, ax0 = plt.subplots()
    ax0.hist(thresholds, bins=9, range=[10, 19], histtype='step')
    ax0.set_xlabel('Threshold Over Baseline (25% of <SPE>) [ADC]')
    ax0.set_ylabel('PMTs')
    ax0.set_title(f'{run_number} - {data_key_to_use}')
    fig0.savefig(os.path.join(run_plot_dir, 'threshold_hist.pdf'))
    plt.close(fig0)

    dfrs = np.array(dfrs)
    fig1, ax1 = plt.subplots()
    ax1.plot(thresholds, dfrs * 100, 'o')
    ax1.set_xlabel('Threshold Over Baseline (25% of <SPE>) [ADC]')
    ax1.set_ylabel(r'$N_{DR}$ <= 2500 Hz / $N_{Total}$ [%]')
    ax1.set_title(f'{run_number} - {data_key_to_use}')
    fig1.savefig(os.path.join(run_plot_dir, 'threshold_vs_dfrs.pdf'))
    plt.close(fig1)

def multi_ana_wrapper(run_json1, run_json2, run_json3=None,
                      n1='latest', n2='latest', n3=None, scaler=False):
    if n3 != None:
        measurement_number = [n1, n2, n3]
    else:
        measurement_number = [n1, n2]

    if run_json1 == run_json2:
        same_run = True
        list_of_deggs = load_run_json(run_json1)
        run_number = extract_runnumber_from_path(run_json1)
    else:
        same_run = False
        print("different runs not yet implemented")
        exit(1)

    if scaler == True:
        data_key = 'DarkrateScalerMeasurement'
   
    keys_list = [] 
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        if scaler == True:
            pmts = ['LowerPmt', 'UpperPmt']
        else:
            pmts = ['LowerPmt']
        for pmt in pmts:
            pmt_id = degg_dict[pmt]['SerialNumber']
            if type(measurement_number) == np.int64:
                measurement_number = [measurement_number]
            #loop over all configured measurements
            fig, ax = plt.subplots()
            for num in measurement_number:
                num = int(num)
                suffix = f'_{num:02d}'
                data_key_to_use = data_key + suffix
                print(data_key_to_use)
                if data_key_to_use not in keys_list:
                    keys_list.append(data_key_to_use)
                run_plot_dir = os.path.join(PLOT_DIR, f'{run_number}_{data_key_to_use}')
                if not os.path.isdir(run_plot_dir):
                    os.mkdir(run_plot_dir)
                t, dr, plotting = run_analysis(data_key_to_use, degg_dict,
                                    pmt, run_number, run_plot_dir, scaler, multi=True)
                if plotting:
                    print("plotted!")
                    ax.plot(t, dr, 'o', label=f'{num}', alpha=0.6)
            
            ax.set_xlabel('Measurement Number')
            ax.set_ylabel('Dark Rate (Corr.) [Hz]')
            ax.legend()
            ax.set_title(f'{pmt_id} - 30% <SPE>')
            fig.tight_layout()
            fig.savefig(os.path.join(run_plot_dir, f'common_threshold_{pmt_id}.png'), dpi=300)


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
@click.option('--measurement_number', '-n', default='latest')
@click.option('run_json2', '-r2', type=click.Path(exists=True), default=None)
@click.option('--measurement_number2', '-n2', default='latest')
@click.option('run_json3', '-r3', type=click.Path(exists=True), default=None)
@click.option('--measurement_number3', '-n3', default=None)
@click.option('--scaler', is_flag=True)
def main(run_json, measurement_number, run_json2, 
         measurement_number2, run_json3, measurement_number3,
         scaler):
    if run_json2 == None and run_json3 == None:
        analysis_wrapper(run_json, measurement_number,
                     scaler)
    if run_json2 != None or run_json3 != None:
        multi_ana_wrapper(run_json, run_json2, run_json3,
                          measurement_number, measurement_number2, measurement_number3,
                          scaler)

if __name__ == "__main__":
    main()

##end
