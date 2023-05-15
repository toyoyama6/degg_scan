import sys
import datetime
import time
from subprocess import PIPE, Popen
import os

dt_now = datetime.datetime.now()

strdate = dt_now.strftime('%Y_%m_%d_%H_%M')

os.mkdir('./data/{}'.format(strdate))

READCH = "1"
data_dir = "./data/{}/".format(strdate)
FILENAME_prefix = "data"
nWFM = 10

# cmd = "python microbase_controll_4inch_argHV.py 85.25" 
# Popen(cmd, stdout=PIPE,shell=True)
# time.sleep(3600*48)

c = 0
while(1):

	print("Loop:", c)
	dt_now = datetime.datetime.now()

	strdate = dt_now.strftime('%Y_%m_%d_%H_%M_%S')
	filename = data_dir + FILENAME_prefix + "_" + str(c) + ""
	proc = Popen("python3 darkrate_ana_kai.py {0} {1} {2}".format(READCH, filename, nWFM), shell=True, stdout=PIPE)
	lists = proc.communicate()[0].split()
	c += 1