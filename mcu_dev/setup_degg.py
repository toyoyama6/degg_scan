##setup a DEgg since the mini-fieldhub has been power cycled
import os, sys, subprocess
import time
from tqdm import tqdm
import numpy as np
import stf
from iceboot.iceboot_session import startIcebootSession 

def rethink_life():
    choice = input("Only run this script if you rebooted the mini-fieldhub \n Do you want to proceeed [y/n]")

    if choice.lower() not in ["y", "yes"]:
        print("Go home and rethink you life")
        exit(1)

    else:
        print(f"Setting up D-Eggs")
        print("------------------")

def set_paths():
    new_term = input("Do you need to reset the environment variables? [y/n]")

    if new_term.lower() in ["y", "yes"]:
        print("\t Setting environment variables")
        sys.path.insert(0, "/home/scanbox/mcu_dev/src/tools/python/")
        sys.path.insert(0, "/home/scanbox/stf/")
        #subprocess.call(["export", "PYTHONPATH=$PYTHONPATH:/home/scanbox/mcu_dev/src/tools/python/"])
        #sys.path.append("/home/scanbox/stf/")
    else:
        print("\t Not setting environment variables...")

def fpga_set(port_num):
    flash_fpga = input(f"Do you need to re-flash the FPGA firmware ({port_num})? (Takes some time...) [y/n]")
    if flash_fpga.lower() in ["y", "yes"]:
        print(f"\t Flashing FPGA firmware {port_num} - using stable build...")
        if port_num == 5012:
            try:
                os.system("python3 /home/scanbox/mcu_dev/src/tools/python/DEggTest/loadFPGA.py --fpgaConfigurationFile=~/mcu_dev/firmware/degg_fw_v0xfd.rbf --host=localhost --port=5012")
            except:
                print("\t \t Could not flash software, 5012")
            print("sleeping for connections...")
            time.sleep(10)
        if port_num == 5013:
            try:
                os.system("python3 /home/scanbox/mcu_dev/src/tools/python/DEggTest/loadFPGA.py --fpgaConfigurationFile=~/mcu_dev/firmware/degg_fw_v0xfd.rbf --host=localhost --port=5013")
            except:
                print("\t \t Could not flash software, 5013")
        if port_num not in [5012, 5013]:
            print("!!! Invalid port numbers??? !!!")

if __name__ == "__main__":
    rethink_life()
    # set_paths()


    print("\n ------------------------------------------- \n")
    print("Opening serial ports to 5012 and 5013")
    port_5012 = False
    port_5013 = False
    pid_5012 = -1
    pid_5013 = -1
    try:
        print("-----------------")
        print(" --- Try 5012 ---")
        p_5012 = subprocess.Popen(["python3", "/home/scanbox/mcu_dev/src/tools/python/serial_redirect.py", "-P", "5012", "/dev/ttyUSB2", "3000000", "--rtscts", "--rts", "0", "--dtr", "0"])
        port_5012 = True
        pid_5012 = p_5012.pid
        print("sleeping for connections...")
        time.sleep(10)
    except:
        print("Could not connect...")
        port_5012 = False
    try:
        print("-----------------")
        print(" --- Try 5013 ---")
        p_5013 = subprocess.Popen(["python3", "/home/scanbox/mcu_dev/src/tools/python/serial_redirect.py", "-P", "5013", "/dev/ttyUSB3", "3000000", "--rtscts", "--rts", "0", "--dtr", "0"])
        pid_5013 = p_5013.pid
        port_5013 = True
        print("sleeping for connections...")
        time.sleep(10)
    except:
        print("Could not connect...")
        port_5013 = False

    print("sleeping for connections...")
    time.sleep(10)

    if port_5012 is False and port_5013 is False:
        print("No vaid connections, exiting...")
        exit(1)

    print(f"Process IDs: {pid_5012}, {pid_5013}")
    np.savetxt("/home/scanbox/mcu_dev/serial_ids.txt", [pid_5012, pid_5013])


    fpga_set(5012)
    fpga_set(5013)

    if port_5012 is True:
        session_0 = startIcebootSession(host="localhost", port=5012)
        print("------------------")
        print("localhost - 5012")
        print(session_0.cmd("sloAdcReadAll"))
        print("...")
        time.sleep(10)
    if port_5013 is True:
        session_1 = startIcebootSession(host="localhost", port=5013)
        print("------------------")
        print("localhost - 5013")
        print(session_1.cmd("sloAdcReadAll"))
        print("...")
        time.sleep(10)

    print("======================================================")
    print("Note: Most scripts live in ~/mcu_dev/src/tools/python/")
    print("Note: STF lives in /home/scanbox/stf/")
    print("======================================================")
    #end
