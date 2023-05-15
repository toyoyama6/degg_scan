from src.kikusui import *
import sys
import os
from subprocess import PIPE, Popen
import numpy as np


MODE = int(input("which fiber are you going to measure?? \n0 : split fiber\n1 : single fiber\nPlease input 0 or 1  >>>> "))

if(MODE != 0 and MODE != 1):

    print("Choise correct number!!!!")
    sys.exit()

nfiber = input("what fiber number??\nPlease input 1~7  >>>> ")

if(MODE == 0):
    data_dir = './data/splitfiber/{}/'.format(nfiber)
    graph_dir = './graph/splitfiber/{}/'.format(nfiber)

elif(MODE == 1):
    data_dir = './data/singlefiber/{}/'.format(nfiber)
    graph_dir = './graph/singlefiber/{}/'.format(nfiber)

nwfm = 1000
print(data_dir, graph_dir)

if(os.path.exists(data_dir) == False):
    os.mkdir('{}'.format(data_dir))

else:
    ans = input('you already have measured!! You want to remeasure?? (y/n) >>>')

    if(ans=='y'):
        print('start measurement!!!')

    else:
        sys.exit()

if(os.path.exists(graph_dir) == False):
    os.mkdir('{}'.format(graph_dir))

LD = PMX70_1A('10.25.123.249')
LD.connect_instrument()

v_list = np.arange(3, 10, 1)

for i in v_list:

    LD.set_volt_current(i, 0.02)

    # input("Please set scale. and push enter....")

    print("start measurements!!\n LD supply voltage >>>> {}".format(i))

    cmd = "python3 read_waveform.py 1 {0}{1}V {2}".format(data_dir, i, nwfm)
    proc = Popen(cmd, stdout=PIPE, shell=True)
    lists = proc.communicate()[0].split()



 