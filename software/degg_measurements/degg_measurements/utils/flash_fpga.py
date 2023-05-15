##setup a DEgg since the mini-fieldhub has been power cycled
import os, sys, subprocess
from traceback import print_tb
import time
from tqdm import tqdm
import numpy as np
from degg_measurements.utils import startIcebootSession 

from termcolor import colored

def fpga_set(port_num, auto_flash=False):
    fpga_flashed = False 

    print(f"--- {port_num} ---")

    if auto_flash is True:
        flash_fpga = 'y'
    if auto_flash is False:
        flash_fpga = input(f"Do you need to re-flash the FPGA " +
                       f"firmware ({port_num})? (Takes some time...) [y/n] \n")
    
    if flash_fpga.lower() not in ['y', 'yes']:
        return

    if flash_fpga.lower() in ["y", "yes"]:
        isLoaded = 0 
        failedcount = 0
        while isLoaded==0: 
            info = loadFPGA(port_num)
            if len(info)<2:
                if failedcount==1:
                    return fpga_flashed
                failedcount += 1
                continue
            else: 
                fwVer  = info[0]
                fpgaId = info[1]
                
            if fpgaId!="0xffffffffffffffff":
                isLoaded = 1
            else:
                print('Read FPGA was failed. Retry the configuration...')
        
        FpgaVersion = fwVer 

        if hex(FpgaVersion) != "0xffff":
            print(colored("FPGA configured successfully", 'green'))
            fpga_flashed = True

        if hex(FpgaVersion) == "0xffff":
            print(colored("FPGA running 0xffff, try again", 'yellow'))
            fpga_flashed = False

    return fpga_flashed 

# copy from rnagai-hpbsc/MB_FastTest/testitems/fwswversion.py
def loadFPGA(port_num): 
    time.sleep(1)
    try: 
        session = startIcebootSession(host="localhost", port=port_num)
    except OSError:
        print(colored('Timeout starting iceboot session \n', 'yellow'))
        return [0]

    flashLS = session.flashLS()

    if len(flashLS) == 0: 
        print('Valid firmware images not found.')
        print('Please upload the correct image file in the flash memory.')
        session.close()
        return [0]

    try:
        firmwarefilename = flashLS[len(flashLS)-1]['Name'] # latest uploaded file 
    except KeyError:
        print(flashLS)
        raise
    print(f'Found valid firmware {firmwarefilename} in the flash memory.\n' + 
            'Try to configure... ')

    try: 
        session.flashConfigureCycloneFPGA(firmwarefilename)
    except: 
        print(colored('Could not flash FPGA.', 'yellow'))
        session.close()
        return [0]
    
    time.sleep(0.1)

    try:
        FpgaVersion = session.fpgaVersion()
    except ValueError as e:
        print(colored('Could not get fpgaVersion.', 'yellow'))
        print(e)
        session.close()
        return [0]
    SoftwareVersion = session.softwareVersion()
    SoftwareId = session.softwareId()
    FpgaId = session.fpgaChipID()
    FlashId = session.flashID()

    print(f'FPGA: {FpgaId} with Firmware ver.{hex(FpgaVersion)}, Flash ID: {FlashId}, \n' + 
            f'Software ver.{hex(SoftwareVersion)} with ID {SoftwareId}. \n')
    time.sleep(0.5)

    session.close()
    return [FpgaVersion, FpgaId]

if __name__ == "__main__":

    port = int(sys.argv[1])
    if port is None:
        print("Please include the port number")
        exit(1)

    #if port not in open_ports:
    #    print("Port specified is not valid (check setup_deggs.py or configs/open_ports.json)")
    #    exit(1)

    fpga_flashed = False
    #if port in open_ports:
    #    try:
    while fpga_flashed is False:
        fpga_flashed = fpga_set(port)
        if fpga_flashed is True:
            break

        #except KeyboardInterrupt:
        #    print("Manual Interrupt - exiting")
        #    exit(1)

    print("flash_fpga: Exiting...")

##end
