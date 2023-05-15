from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

import time
from subprocess import PIPE, Popen
import os
import datetime





def b_x_measure():

    dt_now = datetime.datetime.now()
    strdate = dt_now.strftime('%Y_%m_%d_%H_%M')
    data_dir = './data/{}_b_x'.format(strdate)
    os.mkdir(data_dir)

    nwfm  = 1000

    theta_range = 180  # degree
    r_range = 10000    # mm (radius)

    theta_step = 10
    r_step = 1000
    n_theta = theta_range/theta_step
    n_r = r_range/r_step

    ##USB3 - THORLABS
    rotate_stage = HDR50(serial_port="/dev/ttyUSB*", serial_number="40106754", home=False)
    ##USB2 - ORIENTAL MOTORS
    r_stage = AZD_AD(port="/dev/ttyUSB*")

    ##Motor ID
    slave_address = 1

    rotate_stage.home()
    rotate_stage.wait_up()

    r_stage.moveToHome(slave_address)
    time.sleep(5)

    theta = 0

    for i in range(n_theta):
        
        r = 0
        appear_theta = theta

        for k in range(n_r):

            # The function to take data

            r_stage.moveRelative(slave_address, r_step)

            r += n_r

        r = 0
        appear_theta = theta + 180

        r_stage.moveToHome(slave_address)
        time.sleep(5)

        for k in range(n_r):

            # The function to take data

            r_stage.moveRelative(slave_address, -r_step)

            r += n_r

        r_stage.moveToHome(slave_address)
        cmd = "python3 read_waveform.py 1 {0}{1}-theta {2}".format(data_dir, theta, nwfm)
        proc = Popen(cmd, stdout=PIPE, shell=True)
        lists = proc.communicate()[0].split()

        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()

        theta += theta_step


def main():

    b_x_measure()

if __name__ == "__main__":
    main()



