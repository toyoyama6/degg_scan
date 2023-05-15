# Script to make plots from the quick monitoring data
#
import os
import click
import pandas as pd
import tables
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import cm
from datetime import datetime
from scipy.optimize import curve_fit
from matplotlib import ticker

from degg_measurements.analysis.analysis_utils import get_measurement_numbers
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import load_run_json
from degg_measurements.analysis.analysis_utils import get_run_json
from degg_measurements.utils import DEggLogBook

from chiba_slackbot import send_message

ignore = ["degg_name", "port", "meas_key", "n_reads", "start_time", "baselineList"]
# Remove baseline from ignore and add it to the plots!
colormap = "magma"

def gaus(x,a,x0,sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))

def add_module_to_cache(df, cache, hv_status):
    degg_name = df['degg_name'].to_numpy()[0]
    # check if cache is empty
    try:
        keys = cache[degg_name]['std'].keys()
    except KeyError:
        cache[degg_name] = {
            "mean": {},
            "std": {},
            "start_time": [],
            "HVStatus": [],
            "port": df['port'].to_numpy()[0]
        }
        keys = [k for k in df.keys() if k not in ignore]
        for k in keys:
            cache[degg_name]['mean'][k] = []
            cache[degg_name]['std'][k] = []

    cache[degg_name]['start_time'].append(np.float64(df['start_time'].to_numpy()[0]))
    cache[degg_name]['HVStatus'].append(hv_status)
    for k in keys:
        _data = df[k].to_numpy()
        cache[degg_name]['mean'][k].append(np.mean(_data))
        cache[degg_name]['std'][k].append(np.std(_data))


def fill_cache(degg_dict, cache, measurement_type, remote, silence=False):
    if degg_dict[measurement_type]['Folder'] != "None":
        if remote:
            if "RemoteFolder" not in degg_dict[measurement_type]:
                message = "No 'RemoteFolder' for msmt '{}' and DEgg '{}'\n".format(measurement_type, degg_dict["DEggSerialNumber"])
                message += "Is this the skipped DEgg?"
                if silence == False:
                    send_message(message)
                return
            elif degg_dict[measurement_type]["RemoteFolder"] is None:
                return
            data_dir = degg_dict[measurement_type]['RemoteFolder']
        else:
            data_dir = degg_dict[measurement_type]['Folder']
        # We know there should be 16 files
        for j in range(16):
            moni_file = os.path.join(data_dir, f"mon_50{j:02}.hdf5")
            if not os.path.exists(moni_file):
                _msg = f"Could not find quick monitoring file for channel 50{j:02} in {moni_file}"
                print(_msg)
                if silence == False:
                    send_message(_msg)
                continue
            print(moni_file)
            try:
                df = pd.read_hdf(moni_file)
            except ValueError:
                print(f"File not readable: {moni_file}")
                continue
            hv_status = degg_dict[measurement_type]['HVStatus']
            add_module_to_cache(df, cache, hv_status)


def get_cache(cache_file):
    if os.path.exists(cache_file):
        cache = np.load(cache_file, allow_pickle=True).item()
    else:
        cache = {}
    return cache


def save_cache(cache_file, cache):
    cache_dir = os.path.dirname(cache_file)
    if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir)
    np.save(cache_file, cache)


def make_plot(x, y_list, err_list, ylabel, titel, label_list,
              mask=None,
              file_name="plot.pdf", ledgend_outside=False,
              sec_y=None, sec_err=None, sec_ylabel="Temperature / °C",
              time_as_list=False):
    font_size = 10
    cmap = cm.get_cmap(colormap)

    fig, ax1 = plt.subplots(figsize=(8, 6))
    fig.autofmt_xdate()

    if sec_y != None:
        ma = 0.9
        mi = 0.6
        sec_color = cmap(0.2)
        ax = ax1.twinx()

        ax1.errorbar(x, sec_y, yerr=sec_err,
                    marker="", markersize=5, linestyle="--",
                    color=sec_color, zorder=2)
        ax1.set_ylabel(sec_ylabel, fontsize=font_size)
        ax1.tick_params(axis='y', colors=sec_color)
        ax1.yaxis.label.set_color(sec_color)
        ax1.set_ylim(-50., 40)
    else:
        ma = 0.9
        mi = 0.1
        ax = ax1

    if len(y_list) == 1:
        steps = [0.6]
    else:
        steps = (np.arange(len(y_list))/(len(y_list)-1)*(ma-mi))+mi
    colors = iter(cmap(steps))

    if time_as_list == True:
        for i in range(len(y_list)):
            _this_color = next(colors)
            if mask != None:
                _x = x[i][mask]
                _y_list = y_list[i][mask]
                _yerr = err_list[i][mask]
                _xN = x[i][~mask]
                _y_listN = y_list[i][~mask]
                _yerrN = err_list[i][~mask]
                ax.errorbar(_xN, _y_list, yerr=_yerr,
                            marker="x", markersize=5, linestyle="",
                            color=_this_color, zorder=3)
            else:
                _x = x[i]
                _y_list = y_list[i]
                _yerr = err_list[i]
            ax.errorbar(_x, _y_list, yerr=_yerr,
                        marker="o", markersize=5, linestyle="",
                        label=f"{label_list[i]}", color=_this_color, zorder=3)
    else:
        for i in range(len(y_list)):
            ax.errorbar(x, y_list[i], yerr=err_list[i],
                    marker="o", markersize=5, linestyle="",
                    label=f"{label_list[i]}", color=next(colors), zorder=3)

    xfmt = mdates.DateFormatter("%y-%m-%d %H:%M")
    ax.xaxis.set_major_formatter(xfmt)
    ax.set_ylabel(ylabel, fontsize=font_size)
    ax.set_title(titel)
    ax.tick_params(labelsize=font_size)
    if ledgend_outside:
        # should be used if all Deggs are in one plot and the ledgend get's crowded
        # the ledgend takes ca. 1/4 of the plot space, so we adjust the limits accordingly
        y_limits = ax.get_ylim()
        y_min = y_limits[0]
        y_max = y_limits[1]
        y_min = y_max - ((y_max - y_min)/3)*4
        ax.legend(bbox_to_anchor=(0, 0, 1, 0), loc="lower left", mode="expand", ncol=4, handletextpad=0.05)
        ax.set_ylim((y_min, y_max))
    else:
        ax.legend()

    fig.savefig(file_name, bbox_inches='tight')
    plt.close(fig)


def module_plots(degg_name, cache, plot_dir=None):
    if plot_dir == None:
        plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig", f"run_{cache['run_number']}")
    if not os.path.isdir(plot_dir):
        os.makedirs(plot_dir)
    titel = f"{degg_name} channel {cache[degg_name]['port']}"

    times = np.array([datetime.fromtimestamp(t) for t in cache[degg_name]['start_time']])
    temp = cache[degg_name]['mean']['temperature']
    temp_err = cache[degg_name]['std']['temperature']

    # plot currents
    y = []
    yerr = []
    label = ["i1v1", "i1v35", "i1v8", "i2v5", "i3v3"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_mbCurrent.pdf")
    make_plot(times, y, yerr, "Current / mA", titel, label, file_name=file_name,
              sec_y=temp, sec_err=temp_err)

    # plot volages
    y = []
    yerr = []
    label = ["v1v8", "v1v1", "v1v35", "v2v5", "v3v3"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_mbVoltage.pdf")
    make_plot(times, y, yerr, "Voltage / V", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot HV
    y = []
    yerr = []
    label = ["hv0", "hv1"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_HV.pdf")
    make_plot(times, y, yerr, "Voltage / V", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot Gain
    y = []
    yerr = []
    label = ["hv1e7gain0", "hv1e7gain1"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_Gain.pdf")
    make_plot(times, y, yerr, "Gain", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot scaler
    y = []
    yerr = []
    label = ["scaler0", "scaler1"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_Scaler.pdf")
    make_plot(times, y, yerr, "Scaler", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot dark rate
    y = []
    yerr = []
    label = ["dark_rate0", "dark_rate1"]
    for k in label:
        darkrate = np.array(cache[degg_name]['mean'][k])
        darkrate = np.clip(darkrate, a_min=None, a_max=10000)
        _hv_status = np.array(cache[degg_name]['HVStatus'])
        mask = [True] * len(_hv_status)
        for l, _name in enumerate(_hv_status):
            if _name.split('_')[-1] == 'postIllumination':
                mask[l] = False
        y.append(darkrate)
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_DarkRate.pdf")
    make_plot(times, y, yerr, "Dark Rate / Hz", titel, label, mask=None,
              file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot baseline
    y = []
    yerr = []
    label = ["baseline0", "baseline1"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_Baseline.pdf")
    make_plot(times, y, yerr, "Baseline / ADC", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)

    # plot pressure
    y = []
    yerr = []
    label = ["pressure"]
    for k in label:
        y.append(cache[degg_name]['mean'][k])
        yerr.append(cache[degg_name]['std'][k])
    file_name = os.path.join(plot_dir, f"{degg_name}_Pressure.pdf")
    make_plot(times, y, yerr, "Pressure / hPa", titel, label, file_name=file_name, sec_y=temp, sec_err=temp_err)


    ##plot the difference between the HV set and read
    for ch in [0, 1]:
        hv_rb  =  cache[degg_name]['mean'][f'hv{ch}']
        hv_set =  cache[degg_name]['mean'][f'hv1e7gain{ch}']
        _diff = np.array(hv_rb) - np.array(hv_set)
        file_name = os.path.join(plot_dir, f'{degg_name}_{ch}_hvDiff.pdf')
        _fig, _ax = plt.subplots()
        _ax.plot(range(len(_diff)), _diff, 'o', color='royalblue')
        _ax.set_ylabel('HV Readback - Set [V]')
        _ax.set_xlabel('Measurement Number')
        _ax.set_title(titel)
        _fig.savefig(file_name)
        plt.close(_fig)

        ##do dark rate, gain, hv, hverr
        for _str in ['dark_rate', 'hv']:
            _vals = cache[degg_name]['mean'][f'{_str}{ch}']
            if _str == 'dark_rate':
                _vals = np.array(_vals)
                mask = _vals < 10000
                _vals = _vals[mask]
            fig00, ax00 = plt.subplots()
            ax00.hist(_vals, 40, histtype='step', color='royalblue', label=f'N={len(_vals)}')
            ax00.legend()
            ax00.set_xlabel(_str)
            ax00.set_ylabel('Entries')
            ax00.set_title(titel)
            hist_filename = os.path.join(plot_dir, f'{degg_name}_{ch}_{_str}_hist.pdf')
            fig00.savefig(hist_filename)
            plt.close(fig00)
        for _str in ['dark_rate', 'hv']:
            _vals = cache[degg_name]['std'][f'{_str}{ch}']
            fig00, ax00 = plt.subplots()
            ax00.hist(_vals, 40, histtype='step', color='royalblue', label=f'N={len(_vals)}')
            ax00.legend()
            ax00.set_xlabel(_str+' std')
            ax00.set_ylabel('Entries')
            ax00.set_title(titel)
            hist_filename = os.path.join(plot_dir, f'{degg_name}_{ch}_{_str}_hist_std.pdf')
            fig00.savefig(hist_filename)
            plt.close(fig00)

def degg_comparison_plots(cache, plot_dir=None):
    if plot_dir == None:
        plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig", f"run_{cache['run_number']}")
    if not os.path.isdir(plot_dir):
        os.makedirs(plot_dir)
        print(f"Created {plot_dir}")

    ignore = ["run_number", "needs_to_be_here_for_next_line_to_work"]
    list_of_deggs = [k for k in cache.keys() if k not in ignore]
    # Keys to plot are hardcooded to also get the right lable
    keys = ["i1v1", "i1v35", "i1v8", "i2v5", "i3v3",
            "v1v8", "v1v1", "v1v35", "v2v5", "v3v3",
            "power", "powerIsValid",
            "hv0", "hv1", "hv1e7gain0", "hv1e7gain1",
            "pressure", "temperature", "baseline0", "baseline1",
            "scaler0", "scaler1", "dark_rate0", "dark_rate1"]
    y_label = ["Current / mA", "Current / mA", "Current / mA", "Current / mA", "Current / mA",
               "Voltage / V", "Voltage / V", "Voltage / V", "Voltage / V", "Voltage / V",
               "Power / W", "",
               "Voltage / V", "Voltage / V", "Voltage / V", "Voltage / V",
               "Pressure / hPa", "Temperature / °C", "Baseline /ADC", "Baseline /ADC",
               "Scaler / Counts/10ms", "Scaler / Counts/100ms", "Dark Rate / Hz", "Dark Rate / Hz"]

    for i in range(len(keys)):
        k = keys[i]
        titel = f"Comparison of {k}"
        y = []
        times = []
        yerr = []
        label = []
        for degg_name in list_of_deggs:
            #times = np.array([datetime.fromtimestamp(t) for t in cache[degg_name]['start_time']])
            times.append(np.array([datetime.fromtimestamp(t) for t in cache[degg_name]['start_time']]))
            y.append(cache[degg_name]['mean'][k])
            yerr.append(cache[degg_name]['std'][k])
            label.append(degg_name)
            file_name = os.path.join(plot_dir, f"comparison_{k}.pdf")
        make_plot(times, y, yerr, y_label[i], titel, label, file_name=file_name,
                  ledgend_outside=True, time_as_list=True)


def make_hv_stability_plot(cache, plot_dir=None):
    if plot_dir == None:
        plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig", f"run_{cache['run_number']}")
    if not os.path.isdir(plot_dir):
        os.makedirs(plot_dir)
        print(f"Created {plot_dir}")

    font_size = 10
    tick_size = 6
    hv_key = "HVStatus"
    status = "very_cold1"
    width = 0.1
    n_bin = 20
    bad_sigma_thresh = 1.0

    cmap = cm.get_cmap(colormap)

    ignore = ["run_number", "needs_to_be_here_for_next_line_to_work"]
    list_of_deggs = [k for k in cache.keys() if k not in ignore]
    for k in ["hv0", "hv1", 'dark_rate0', 'dark_rate1']:
        fig, axs = plt.subplots(nrows=4, ncols=4, constrained_layout=True, figsize=(10, 7))
        if k == "hv0":
            fig.suptitle("Lower PMTs")
            file_name = os.path.join(plot_dir, f"HV_stability_LowerPMTs.pdf")
        elif k == 'hv1':
            fig.suptitle("Upper PMTs")
            file_name = os.path.join(plot_dir, f"HV_stability_UpperPMTs.pdf")
        elif k == 'dark_rate0':
            fig.suptitle('Lower PMTs')
            file_name = os.path.join(plot_dir, f"dark_rate_LowerPMTs.pdf")
        else:
            fig.suptitle('Upper PMTs')
            file_name = os.path.join(plot_dir, f"dark_rate_UpperPMTs.pdf")

        for i in range(len(list_of_deggs)):
            ax = axs.flat[i]
            degg_name = list_of_deggs[i]
            hv_values = np.array(cache[degg_name]['mean'][k])
            mask = np.where(np.array(cache[degg_name][hv_key]) == status)
            if len(mask[0]) < 1:
                print("No data points found. Not creating plots.")
                break

            #if k == 'dark_rate0' or k == 'dark_rate1':
            #    print(hv_values[mask])
            #    _mask = hv_values[mask] < 1000
            #    mask = mask * _mask

            # we will use half-volt wide bins with the center bin... centered on the mean of the data

            mean = np.mean(hv_values[mask])
            sigma = np.std(hv_values[mask])

            # puts the center bin right over the mea
            upper_edges = np.arange(mean + 0.5*width, mean + n_bin*width, width)
            lower_edges = np.arange(mean - 0.5*width, mean - n_bin*width, -width)[::-1]
            edges = np.concatenate((lower_edges, upper_edges))

            n, bin_edges = np.histogram(hv_values[mask], bins=edges)

            bin_centers = (edges[1:] + edges[:-1])*0.5

            try:
                popt,pcov = curve_fit(gaus,
                                      bin_centers,
                                      n,
                                      p0=[1,mean,sigma],
                                      bounds=(0, np.inf)
                                      )
                failed = False
            except RuntimeError:
                failed = True
                popt = [1, 0, 0]

            a = popt[0]
            mu = popt[1]
            sigma = popt[2]
#            width = bin_edges[1] - bin_edges[0]
#            bin_centres = (bin_edges[:-1] + bin_edges[1:])/2
#            ax.bar(bin_centres, n, width=width, align="center", color=cmap(0.2), alpha=0.75)
            ax.stairs(values=n, edges=bin_edges, color=cmap(0.2,alpha=0.75))

            if sigma<1e-15 or sigma>bad_sigma_thresh or failed:
                color = "red"
            else:
                color="black"

            ax.set_title(degg_name, fontsize=font_size, color=color)

            gaus_x = np.arange(bin_edges[0], bin_edges[-1], (bin_edges[-1]-bin_edges[0])/100)
            y = gaus(gaus_x, a, mu, sigma)
            ax.plot(gaus_x, y, marker="", linestyle="--", color=cmap(0.9), label=f"sigma = {sigma:2f} V")

            ax.legend(loc="upper right", fontsize=font_size)
            ax.set_yticks([])
            #ax.xaxis.set_major_formatter(ticker.StrMethodFormatter("{x:.1f}"))
            #ax.tick_params(labelsize=tick_size)
            #ax.locator_params(axis="x", tight=True, nbins=3)
        fig.tight_layout()
        fig.savefig(file_name, bbox_inches="tight")
        plt.close(fig)


def analysis_wrapper(run_json, measurement_number="latest", remote=False,
                     offline=False, cache_file=None, silence=False):
    run_json, run_number = get_run_json(run_json)
    list_of_deggs = load_run_json(run_json)

    # if offline != True:
    #     logbook = DEggLogBook()
    # else:
    #     logbook = None

    if cache_file == None:
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'cache', f'run_{run_number}.npy')
    cache = get_cache(cache_file)
    degg_dict = load_degg_dict(list_of_deggs[0])
    max_n = get_measurement_numbers(degg_dict, None, measurement_number, "OnlineMon")

    if len(cache.keys()) == 0 and max_n[0] != 0:
        # No cache found and not the first measurement made:
        # Rebuild the cache
        for i in range(max_n[0]+1):
            k = f"OnlineMon_{i:02}"
            fill_cache(degg_dict, cache, k, remote, silence)
            cache['run_number'] = run_number
    else:
        k = f"OnlineMon_{max_n[0]:02}"
        fill_cache(degg_dict, cache, k, remote, silence)

    save_cache(cache_file, cache)
    # Make plots
    degg_comparison_plots(cache)
    make_hv_stability_plot(cache)
    for degg in list_of_deggs:
        degg_file = os.path.basename(degg)
        degg_name = degg_file.split(".")[0]
        if degg_name not in cache:
            if silence == False:
                send_message("Skipping {} in moni_quick".format(degg_name))
            continue
        module_plots(degg_name, cache)

    plot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fig", f"run_{cache['run_number']}")
    if silence == False:
        send_message(f'Monitoring plots have been updated at {plot_dir}')

@click.command()
@click.argument("run_json")
@click.option("--measurement_number", "-n", default="latest")
@click.option("--remote", is_flag=True)
@click.option("--offline", is_flag=True)
@click.opeion("--silence", is_flag=True)
def main(run_json, measurement_number, remote, offline, silence):
    analysis_wrapper(run_json, measurement_number, remote, offline, silence)


if __name__ == "__main__":
    main()
