##quickly measure the gain and extract peak height for all connected D-Eggs
import threading
import os

from degg_measurements.utils import CALIBRATION_FACTORS
from degg_measurements.daq_scripts.master_scope import initialize_dual
from degg_measurements.daq_scripts.measure_gain_online import min_gain_check
from degg_measurements.daq_scripts.measure_pmt_baseline import min_measure_baseline
from degg_measurements.analysis.gain.analyze_gain import calc_avg_spe_peak_height
from degg_measurements.analysis import calc_baseline
from degg_measurements.analysis.gain.analyze_gain import run_fit as fit_charge_hist

from degg_measurements.timing.setupHelper import overwriteCheck
from degg_measurements.timing.setupHelper import deggContainer
from degg_measurements.timing.setupHelper import makeBatches

E_CONST = 1.60217662e-7

def checkDEggGain(deggsList, overwrite):
    print("Checking D-Egg Gain and Peak Height")
    threads = []
    '''
    for degg in deggsList:
        threads.append(threading.Thread(target=checkGain, args=[degg]))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    '''
    deggBatches = makeBatches(deggsList)
    for batch in deggBatches:
        for degg in deggsList:
            checkGain(degg, overwrite)

def getCurrentPeakHeight(session, channel, gfilename, hvSet, gthreshold, params):
    if channel == 0:
        session = initialize_dual(session, n_samples=128, dac_value=30000,
                              high_voltage0=hvSet, high_voltage1=0,
                              threshold0=gthreshold, threshold1=gthreshold+2000,
                              burn_in=10, modHV=False)
    if channel == 1:
        session = initialize_dual(session, n_samples=128, dac_value=30000,
                              high_voltage0=0, high_voltage1=hvSet,
                              threshold0=gthreshold+2000, threshold1=gthreshold,
                              burn_in=10, modHV=False)
    try:
        session = min_gain_check(session, channel, os.path.basename(gfilename), 128, hvSet, gthreshold, 30000, burn_in=10, nevents=1000)
        add_dict_to_hdf5(params, filename=os.path.basename(gfilename), node_name='parameters')
        fit_info = fit_charge_hist(os.path.basename(gfilename), pmt=None, pmt_id=None, save_fig=False, chargeStamp=False)
        gain = fit_info['popt'][1] / E_CONST
        spe_peak_height = calc_avg_spe_peak_height(
                fit_info['time']*CALIBRATION_FACTORS.fpga_clock_to_s,
                fit_info['waveforms']*CALIBRATION_FACTORS.adc_to_volts,
                fit_info['charges'],
                fit_info['hv'],
                fit_info['popt'][1],
                bl_start=50,
                bl_end=120)
    except:
        print(f'Unable to extract peak height from {gfilename}. Using default')
        spe_peak_height = 0.004

    return spe_peak_height

def checkGain(degg, overwrite):
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
    if not os.path.exists(base_path):
        os.mkdir(base_path)
    with degg.lock:
        m_num = 0
        baseline0 = float(calc_baseline(degg.blFiles[0])['baseline'].values[0])
        baseline1 = float(calc_baseline(degg.blFiles[1])['baseline'].values[0])
        ##re-measure baseline
        bl_file0 = os.path.join(base_path, f'{degg.lowerPMT}_baseline_0_{degg.loop}_{m_num}.hdf5')
        bl_file1 = os.path.join(base_path, f'{degg.upperPMT}_baseline_1_{degg.loop}_{m_num}.hdf5')
        if os.path.isfile(bl_file0):
            overwriteCheck(bl_file0, overwrite)
        if os.path.isfile(bl_file1):
            overwriteCheck(bl_file1, overwrite)
        gfilename0 = os.path.join(base_path, f'{degg.lowerPMT}_chargeStamp_{degg.hvSet0}_{degg.loop}_{m_num}.hdf5')
        gfilename1 = os.path.join(base_path, f'{degg.upperPMT}_chargeStamp_{degg.hvSet1}_{degg.loop}_{m_num}.hdf5')
        if os.path.isfile(gfilename0):
            overwriteCheck(gfilename0, overwrite)
        if os.path.isfile(gfilename1):
            overwriteCheck(gfilename1, overwrite)

        session = degg.session
        session = min_measure_baseline(session, 0, bl_file0, 1024, 30000, 0, nevents=50)
        baseline0 = calc_baseline(bl_file0)['baseline'].values[0]
        session = min_measure_baseline(session, 1, bl_file1, 1024, 30000, 0, nevents=50)
        baseline1 = calc_baseline(bl_file1)['baseline'].values[0]

        gthreshold0 = int(baseline0 + 25)
        gthreshold1 = int(baseline1 + 25)
        params0 = {'filename': os.path.basename(gfilename0), 'degg_temp': -1, 'hv': degg.hvSet0, 'hv_mon': -1, 'hv_mon_pre': -1, 'threshold': gthreshold0, 'baseline':baseline0}
        params1 = {'filename': os.path.basename(gfilename1), 'degg_temp': -1, 'hv': degg.hvSet1, 'hv_mon': -1, 'hv_mon_pre': -1, 'threshold': gthreshold1, 'baseline':baseline1}
        peakHeight0 = getCurrentPeakHeight(session, 0, gfilename0, degg.hvSet0, gthreshold0, params0)
        peakHeight1 = getCurrentPeakHeight(session, 1, gfilename1, degg.hvSet1, gthreshold1, params1)


        degg.peakHeight0 = peakHeight0
        degg.peakHeight1 = peakHeight1
        ###end gain part
        threshold0 = baseline0 + (0.25 * peakHeight0 / CALIBRATION_FACTORS.adc_to_volts)
        threshold1 = baseline1 + (0.25 * peakHeight1 / CALIBRATION_FACTORS.adc_to_volts)
        degg.threshold0 = threshold0
        degg.threshold1 = threshold1

##end
