import numpy as np
import click
import os, sys
import pandas as pd
import csv
from glob import glob
import json
import matplotlib.pyplot as plt


def json_info(json_file):
    with open(json_file, 'r') as open_file:
        current_dict = json.load(open_file)
        device = current_dict['device_uid']
        subdevice_uid = current_dict['subdevice_uid']
        pmt = subdevice_uid.split("_")[-1]
        try:
            hv = current_dict['meas_data'][0]['value']
        except KeyError:
            hv = current_dict['meas_data'][0]['x_values'][-1]

        x_values = current_dict['meas_data'][0]['x_values']
        y_values = current_dict['meas_data'][0]['y_values']

        temp = current_dict['meas_data'][0]['temperature']

    return device, pmt, hv, temp, x_values, y_values


def extract_info(input_file):
    this_path = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(this_path, '../database_jsons')

    device_l =[]
    pmt_l = []
    hv_l = []
    temperature_l =[]
    run_l = []
    meas_l = []
    id_l = []
    x_l = []
    y_l = []

    with open(input_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        len_rows = 0
        run_id = 0
        for row in reader:
            run_num  = row['RunNumber']
            meas_num = row['MeasurementNumber']
            file_dir = os.path.join(json_dir, f'run_{run_num}')
            json_file_list = glob(file_dir+f'/*GainMeasurement*_{meas_num}.json')
            if len(json_file_list) == 0:
                raise IOError('Globbed file list is empty! Check csv file!')

            for json_file in json_file_list:
                device, pmt, hv, temp, x_vals, y_vals = json_info(json_file)
                device_l.append(device)
                pmt_l.append(pmt)
                hv_l.append(hv)
                temperature_l.append(temp)
                run_l.append(run_num)
                meas_l.append(meas_num)
                id_l.append(run_id)
                x_l.append(x_vals)
                y_l.append(y_vals)

            run_id += 1
            len_rows += 1

    d = {
        'Run':run_l,
        'Measurement':meas_l,
        'ID': id_l,
        'Device':device_l,
        'PMT': pmt_l,
        'HV': hv_l,
        'Temperature': temperature_l,
        'xVals': x_l,
        'yVals': y_l
        }
    df = pd.DataFrame(data=d)
    return df, len_rows


def make_plot(df, plot_dir, show_run=False):
    device_l = df['Device']
    pmt_l = df['PMT']
    hv_l = df['HV']
    temp_l = df['Temperature']
    run = df['Run'].values[0]
    meas = df['Measurement'].values[0]


    bins = np.arange(1400, 1820, 20)
    fig1, ax1 = plt.subplots()
    ax1.hist(list(map(float, hv_l)), bins=bins, label=f'N={len(hv_l)}')
    ax1.set_xlabel('HV at 1e7 Gain [V]')
    ax1.set_ylabel('Num. PMTs')
    if show_run == False:
        ax1.set_title('D-Egg PMT HVs at 1e7 Gain')
    if show_run == True:
        ax1.set_title(f'Run:{run} - Measurement:{meas}')

    ax1.legend()
    save = os.path.join(plot_dir, 'summary_hv.pdf')
    fig1.savefig(save)

    for i, pmt in enumerate(pd.unique(df['PMT'])):
        temp_df = df[df.PMT == pmt]
        x_l = temp_df['xVals'].values
        y_l = temp_df['yVals'].values
        i = 0
        fig2, ax2 = plt.subplots()
        for xs, ys in zip(x_l, y_l):
            x = list(map(float, xs))
            y = list(map(float, ys))
            if i < 10:
                if i == 0:
                    ax2.plot(x, y, marker='x', linewidth=0, label=f'+30ish')
                else:
                    ax2.plot(x, y, marker='x', linewidth=0)
            if i >= 10:
                if i == 10:
                    ax2.plot(x, y, marker='o', markerfacecolor='none', linewidth=0, label=f'-40')
                else:
                    ax2.plot(x, y, marker='o', markerfacecolor='none', linewidth=0)
            i += 1

        x_l = np.array(x_l)
        flat_x_l = x_l.flatten()
        flat_x_l = sum(flat_x_l, [])
        ax2.plot([np.amin(flat_x_l), np.amax(flat_x_l)], [1e7, 1e7], linestyle='dashdot', color='red')
        ax2.set_title(f'PMT:{pmt} ({temp_df["Device"].values[0]})')
        ax2.legend(title='Temp.')
        ax2.set_yscale('log')
        ax2.set_xlabel('Control Voltage [V]')
        ax2.set_ylabel('Gain')
        save2 = os.path.join(plot_dir, f'gain_summary_{pmt}.pdf')
        fig2.savefig(save2)
        plt.close(fig2)

def make_multi_plot(df, plot_dir):

    d = {'Run':df['Run'].values, 'Measurement':df['Measurement'].values}
    sub_df = pd.DataFrame(data=d)
    tuples = sub_df.to_records(index=False)
    unique_pairs = pd.unique(tuples)

    bins = np.arange(1400, 1820, 20)
    fig1, ax1 = plt.subplots()
    for pair in unique_pairs:
        condition = (df.Run == pair[0]) & (df.Measurement == pair[1])
        temp_df = df[condition]
        device_l = temp_df['Device']
        pmt_l = temp_df['PMT']
        hv_l = temp_df['HV']
        temp_l = temp_df['Temperature']
        label = f'{pair[0]}, {pair[1]}'
        ax1.hist(list(map(float, hv_l)), histtype='step',
                 bins=bins, label=label)

    ax1.set_xlabel('HV at 1e7 Gain [V]')
    ax1.set_ylabel('Num. PMTs')
    ax1.set_title('D-Egg PMT HVs at 1e7 Gain')
    #ax1.legend(title='Run, SubRun')

    save = os.path.join(plot_dir, 'summary_per_run_hv.pdf')
    fig1.savefig(save)
    plt.close(fig1)

    hv_l = df['HV']
    id_l = df['ID']
    fig2, ax2 = plt.subplots()
    pair_ind = np.linspace(0, len(unique_pairs), 1)
    ax2.scatter(id_l, list(map(float, hv_l)))
    ax2.set_xlabel('Measurement ID')
    ax2.set_ylabel('HV at 1e7 Gain [V]')
    save2 = os.path.join(plot_dir, 'scatter_hv.pdf')
    fig2.savefig(save2)
    plt.close(fig2)

    spread = []
    fig3 = plt.figure(constrained_layout=True)
    gs = fig3.add_gridspec(2, 2, height_ratios=[5, 1], width_ratios=[25,1], hspace=0.01)
    ax3a = fig3.add_subplot(gs[0, 0])
    ax3b = fig3.add_subplot(gs[1, 0])
    ax3c = fig3.add_subplot(gs[:, 1])

    ##make plots on per PMT basis
    print("Trying to make plots for each PMT across runs")
    for i, pmt in enumerate(pd.unique(df['PMT'])):
        print(f"{i}, {pmt}")
        temp_df = df[df.PMT == pmt]
        hv_l = temp_df.HV
        i_l = np.full(len(hv_l), i)
        p = ax3a.scatter(i_l[:9],
                    list(map(float, hv_l[:9])),
                    c=np.arange(len(hv_l[:9])),
                    cmap='viridis')
        p = ax3a.scatter(i_l[10:], hv_l.values[10:],
                        c='mediumvioletred',
                        marker='x')
        #hv_std = np.std(hv_l.values)
        hv_std = np.quantile(hv_l.values, 0.9)
        #print(hv_std)
        spread.append((hv_std / np.mean(hv_l.values)) - 1)
    fig3.colorbar(p, cax=ax3c, label='Measurements')
    ax3a.grid()
    ax3b.grid()

    xs = np.arange(0, 32)
    ax3a.set_xticklabels([])
    ax3b.scatter(xs, spread)

    ax3b.set_ylabel(r'Q=0.9/Mean')
    ax3b.set_xlabel('PMT ID')
    ax3a.set_ylabel('HV at 1e7 Gain [V]')
    save3 = os.path.join(plot_dir, 'scatter_pmt.pdf')
    fig3.savefig(save3)

##input file is pair of run number & measurement number
@click.command()
@click.argument('input_file')
def main(input_file):
    if not os.path.isfile(input_file):
        raise IOError(f'Could not find list of measurements: {input_file}!')

    plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_summ')

    dataframe, input_size = extract_info(input_file)
    print(dataframe)

    if input_size > 1:
        make_plot(dataframe, plot_dir, show_run=False)
    else:
        make_plot(dataframe, plot_dir, show_run=True)

    make_multi_plot(dataframe, plot_dir)

if __name__ == "__main__":
    main()


##end
