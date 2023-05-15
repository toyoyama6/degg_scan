##this function is needed for importing
##into config files for the master

from skippylab.instruments.function_generators import Agilent3101CFunctionGenerator as FG3101

def disable_laser(run_json):
    try:
        fg = FG3101()
        fg.disable()
        return True
    except:
        print("Error disabling the laser control!")
        return False

##end
