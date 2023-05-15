from goldschmidt.magnetometer import ThermometerTM947SD
from chiba_slackbot import send_message, send_warning
import numpy as np
import time

def check_temperature(device='/dev/ttyUSB1', do_repeat=False):
    ##try to catch string handling
    if do_repeat == 'False':
        do_repeat = False
    if do_repeat == 'True':
        do_repeat = True


    while True:
        meter = ThermometerTM947SD(device=device)
        temperatures = []
        ready_for_dehumidifier = False
        for channel_i in [1, 2, 3]:
            meter.select_channel(channel_i)
            temp_i = meter.measure()
            temperatures.append(temp_i)
            if temp_i < 5:
                continue
            if temp_i >= 5:
                ready_for_dehumidifier = True

        if ready_for_dehumidifier == False:
            send_message(f'Freezer still at: {np.mean(temperatures)}C, no action needed!')
        if ready_for_dehumidifier == True:
            send_warning(f'Freezer is at: {np.mean(temperatures)}C, install dehumidifiers!')
            send_warning(f'The master script will now exit!')
            raise ValueError(f'Run is finished - no need to continue')

        if do_repeat == True:
            print('Waiting to check temperature again...')
            time.sleep(600)
        else:
            break

def main():
    check_temperature(do_repeat=False)

if __name__ == "__main__":
    main()
##end
