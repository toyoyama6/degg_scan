from datetime import datetime
import os

def create_save_dir(filepath, measurement_type):
    today = datetime.today()
    today = today.strftime("%Y%m%d") 
    
    cnt = 0
    while True: 
        today = today + f'_{cnt:02d}'
        dirname = os.path.join(filepath, measurement_type, today)
        if os.path.isdir(dirname):
            today = today[:-3]
            cnt += 1
        else:
            os.makedirs(dirname)
            print(f"Created directory {dirname}")
            break
    return dirname


def extract_runnumber_from_path(run_path):
    basename = os.path.basename(run_path)
    prefix = basename.split('.')[0]
    run_number = int(prefix.split('_')[-1])
    return run_number

