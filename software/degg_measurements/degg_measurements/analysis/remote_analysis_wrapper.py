# This script is intended to run on grappa
# It recieves the run json from a scanbox and runs the further analysis.
#
# It partners with the trigger_remote_analysis.py on the scanbox PC

import shutil
import os
import click
import importlib
import traceback
from time import sleep
from datetime import datetime
from chiba_slackbot import send_warning


LOCKFILE = "/disk20/fat/data/analysis.lock"
SCREENLOG = "/home/icecube/screenlog.0"
LOG_PATH = "/disk20/fat/data/logs"

@click.command()
@click.argument('analysis')
@click.argument('run_json')
@click.option('--number', '-n')
@click.option('--offline', is_flag=True)
def main(analysis, run_json, number, offline):
    # do everything in a try block
    # used to copy the screen log to new location and clean up
    try:
        # hardcode remote because this script is only run on remote location
        remote = True
        available_analyses = {"baseline": { "type" : None,
                                            "module": None},
                              "darkrate": { "type" : "DarkrateScalerMeasurement",
                                            "module": "darkrate.analyze_darkrates"},
                              "double_pulse": { "type" : "DoublePulse",
                                                "module": "double_pulse.analyze_double_pulse"},
                              "flasher_chargestamp": { "type" : "FlasherCheck",
                                                "module": "flasher_chargestamp.analyze_flasher"},
                              "gain": { "type" : "GainMeasurement",
                                        "module": "gain.analyze_gain"},
                              "linearity": { "type" : "LinearityMeasurement",
                                                "module": "linearity.analyze_linearity"},
                              "quick_monitoring": { "type" : "OnlineMon",
                                                "module": "monitoring.monitor_quick"},
                              "detailed_monitoring": { "type" : "DetailedMonitoring",
                                                "module": None},
                              "gainscan_monitoring": { "type" : "GainScanMonitoring",
                                                "module": None},
                              "reboot_monitoring": { "type" : "RebootMonitoring",
                                                "module": None},
                              "spe": { "type" : "SpeMeasurement",
                                        "module": "spe.analyze_spe"},
                              "stf": { "type" : "STF",
                                        "module": "stf.analyze_stf"},
                              "tts": { "type" : "TransitTimeSpread",
                                        "module": "tts.analyze_tts"},
                              "dt": { "type" : "DeltaTMeasurement",
                                        "module": "darkrate.analyze_dt"},
                              "detailed_monitoring": { "type" : "AdvancedMonitoring",
                                                      "module": "stability.analyze_stability"}
                              }
        if analysis not in available_analyses.keys():
            raise Exception(f"<{analysis}> is not a valid analysis.")

        # Check for analysis.lock in /disk20/fat/data
        # Used to just run one analysis at the same time because screen uses same log file
        while os.path.exists(LOCKFILE):
            sleep(10)

        # Create the lockfile to tell other instances that an analysis is running
        open(LOCKFILE, 'a').close()
        # import analysis as module
        try:
            anamodule = importlib.import_module(available_analyses[analysis]['module'])
        except AttributeError:
            print(f"Could not find an analysis for {analysis}. Skipping analysis.")
        else:
            # run analysis
            if number == None:
                anamodule.analysis_wrapper(run_json, remote=remote, offline=offline)
            else:
                anamodule.analysis_wrapper(run_json, remote=remote, offline=offline,
                                       measurement_number=number)
    except:
        send_warning(
            traceback.format_exc() + '\n' +
            f'This exception was raised in the {analysis}-Analysis.'
        )
        traceback.print_exc()
    # Wait 10 sec, because the screen log is updated every 10 seconds
    sleep(10)
    # copy screenlog.0 to new location and rename it
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d_%H:%M")
    os.makedirs(LOG_PATH, exist_ok=True)
    new_name = f"{dt_string}_{analysis}.log"
    new_file = os.path.join(LOG_PATH, new_name)

    if os.path.isfile(SCREENLOG):
        shutil.copy(SCREENLOG, new_file)
        os.remove(SCREENLOG)
    os.remove(LOCKFILE)


if __name__ == "__main__":
    main()

