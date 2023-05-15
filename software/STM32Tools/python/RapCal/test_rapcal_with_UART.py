################################################################
#### 25.01.2021 - Sarah Mechbal - DESY Zeuthen
#### Script adapted from Thomas Meures
#### Long-running RAPCal calibration pulses
#### All equations are related to the IceCube Gen1 paper
#### https://arxiv.org/pdf/1612.05093.pdf
################################################################


import comms_testing as ct
import time
import numpy as np
import rapcal as rp
import sys


# The script takes one argument, 
# the number of RAPCal pulses 
# needed for this run
n_rapcal = int(sys.argv[1])

time_sleep = 1.0

# Let's go!
all_rapcals = rp.RapCalCollection()

dd=ct.comms_testing_device("/dev/ttyUSB0")
#dd=ct.comms_testing_device("/dev/ttyUSB1")
rapcal_dev_vec  = 0
conn_devs=[2,4,7]
#conn_devs=[7]
for dev in  conn_devs:
    rapcal_dev_vec+=(0x1   << dev)

for n in range(n_rapcal):

    rapcal_data= []
    dd.write_reg(0x8, 0x35, 7,  [0,rapcal_dev_vec])
    time.sleep(time_sleep)
   
    dd.read_uart()
    for dev in  conn_devs:
         val = dd.read_reg(dev, 0x9, 6)
         if(len(val)>1):
            count = val[4]*256 +   val[5]
            #time.sleep(0.5)
            rapcal_data.append(dd.read_reg(dev,  0x8, count+4))
        
    rapcal_data = np.array(rapcal_data)
    #reshape the array  to make it 1-D        
    rapcal_data =   rapcal_data.reshape((rapcal_data.shape[0]*rapcal_data.shape[1],))

    event =  rp.RapCalEvent(rapcal_data)
    event._analyze(1)        
    all_rapcals.add_rapcal(event)
    
    
all_rapcals.get_rapcal_stats()    
# for dev in conn_devs:
#     print(dev)
#     all_rapcals.get_rapcal_stats_per_module(dev)


# close the connection with device
dd.close()


