import os, sys
import click
import time
import numpy as np
from degg_measurements.utils import startIcebootSession

from chiba_slackbot import send_message
from chiba_slackbot import send_warning

def disable_all_lights(run_json=''):
    for port in np.arange(5000, 5016):
        session = startIcebootSession(host='localhost', port=port)
        for cam in [1, 2, 3]:
            session.setCameraSensorStandby(cam, 1)
            # Disables all available cameras
            session.setCameraEnableMask(0)
            session.disableCalibrationPower()
            time.sleep(1)

        session.close()
        send_message(f'Camera Lights disabled for {port}')
        time.sleep(2)

def disable_lights_interactive(port):
    session = startIcebootSession(host='localhost', port=port)
    for cam in [1, 2, 3]:
        session.setCameraSensorStandby(cam, 1)
        # Disables all available cameras
        session.setCameraEnableMask(0)
        session.disableCalibrationPower()
    session.close()

@click.command()
@click.option('--port', '-p')
@click.option('--all', is_flag=True)
def main(port, all):
    if all == True:
        disable_all_lights()
    if all == False:
        if port != None:
            port = int(port)
            disable_lights_interactive(port)
        else:
            print(f'port {port} should be an int')
            exit(1)

if __name__ == "__main__":
    main()
##end
