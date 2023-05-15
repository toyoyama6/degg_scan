import time
import os, sys
import math
import datetime as datetime
import cv2
import click

#does this power cycle the MFH?
#IT USED TO - DEFAULT BEHAVIOUR ON BOARD CHANGED: 2021/07
import board
import digitalio

from chiba_slackbot import send_message, send_warning, push_slow_mon

@click.command()
@click.option('--monitor', is_flag=True, default=False)
@click.option('--fcurrent', default=None)
@click.option('--fdelta', default=None)
def main(monitor, fcurrent, fdelta):
    control_wrapper(monitor, fcurrent, fdelta)

def control_wrapper(monitor, fcurrent, fdelta):
    pic_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pictures")
    if not os.path.exists(pic_path):
        os.mkdir(pic_path)
        print(f"Created directory at {pic_path}")

    frz_set = digitalio.DigitalInOut(board.C1)
    frz_set.direction = digitalio.Direction.OUTPUT
    if monitor == True:
        freezer_monitor(frz_set, pic_path)
        print("Exiting...")
        exit(1)

    fdelta = float(fdelta)
    fcurrent = float(fcurrent)
    if(math.isnan(fdelta)):
        raise ValueError(f"Error! invalid delta T {fdelta}")
    freezer_control(frz_set, fcurrent, fdelta, pic_path)


def freezer_monitor(frz_set, pic_path):
    dt_now = datetime.datetime.now()
    strnow = dt_now.strftime("%Y-%m-%d_%H%M_%S_bf.png")
    cc = cv2.VideoCapture(0)
    frz_set.value = False
    time.sleep(0.2)
    frz_set.value = True
    time.sleep(3)
    frz_set.value = False
    rr,img = cc.read()
    cv2.imwrite(f"{pic_path}/{strnow}", img)
    frz_set.value = True
    time.sleep(0.2)
    frz_set.value = False
    print(f"Current temperature settings recorded ({strnow})")

    send_message("<Freezer Monitoring Check>")
    time.sleep(2)
    push_slow_mon(f"{pic_path}/{strnow}", 'Freezer_Monitoring')


def freezer_control(frz_set, fcurrent, fdelta, pic_path):
    prepare_control(frz_set)
    newt = fcurrent + fdelta
    print(f"Change temperature from {fcurrent} to {newt}")
 
    Tnow = fcurrent
    Tdelta = fdelta

    if Tdelta < 0:
        step_down(Tnow, Tdelta)
    elif Tdelta > 0:
        step_up(Tnow, Tdelta)
    else:
        raise ValueError(f'Could not parse input {fdelta} for step up or down')
    send_message(f'Changing freezer temp from {fcurrent} to {fcurrent + fdelta}')
    confirm(frz_set)
    record_temp(frz_set, pic_path)
    print("Finished")

def prepare_control(frz_set):
    frz_set.value = False
    time.sleep(0.2)
    frz_set.value = True
    time.sleep(4)
    frz_set.value = False
    time.sleep(0.2)

def step_down(Tnow, Tdelta):
    frz_down = digitalio.DigitalInOut(board.C3)
    frz_down.direction = digitalio.Direction.OUTPUT
    nstep_down = int(-Tdelta/0.1)
    for i in range(nstep_down):
        frz_down.value = True
        time.sleep(0.1)
        frz_down.value = False
        time.sleep(0.3)
        Tdelta -= 0.1
        #print("Temp:{0:.3f}".format(Tnow+Tdelta))

def step_up(Tnow, Tdelta):
    frz_up = digitalio.DigitalInOut(board.C2)
    frz_up.direction = digitalio.Direction.OUTPUT
    nstep_up = int(Tdelta/0.1)
    for i in range(nstep_up):
        frz_up.value = True
        time.sleep(0.1)
        frz_up.value = False
        time.sleep(0.3)
        Tdelta += 0.1
        #print("Temp:{0:.3f}".format(Tnow+Tdelta))

def confirm(frz_set):
    frz_set.value = True
    time.sleep(0.2)
    frz_set.value = False

def record_temp(frz_set, pic_path):
    dt_now = datetime.datetime.now()
    strnow = dt_now.strftime("%Y-%m-%d_%H%M_%S_af.png")
    print("Changed Temperature!")
    #time.sleep(4)
    frz_set.value = True
    time.sleep(4)
    frz_set.value = False
    time.sleep(0.2)
    cc = cv2.VideoCapture(0)
    rr,img = cc.read()
    cv2.imwrite(f"{pic_path}/{strnow}", img)
    print(f"Current temperature settings recorded ({strnow})")
    send_message("<Freezer Temperature Modified>")
    time.sleep(2)
    push_slow_mon(f"{pic_path}/{strnow}", 'Freezer_Monitoring')

if __name__ == "__main__":
    main()
##end
