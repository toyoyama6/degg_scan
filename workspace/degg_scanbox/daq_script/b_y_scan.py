from src.oriental_motor import *
from src.thorlabs_hdr50 import *
from src.kikusui import *

import time
from subprocess import PIPE, Popen
import os
import datetime


def b_y_measure():

    dt_now = datetime.datetime.now()
    strdate = dt_now.strftime('%Y_%m_%d_%H_%M')
    data_dir = './data/{}_b_y'.format(strdate)
    os.mkdir(data_dir)

    nwfm = 1000

    theta_range = 360  # degree
    z_range = 10000    # mm

    theta_step = 10
    z_step = 1000
    n_theta = theta_range/theta_step
    n_z = z_range/z_step

    rotate_stage = HDR50(serial_port="/dev/ttyUSB*", serial_number="40106754", home=False)
    z_stage = AZD_AD(port="/dev/ttyUSB*")

    slave_address = 2

    rotate_stage.home()
    rotate_stage.wait_up()

    z_stage.moveToHome(slave_address)
    time.sleep(5)

    theta = 0

    for i in range(n_theta):
        
        z = 0

        for k in range(n_z):

            # 波形を取るコードを書く

            z_stage.moveRelative(slave_address, z_step)

            z += n_z

        cmd = "python3 read_waveform.py 1 {0}{1}-theta {2}".format(data_dir, theta, nwfm)
        proc = Popen(cmd, stdout=PIPE, shell=True)
        lists = proc.communicate()[0].split()

        rotate_stage.move_relative(theta_step)
        rotate_stage.wait_up()

        theta += theta_step


def main():

    b_y_measure()

if __name__ == "__main__":
    main()



