##periodically make copies of monitoring data
##consider backing up in safe location
import numpy as np
import os, sys
from termcolor import colored
from datetime import datetime

sys.path.append('/home/scanbox/dvt/slackbot')
from chiba_slackbot import send_message, send_warning

def add_to_backup(file_list, file_path):

    now = datetime.now()

    if os.path.isfile(file_path) is True:
        #print(colored(f"Appending: {file_path}", "green"))
        file_list.append(file_path)
    else:
        #print(colored(f"Failed to find file: {file_path}", "red"))
        send_warning("@channel - Backup failed at " + str(now) + ": " + file_path)

    return file_list

def perform_backup(file_list):
    was_warn = False
    msg_str = f"[Backup Cron] List of files being backed up: \n {file_list}"
    send_message(msg_str)
    
    today = datetime.today()
    today = today.strftime("%Y-%m-%d")
    print(today)
    backup_path = f"/home/scanbox/backup/{today}/"
    if not os.path.exists(backup_path):
        try:
            os.makedirs(backup_path)
        except:
            send_warning("@channel - Could not create directory for backup")
            was_warn = True

    for file in file_list:
        #print(file)
        ##first do the local backup
        backup_string = f"cp {file} {backup_path}"
        try:
            os.system(backup_string)
        except:
            send_warning("@channel - Copy of backup files failed (local)")
            was_warn = True

        ##then backup to grappa
        remote_backup_path = "icecube@grappa.phys.chiba-u.jp:/misc/home/icecube/backup_scanbox/"
        backup_string_remote = f"rsync -v {file} {remote_backup_path}"
        try:
            os.system(backup_string_remote)
        except:
            send_warning("@channel - Copy of backup files failed (remote)")
            was_warn = True

    if was_warn is True:
        return False

    send_message("[Backup Cron] No errors during copying")
    return True

def log_backup(file_list, log_file, _rtrn):
    now = datetime.now()
    rtrn = _rtrn

    f = open(log_file, 'a')
    tup = (str(now) + ', ' + str(rtrn) + '\n')
    f.write(tup)

    #tup = (str(now), str(rtrn))
    #tup = np.array(tup)
    #np.savetxt(log_file, tup)

if __name__ == "__main__":
    #print(colored("--- Running Local Backup ---", "green"))

    log_file = "/home/scanbox/backup/logs.txt"

    ##get the files
    file_list = []
    add_to_backup(file_list, '/home/scanbox/software/goldschmidt/goldschmidt/temp.csv')
    add_to_backup(file_list, '/home/scanbox/software/check_disk/disk_space.csv')
    add_to_backup(file_list, '/home/scanbox/software/USBRH_driver/humidity_0.csv')
    add_to_backup(file_list, '/home/scanbox/software/USBRH_driver/humidity_1.csv')


    rtrn = perform_backup(file_list)

    log_backup(file_list, log_file, rtrn)

##end
