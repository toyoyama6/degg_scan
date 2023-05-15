from src.thorlabs_hdr50 import *

stage = HDR50(serial_number="40106754", home=True, swap_limit_switches=False)
stage.wait_up()
print(stage.status)
stage.close()