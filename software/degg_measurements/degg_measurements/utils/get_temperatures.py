from degg_measurements.monitoring import readout_sensor
from degg_measurements.utils import startIcebootSession
import numpy as np

ports = np.arange(5000, 5016)
print('Measuring Temperatures for all Ports!')

temperatures = [0] * len(ports)
for i, port in enumerate(ports):
    try:
        session = startIcebootSession(host='localhost', port=port)
    except:
        session = None
        print(f'Unable to create session on {port}...')
        continue

    if session is not None:
        temp = readout_sensor(session, 'temperature_sensor')
        temperatures[i] = temp
        print(f'{ports[i]}: {temp} C')
        session.endStream()
        session.close()
        del session

print(f'Average: {np.mean(temperatures)}')

##end
