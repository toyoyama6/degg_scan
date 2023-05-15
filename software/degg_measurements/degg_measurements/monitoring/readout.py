from degg_measurements.utils import startIcebootSession
import time
from tqdm import tqdm
import os

from monitoring import readout, get_fpga_version
from monitoring import set_degg_hv_zero


def main(ports):
    sessions = []
    for port in ports:
        session = startIcebootSession(host='localhost',
                                      port=port)
        sessions.append(session)
    for i in tqdm(range(10000)):
        for port, session in zip(ports, sessions):
            #  print(port)
            set_degg_hv_zero(session)
            # get_fpga_version(session)


if __name__ == '__main__':
    filenames = ['$HOME/dvt/data/monitoring/sensor_5012.csv', 
                 '$HOME/dvt/data/monitoring/sensor_5013.csv',
                 '$HOME/dvt/data/monitoring/sensor_5014.csv']
    filenames = list(map(os.path.expandvars, filenames))
    ports = [5012, 5013, 5014]
    main(ports)

