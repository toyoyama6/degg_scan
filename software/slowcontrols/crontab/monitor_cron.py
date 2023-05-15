##run once on startup

##can check current configs with crontab -l

##this adds processes to the local cron
##these will run periodically, automatically

import sys, os
from crontab import CronTab
import datetime


def start_cron():
    cron = CronTab(user='scanbox')
    return cron

def inspect_cron(cron):
    for job in cron:
        print(f"--- Job {job} ---")
        sch = job.schedule(date_from=datetime.datetime.now())
        print("Next Run Time: ", sch.get_next())

if __name__ == '__main__':
    cron = start_cron()
    inspect_cron(cron)

    ##write the cron
    #cron.write()

##end
