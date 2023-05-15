from crontab import CronTab
import os,sys
sys.path.append('/home/scanbox/dvt/slackbot')
import chiba_slackbot
from chiba_slackbot import send_message, send_warning
from datetime import datetime

def check_cron_list():
    invalid_jobs = False
    cron = CronTab(user='scanbox')
    now = datetime.now()
    send_message(f"Slow Monitoring Script Status ({now}):")
    #print(f"Slow Monitoring Script Status ({now}):")

    for job in cron:
    
        #get the script name
        split_str = str(job).split()
        for string in split_str:
            if string.endswith(".py"):
                script_name = os.path.basename(string)

        if job.is_valid() is False:
            send_warning("@channel cron job invalid: " + script_name  + " :x:")
            #print("@channel cron job invalid: " + script_name + " :x:")
            invalid_jobs = True
        if job.is_valid() is True:
            send_message("Running: " + script_name + " :white_check_mark:")
            #print("Running: " + script_name + " :white_check_mark:")
    if invalid_jobs is False:
        return False
    if invalid_jobs is True:
        return True

if __name__ == '__main__':
    invalid_jobs = check_cron_list()
    if invalid_jobs is True:
        send_warning("@channel Invalid Cron Jobs")
