import os
import numpy as np

from degg_measurements import FILTER_WHEEL_PATH0
from degg_measurements import FILTER_WHEEL_PATH1

from filterWheel.control102C import connect_wheel, check_wheel
from filterWheel.control102C import disable_running_lights
from filterWheel.control102C import change_filter, get_valid_strengths

def setup_fw(no_check=False, get_list=False):
    validList = []
    by_id = '/dev/serial/by-id/'
    fw0 = connect_wheel(port=os.path.join(by_id, FILTER_WHEEL_PATH0))
    fw1 = connect_wheel(port=os.path.join(by_id, FILTER_WHEEL_PATH1))

    for i, fw in enumerate([fw0, fw1]):
        if no_check == True:
            fw_info = check_wheel(fw)
            if fw_info['RunningLights'] == 1:
                disable_running_lights(fw)
        # to measure by increasing intensity, sort first
        valid_strengths = np.sort(get_valid_strengths(i))
        validList.append(valid_strengths)
        print(f"Filter Strengths No.{i}: {valid_strengths}")

    if get_list == True:
        return fw0, fw1, validList
    else:
        return fw0, fw1

def change_filter_str(fw0, str0, fw1, str1):
    change_filter(fw0, str0, wheelNum=0)
    change_filter(fw1, str1, wheelNum=1)

def create_str_list(validList):
    print(f'Creating Linearity List from {validList}')
    l0 = validList[0]
    l1 = validList[1]

    ##hard coded
    new_list = [(1.0, 0.01),
                (0.05, 0.5),
                (0.05, 1.0),
                (1.0,  0.1),
                (0.25, 0.5),
                (0.32, 0.5),
                (0.25, 1.0),
                (0.32, 1.0),
                (1.0,  0.5),
                (1.0,  1.0)]

    for n in new_list:
        if n[0] not in l0:
            raise ValueError(f'Filter0 value {n[0]} not in {l0}')
        if n[1] not in l1:
            raise ValueError(f'Filter1 value {n[1]} not in {l1}')

    return new_list

def main():
    print("This script will connect to the filter wheels and reset to 100%")
    fw0, fw1 = setup_fw()
    change_filter_str(fw0, 1.0, fw1, 1.0)
    print("Done")

if __name__ == "__main__":
    main()
##end
