from src.thorlabs_hdr50 import *
import time

stage = HDR50(serial_number="40106754", home=True, swap_limit_switches=False)
stage.wait_up()
time.sleep(1)
stage.turn_on()
time.sleep(1)

######################################################################3

# print('homing')
# stage.home()
# stage.wait_up()



# print('jogging')
# stage.move_relative(180)
# time.sleep(3)
# stage.wait_up()
# for i in range(18):
#     stage.move_relative(10)
#     stage.wait_up()
#     print(i)
print(stage.status)

stage.turn_off()
stage.close()


