from monitoring import readout_sensor
from degg_measurements.utils import startIcebootSession

import matplotlib.pyplot as plt
import numpy as np

ports = np.arange(5000, 5016)

for port in ports:
    session = startIcebootSession(host='localhost', port=port)
    light_list = []
    for i in range(10000):
        light_mv = readout_sensor(session, 'light_sensor')
        light_list.append(light_mv)

    session.close()
    del session

    fig, ax = plt.subplots()
    ax.hist(light_list, histtype='step')
    ax.set_xlabel('Light Sensor Readback [mV]')
    ax.set_ylabel('Entries')
    fig.savefig(f'light_sensor_hist_{port}.pdf')
    plt.close(fig)

##end
