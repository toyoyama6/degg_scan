from datetime import datetime
import numpy as np
import os, sys
from termcolor import colored

#sys.path.append('/home/scanbox/dvt/slackbot/')
from chiba_slackbot import send_message

def update_log(logfile, errorfile, tags):

    now = datetime.now()
    f = open(logfile, "w")
    t_tags = str(tags['Tags'])
    t_name = str(tags['Name'])
    t_num = str(tags['Num'])
    write_string = str(now) + ", " + t_tags + ", " + t_name + ", " + t_num + '\n'
    try:
        f.write(write_string)
    except:
        raise IOError
    f.close()
    print("Log file updated")

def get_info(num):

    info = []
    tags = {}
    print("Please Input the Error Details...")
    info = str(input("Please Describe the Error: "))

    tag = input("Please give a brief list of tags (meta-info): ")
    user = input("Please Give your Name: ")
    tags['Name'] = user
    tags['Tags'] = tag
    tags['Num'] = num

    return (info, tags)

def new_error(logfile):
    num = len(os.listdir("/home/scanbox/errors/"))
    path = f"/home/scanbox/errors/err_{num}.txt"
    if os.path.exists(path):
        inpt = input("You're overwriting " + path + " - Proceed? [y/n]")
        if inpt.lower() not in ["y", "yes"]:
            print("Not overwriting file...")
            exit(1)
    new_error_file = path
    f = open(new_error_file, "w+")
    print(f"Creating new error file: {new_error_file}")
    
    info, tags = get_info(num)
    f.write(info + '\n')
    f.close()

    update_log(logfile, new_error_file, tags)

if __name__ == "__main__":

    choice = input("Logging an error? [y/n]: ")
    if choice.lower() not in ["y", "yes"]:
        print("Go home and rethink your life")
        exit(1)

    print(colored("If this is a software error, please also provide the error!", 'blue'))

    logfile = "/home/scanbox/errors/log.txt"

    new_error(logfile) 

    msg_text = "New error was logged to scanbox by a user in file: " + logfile
    send_message(msg_text)

##end
