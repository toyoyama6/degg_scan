import sys
import numpy as np

from degg_measurements.utils import load_degg_dict
from degg_measurements.utils import CALIBRATION_FACTORS

if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable


class DEggCal:
    def __init__(self, degg_file, key, gain_reference='latest'):
        self.degg_file = degg_file
        self.key = key
        self.degg_dict = load_degg_dict(degg_file)
        self._setup_pmt_cals(gain_reference)

    def _setup_pmt_cals(self, gain_reference):
        self.pmt_cals = []
        for channel, pmt in enumerate(['LowerPmt', 'UpperPmt']):
            hv = self.degg_dict[pmt]['HV1e7Gain']
            if hv < 0:
                hv = 0
            try:
                spe_peak_height = self.degg_dict[pmt]['SPEPeakHeight']
            except KeyError:
                spe_peak_height = np.nan
            gain_key = self._determine_gain_key(gain_reference, pmt)
            try:
                gain_fit_params = [
                    self.degg_dict[pmt][gain_key]['GainFitNorm'],
                    self.degg_dict[pmt][gain_key]['GainFitExp']
                ]
            except KeyError:
                gain_fit_params = [
                    np.nan,
                    np.nan
                ]
            pmt_cal = PMTCal(
                hv,
                gain_fit_params,
                spe_peak_height,
                baseline=None)
            self.pmt_cals.append(pmt_cal)

    def _determine_gain_key(self, gain_reference, pmt):
        data_key = 'GainMeasurement'
        if gain_reference == 'latest':
            eligible_keys = [key for key in self.degg_dict[pmt].keys()
                             if key.startswith(data_key)]
            cts = [int(key.split('_')[1]) for key in eligible_keys]
            if len(cts) == 0:
                print(f'No measurement found for '
                      f'{self.degg_dict[pmt]["SerialNumber"]} '
                      f'in DEgg {self.degg_dict["DEggSerialNumber"]}. '
                      f'Skipping it!')
            measurement_number = np.max(cts)
        else:
            measurement_number = gain_reference

        suffix = f'_{int(measurement_number):02d}'
        data_key_to_use = data_key + suffix
        return data_key_to_use

    def get_pmt_cal(self, channel):
        if channel not in [0, 1]:
            raise ValueError('Channel can only be 0 or 1.')
        return self.pmt_cals[channel]


class GainFitParams:
    def __init__(self, norm, exponent):
        self._norm = norm
        self._exponent = exponent

    @property
    def norm(self):
        return self._norm

    @property
    def exponent(self):
        return self._exponent

    def __iter__(self):
        return iter((self._norm, self._exponent))

    def __str__(self):
        return (f'{self.__class__.__name__}(Norm={self._norm}, '
                f'Exponent={self._exponent})')


class PMTCal:
    def __init__(self,
                 hv=None,
                 gain_fit_params=None,
                 spe_peak_height=None,
                 baseline=None):
        self.adc_to_volts = CALIBRATION_FACTORS.adc_to_volts
        if hv is not None:
            self._set_hv(hv)
        else:
            self._hv = hv
        if gain_fit_params is not None:
            self._set_gain_fit_params(gain_fit_params)
        else:
            self._gain_fit_params = gain_fit_params
        if spe_peak_height is not None:
            self._set_spe_peak_height(spe_peak_height)
        else:
            self._spe_peak_height = spe_peak_height
        if baseline is not None:
            self._set_baseline(baseline)
        else:
            self._baseline = baseline

    def _get_hv(self):
        return self._hv

    def _set_hv(self, hv):
        hv_min = 0
        hv_max = 2000
        if hv < hv_min or hv > hv_max:
            raise ValueError(
                f'hv can not be set to {hv}, it has to be between '
                f'{hv_min} and {hv_max}!')
        self._hv = int(hv)

    hv = property(_get_hv, _set_hv)

    def _set_gain_fit_params(self, gain_fit_params):
        if isinstance(gain_fit_params, GainFitParams):
            self._gain_fit_params = gain_fit_params
        elif isinstance(gain_fit_params, Iterable):
            self._gain_fit_params = GainFitParams(*gain_fit_params)

    def _get_gain_fit_params(self):
        return self._gain_fit_params

    gain_fit_params = property(_get_gain_fit_params,
                               _set_gain_fit_params)

    def _set_spe_peak_height(self, spe_peak_height):
        if spe_peak_height < 0:
            raise ValueError(f'spe_peak_height has to be positive, '
                             f'but is {spe_peak_height}!')
        self._spe_peak_height = spe_peak_height

    def _get_spe_peak_height(self):
        return self._spe_peak_height

    spe_peak_height = property(_get_spe_peak_height,
                               _set_spe_peak_height)

    def _set_baseline(self, baseline):
        min_baseline = 0
        max_baseline = 16000
        if baseline < min_baseline or baseline > max_baseline:
            raise ValueError(
                f'Baseline can not be set to {baseline}, it has to be between '
                f'{min_baseline} and {max_baseline}!')
        self._baseline = int(baseline)

    def _get_baseline(self):
        return self._baseline

    baseline = property(_get_baseline, _set_baseline)

    def threshold_in_adc(self, threshold_in_pe):
        if self._spe_peak_height is None:
            raise ValueError(
                f'Threshold can not be calculated before setting '
                f'the SPE peak height.')
        return np.ceil(self._spe_peak_height * threshold_in_pe /
                       self.adc_to_volts)

    def __str__(self):
        string = (f'{self.__class__.__name__}:(HV={self._hv}, ' +
                  f'{self._gain_fit_params}, ' +
                  f'SPEPeakHeight={self._spe_peak_height}, ' +
                  f'Baseline={self._baseline})')
        return string

