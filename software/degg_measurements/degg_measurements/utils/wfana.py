import sys
import os.path
import numpy as np
from scipy import integrate, interpolate
import tqdm
from degg_measurements.utils import CALIBRATION_FACTORS

if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable


def get_charges(waveforms,
                gate_start,
                gate_width,
                baseline,
                return_pulse_height=False):
    '''
    Parameters
    ----------
    waveforms : np.array shape: (n_waveforms, n_bins)
        Waveforms in volts to perform the charge calculation for.
    gate_start : int
        Bin number determining the beginning of the integration window.
    gate_width : int
        Width of the integration window in units of bins.
    baseline : np.array or float
        Baseline in volts to subtract from the waveforms.
        Can be either a float or an array of individual values for
        each waveform.
    return_pulse_height : bool
        Whether this function returns the pulse_height of each waveform
        in addition to the charges.

    Returns
    -------
    charge : np.array shape: (len(waveforms),)
        Charges in units of pico coulomb
    pulse_height : np.array shape: (len(waveforms),)
        Pulse heights in units of volts
    '''
    resistance = CALIBRATION_FACTORS.front_end_impedance_in_ohm
    bin_width = CALIBRATION_FACTORS.fpga_clock_to_s
    coulomb_to_pico_coulomb = 1e12

    if isinstance(baseline, Iterable):
        waveforms -= baseline[:, np.newaxis]
    else:
        waveforms -= baseline

    gate_end = gate_start + gate_width + 1
    area = np.sum(waveforms[:, gate_start:gate_end], axis=1) * bin_width
    charge = area / resistance * coulomb_to_pico_coulomb
    if not return_pulse_height:
        return charge
    else:
        pulse_height = np.max(waveforms, axis=1)
        return charge, pulse_height


def calc_charge(times, volts, index_start, index_stop, return_pulse_height=False):
    """
    Returns charge [pC] of a given waveform
    Args:
      times, volts, start index to integrate, end index to integrate
    """

    resistance = 36.96 #50.0
    area = 0

    times_mod = times[index_start:index_stop+1]
    volts_mod = volts[index_start:index_stop+1]

    area = integrate.simps(volts_mod, times_mod)
    charge = area/resistance*1e12

    if not return_pulse_height:
        return charge
    else:
        pulse_height = np.min(volts_mod) - np.median(volts_mod)
        return charge, pulse_height


def get_charges_old(times_, waveforms, gate_start, gate_width,
                    pede_gate_start, pede_gate_width, baseline,
                    return_pulse_height=False):
    """
    Returns charges [pC] at the given position
    Args:
     path to the wf directory
    """
    print(
        'This function is deprecated, use the new implementation instead.')
    # obtained charges will be filled into this array
    res_charges = np.array([])
    pulse_heights = np.array([])

    # loop over 10000 waveforms (or less)
    for iev in range(waveforms.shape[0]):
        # read data file
        times, volts = times_[iev], waveforms[iev]
        if not isinstance(baseline, Iterable):
            volts -= baseline
        else:
            volts -= baseline[iev]

        start_bin = len(times[times - gate_start <= 0]) - 1
        stop_bin = len(times[times - (gate_start+gate_width) < 0])
        ped_start_bin = len(times[times - pede_gate_start <= 0]) - 1
        ped_stop_bin = len(times[times - (pede_gate_start+pede_gate_width) < 0])

        interpf = interpolate.interp1d(times, volts)
        volts[start_bin] = interpf(gate_start)
        volts[stop_bin] = interpf(gate_start+gate_width)
        volts[ped_start_bin] = interpf(pede_gate_start)
        volts[ped_stop_bin] = interpf(pede_gate_start+pede_gate_width)
        times[start_bin] = gate_start
        times[stop_bin] = gate_start + gate_width
        times[ped_start_bin] = pede_gate_start
        times[ped_stop_bin] = pede_gate_start + pede_gate_width

        # calculate charge
        if not return_pulse_height:
            raw_charge = calc_charge(times, volts, start_bin, stop_bin)

        else:
            raw_charge, pulse_height = calc_charge(times, volts, start_bin,
                                                   stop_bin, return_pulse_heights=True)
            pulse_heights = np.append(pulse_heights, pulse_height)

        # calculate pedestal
        pedestal = calc_charge(times, volts, ped_start_bin, ped_stop_bin)

        # rescale pedestal if signal and pedestal integration
        # windows are different
        if gate_width != pede_gate_width:
            pedestal = pedestal / pede_gate_width * gate_width

        # pedestal subtraction
        charge = 1*(raw_charge - pedestal)

        # append a result to the existing array
        res_charges = np.append(res_charges, charge)

    if not return_pulse_height:
        return res_charges
    else:
        return res_charges, pulse_heights


def get_spe_avg_waveform(times, waveforms,
                         charges, spe_charge,
                         allowed_peak_time_offset=1e-7):

    mask = np.logical_and(charges >= 0.8 * spe_charge,
                          charges <= 1.2 * spe_charge)

    filtered_waveforms = waveforms[mask]
    filtered_charges = charges[mask]
    peak_times = times[0][np.argmax(filtered_waveforms, axis=1)]
    median_peak_time = np.median(peak_times)

    mask = np.logical_and(
        peak_times > median_peak_time - allowed_peak_time_offset,
        peak_times < median_peak_time + allowed_peak_time_offset)

    avg_times = times[0]
    avg_waveform = np.mean(filtered_waveforms[mask], axis=0)
    spe_charges = filtered_charges[mask]
    return avg_times, avg_waveform, spe_charges


def get_highest_density_region_charge(waveforms,
                                      time_binsize,
                                      n_bins,
                                      baseline):
    cumsum = np.cumsum(np.insert(waveforms, 0, 0, axis=1), axis=1)
    ints = (cumsum[:, n_bins:] - cumsum[:, :-n_bins])
    ints -= (baseline * n_bins)
    ints *= time_binsize

    #ints_ = np.zeros((waveforms.shape[0], waveforms.shape[1]-n_bins))
    #for i in range(waveforms.shape[1]-n_bins):
    #    ints_[:, i] = np.sum(waveforms[:, i:i+n_bins], axis=1) * time_binsize

    # This should also do the trick, but I guess its slower
    # ints = np.convolve(waveforms, np.ones(n_bins), mode='valid') * time_binsize

    # Divide by resistance to convert to Coulomb.
    resistance = 36.96 #50
    charges = ints / resistance * 1e12
    return np.max(charges, axis=1)


