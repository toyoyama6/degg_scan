"""
This script is used to prepare the summary PDFs of a DEgg FAT run

It takes one argument: the path to the run JSON file

It makes:
    - a PDF for each DEgg summarizing the tests: it highlights the tests which fail. It includes all the analysis plots
    - a PDF summarizing the whole run and which tests (if any) failed. This PDF includes relevant plots
"""

import click
import json
from enum import Enum
import numpy as np
import pandas as pd
import os
from glob import glob
import sys
import platform
import string
from collections import defaultdict

from types import DynamicClassAttribute
from PyTex import PyTex

from degg_measurements.utils import load_degg_dict, load_run_json, extract_runnumber_from_path
from degg_measurements.analysis import goalpost as gp


metaresults = {}

OUTFOLDER = "/disk20/fat/data/degg_result_pdfs/"


class Pass_State(Enum):
    fail = 0
    passed = 1
    warn = 2

    # cast name to Tex friendly form
    @DynamicClassAttribute
    def name(self):
        name = super(Pass_State, self).name
        if name=="fail":
            return "\\txfail"
        elif name=="passed":
            return "\\txpass"
        elif name=="warn":
            return "\\txwarn"


    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def get_alternate_text(self)->str:
        name = super(Pass_State, self).name
        if name=="fail":
            return "\\fail"
        elif name=="passed":
            return "\\pass"
        elif name=="warn":
            return "\\warn"

def metaload(fpath)->dict:
    """
    Takes the filepath to a json file, loads it in, and returns the dictionary
    """
    _obj = open(fpath,'rt')
    data = json.load(_obj)
    _obj.close()
    return data


################### TEST PASS CHECK

# collection of all our goal poasts
ALL_GP = gp.Goalpost.get_instances()

# make a dictionary referencing the names (which appear in our json files) to the goalpost itself
GP_DICT = { goal.testname:goal for goal in ALL_GP }

def gp_passed(value:float, which:gp.Goalpost)->bool:
    """
    For a given Goalpost and measured value, returns whether or not the value passes the goal post

    raises ValueError if there is an unknown test-type for the Goalpost
    """
    if which.testtype == "in-range":
        return value>which.testbounds[0] and value<which.testbounds[1]
    elif which.testtype=="max":
        return value < which.testbounds
    elif which.testtype=="min":
        return value > which.testbounds
    elif which.testtype=="equals":
        return which.testbounds == value
    else:
        raise ValueError("Unknown testtype {}".format(which.testtype))

def test_passed(data:dict, gp_i:int)->Pass_State:
    """
        Takes adictionary for a given goalpost file (and an integer specifying which GP it is)
        Checks whether it passed or failed

        returns a Pass_State
        raises a ValueError if the GoalPost associated with this dict has an unknown testtype
    """
    goal = GP_DICT[data["meas_data"][0]["goalpost"][gp_i]["testname"]]
    if "value" in  data["meas_data"][0]:
        value = data["meas_data"][0]["value"]
    else:
        edges =np.logspace(data["meas_data"][0]["x_min"], data["meas_data"][0]["x_max"], data["meas_data"][0]["n_bins"]+1)
        centers = 0.5*(edges[:-1] + edges[1:])
        value = sum(data["meas_data"][0]["y_values"])/(sum(data["meas_data"][0]["y_values"]*centers))

    return Pass_State(int(gp_passed(value, goal)))

def get_test_result(test_dict:dict, goalpost_index:int, msmt_no:int)->dict:
    """
        For a test, measurement number, and goalpost index
        get the dictionary for our panda dataframe
    """
    if test_dict["meas_name"]!="pmt-darknoise-delta-t": # weird one
        print(test_dict['meas_data'][0])
        #if isinstance(test_dict["meas_data"][0]["value"], (tuple, list, np.ndarray)):
        try:
            if isinstance(test_dict["meas_data"][0]["y_values"], (tuple, list, np.ndarray)):
                print("Skipping {}".format(test_dict["meas_name"]))
                return {}
        except:
            if isinstance(test_dict["meas_data"][0]["value"], (tuple, list, np.ndarray)):
                print("Skipping {}".format(test_dict["meas_name"]))
                return {}


    if msmt_no=="FlasherCheck": # flasher is only done once
        msmt_no="00"

    goal = GP_DICT[test_dict["meas_data"][0]["goalpost"][goalpost_index]["testname"]]

    if goal.testtype=="equals":
        condition = "x=={}".format(goal.testbounds)
    elif goal.testtype == "in-range":
        condition = "${}\\leq x \\leq {}$".format(goal.testbounds[0], goal.testbounds[1])
    elif goal.testtype=="max":
        condition = "$x \\leq {}$".format(goal.testbounds)
    elif goal.testtype=="min":
        condition = "${} \\leq x$".format(goal.testbounds)
    else:
        raise ValueError()

    if "value" in  test_dict["meas_data"][0]:
        value = test_dict["meas_data"][0]["value"]
    else:
        edges =np.logspace(test_dict["meas_data"][0]["x_min"], test_dict["meas_data"][0]["x_max"], test_dict["meas_data"][0]["n_bins"]+1)
        centers = 0.5*(edges[:-1] + edges[1:])
        value = sum(test_dict["meas_data"][0]["y_values"])/(sum(test_dict["meas_data"][0]["y_values"]*centers))

    passed = test_passed(test_dict, goalpost_index)
    return {
        "GoalPost":[test_dict["meas_name"],],
        "Msmt":[msmt_no,],
        "Temp":[float(test_dict["meas_data"][0]["temperature"]),],
        "condition":[condition,],
        "value":[value,],
        "result":[passed ,]
    }

def filter_json(data:dict):
    """
        Function to check if this json file is a goal post
    """
    if "meas_data" not in data[1]:
        return False
    if "goalpost" not in data[1]["meas_data"][0]:
        return False
    return True

MEASUREMENTS = [
    "GainMeasurement",
    "DarkrateScalerMeasurement",
    "DeltaTMeasurement",
    "TransitTimeSpread",
    "LinearityMeasurement",
    "FlasherCheck",
    "DoublePulse",
    "AdvancedMonitoring"
]

reverse_msmt_lookup = defaultdict(set)
def update_msmt_lookup(measurement, goalpost_name):
    global reverse_msmt_lookup
    reverse_msmt_lookup[goalpost_name].add(measurement)


def get_measurement_test_dicts(root_folder, pmt_id:str, measurement_kind:str)->'list[tuple[int, dict]]':
    """
    For a given pmt, and for a specific kind of measurement, get the goalpost json files
    """
    assert os.path.exists(root_folder), f"--- No folder found for {pmt_id}, {measurement_kind}"
    these_files = glob(os.path.join(root_folder, "*"+pmt_id+"*"+measurement_kind+"_*.json") )
    print(f'--- Found {len(these_files)} for {pmt_id}, {measurement_kind}')

    msmt_nos = [filename.split("_")[-2] for filename in these_files]

    these_files = [metaload(fpath) for fpath in these_files]

    metadata = [(msmt_nos[i], these_files[i]) for i in range(len(msmt_nos))]

    metadata = list(filter(filter_json, metadata))
    return metadata

TEST_FOLDER = "/disk20/fat/software/degg_measurements/degg_measurements/analysis/database_jsons/"
def build_test_table(pmt_id:str, run_id:int)->pd.DataFrame:
    sub_folder = os.path.join(TEST_FOLDER, "run_{:016d}".format(run_id))

    headers = [
        "GoalPost",
        "Msmt",
        "Temp",
        "condition",
        "value",
        "result"]

    dframe = pd.DataFrame(columns=headers)
    for measurement in MEASUREMENTS:
        msmt_data = get_measurement_test_dicts(sub_folder, pmt_id, measurement)
        if len(msmt_data) == 0:
            pass
        else:
            for entry in msmt_data:
                for i in range(len(entry[1]["meas_data"][0]["goalpost"])):
                    update_msmt_lookup(measurement, entry[1]["meas_name"])
                    result = get_test_result(entry[1], i, entry[0])
                    dframe = pd.concat(
                        [dframe, pd.DataFrame.from_dict(result)],
                        ignore_index=True
                    )
    return dframe

def get_plots(degg_config, pmt, run_number)->dict:
    """
    Returns a dictionary that helps us add the plots.
        keys give lists with [figname, caption] entries; one per plot
        the key i the figure type
    """
    out = {}
    pmt_id = degg_config[pmt]["SerialNumber"]
    figdict = metaload(os.path.join(os.path.dirname(__file__), "figdat.json"))
    for fig_key in figdict.keys():

        out[fig_key] = []

        fig_entry=figdict[fig_key]

        if fig_entry["with_degg"]:
            true_figpath = fig_entry["figpath"].format(run_number,degg_config["DEggSerialNumber"], pmt_id)
        else:
            true_figpath = fig_entry["figpath"].format(run_number, pmt_id)
        # now we need to clean up the filepath
        all_figs = glob(true_figpath)
        for fname in all_figs:
            # as far as I can tell, the msmt number is consistently the last thing listed...
            try:
                msmt = int(os.path.split(fname)[0].split("_")[-1])
            except ValueError:
                print(f'--- No measurement value found for {fname}')
                msmt = -1

            # fname ="{"+os.path.join(path_dir, ""+".".join(filename[:-1]) + "}." + filename[-1])

            out[fig_key].append([fname, fig_entry["caption"]+". Measurement number {}".format(msmt)])

    return out


##################  SUMMARY TABLE

def get_test_config_str(degg_config)->str:
    """
        Grabs some information shared by all tests and each PMT, then compiles that into a LaTeX table
            See Table 1

        Note: some of these entries had underscore "_" characters that break the compiler, so we have to insert a backslash behind them
    """
    pform = platform.platform().replace("_", "\\_")
    pyvers = sys.version.replace("_", "\\_")
    hvboard = degg_config["UpperPmt"]["HVB"].replace("_", "\\_")
    base_str = f"""
\\section{{Test Configuration}}
\\begin{{center}}
\\begin{{table}}[h]
    \\caption{{Test Configuration Summary}}
    \\begin{{tabular}}{{ll}}\\hline
        Contents & Values \\\\\\hline
        Flash ID & {degg_config["flashID"]} \\\\
        ICMID & {degg_config["ICMID"]} \\\\
        Upper PMT & {degg_config["UpperPmt"]["SerialNumber"]}\\\\
        Lower PMT & {degg_config["LowerPmt"]["SerialNumber"]}\\\\\\hline
        Host IP Address & localhost; Using Mini-FieldHub \\\\
        Port Number & {degg_config["Port"]}\\\\
        Box Number & {degg_config["BoxNumber"]} \\\\
        FPGA FW Ver. & {degg_config["fpgaVersion"]} \\\\
        Iceboot SW Ver. & {degg_config["IcebootVersion"]} \\\\\\hline
        HV Boards &  {hvboard} \\\\
        Camera & {degg_config["CameraNumber"]}  \\\\\\hline
        OS & {pform} \\\\
        Python Ver. & {pyvers} \\\\
        Test Date & \\\\\\hline
    \\end{{tabular}}
\\end{{table}}
\\end{{center}}
    """

    return base_str

def get_pmt_pass_state(pmt_panda:pd.DataFrame)->Pass_State:
    n_pass = 0
    n_fail = 0
    n_warn = 0

    threshold = 0.80

    for entry in pmt_panda['result']:
        if entry == Pass_State.fail:
            n_fail+=1
        elif entry == Pass_State.passed:
            n_pass+=1
        elif entry==Pass_State.warn:
            n_warn+=1
        else:
            raise ValueError(entry)

    if n_fail == 0:
        return Pass_State.passed
    else:
        if n_pass/(n_pass+n_warn+n_fail)>=threshold:
            return Pass_State.warn
        else:
            return Pass_State.fail

color_header = f"""
    \\usepackage{{color}}
    \\usepackage{{colortbl}}
    \\definecolor{{ao}}{{rgb}}{{0.0, 0.5, 0.0}}
    \\definecolor{{amber}}{{rgb}}{{1.0, 0.49, 0.0}}
    \\newcommand{{\\txpass}}{{\\textcolor{{ao}}{{PASS}}}}
    \\newcommand{{\\txfail}}{{\\textcolor{{red}}{{FAIL}}}}
    \\newcommand{{\\txwarn}}{{\\textcolor{{amber}}{{WARN}}}}
"""

def write_for_degg(degg_config:dict, run_number:int):
    passing = Pass_State.passed
    summary = {} # for summary table
    tables = {} # the tables themselves, used for individual pdfs

    for pmt in ["UpperPmt","LowerPmt"]:
        pmt_id = degg_config[pmt]["SerialNumber"]
        pmt_table = build_test_table(pmt_id, run_number)
        pmt_pass_state = get_pmt_pass_state(pmt_table)
        if pmt_pass_state == Pass_State.fail:
            passing = Pass_State.fail
            verdict = "fail"
        elif pmt_pass_state == Pass_State.warn and (passing!=Pass_State.fail):
            passing = Pass_State.warn
            verdict = "warn"
        else:
            verdict = "pass"

        tables[pmt_id]=pmt_table

        summary[pmt_id] = {
            "warn":[],
            "fail":[],
            "verdict":verdict
        }
        headers = [
            "GoalPost",
            "Msmt",
            "Temp",
            "condition",
            "value",
            "result"]

        headers = pmt_table.columns.values.tolist()
        for i in range(len(pmt_table[headers[0]])):
            if pmt_table["result"][i] == Pass_State.fail:
                for entry in reverse_msmt_lookup[pmt_table["GoalPost"][i]]:
                    summary[pmt_id]["fail"].append("{}_{}".format(entry, pmt_table["Msmt"][i]))


            elif pmt_table["result"][i] == Pass_State.warn:
                for entry in reverse_msmt_lookup[pmt_table["GoalPost"][i]]:
                    summary[pmt_id]["warn"].append("{}_{}".format(entry, pmt_table["Msmt"][i]))


    passing_str = passing.get_alternate_text()


    fax_str = f"""
\\fbox{{\\begin{{minipage}}{{\\linewidth}}
    \\vspace{{0.25cm}}
    \\begin{{center}}
        {{\\Large \\textbf{{\\underline{{FINAL ACCEPTANCE}}}}}}\\\\

        {passing_str}

    \\end{{center}}
    \\vspace{{0.1cm}}
\\end{{minipage}}}}
"""

    run_folder = os.path.join(OUTFOLDER, "run_{}".format(run_number))
    pdf_filename = os.path.join(
        run_folder,
        '{}_result.pdf'.format(degg_config['DEggSerialNumber'])
    )

    with PyTex(pdf_filename, keep_tex=True) as _obj:
        conf = degg_config["DEggSerialNumber"].replace('_', '-')
        _obj.inject_header(color_header)
        _obj.add_title(
            "\\textbf{{D-Egg FAT Report}}",
            f"\\textbf{{for \\# \\underline{{{conf}}}}}"
        )
        _obj.inject_tex(fax_str)
        _obj.inject_tex(get_test_config_str(degg_config))

        format_str = ',,.2f,,.2f,'

        for pmtid in tables.keys():
            _obj.page_break()
            _obj.new_section("Results for {}".format(pmtid))
            _obj.inject_tex(get_pmt_pass_state(tables[pmtid]).get_alternate_text()) # pass/warn/fail
            _obj.add_table(tables[pmtid],"Test results for {}".format(pmtid), format_str=format_str, header_justification='l|ccccl')

        for pmt in ["UpperPmt","LowerPmt"]:
            entries = get_plots(degg_config, pmt, run_number)
            for section in entries.keys():
                _obj.new_section(section)

                for figname, caption in entries[section]:
                    _obj.add_figure(caption, figname)

    return summary

def find_plots(search:str):
    figdat_path = "/disk20/fat/software/degg_measurements/degg_measurements/utils/figdat.json"
    with open(figdat_path,'rt') as _obj:
        data = json.load(_obj)

    matches = []
    for key in data.keys():
        if search.lower() in str(key).lower():
            matches.append(data[key])
            continue
        elif search.lower() in data[key]["figpath"].lower():
            matches.append(data[key])
            continue
        elif search.lower() in data[key]["caption"].lower():
            matches.append(data[key])
            continue
    print(f'Matches: {matches}')
    return matches

def make_summary(data, run_number ):
    headers = ["DEgg","PMT0 ID", "PMT0 Verdict","PMT1 ID", "PMT1 Verdict", "Failures"]
    dframe = pd.DataFrame(columns=headers)

    anywarn = False

    check_combo = []

    for key in data.keys():
        pmt_ids = list(data[key].keys())

        verdict_0 = ""
        if data[key][pmt_ids[0]]["verdict"].lower() == "pass":
            verdict_0="\\txpass"
        elif data[key][pmt_ids[0]]["verdict"].lower() == "warn":
            verdict_0="\\txwarn"
        else:
            verdict_0="\\txfail"

        verdict_1 = ""
        if data[key][pmt_ids[1]]["verdict"].lower() == "pass":
            verdict_1="\\txpass"
        elif data[key][pmt_ids[1]]["verdict"].lower() == "warn":
            verdict_1="\\txwarn"
        else:
            verdict_1="\\txfail"

        for entry in list(set(data[key][pmt_ids[0]]["fail"])):
            kinda = entry.split("_")

            check_combo.append([key, pmt_ids[0], kinda[0], kinda[1]])

        for entry in list(set(data[key][pmt_ids[1]]["fail"])):
            kinda = entry.split("_")
            check_combo.append([key, pmt_ids[1], kinda[0], kinda[1]])

        failures = []
        failures += data[key][pmt_ids[0]]["fail"]
        failures += data[key][pmt_ids[1]]["fail"]
        failures = set(failures)

        if len(failures)>0:
            anywarn = True

        failures = ", ".join(failures)
        failures = failures.replace("_","\\_")

        entry = pd.DataFrame.from_dict({
            "DEgg":[key.replace('_', '-')],
            "PMT0 ID":[pmt_ids[0]],
            "PMT0 Verdict": [verdict_0],
            "PMT1 ID":[pmt_ids[1]],
            "PMT1 Verdict": [verdict_1],
            "Failures":[failures]
        })

        dframe = pd.concat([dframe, entry], ignore_index=True)
    dframe = dframe.sort_values(by="DEgg")

    pdf_filename = os.path.join(
        OUTFOLDER,
        'run_{}'.format(run_number),
        'run_{}_summary.pdf'.format(run_number)
    )

    with PyTex(pdf_filename, True) as obj:
        obj.inject_header(color_header)
        obj.add_title("Run {}".format(run_number), "Summary")

        obj.new_section("Summary of Tests")
        obj.add_table(dframe, "Run {} summary".format(run_number),header_justification='l|lclcl', line_break_delimiter=',')

        if anywarn:
            obj.new_section("Plots to Consider")

            for entry in check_combo:
                degg = entry[0]
                pmt = entry[1]
                search_key = entry[2]
                msmt_no = entry[3]
                print(f'Trying to find plots for {degg} {pmt} {search_key} {msmt_no}')

                plot_dicts = find_plots(search_key)
                print(f'Found {len(plot_dicts)} plot_dicts')
                for plot_dict in plot_dicts:
                    print(f'plot_dict: {plot_dict}')


                    if plot_dict["with_degg"]:
                        true_figpath = plot_dict["figpath"].format(run_number, degg, pmt)
                    else:
                        n_formats = len(
                            list(string.Formatter().parse(plot_dict['figpath']))
                        ) - 1
                        if n_formats == 1:
                            true_figpath = plot_dict['figpath'].format(pmt)
                        elif n_formats == 2:
                            true_figpath = plot_dict["figpath"].format(run_number, pmt)
                        else:
                            print(list(string.Formatter().parse(plot_dict['figpath'])))
                            raise NotImplementedError(
                                f'Unexpected number of format placeholders '
                                f' ({n_formats}) in {plot_dict["figpath"]}.'
                            )
                    print(f'Checking true_figpath: {true_figpath}')

                    all_figs = glob(true_figpath)
                    print(f'all_figs: {all_figs}')
                    all_figs = list(filter(
                        lambda fname:int(msmt_no)==int(os.path.dirname(fname).split("_")[-1]),
                        all_figs))
                    print(f'all_figs filtered: {all_figs}')
                    id_str = "{}, {}. ".format(degg,pmt)
                    id_str = id_str.replace('_', '-')
                    msmt_nos = [ int(os.path.dirname(fname).split("_")[-1]) for fname in all_figs ]
                    msmt_str = ". Measurement number(s) " + ", ".join([str(msmt_no) for msmt_no in msmt_nos])
                    try:
                        obj.add_figures(id_str + plot_dict["caption"]+msmt_str, *all_figs)
                    except ValueError:
                        print(f'--- Could not find plots related to summary file for {id_str}')
                        print(f'{all_figs}')


def pretty_print(what):
    for key in what.keys():
        print(key)
        for subkey in what[key].keys():
            if subkey!="fail" and subkey!="warn":
                continue
            print("    ", subkey)
            for entry in what[key][subkey]:
                print("      ",entry)


@click.command()
@click.argument('run_json', type=click.Path(exists=True))
def main(run_json):
    list_of_deggs = load_run_json(run_json)
    run_number = extract_runnumber_from_path(run_json)
    summary = {}
    for degg_file in list_of_deggs:
        degg_dict = load_degg_dict(degg_file)
        print(f'Working on DEgg {degg_dict["DEggSerialNumber"]}')

        _meta = write_for_degg(degg_dict, run_number)
        serial_no = degg_dict["DEggSerialNumber"]
        summary[serial_no] = {}
        for key in _meta.keys():
            summary[serial_no][key] = _meta[key]

    print('Making summary PDF!')
    make_summary(summary, run_number)

    print('Done')
    print(f'Check {OUTFOLDER}')

if __name__=="__main__":
    main()

