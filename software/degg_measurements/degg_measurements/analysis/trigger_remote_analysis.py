# This script is intended to run on the scanbox PC
# It sends the run json to a remote server and triggers the further analysis on this server.
#
# It partners with the do_remote_analysis.py on the remote server

from genericpath import isfile
import os
import click
import json
from datetime import date

from degg_measurements.utils import ssh_client
from degg_measurements.utils import load_run_json
from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import update_json
from degg_measurements.utils.load_dict import load_config_dict
from degg_measurements import DATA_DIR, RUN_DIR
from degg_measurements.analysis.analysis_utils import get_measurement_numbers

#from degg_measurements import IGNORE_LIST
from degg_measurements.utils.load_dict import audit_ignore_list


class RemoteAnanlys(object):
    def __init__(self, hostname="grappa", remote_data_dir="/disk20/fat/data",
                 remote_sw_dir="/disk20/fat/software"):

        self.ssh_session = ssh_client.SSHClient(hostname)
        self.remote_data_dir = remote_data_dir
        self.remote_sw_dir = remote_sw_dir
        self.remote_degg_sw_dir = os.path.join(self.remote_sw_dir, "degg_measurements/degg_measurements/analysis")
        self.data_copied = False
        self.degg_copied = False
        self.run_copied = False
        self.run_config = None
        # Dictionary containg the names of valid analysis (key) and measurement types (values)
        self.analyses = {"baseline": { "type" : "BaselineFilename",
                                       "module": None},
                         "darkrate": { "type" : "DarkrateScalerMeasurement",
                                       "module": None},
                         "double_pulse": { "type" : "DoublePulse",
                                           "module": None},
                         "flasher_chargestamp": { "type" : "FlasherCheck",
                                                  "module": None},
                         "gain": { "type" : "GainMeasurement",
                                   "module": None},
                         "linearity": { "type" : "LinearityMeasurement",
                                        "module": None},
                         "quick_monitoring": { "type" : "OnlineMon",
                                         "module": None},
                         "detailed_monitoring": { "type" : "AdvancedMonitoring",
                                         "module": None},
                         #"gainscan_monitoring": { "type" : "GainScanMonitoring",
                         #                "module": None},
                         "reboot_monitoring": { "type" : "RebootMonitoring",
                                         "module": None},
                         "spe": { "type" : "SpeMeasurement",
                                  "module": None},
                         "tts": { "type" : "TransitTimeSpread",
                                  "module": None},
                         "dt": { "type" : "DeltaTMeasurement",
                                  "module": None},
                         "gainscan_monitoring": {"type" : "DarkrateTemperature",
                                  "module": None}}

    def copy_run_json(self, run_json, remote_path=None):
        if not self.data_copied:
            print("Data not copied! Copy data and Degg files first!")
            return 0
        if not self.degg_copied:
            print("Degg files not copied! Run json doesn't contain the remote folder location")
            print("Copy the degg files first!")
            return 0

        run_json_file = os.path.split(run_json)[1]

        # First we need to save a temporary run_json file
        tmp_run_json = os.path.join("/home/scanbox/data/tmp/", run_json_file)
        # Make sure to not write a corrupted json file if
        # the new dict is not json serializable
        try:
            json.dumps(self.run_config)
        except TypeError:
            raise

        with open(tmp_run_json, 'w') as open_file:
            json.dump(self.run_config, open_file, indent=4)

        # Now we can copy the temporary file to the remote location
        if remote_path is None:
            self.remote_run_json = os.path.join(self.remote_data_dir, "json/run", run_json_file)
        else:
            self.remote_run_json = remote_path

        #try to create the remote dir
        self.ssh_session.run_cmd(f"mkdir -p {os.path.dirname(self.remote_run_json)}")
        #copy the run json to remote location
        self.ssh_session.send_file(tmp_run_json, self.remote_run_json, force=True)
        #now we delete the temprary file
        if os.path.exists(tmp_run_json):
            os.remove(tmp_run_json)

        self.run_copied = True

    def copy_data(self, run_json, analysis, measurement_number="latest", remote_path=None):

        if remote_path is None:
            remote_dir = os.path.join(self.remote_data_dir, "fat_callibration")
        else:
            remote_dir = remote_path

        if measurement_number != 'latest':
            measurement_number = int(measurement_number)

        list_of_deggs = load_run_json(run_json)
        measurement_type = self.analyses[analysis]['type']
        # get a list of all data for each degg
        local_data_list = []
        remote_data_list = []
        for degg_file in list_of_deggs:
            degg_dict = load_degg_dict(degg_file)

            if analysis == "flasher_chargestamp":
                pmt_list = ["LowerPmt"]
            elif analysis == "quick_monitoring":
                pmt_list = [None]
            else:
                pmt_list = ["LowerPmt", "UpperPmt"]
            for pmt in pmt_list:
                try:
                    measurement_numbers = get_measurement_numbers(
                        degg_dict, pmt, measurement_number,
                        measurement_type)
                except:
                    print(f'No measurement found for \
                          {degg_dict["DEggSerialNumber"]}, {measurement_type}')
                    continue
                for m_num in measurement_numbers:
                    measurement_key = f"{measurement_type}_{m_num:02}"
                    if audit_ignore_list(degg_file, degg_dict, measurement_key,
                                         file_path=IGNORE_LIST,analysis=True) == True:
                        continue
                    if pmt == None:
                        local_data_dir = degg_dict[measurement_key]['Folder']
                        #add path to list
                        local_data_list.append(local_data_dir)
                        #replace the DATA_DIR with the remote one
                        remote_data_dir = local_data_dir.replace(DATA_DIR, remote_dir)
                        #create new remoteFolder key in Degg dict
                        degg_dict[measurement_key]['RemoteFolder'] = remote_data_dir
                    else:
                        local_data_dir = degg_dict[pmt][measurement_key]['Folder']
                        #add path to list
                        local_data_list.append(local_data_dir)
                        #replace the DATA_DIR with the remote one
                        remote_data_dir = local_data_dir.replace(DATA_DIR, remote_dir)
                        #create new remoteFolder key in Degg dict
                        degg_dict[pmt][measurement_key]['RemoteFolder'] = remote_data_dir
            #now we need to save the updated degg_dict
            update_json(degg_file, degg_dict)
        #remove duplicate entries
        local_data_list = [*set(local_data_list)]
        print(local_data_list)
        # for testing remove None from list
        local_data_list = [i for i in local_data_list if i != "None"]
        remote_data_list = [i.replace(DATA_DIR, remote_dir) for i in local_data_list]
        print(local_data_list)
        print(f'Remote Data: {remote_data_list}')
        #copy data
        for i in range(len(local_data_list)):
            if local_data_list[i][0] == '.':
                continue
            #to send the folder we only need the parent dir
            remote_data_dir = os.path.dirname(remote_data_list[i])
            ##try to create the remote dir
            self.ssh_session.run_cmd(f"mkdir -p {remote_data_dir}")
            #now copy the folder to the remote location
            self.ssh_session.send_directory(local_data_list[i], f"{remote_data_dir}/")
            #change permissions for copied files via tar as tar conserves permissions from the source
            self.ssh_session.run_cmd(f"chmod -R 775 {remote_data_list[i]}")
            #self.ssh_session.run_cmd(f"chmod {remote_data_list[i]}")

        self.data_copied = True

    def copy_degg_json(self, run_json, remote_path=None):
        if not self.data_copied:
            print("Data not copied! DEgg jsons don't contain the remote folder location")
            print("Copy the data first!")
            return 0

        if remote_path is None:
            remote_dir = os.path.join(self.remote_data_dir, "json")
        else:
            remote_dir = remote_path

        list_of_deggs = load_run_json(run_json)
        #save the run config to change the degg path
        self.run_config = load_config_dict(run_json)
        ban_list = ['comment', 'date', 'end_time', 'RunTerminated']
        for key in self.run_config:
            #print(key)
            if key in ban_list:
                continue
            if key[:-1] == 'ManualInputTime':
                continue
            if self.run_config[key] in [-1, 0, 1]:
                continue
            if key[:-3] == "MasterFAT":
                continue
            self.run_config[key] = self.run_config[key].replace(RUN_DIR, remote_dir)

        #pick one file to get the folder which holds all degg jsons
        degg_file = list_of_deggs[0]
        local_degg_dir = os.path.split(degg_file)[0]
        remote_degg_dir = local_degg_dir.replace(RUN_DIR, remote_dir)
        #to send the folder we only need the parent dir
        remote_degg_par = os.path.dirname(remote_degg_dir)
        #try to create the remote dir
        self.ssh_session.run_cmd(f"mkdir -p {remote_degg_par}")
        #copy the run json to remote location
        self.ssh_session.send_directory(local_degg_dir, f"{remote_degg_par}/")
        #change permissions for copied files via tar as tar conserves permissions from the source
        print(f'Remote degg dir: {remote_degg_dir}')
        self.ssh_session.run_cmd(f"chmod 775 {remote_degg_dir}/*.json")
        self.degg_copied = True

    def copy_baseline(self, run_json, analysis, remote_path=None):

        if remote_path is None:
            remote_dir = os.path.join(self.remote_data_dir, "fat_callibration")
        else:
            remote_dir = remote_path

        list_of_deggs = load_run_json(run_json)
        measurement_type = self.analyses[analysis]['type']
        # get a list of all data for each degg
        local_data_list = []
        remote_data_list = []
        for degg_file in list_of_deggs:
            degg_dict = load_degg_dict(degg_file)
            for pmt in ["LowerPmt", "UpperPmt"]:
                local_data_dir = degg_dict[pmt][measurement_type]
                #replace the DATA_DIR with the remote one
                remote_data_dir = local_data_dir.replace(DATA_DIR, remote_dir)
                #add path to list
                local_data_list.append(local_data_dir)
                remote_data_list.append(remote_data_dir)
        #remove duplicate entries
        local_data_list = [*set(local_data_list)]
        remote_data_list = [*set(remote_data_list)]
        #copy data
        for i in range(len(local_data_list)):
            #to send the folder we only need the parent dir
            remote_data_dir = os.path.dirname(remote_data_list[i])
            ##try to create the remote dir
            self.ssh_session.run_cmd(f"mkdir -p {remote_data_dir}")
            #now copy the file to the remote location
            self.ssh_session.send_file(local_data_list[i], remote_data_list[i], force=True)
            #change permissions for copied files via tar as tar conserves permissions from the source
            self.ssh_session.run_cmd(f"chmod -R 775 {remote_data_list[i]}")

    def run_remote_analyis(self, run_json=None, analysis=None, measurement_number=None):
        if run_json is None:
            if hasattr(self, "remote_run_json"):
                run_json = self.remote_run_json
            else:
                print("Could not find run json. Please provide valid path to run json on remote server or run copy_run_json first.")

        if analysis is None:
            print("No analysis to execute was given. Please choose from {self.analyses}.")
        elif analysis not in self.analyses:
            print(f"Did not recognized given analysis: {analysis}.")
            print(f"Please choose from: {self.analyses}")
        else:
            print(f"Starting remote analysis: {analysis}")
            remote_ana_path = os.path.join(self.remote_degg_sw_dir, "remote_analysis_wrapper.py")
            session_name = f"{date.today()}_{analysis}"

            ##run the latest analysis
            if measurement_number == None:
                analysis_cmd = f"python {remote_ana_path} {analysis} {run_json}"
            else:
                analysis_cmd = f"python {remote_ana_path} {analysis} {run_json} \
                    -n {measurement_number}"

            ssh_cmd = f"screen -S {session_name} -L -d -m {analysis_cmd}"
            self.ssh_session.run_cmd(ssh_cmd)

            print("-"*20)
            print(f"session name: {session_name}")
            print(f"session logfile: /disk20/fat/data/logs/")
            print(f"Run json: {run_json}")
            print(f"Analysis: {analysis}")
            print(f"File: {remote_ana_path}")
            print("-"*20)


def trigger_remote_wrapper(run_json, analysis, number='latest'):
    rmt_ana = RemoteAnanlys()

    if analysis == "baseline":
        rmt_ana.copy_baseline(run_json, analysis)
    else:
        rmt_ana.copy_data(run_json, analysis, measurement_number=number)
        rmt_ana.copy_degg_json(run_json)
        rmt_ana.copy_run_json(run_json)
        if number != 'latest':
            rmt_ana.run_remote_analyis(analysis=analysis, measurement_number=number)
        ##default behaviour
        else:
            rmt_ana.run_remote_analyis(analysis=analysis)


@click.command()
@click.argument("run_json")
@click.argument("analysis")
@click.option('--number', '-n')
def main(run_json, analysis, number):
    trigger_remote_wrapper(run_json, analysis, number)


if __name__ == "__main__":
    main()
