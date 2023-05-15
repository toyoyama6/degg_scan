import os, sys
from degg_measurements import FREEZER_CONTROL
sys.path.append(FREEZER_CONTROL)
from degg_measurements import FREEZER_CONTROL_PATH

try:
    from changeTemp import control_wrapper
except ImportError:
    raise ImportError('Cannot import freezer control software!')

def dummy_wrapper(run_json, fcurrent, fdelta, monitor=False):
    print(f'MicroController on {FREEZER_CONTROL_PATH}')
    control_wrapper(monitor, fcurrent, fdelta)
    print("Finished")

##for debugging purposes
def main():
    dummy_wrapper('', -40, 60, False)

if __name__ == "__main__":
    main()

##end
