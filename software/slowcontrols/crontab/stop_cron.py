import os, sys
from termcolor import colored

user = 'scanbox'

print("current cron: ")
print(os.system("crontab -l"))

print(colored("WARNING - This will stop the slow monitoring (ALL cronjobs)", "yellow"))
choice = input("\t Do you want to proceed? [y/n]")
if choice.lower() not in ["y", "yes"]:
    print("Cron is still running - exiting...")
    exit(1)
else:
    print(f"Removing all cron jobs for {user}...")
    try:
        os.system("crontab -r")
        print("Removing...")
    except:
        print("Could not remove crontab")
        exit(1)
print("Current Cron:")
print(os.system("crontab -l"))
