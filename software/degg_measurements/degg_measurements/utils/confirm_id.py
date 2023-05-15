##code for getting unique flashID and matching to port number
##then acquiring the D-Egg info from the ID via database

import time
import json
import click
import numpy as np
import os, sys
from degg_measurements.utils.parser import startIcebootSession
from degg_measurements.utils.stack_fmt import stripStackSize
from degg_measurements.utils.setup_degg import OPEN_PORTS
from degg_measurements.utils import short_sha
from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils.degg import DEgg
from datetime import datetime
from termcolor import colored

def get_flash_id(session):
    try:
        flashID = session.cmd('flashID')
    except:
        print("Could not determine the flashID")
        flashID = -1
    return flashID


def get_icm_id(session):
    try:
        icm_id = session.cmd('icmID')
    except:
        print("Could not determine the icmID")
        icm_id = -1
    return icm_id


## only call this function once -
## do not overload spreadsheet API
def logbook_instance():
    try:
        print("Connecting to D-Egg Log Book Spreadsheet")
        logbook_dataframes = DEggLogBook()
    except IndexError:
        print("Unable to construct dataframe from logbook")
    return logbook_dataframes


def get_degg_info(logbook_dataframes,
                  icm_id, fpgaVersion, icebootVersion,
                  spread_sheet_names,
                  sub_sheet_names, port):

    print('-'* 20)
    print('Info from the D-Egg')
    print(f'ICM ID         : {icm_id}')
    print(f'FPGA Version   : {fpgaVersion}')
    print(f'IceBoot Version: {icebootVersion}')
    print(f"Port: {port}")

    df_row = logbook_dataframes.get_degg_from_ID(icm_id, 'Serial number', 'Label number',
                                                 'icm', spread_sheet_names)
    if df_row is None:
        raise ValueError(f"Can't find icmID {icm_id} in the logbook!")

    if len(df_row) == 2:
        print("found duplicate ID!, trying to using the port also")
        try:
            df_row = logbook_dataframes.get_degg_from_ID(
                str(port), 'Port', spread_sheet_names)
        except:
            df_row = logbook_dataframes.get_degg_from_ID(
                port, 'Port', spread_sheet_names)

    print('-'*20)
    print('Info from Logbook! Check that it is correct!')
    print(f'DEgg:  {df_row["Nickname"].values[0]}')
    print(f'Degg:  {df_row["Serial number"].values[0]}')
    print(f'Upper: {df_row["Serial number (Upper D-Egg half)"].values[0]}')
    print(f'Lower: {df_row["Serial number (Lower D-Egg half)"].values[0]}')
    print(f'MCU:   {df_row["MCU Version"].values[0]}')
    print(f'FPGA:  {df_row["FPGA Version"].values[0]}')
    print(f'ICM0:  {df_row["ICM 0 Version"].values[0]}')
    print(f'ICM1:  {df_row["ICM 1 Version"].values[0]}')
    print(f'ICM2:  {df_row["ICM 2 Version"].values[0]}')

def get_fpga_version(session):
    try:
        fpgaVersion = session.cmd('fpgaVersion .s drop')
    except:
        print("Could not determine the fpgaVersion")
        fpgaVersion = -1
    fpgaVersion = stripStackSize(fpgaVersion)
    return fpgaVersion

def get_iceboot_version(session):
    icebootVersion = -1
    try:
        icebootVersion = session.cmd('softwareVersion .s drop')
    except:
        print("Could not determine the iceboot version")
        icebootVersion = -1
    icebootVersion = stripStackSize(icebootVersion)
    return icebootVersion

def start_session(_port):
    _port = int(_port)
    session = startIcebootSession(host='localhost', port=_port)
    time.sleep(0.5)
    return session

@click.command()
@click.argument('port')
def main(port):

    ##set which spreadsheets to check - lower case
    #spread_sheets = ['d-egg_for_dvt', 'rev4mb_tests']
    spread_sheets = [
        'd-egg_batch#1',
        'd-egg_batch#2',
        'd-egg_batch#3'
    ]
    sub_sheets = [
        'half_d-egg_batch#1',
        'half_d-egg_batch#2',
        'half_d-egg_batch#3'
    ]

    ##connect to google API and return dataframes
    logbook_dataframes = logbook_instance()

    session = start_session(port)
    icm_id = get_icm_id(session)
    fpgaVersion = get_fpga_version(session)
    icebootVersion = get_iceboot_version(session)
    del session

    get_degg_info(logbook_dataframes,
                  icm_id,
                  fpgaVersion,
                  icebootVersion,
                  spread_sheets,
                  sub_sheets,
                  port)

if __name__ == "__main__":
    main()

