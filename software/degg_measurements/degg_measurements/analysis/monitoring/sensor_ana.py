from degg_measurements.utils import load_degg_dict, load_run_json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import click
import csv
import matplotlib.dates as mdates
import os, sys
import re
import glob

def hv_tests(df, degg_id, run, set_hv_u, set_hv_l, measurement, filepath):
    print("Runnning HV Tests")

    hv0 = np.array(df['voltage_channel0'], dtype=float)
    hv1 = np.array(df['voltage_channel1'], dtype=float)
    time = pd.to_datetime(df.index)
    min_time = time[0]
    max_time = time[-1]
    #print(time)
    temp = np.array(df['temperature_sensor'], dtype=float)
    min_temp = temp[0] - 3
    max_temp = temp[-1] + 3
    #print(temp)

    fig1, ax1 = plt.subplots()
    ax1.plot(time, hv0, label='Ch0', color='royalblue')
    ax1.set_title(degg_id)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()
    if set_hv_l is not None and set_hv_l != -1:
        ax1.plot([min_time, max_time], [set_hv_l, set_hv_l], label='HV 1e7 Gain', color='red', markersize=0)
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv0_time.pdf')

    fig2, ax2 = plt.subplots()
    ax2.plot(time, hv1, label='Ch1', color='goldenrod')
    ax2.set_title(degg_id)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    ax2.legend()
    if set_hv_u is not None and set_hv_u != -1:
        ax2.plot([min_time, max_time], [set_hv_u, set_hv_u], label='HV 1e7 Gain', color='red', markersize=0)
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv1_time.pdf')

    fig1b, ax1b = plt.subplots()
    ax1b.plot(temp, hv0, label='Ch0', color='royalblue', marker='o', linewidth=0)
    ax1b.set_title(degg_id)
    ax1b.set_xlabel('Temperature')
    ax1b.set_ylabel('PMT High Voltage [V]')
    ax1b.grid()
    ax1b.legend()
    if set_hv_l is not None and set_hv_l != -1:
        ax1b.plot([min_temp, max_temp], [set_hv_l, set_hv_l], label='HV 1e7 Gain', color='red', markersize=0)
    fig1b.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv0_temperature.pdf')

    fig2b, ax2b = plt.subplots()
    ax2b.plot(temp, hv1, label='Ch1', color='goldenrod', marker='o', linewidth=0)
    ax2b.set_title(degg_id)
    ax2b.set_xlabel('Temperature')
    ax2b.set_ylabel('PMT High Voltage [V]')
    ax2b.grid()
    ax2b.legend()
    if set_hv_u is not None and set_hv_u != -1:
        ax2b.plot([min_temp, max_temp], [set_hv_u, set_hv_u], label='HV 1e7 Gain', color='red', markersize=0)
    fig2b.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv1_temperature.pdf')

    hv0 = np.array(hv0)
    hv1 = np.array(hv1)
    diff_hv0 = np.diff(hv0)
    diff_hv1 = np.diff(hv1)

    fig3, ax3 = plt.subplots()
    ax3.plot(time[:-1], diff_hv0, label='Ch0', color='royalblue', marker='o', linewidth=0)
    ax3.set_title(degg_id)
    ax3.set_xlabel('Time')
    ax3.set_ylabel(r'$\Delta$ PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax3.xaxis.set_major_formatter(date_format)
    fig3.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax3.grid()
    ax3.legend()
    fig3.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv0_diff_time.pdf')

    fig4, ax4 = plt.subplots()
    ax4.plot(time[:-1], diff_hv1, label='Ch1', color='goldenrod', marker='o', linewidth=0)
    ax4.set_title(degg_id)
    ax4.set_xlabel('Time')
    ax4.set_ylabel(r'$\Delta$ PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax4.xaxis.set_major_formatter(date_format)
    fig4.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax4.grid()
    ax4.legend()
    fig4.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv1_diff_time.pdf')

    fig5, ax5 = plt.subplots()
    ax5.hist(hv0, bins=20, label='Ch0', color='royalblue')
    ax5.set_title(degg_id)
    ax5.set_xlabel('PMT HV [V]')
    ax5.legend()
    if set_hv_l is not None and set_hv_l != -1:
        ax5.axvline(x=set_hv_l, color='red', linestyle='dashed', linewidth=2)
        ax5.axvspan(set_hv_l * 0.95, set_hv_l * 1.05, color='gray', alpha=0.5)
    #ax5.fill_between((set_hv_l * 0.95, set_hv_l * 1.05), facecolor='gray', alpha=0.5)
    fig5.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv0.pdf')

    fig6, ax6 = plt.subplots()
    ax6.hist(hv1, bins=20, label='Ch1', color='goldenrod')
    ax6.set_title(degg_id)
    ax6.set_xlabel('PMT HV [V]')
    ax6.legend()
    if set_hv_u is not None and set_hv_u != -1:
        ax6.axvline(x=set_hv_u, color='red', linestyle='dashed', linewidth=2)
        ax6.axvspan(set_hv_u * 0.95, set_hv_u * 1.05, color='gray', alpha=0.5)
    #ax6.fill_between(set_hv_u * 0.95, set_hv_u * 1.05, facecolor='gray', alpha=0.5)
    fig6.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv1.pdf')


def hv_tests_aggregate(df_list, degg_id_list, filepath):
    print("Running HV Aggregate Tests")

    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()

    index = 0
    for df in df_list:
        degg_id = degg_id_list[index]
        hv0 = np.array(df['voltage_channel0'], dtype=float)
        hv1 = np.array(df['voltage_channel1'], dtype=float)
        time = pd.to_datetime(df.index)
        ax1.plot(time, hv0, label=degg_id, marker='o', linewidth=0)
        ax2.plot(time, hv1, label=degg_id, marker='o', linewidth=0)
        index += 1

    ax1.set_title("Channel 0")
    ax1.set_xlabel('Time')
    ax1.set_ylabel('PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()
    fig1.savefig(f'{filepath}/aggregate_hv0_time.pdf')

    ax2.set_title("Channel 1")
    ax2.set_xlabel('Time')
    ax2.set_ylabel('PMT High Voltage [V]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    ax2.legend()
    fig2.savefig(f'{filepath}/aggregate_hv1_time.pdf')


def temperature_tests(df, degg_id, run, temp_df, measurement, filepath):
    print("Running Temperature Tests")

    if temp_df is not None:
        temp_time = pd.to_datetime(temp_df.index)
        temp_ch1 = temp_df['Temp Channel 1'] #degg exterior
        temp_ch2 = temp_df['Temp Channel 2'] #box exterior
        temp_ch3 = temp_df['Temp Channel 3'] #box interior
        temp_ch4 = temp_df['Temp Channel 4'] #room temp

    temp = df['temperature_sensor']
    time = pd.to_datetime(df.index)
    min_time = np.min(time)
    max_time = np.max(time)

    if temp_df is not None:
        ##get thermometer only in relevant range
        #cut = np.logical_and(temp_time > min_time, temp_time < max_time)
        cut = (temp_time > min_time) & (temp_time < max_time) & (temp_ch1 < 30) & (temp_ch2 < 30) & (temp_ch3 < 30)
        temp_df_sliced = temp_df.loc[cut]
        temp_time_slice = pd.to_datetime(temp_df_sliced.index)
        temp_ch1_slice = temp_df_sliced['Temp Channel 1']
        temp_ch2_slice = temp_df_sliced['Temp Channel 2']
        temp_ch3_slice = temp_df_sliced['Temp Channel 3']

    fig1, ax1 = plt.subplots()
    ax1.plot(time, temp, color='royalblue', label='DEgg Internal', marker='o', linewidth=0)
    if temp_df is not None:
        ax1.plot(temp_time_slice, temp_ch1_slice, color='skyblue', label='DEgg Surface', linestyle='--', markersize=0)
        ax1.plot(temp_time_slice, temp_ch3_slice, color='firebrick', label='Box Interior', linestyle='--', markersize=0)
        ax1.plot(temp_time_slice, temp_ch2_slice, color='salmon', label='Box Exterior', linestyle='--', markersize=0)
    ax1.set_title(degg_id)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Temperature [C]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_temperature_time.pdf')


def temperature_tests_aggregate(df_list, degg_id_list, filepath):
    print("Running Aggregate Temperature Tests")
    fig1, ax1 = plt.subplots()
    index = 0
    for df in df_list:
        degg_id = degg_id_list[index]
        temp = np.array(df['temperature_sensor'], dtype=float)
        time = pd.to_datetime(df.index)
        ax1.plot(time, temp, label=degg_id)
        index += 1
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Temperature [C]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()
    fig1.savefig(f'{filepath}/aggregate_temperature_time.pdf')


def pressure_tests(df, degg_id, run, measurement, filepath):
    print("Running Pressure Tests")
    time = pd.to_datetime(df.index)
    pressure = np.array(df['pressure_sensor'], dtype=float)

    p_num_total = len(pressure)

    ##get invalid pressures
    cut = np.logical_and(df['pressure_sensor'] > 300, df['pressure_sensor'] < 600)
    df.loc[cut]
    pressure_cut = df['pressure_sensor']
    temperature_cut = df['temperature_sensor']
    time_cut = pd.to_datetime(df.index)

    p_num = len(pressure_cut)

    fig1, (ax1, ax2) = plt.subplots(1,2)
    ax1.plot(time_cut, pressure_cut, label='DEgg Internal Pressure', color='royalblue')
    ax1.set_title(" ")
    fig1.suptitle(degg_id)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Pressure [hPa]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()

    ax2.bar('Valid', p_num, hatch='/', color='royalblue', alpha=0.7)
    ax2.bar('Invalid', (p_num_total - p_num), hatch='/', color='goldenrod', alpha=0.7)
    ax2.set_ylabel('Data Points')
    plt.text('Valid', p_num*0.1, p_num, verticalalignment='bottom', horizontalalignment='center', bbox={'facecolor':'white', 'alpha':0.5})
    plt.text('Invalid', p_num*0.1, (p_num_total - p_num), verticalalignment='bottom', horizontalalignment='center', bbox={'facecolor':'white', 'alpha':0.5})

    fig1.tight_layout()
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_pressure_time.pdf')

    fig2d, ax2d = plt.subplots()
    ax2d.set_title(degg_id)
    ax2d.plot(temperature_cut, pressure_cut, color='royalblue', linewidth=0, marker='o', alpha=0.5)
    ax2d.set_xlabel('Temperature [C]')
    ax2d.set_ylabel('Pressure [hPa]')
    fig2d.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_pressure_temperature.pdf')


def current_tests(df, degg_id, run, measurement, filepath):
    print("Running MB Current Tests")
    time = pd.to_datetime(df.index)
    i0 = np.array(df['current_channel0'], dtype=float)
    i1 = np.array(df['current_channel1'], dtype=float)
    hv0 = np.array(df['voltage_channel0'], dtype=float)
    hv1 = np.array(df['voltage_channel1'], dtype=float)

    fig1, ax1 = plt.subplots()
    ax1.plot(time, i0, label='Ch0', color='royalblue', marker='o', linewidth=0)
    ax1.set_title(degg_id)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Current [uA]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    ax1.legend()
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_current0_time.pdf')

    fig2, ax2 = plt.subplots()
    ax2.plot(time, i1, label='Ch1', color='goldenrod', marker='o', linewidth=0)
    ax2.set_title(degg_id)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Current [uA]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    ax2.legend()
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_current1_time.pdf')

    fig3, ax3 = plt.subplots()
    ax3.plot(hv0, i0, label='Ch0', color='royalblue', marker='o', linewidth=0)
    ax3.set_title(degg_id)
    ax3.set_xlabel('PMT High Voltage [V]')
    ax3.set_ylabel('Current [uA]')
    ax3.grid()
    ax3.legend()
    fig3.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv0_current0.pdf')

    fig4, ax4 = plt.subplots()
    ax4.plot(hv1, i1, label='Ch1', color='goldenrod', marker='o', linewidth=0)
    ax4.set_title(degg_id)
    ax4.set_xlabel('PMT High Voltage [V]')
    ax4.set_ylabel('Current [uA]')
    ax4.grid()
    ax4.legend()
    fig4.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_hv1_current1.pdf')


def reflash_tests(df, degg_id, run, measurement, filepath):
    print("Running Reflash Tests")
    reflash_count = np.array(df['reflash_count'], dtype=int)
    temp = np.array(df['temperature_sensor'], dtype=float)
    time = pd.to_datetime(df.index)

    fig1, ax1 = plt.subplots()
    ax1.plot(time, reflash_count, color='royalblue', linewidth=0, marker='o')
    ax1.set_title(degg_id)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('FPGA Re-Flash Attempt')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)
    fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax1.grid()
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_reflash_time.pdf')

    fig2, ax2 = plt.subplots()
    ax2.plot(temp, reflash_count, color='royalblue')
    ax2.set_title(degg_id)
    ax2.set_xlabel('Temperature')
    ax2.set_ylabel('FPGA Re-Flash Attempt')
    ax2.grid()
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_reflash_temperature.pdf')

    fig3, ax3 = plt.subplots()
    ax3.hist(reflash_count, bins=4, color='royalblue')
    ax3.set_title(degg_id)
    ax3.set_xlabel('FPGA Re-Flash Attempt')
    ax3.set_ylabel('Entries')
    fig3.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_reflash.pdf')


def photodiode_tests(df, degg_id, run, measurement, filepath):
    print("Running Photodiode Tests")
    temp = np.array(df['temperature_sensor'], dtype=float)
    time = pd.to_datetime(df.index)
    light = np.array(df['light_sensor'], dtype=float)

    fig1, ax1 = plt.subplots()
    ax1.hist(light, bins=50, color='royalblue')
    ax1.set_title(degg_id)
    ax1.set_xlabel('MB Photodiode [mV]')
    ax1.set_ylabel('Entries')
    fig1.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_photodiode.pdf')

    fig2, ax2 = plt.subplots()
    ax2.plot(time, light, color='royalblue', linewidth=0, marker='o')
    ax2.set_title(degg_id)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('MB Photodiode [mV]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_photodiode_time.pdf')

    fig3, ax3 = plt.subplots()
    ax3.plot(temp, light, color='royalblue', linewidth=0, marker='o')
    ax3.grid()
    ax3.set_title(degg_id)
    ax3.set_xlabel('MB Temperature [C]')
    ax3.set_ylabel('MB Photodiode [mV]')
    fig3.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_photodiode_temperature.pdf')


def magnetometer_tests(df, degg_id, run, measurement, filepath):
    print("Running Magnetometer Tests")
    time = pd.to_datetime(df.index)
    mg_x = np.array(df['magnetometer_x'], dtype=float) * 1000
    mg_y = np.array(df['magnetometer_y'], dtype=float) * 1000
    mg_z = np.array(df['magnetometer_z'], dtype=float) * 1000

    for i in range(len(mg_x)):
        if mg_x[i] == -1000:
            mg_x[i] = -1
        if mg_y[i] == -1000:
            mg_y[i] = -1
        if mg_z[i] == -1000:
            mg_z[i] = -1

    #histograms
    fig1x, ax1x = plt.subplots()
    ax1x.hist(mg_x, bins=50, color='royalblue')
    ax1x.set_title(degg_id)
    ax1x.set_xlabel('MB Magnetomter - X [mT]')
    ax1x.set_ylabel('Entries')
    fig1x.tight_layout()
    fig1x.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_x.pdf')

    fig1y, ax1y = plt.subplots()
    ax1y.hist(mg_y, bins=50, color='goldenrod')
    ax1y.set_title(degg_id)
    ax1y.set_xlabel('MB Magnetomter - Y [mT]')
    ax1y.set_ylabel('Entries')
    fig1y.tight_layout()
    fig1y.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_y.pdf')

    fig1z, ax1z = plt.subplots()
    ax1z.hist(mg_z, bins=50, color='salmon')
    ax1z.set_title(degg_id)
    ax1z.set_xlabel('MB Magnetomter - Z [mT]')
    ax1z.set_ylabel('Entries')
    fig1z.tight_layout()
    fig1z.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_z.pdf')

    #variation with time
    fig2, ax2 = plt.subplots()
    ax2.plot(time, mg_x, color='royalblue', marker='.', markersize=15, linewidth=0, label='X')
    ax2.plot(time, mg_y, color='goldenrod', marker='.', markersize=15, linewidth=0, label='Y')
    ax2.plot(time, mg_z, color='salmon', marker='.', markersize=15, linewidth=0, label='Z')
    ax2.set_title(degg_id)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('MB Magnetometer [mT]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_time.pdf')

    fig2x, ax2x = plt.subplots()
    ax2x.plot(time, mg_x, color='royalblue', marker='.', markersize=15, linewidth=0, label='X')
    ax2x.set_title(degg_id)
    ax2x.set_xlabel('Time')
    ax2x.set_ylabel('MB Magnetometer [mT]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2x.xaxis.set_major_formatter(date_format)
    fig2x.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2x.grid()
    ax2x.legend()
    fig2x.tight_layout()
    fig2x.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_x_time.pdf')

    fig2y, ax2y = plt.subplots()
    ax2y.plot(time, mg_y, color='goldenrod', marker='.', markersize=15, linewidth=0, label='Y')
    ax2y.set_title(degg_id)
    ax2y.set_xlabel('Time')
    ax2y.set_ylabel('MB Magnetometer [mT]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2y.xaxis.set_major_formatter(date_format)
    fig2y.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2y.grid()
    ax2y.legend()
    fig2y.tight_layout()
    fig2y.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_y_time.pdf')

    fig2z, ax2z = plt.subplots()
    ax2z.plot(time, mg_z, color='salmon', marker='.', markersize=15, linewidth=0, label='Z')
    ax2z.set_title(degg_id)
    ax2z.set_xlabel('Time')
    ax2z.set_ylabel('MB Magnetometer [mT]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2z.xaxis.set_major_formatter(date_format)
    fig2z.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2z.grid()
    ax2z.legend()
    fig2z.tight_layout()
    fig2z.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_magnetometer_z_time.pdf')


def accelerometer_tests(df, degg_id, run, measurement, filepath):
    print("Running Accelerometer Tests")
    time = pd.to_datetime(df.index)
    ac_x = np.array(df['accelerometer_x'], dtype=float)
    ac_y = np.array(df['accelerometer_y'], dtype=float)
    ac_z = np.array(df['accelerometer_z'], dtype=float)

    #histograms
    fig1x, ax1x = plt.subplots()
    ax1x.hist(ac_x, bins=50, color='royalblue')
    ax1x.set_title(degg_id)
    ax1x.set_xlabel('MB Acceleromter - X [g]')
    ax1x.set_ylabel('Entries')
    fig1x.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_x.pdf')

    fig1y, ax1y = plt.subplots()
    ax1y.hist(ac_y, bins=50, color='goldenrod')
    ax1y.set_title(degg_id)
    ax1y.set_xlabel('MB Acceleromter - Y [g]')
    ax1y.set_ylabel('Entries')
    fig1y.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_y.pdf')

    fig1z, ax1z = plt.subplots()
    ax1z.hist(ac_z, bins=50, color='salmon')
    ax1z.set_title(degg_id)
    ax1z.set_xlabel('MB Acceleromter - Z [g]')
    ax1z.set_ylabel('Entries')
    fig1z.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_z.pdf')

    #variation with time
    fig2, ax2 = plt.subplots()
    ax2.plot(time, ac_x, color='royalblue', marker='.', markersize=15, linewidth=0, label='X')
    ax2.plot(time, ac_y, color='goldenrod', marker='.', markersize=15, linewidth=0, label='Y')
    ax2.plot(time, ac_z, color='salmon', marker='.', markersize=15, linewidth=0, label='Z')
    ax2.set_title(degg_id)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('MB Accelerometer [g]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2.xaxis.set_major_formatter(date_format)
    fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2.grid()
    ax2.legend()
    fig2.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_time.pdf')

    fig2x, ax2x = plt.subplots()
    ax2x.plot(time, ac_x, color='royalblue', marker='.', markersize=15, linewidth=0, label='X')
    ax2x.set_title(degg_id)
    ax2x.set_xlabel('Time')
    ax2x.set_ylabel('MB Accelerometer [g]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2x.xaxis.set_major_formatter(date_format)
    fig2x.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2x.grid()
    ax2x.legend()
    fig2x.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_x_time.pdf')

    fig2y, ax2y = plt.subplots()
    ax2y.plot(time, ac_y, color='goldenrod', marker='.', markersize=15, linewidth=0, label='Y')
    ax2y.set_title(degg_id)
    ax2y.set_xlabel('Time')
    ax2y.set_ylabel('MB Accelerometer [g]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2y.xaxis.set_major_formatter(date_format)
    fig2y.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2y.grid()
    ax2y.legend()
    fig2y.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_y_time.pdf')

    fig2z, ax2z = plt.subplots()
    ax2z.plot(time, ac_z, color='salmon', marker='.', markersize=15, linewidth=0, label='Z')
    ax2z.set_title(degg_id)
    ax2z.set_xlabel('Time')
    ax2z.set_ylabel('MB Accelerometer [g]')
    date_format = mdates.DateFormatter('%m-%d %H:%M')
    ax2z.xaxis.set_major_formatter(date_format)
    fig2z.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
    ax2z.grid()
    ax2z.legend()
    fig2z.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_accelerometer_z_time.pdf')



def baseline_tests(degg_dict, data_key_to_use, degg_id, run, measurement, filepath):
    print("Running Baseline Tests")

    nevent = np.empty(0, dtype=int)
    pctime = np.empty(0, dtype=float)
    temp = np.empty(0, dtype=float)
    bl_l = np.empty(0, dtype=float)
    bl_u = np.empty(0, dtype=float)
    vol_l = np.empty(0, dtype=float)
    vol_u = np.empty(0, dtype=float)

    eligible_keys = [key for key in degg_dict[data_key_to_use].keys()
            if key.startswith("Baseline_")]
    #print(eligible_keys)
    for key in eligible_keys[1:]: # excluding the initial one (Baseline_00)
        #print(degg_dict[data_key_to_use][key])
        nevent = np.append(nevent, degg_dict[data_key_to_use][key]["Event"])
        pctime = np.append(pctime, degg_dict[data_key_to_use][key]["PCTime"])
        temp = np.append(temp, degg_dict[data_key_to_use][key]["Temperature"])
        bl_l = np.append(bl_l, degg_dict[data_key_to_use][key]["Baseline_L"])
        bl_u = np.append(bl_u, degg_dict[data_key_to_use][key]["Baseline_U"])
        vol_l = np.append(vol_l, degg_dict[data_key_to_use][key]["Voltage_L"])
        vol_u = np.append(vol_u, degg_dict[data_key_to_use][key]["Voltage_U"])


    fig, ax = plt.subplots()
    ax.plot(temp, bl_l, marker='.', markersize=15, linewidth=0, label="Ch0", color="royalblue")
    ax.set_title(degg_id)
    ax.set_xlabel("Temperature [C]")
    ax.set_ylabel("Lower PMT Baseline")
    fig.autofmt_xdate(bottom=0.2, rotation=45, ha="right")
    ax.grid()
    ax.legend()
    fig.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_baseline0_temperature.pdf')

    fig, ax = plt.subplots()
    ax.plot(temp, bl_u, marker='.', markersize=15, linewidth=0, label="Ch1", color="royalblue")
    ax.set_title(degg_id)
    ax.set_xlabel("Temperature [C]")
    ax.set_ylabel("Upper PMT Baseline")
    fig.autofmt_xdate(bottom=0.2, rotation=45, ha="right")
    ax.grid()
    ax.legend()
    fig.savefig(f'{filepath}/{degg_id}_{run}_{measurement}_baseline1_temperature.pdf')



def readout_reboot_tests(run_json, temperature_file, measurement_type, measurement_number, filepath):

    try:
        file_name = open(temperature_file, "r")
    except:
        file_name = None
    if file_name is not None:
        temp_df = pd.read_csv(file_name, index_col='Local time', infer_datetime_format=True)

    try:
        measurement_number = int(measurement_number)
    except ValueError:
        pass

    df_list = []
    degg_id_list = []

    run = os.path.basename(run_json)
    run = run.split(".")
    run = run[0]

    data_key = measurement_type
    print(f"Analysing Measurement Key: {measurement_type}!")

    list_of_deggs = load_run_json(run_json)
    for degg_file in list_of_deggs:
        #print(degg_file)
        degg_dict = load_degg_dict(degg_file)

        degg_id = degg_dict['DEggSerialNumber']
        pmt_id_u = degg_dict['UpperPmt']['SerialNumber']
        pmt_id_l = degg_dict['LowerPmt']['SerialNumber']
        try:
            set_hv_u = degg_dict['UpperPmt']['HV1e7Gain']
            set_hv_l = degg_dict['LowerPmt']['HV1e7Gain']
        except KeyError:
            set_hv_u = None
            set_hv_l = None

        if measurement_number == 'latest':
            for key in degg_dict:
                eligible_keys = [key for key in degg_dict.keys()
                        if key.startswith(data_key)]
                #print(eligible_keys)
                cts = [int(key.split('_')[1]) for key in eligible_keys]
                if len(cts) == 0:
                    print(f"No valid measurement found for {data_key}")
                    continue

            measurement_number = np.max(cts)

        suffix = f'_{measurement_number:02d}'
        data_key_to_use = data_key + suffix
        measurement =  data_key_to_use

        filename = degg_dict[data_key_to_use]['Filename']
        print(f"Using {filename} for Module: {degg_id}")

        df = pd.read_csv(filename, index_col='Local time', infer_datetime_format=True)
        print(f"Dataframe Size: {df.shape}")
        df_list.append(df)
        degg_id_list.append(degg_id)

        hv_tests(df, degg_id, run, set_hv_u, set_hv_l, measurement, filepath)
        temperature_tests(df, degg_id, run, temp_df, measurement, filepath)
        pressure_tests(df, degg_id, run, measurement, filepath)
        current_tests(df, degg_id, run, measurement, filepath)
        reflash_tests(df, degg_id, run, measurement, filepath)
        photodiode_tests(df, degg_id, run, measurement, filepath)
        magnetometer_tests(df, degg_id, run, measurement, filepath)
        accelerometer_tests(df, degg_id, run, measurement, filepath)

        baseline_tests(degg_dict, data_key_to_use, degg_id, run, measurement, filepath)


    hv_tests_aggregate(df_list, degg_id_list, filepath)
    temperature_tests_aggregate(df_list, degg_id_list, filepath)


@click.command()
@click.option('--run_json', '-run', default='latest')
@click.option('--temperature_file', '-temp', default=None)
@click.option('--measurement_type', '-type', default=0)
@click.option('--measurement_number', '-num', default='latest')
@click.option('--local_path', default=None)
def main(run_json, temperature_file, measurement_type, measurement_number, local_path):
    # -- run number

    if local_path == None:
        local_path = '/home/scanbox/data/json/run/'
        if not os.path.exists(local_path):
            raise IOError(f'Using default path of {local_path}, but does not exist! Configure --local_path')

    if run_json == 'latest':
        list_of_files = glob.glob(os.path.join(local_path, '/*.json'))
        latest_file = max(list_of_files, key=os.path.getctime)
        run_json = latest_file
        run_number = re.split('[_]', os.path.basename(run_json))[1]
        run_number = re.split('[.]', os.path.basename(run_number))[0]
    else:
        run_number = '{0:05d}'.format(int(run_json))
        run_json = os.path.join(local_path, f'run_{run_number}.json')

    # -- temperature file
    if temperature_file is None:
        try:
            temperature_file = "/home/scanbox/software/goldschmidt/goldschmidt/temp.csv"
        except:
            print(colored("Could not find thermometer file"), 'yellow')

    # -- measurement type and its number
    if measurement_type == 0:
        measurement_type = 'ReadoutOnly'
    else:
        measurement_type = 'ReadoutReboot'

    print(f"Making plots for run{run_number}...")
    plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs')
    filepath = os.path.join(plot_dir, f'run_{run_number}_monitoring')
    if os.path.exists(filepath) == False:
        os.mkdir(filepath)
        print(f'Created directory {filepath}')

    # -- plotting
    readout_reboot_tests(run_json, temperature_file, measurement_type, measurement_number, filepath)

if __name__ == "__main__":
    main()


##end
