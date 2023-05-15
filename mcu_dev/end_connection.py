import numpy as np
import os, sys, subprocess
import signal

def kill_process(pid):
    if pid == -1:
        print("PID not set... skipping")
    if pid != -1:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Process {pid} killed (I hope...)")
        except:
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                print(f"Unable to remove process {pid}")
                return False
    return True

if __name__ == "__main__":
    try:
        text = np.loadtxt("/home/scanbox/mcu_dev/serial_ids.txt")
    except:
        raise IOError("Could not find file")



    pid_5012 = int(text[0])
    pid_5013 = int(text[1])

    print("---------------------------------------")
    print("Removing serial port processes to DEggs")
    print(f"Process IDs: 5012 - {pid_5012}, 5013 - {pid_5013}")
    print("---------------------------------------")

    choice = input("Terminate processes? [0/1/both]")

    proc_5012 = False
    proc_5013 = False

    if choice == "0":
        proc_5012 = kill_process(pid_5012)
    if choice == "1":
        proc_5013 = kill_process(pid_5013)
    if choice.lower() in ["both", "b", "y", "yes"]:
        proc_5012 = kill_process(pid_5012)
        proc_5013 = kill_process(pid_5013)

    print("Serial IDs set to -1")
    if proc_5012 is True and proc_5013 is True:
        np.savetxt("serial_ids.txt", [-1, -1])
    #end
