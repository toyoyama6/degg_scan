from degg_measurements.utils import startIcebootSession
from master_scope import initialize, setup_plot, take_waveform
from master_scope import write_to_hdf5, update_plot, exit_gracefully
from master_scope import add_dict_to_hdf5
import os

def measure(params):
    host = params['host']
    port = params['port']
    hv_ch0 = params['hv_ch0']
    hv_ch1 = params['hv_ch1']
    wf_size = params['wf_size']
    dac_value = params['dac_value']
    ch0_baseline = params['ch0_baseline']
    ch1_baseline = params['ch1_baseline']
    ch0_threshold = params['ch0_threshold']
    ch1_threshold = params['ch1_threshold']
    num_waveforms = params['num_waveforms']
    name = params['name']
    filename = params['filename']

    session = startIcebootSession(host=host, port=port)
    session = initialize_dual(session, n_samples=wf_size, high_voltage0=hv_ch0,
                        high_voltage1=hv_ch1, threshold0=ch0_threshold,
                        threshold1=ch1_threshold, dac_value=dac_value)

    ref_time = time.monotonic()
    for i in range(0, num_waveforms)
        session, xdata, wf, timestamp, pc_time, channel = take_waveform(session)
        write_to_hdf5(filename, i, xdata, wf, timestamp, pc_time-ref_time)
    
    add_dict_to_hdf5(params, params['filename'])
    exit_gracefully(session)

if __name__ == "__main__":

    info_dict = {}

    host = 'localhost'
    port = 5012
    info_dict['host'] = host
    info_dict['port'] = port

    print(f"Running with port: {port}")

    info_dict['hv_ch0'] = 1464
    info_dict['hv_ch1'] = 1374
    info_dict['wf_size'] = 32
    info_dict['dac_value'] = 30000
    info_dict['ch0_baseline'] = 7913
    info_dict['ch1_baseline'] = 8050
    info_dict['ch0_threshold'] = 1000 + info_dict['ch0_baseline']
    info_dict['ch1_threshold'] = 1000 + info_dict['ch1_baseline']
    info_dict['num_waveforms'] = 1000
    info_dict['name'] = "colton" 

    filename = os.path.expandvars(
        f"$HOME/workshop/{name}/dual_channel_{port}.hdf5")
    info_dict['filename'] = filename

    measure(info_dict)

##end
