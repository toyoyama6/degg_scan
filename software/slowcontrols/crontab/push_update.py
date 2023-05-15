import os
import sys
sys.path.append('/home/scanbox/dvt/slackbot')
import chiba_slackbot
from chiba_slackbot import send_warning, push_slow_mon
import time

def push_plot(file_path, name):
    try:
        os.path.isfile(file_path)
    except:
        send_warning("@channel Path to slow-mon plot not found:"+file_path)
        return False

    push_slow_mon(file_path, name)
    return True

if __name__ == '__main__':
    temperature_plot = "/home/scanbox/software/plotting/recent_temp.png"
    push_plot(temperature_plot, "Recent Freezer Temperature")

    #try to avoid pushing too fast
    time.sleep(15)

    disk_plot = "/home/scanbox/software/plotting/recent_disk.png"
    push_plot(disk_plot, "Disk Space")

    time.sleep(15)

    humidity_plot = "/home/scanbox/software/plotting/recent_humidity.png"
    push_plot(humidity_plot, "Recent Humidity")

    time.sleep(15)
