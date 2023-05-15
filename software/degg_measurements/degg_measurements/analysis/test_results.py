import sys
import json
import click
import logging
import os

import numpy as np

import time
from copy import copy
from glob import glob
from tqdm import tqdm

from abc import ABCMeta, abstractmethod

from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils.database_helper import DatabaseHelper
from degg_measurements.utils.ssh_client import SSHClient
from degg_measurements.analysis.goalpost import Goalpost


if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable

RESULT_REQUIREMENTS = [
    'device_uid',
    'subdevice_uid',
    'meas_class',
    'meas_stage',
    'meas_site',
    'meas_group',
    'meas_name',
    'meas_time',
    'meas_data',
]

MEASUREMENT_GROUPS = [
    'darknoise',
    'gain',
    'charge',
    'timing',
    'linearity',
    'luminosity',
    'sensitivity',
    'transmissivity',
    'monitoring',
    'electronic-response',
    'focus-and-alignment'
]

class ResultBase(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def _add_raw_data(self, meas_group, files, **kwargs):
        pass

    @abstractmethod
    def _extract_device_id(self):
        pass

    @abstractmethod
    def _add_test_result(self, meas_group, **kwargs):
        pass

    def _setup_result_dict(self):
        '''
        Setup the result_dict with the most basic information.
        The actual test result will be determined later.
        '''
        self.result_dict = dict()
        self.result_dict['device_uid'] = self._extract_device_id()
        self.result_dict['subdevice_uid'] = self.subdevice_id
        self.result_dict['meas_site'] = self.meas_site
        self.result_dict['meas_stage'] = self.meas_stage
        self.result_dict['meas_time'] = self._extract_current_time()

        if self.run_number is not None:
            self.result_dict['run_number'] = int(self.run_number)

    def load_json(self, filename):
        with open(filename, 'r') as open_file:
            data = json.load(open_file)
        return data

    def _extract_current_time(self):
        t = time.time()
        return t

    def _check_requirements(self, result_dict):
        passed = True
        for requirement in RESULT_REQUIREMENTS:
            if requirement not in result_dict.keys():
                passed = False
                self.log.warning(f'{requirement} not found in result_dict')
        if not passed:
            print(result_dict)
            raise ValueError('result_dict did not pass requirements!')
        return passed

    def _generate_jsons(self, meas_group, raw_files, **kwargs):
        meas_group = meas_group.lower()
        if meas_group not in MEASUREMENT_GROUPS:
            self.log.warning(f'{meas_group} will not be ' +
                             'accepted by the database!')
        self.result_dict['meas_group'] = meas_group

        if raw_files is not None:
            self.result_dict_adds = []
            self.test_results = []
            self._add_raw_data(meas_group, raw_files)
            data_flag = True
            yield data_flag

        self.result_dict_adds = []
        self.test_results = []
        self._add_test_result(meas_group, **kwargs)
        data_flag = False
        yield data_flag

    def to_json(
            self,
            meas_group,
            raw_files,
            folder_name,
            filename_add=None,
            **kwargs
        ):
        if self.run_number is not None:
            folder_name = os.path.join(folder_name,
                                       f'run_{self.run_number}')
        if not os.path.isdir(folder_name):
            print(f'Creating directory {folder_name}.')
            os.makedirs(folder_name)

        # For some subdevice UIDs it's good to add a prefix
        # to the filename for clarity
        subdevice_type = getattr(self, 'subdevice_type', None)
        filename_prefix = ''
        if subdevice_type == 'mainboard':
            filename_prefix = 'degg-mainboard_'

        basename = filename_prefix + self.subdevice_id + '_' + meas_group
        if filename_add is not None:
            basename += '_' + filename_add
        basename += '.json'

        for data_flag in self._generate_jsons(
                    meas_group, raw_files, **kwargs):
            res_filenames = []
            for i, (result_dict_add, test_result) in enumerate(
                    zip(self.result_dict_adds, self.test_results)):
                result_dict = copy(self.result_dict)
                result_dict.update(result_dict_add)
                if result_dict.get('meas_class', None) is 'derived':
                    result_dict['derived_source'] = self.data_jsons

                if not isinstance(test_result, list):
                    test_result = [test_result]
                result_dict = {**result_dict, 'meas_data': test_result}

                if data_flag:
                    basename_i = basename.replace('.json',
                                                  f'_{i:02d}_data.json')
                    result_dict['support_files'] = self.supp_files
                else:
                    basename_i = basename.replace('.json',
                                                  f'_{i:02d}.json')

                self._check_requirements(result_dict)

                filename_i = os.path.join(folder_name, basename_i)
                with open(filename_i, 'w') as open_file:
                    json.dump(result_dict, open_file, indent=4)
                self.log.info(f'Saved result_dict to {filename_i}!')
                res_filenames.append(os.path.abspath(filename_i))
                if data_flag:
                    self.data_jsons = res_filenames
            self.result_filenames.extend(res_filenames)
        return np.array(self.result_filenames)



class Result(ResultBase):
    def __init__(self,
                 subdevice_id,
                 run_number=None,
                 logbook=None,
                 meas_site='chiba',
                 meas_stage='fat',
                 remote_path=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.input_id = subdevice_id
        self._extract_device_type_from_subdevice_id(subdevice_id)
        if logbook is None:
            self.logbook = DEggLogBook()
        else:
            self.logbook = logbook
        self.meas_site = meas_site
        self.meas_stage = meas_stage
        if run_number is None and meas_stage.lower() is 'fat':
            raise ValueError('run_number is not optional for "fat", '
                             'change the measurement stage or supply '
                             'a run_rumber!')
        self.run_number = str(run_number).zfill(16)
        self._setup_result_dict()

        self.remote_path = remote_path
        self.result_filenames = []
        self.data_jsons = []

    def _extract_device_type_from_subdevice_id(self, subdevice_id):
        if subdevice_id.startswith('SQ') and len(subdevice_id) == 6:
            self.subdevice_type = 'pmt'
        elif subdevice_id.startswith('4A') or subdevice_id.startswith('4.1'):
            self.subdevice_type = 'mainboard'
        else:
            raise NotImplementedError(
                f'Device type extraction is only implemented for PMTs and'
                f'mainboards! Given subdevice ID is {subdevice_id}.'
            )

    def _extract_device_id(self):
        if self.subdevice_type == 'pmt':
            device_id = self.logbook.get_degg_serial_number_from_pmt(
                self.input_id)
            self.subdevice_id = 'degg-pmt_R5912-100-70_' + self.input_id
        elif self.subdevice_type == 'mainboard':
            device_id = self.logbook.get_degg_serial_number_from_mainboard(
                self.input_id
            )
            self.subdevice_id = self.logbook.get_mainboard_serial_number(
                self.input_id
            )
        else:
            raise NotImplementedError(
                f'Device type extraction is only implemented for PMTs and'
                f'mainboards! Given subdevice ID is {subdevice_id}.'
            )
        if device_id is None:
            raise ValueError(f'Could not find a device matching the subdevice '
                             f'{self.subdevice_id}. Check the logbook!')
        # device_id = device_id.replace('_', '-')
        device_id = device_id.replace(' ', '')
        if len(device_id.split('_v')) == 1:
            device_id = device_id + '_v1'
        return device_id

    def _add_test_result(self, meas_group, **kwargs):
        if meas_group == 'linearity':
            self._add_linearity_result(**kwargs)
        elif meas_group == 'darknoise':
            if 'delta_t_hist' in kwargs:
                self._add_delta_t_result(**kwargs)
            else:
                self._add_darkrate_result(**kwargs)
        elif meas_group == 'gain':
            self._add_gain_results(**kwargs)
        elif meas_group == 'timing':
            self._add_mpe_timing_result(**kwargs)
            ##spe is heavy/slow so MPE is easier.
            ##tests show TTS improves from ~2.7 ns to ~2.3 ns
            #self._add_spe_timing_result(**kwargs)
        elif meas_group == 'sensitivity':
            self._add_double_pulse_result(**kwargs)
        elif meas_group == 'monitoring':
            if 'cold_boot' in kwargs:
                self._add_cold_boot_result(**kwargs)
            elif 'constant' in kwargs:
                self._add_constant_monitoring_result(**kwargs)
            else:
                self._add_monitoring_result(**kwargs)
        elif meas_group == 'luminosity':
            self._add_flasher_result(**kwargs)
        elif meas_group == 'charge':
            self._add_laser_visibility_result(**kwargs)
        else:
            raise NotImplementedError(f'option {meas_group} not supported')

    def _add_delta_t_result(self,
                            bins,
                            delta_t_hist,
                            darkrate,
                            temperature,
                            lin_bins):
        add_infos = dict()
        add_infos['meas_name'] = 'pmt-darknoise-delta-t'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'hist'
        if lin_bins:
            test_result['x_min'] = np.min(bins)
            test_result['x_max'] = np.max(bins)
            test_result['x_label'] = 'Delta T / s'
        else:
            test_result['x_min'] = np.min(np.log10(bins))
            test_result['x_max'] = np.max(np.log10(bins))
            test_result['x_label'] = 'log10(Delta T / s)'
        test_result['n_bins'] = len(delta_t_hist)
        test_result['y_values'] = delta_t_hist.tolist()
        test_result['title'] = f'Darkrate: {darkrate:.1f} Hz'
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'

        test_result['goalpost'] = []
        ##-40
        if temperature < -12.:
            goalpost = Goalpost.find_goalpost(
                'darknoise-at-freezing-temp')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())
        ##-20
        elif temperature >= -12. and temperature < 5.:
            goalpost = Goalpost.find_goalpost(
                'darknoise-at-20-freezing-temp')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name'] = 'pmt-darknoise-delta-t-limit'
        add_infos['meas_class'] = 'derived'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'darknoise-at-freezing-temp-red')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_linearity_result(self,
                              ideal_charge,
                              observed_charge,
                              ideal_current,
                              observed_current,
                              used_filters,
                              temperatures,
                              temperature,
                              ratio_at_200pe=None,
                              ratio_at_10mA=None):
        # Add the measurement in terms of charge
        add_infos = dict()
        add_infos['meas_name'] = 'pmt-ideal-charge-vs-observed-charge'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'graph'
        test_result['x_values'] = ideal_charge
        test_result['y_values'] = observed_charge
        #test_result['x_label'] = 'Ideal charge / pC'
        #test_result['y_label'] = 'Observed charge / pC'
        test_result['x_label'] = 'Ideal charge / PE'
        test_result['y_label'] = 'Observed charge / PE'
        test_result['used_filters'] = used_filters
        test_result['temperatures'] = temperatures
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        # Add the measurement in terms of current
        add_infos = dict()
        add_infos['meas_name'] = 'pmt-ideal-current-vs-observed-current'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'graph'
        test_result['x_values'] = ideal_current
        test_result['y_values'] = observed_current
        test_result['x_label'] = 'Ideal current / mA'
        test_result['y_label'] = 'Observed current / mA'
        test_result['used_filters'] = used_filters
        test_result['temperatures'] = temperatures
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        # Add the goalposts
        if ratio_at_200pe is not None:
            add_infos = dict()
            add_infos['meas_name'] = \
                'pmt-observed-charge-over-ideal-charge-at-200pe'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = ratio_at_200pe
            test_result['label'] = 'Charge ratio'
            test_result['temperature'] = temperature
            test_result['type'] = 'digital'

            test_result['goalpost'] = []
            goalpost = Goalpost.find_goalpost(
                'linearity-charge-ratio-at-200pe')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

        if ratio_at_10mA is not None:
            add_infos = dict()
            add_infos['meas_name'] = \
                'pmt-observed-current-over-ideal-current-at-10mA'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = ratio_at_10mA
            test_result['label'] = 'Current ratio'
            test_result['temperature'] = temperature
            test_result['type'] = 'digital'

            test_result['goalpost'] = []
            goalpost = Goalpost.find_goalpost(
                'linearity-current-ratio-at-10mA')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

    def _add_darkrate_result(self, darkrate, darkrate_error,
                             deadtime, temp, pe_threshold,
                             daq_type):
        add_infos = dict()
        add_infos['meas_name'] = 'pmt-darknoise'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = darkrate
        test_result['error'] = darkrate_error
        test_result['deadtime / s'] = deadtime
        test_result['temperature'] = temp
        test_result['pe_threshold'] = pe_threshold
        test_result['label'] = 'Dark rate / Hz'
        test_result['type'] = 'digital'
        if daq_type.lower() not in ['scaler', 'waveform']:
            raise ValueError(
                f'daq_type has to be scaler or waveform '
                f'instead of {daq_type.lower()}.')
        test_result['daq_type'] = daq_type

        test_result['goalpost'] = []
        ##-40
        if temp < -12.:
            goalpost = Goalpost.find_goalpost(
                'darknoise-at-freezing-temp')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())
        ##-20
        elif temp >= -12. and temp < 5.:
            goalpost = Goalpost.find_goalpost(
                'darknoise-at-20-freezing-temp')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name'] = 'pmt-darknoise-limit'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = darkrate
        test_result['error'] = darkrate_error
        test_result['deadtime / s'] = deadtime
        test_result['temperature'] = temp
        test_result['pe_threshold'] = pe_threshold
        test_result['label'] = 'Dark rate / Hz'
        test_result['type'] = 'digital'
        if daq_type.lower() not in ['scaler', 'waveform']:
            raise ValueError(
                f'daq_type has to be scaler or waveform '
                f'instead of {daq_type.lower()}.')
        test_result['daq_type'] = daq_type
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'darknoise-at-freezing-temp-red')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    ##results from measure_dark_temperature
    ##this includes several things:
    ##baseline, gain, peak height, scaler dark rate, charge stamp dark rate
    def _add_monitoring_result(self, times, temperatures, high_voltages, baselines, gains, peak_heights, scaler_rates, charge_stamp_rates):
        add_infos = dict()
        add_infos['meas_name']  = 'monitoring'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'monitoring'
        test_result['start_time'] = int(np.min(times))
        test_result['stop_time']  = int(np.max(times))
        test_result['moni_times'] = times
        monitoring = [{
                        'moni_name': 'Mainboard Temperature',
                        'moni_units': 'Deg. C',
                        'moni_data': temperatures
                      },
                      {
                        'moni_name': 'PMT Baseline',
                        'moni_units': 'ADC',
                        'moni_data': baselines
                      },
                      {
                        'moni_name': 'PMT High Voltage',
                        'moni_units': 'Volts',
                        'moni_data': high_voltages
                      },
                      {
                        'moni_name': 'PMT Gain',
                        'moni_units': ' ',
                        'moni_data': gains
                      },
                      {
                        'moni_name': 'PMT Peak Height',
                        'moni_units': 'ADC',
                        'moni_data': peak_heights
                      },
                      {
                        'moni_name': 'PMT Dark Rate - Scaler',
                        'moni_units': 'Hz',
                        'moni_data': scaler_rates
                      },
                      {
                        'moni_name': 'PMT Dark Rate - Charge Stamp',
                        'moni_units': 'Hz',
                        'moni_data': charge_stamp_rates
                      }
                      ]
        test_result['monitoring'] = monitoring
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_constant_monitoring_result(self, constant, temperature, darkrates, passDR,
                                        pPos, pErr, hvStd):
        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-high-dark-rates'
        add_infos['meas_class'] = 'derived'
        numFails = len(darkrates) - passDR
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = numFails
        test_result['temperature'] = temperature
        test_result['label'] = 'Number of dark rate measurements exceeding upper bound'
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'allowed-high-dark-rate')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-dark-rate-histogram'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'hist'
        test_result['x_min'] = np.min(darkrates)
        test_result['x_max'] = np.max(darkrates)
        test_result['x_label'] = 'Dark Rate [Hz] (FIR)'
        darkrate_bins, bins = np.histogram(darkrates,
                                           np.linspace(np.min(darkrates), np.max(darkrates), 20))
        test_result['n_bins'] = len(darkrate_bins)
        test_result['y_values'] = darkrate_bins.tolist()
        test_result['title'] = f'Ave Dark Rate: {np.mean(darkrates):.1f} Hz'
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-gain-peak-std-warn'
        add_infos['meas_class'] = 'derived'
        gainPeakStd = np.std(pPos)
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = float(gainPeakStd)
        test_result['temperature'] = temperature
        test_result['label'] = 'SPE Fitted Peak Position 1 sigma [pC]'
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'monitoring-spe-peak-pos-std')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-gain-peak-std-limit'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = float(gainPeakStd)
        test_result['temperature'] = temperature
        test_result['label'] = 'SPE Fitted Peak Position 1 sigma [pC]'
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'monitoring-spe-peak-pos-std-red')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-gain-peak-pos-histogram'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'hist'
        test_result['x_min'] = np.min(pPos)
        test_result['x_max'] = np.max(pPos)
        test_result['x_label'] = 'Fitted SPE Peak Position [pC]'
        pPos_bins, bins = np.histogram(pPos, np.linspace(np.min(pPos), np.max(pPos), 20))
        test_result['n_bins'] = len(pPos_bins)
        test_result['y_values'] = pPos_bins.tolist()
        test_result['title'] = f'{np.mean(pPos):.2f} +/- {np.std(pPos):.2f} pC'
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-gain-fit-err-fails'
        add_infos['meas_class'] = 'derived'
        ##if pErr is > 0.15% --> fail
        ##1 fail is allowed throughout all monitoring
        pErr_bound = 0.15 #%
        failMask = pErr > pErr_bound
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = int(np.sum(failMask))
        test_result['temperature'] = temperature
        test_result['label'] = f'Number of Gain PeakErr/PeakPos exceeding upper \
            bound ({pErr_bound}%)'
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'allowed-high-GainPeakError-div-GainPeakPos')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-hv-std-num_failed'
        add_infos['meas_class'] = 'derived'
        _failedhvStd = hvStd > 1.0 ##V
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = int(np.sum(_failedhvStd))
        test_result['temperature'] = temperature
        test_result['label'] = 'HV Readback Std (N=10) Exceeding Tolerance (1V)'
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'large-hv-std-readback')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'monitoring-hv-readback-histogram'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'hist'
        test_result['x_min'] = np.min(hvStd)
        test_result['x_max'] = np.max(hvStd)
        test_result['x_label'] = 'HV Readback Std (N=10) [V]'
        hvStd_bins, bins = np.histogram(hvStd, np.linspace(np.min(hvStd), np.max(hvStd), 20))
        test_result['n_bins'] = len(hvStd_bins)
        test_result['y_values'] = hvStd_bins.tolist()
        test_result['title'] = f' '
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_cold_boot_result(self, cold_boot_retry, cold_boot_result,
                              temperature, cold_boot=True):
        add_infos = dict()
        add_infos['meas_name'] = 'mb-coldboot'
        add_infos['meas_class'] = 'display'

        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = cold_boot_retry
        test_result['coldBootResult'] = cold_boot_result
        test_result['temperature'] = temperature
        # TODO: This could be more specific
        test_result['label'] = 'Retry after Cold Boot'
        test_result['type'] = 'digital'

        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost(
            'communication-test-cold-reboot')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_raw_data(self, meas_group, files):
        add_infos = dict()
        add_infos['meas_name'] = meas_group
        add_infos['meas_class'] = 'storage'

        # This is where charges or charge histograms would go
        meas_data = dict()
        meas_data['data_format'] = 'arbitrary'

        self.supp_files = []
        if isinstance(files, str):
            files = [files]
        for file_i in files:
            supp_dict = dict()
            supp_dict['filetype'] = 'hdf5'
            supp_dict['hostname'] = 'data.icecube.wisc.edu'

            dirs = file_i.split('/')

            supp_dict['pathname'] = os.path.join(
                self.remote_path,
                f'run_{self.run_number}',
                '_'.join(dirs[-3:]))
            supp_dict['local_path'] = file_i
            self.supp_files.append(supp_dict)

        self.test_results.append(meas_data)
        self.result_dict_adds.append(add_infos)

    def _add_gain_results(self, high_voltage, gain,
                          temperature, gain_err=None,
                          high_v_at_1e7_gain=None, peak_height=None):
        if not isinstance(high_voltage, Iterable) and not \
                isinstance(gain, Iterable):
            add_infos = dict()
            add_infos['meas_name'] = 'pmt-gain-at-specific-hv'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = gain
            test_result['high_voltage'] = high_voltage
            test_result['peak_height'] = peak_height
            test_result['temperature'] = temperature
            test_result['label'] = 'Gain'
            test_result['type'] = 'digital'

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)
        else:
            add_infos = dict()
            add_infos['meas_name'] = 'pmt-gain-vs-hv'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'graph'
            test_result['x_values'] = high_voltage
            test_result['y_values'] = gain
            test_result['temperature'] = np.mean(temperature)
            test_result['y_errors'] = gain_err
            test_result['x_label'] = 'High voltage / V'
            test_result['y_label'] = 'Gain'
            test_result['type'] = 'digital'

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

        if high_v_at_1e7_gain is not None:
            add_infos = dict()
            add_infos['meas_name'] = 'pmt-hv-at-1e7-gain'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = high_v_at_1e7_gain
            test_result['temperature'] = np.mean(temperature)
            test_result['gain'] = 1e7
            test_result['label'] = 'High voltage / V'
            test_result['peak_height'] = peak_height
            test_result['type'] = 'digital'

            test_result['goalpost'] = []
            goalpost = Goalpost.find_goalpost('hv-at-1e7-gain')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

    def _add_mpe_timing_result(self,
                               efficiency,
                               norm,
                               peak,
                               tts,
                               ttData,
                               ttBins,
                               plotC,
                               fitVals,
                               funcStr,
                               chi2,
                               temperature=None):
        add_infos = dict()
        add_infos['meas_name'] = 'pmt-timing-resolution'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = tts
        test_result['label'] = 'Fit Width / ns'
        test_result['efficiency'] = efficiency
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('pmt-timing-resolution')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)


        add_infos = dict()
        add_infos['meas_name'] = 'pmt-timing-resolution-info'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'hist-with-fit'
        test_result['x_min'] = np.min(ttBins)
        test_result['x_max'] = np.max(ttBins)
        test_result['x_label'] = 'PMT Time - Tabletop Time / ns'
        hist, edges = np.histogram(ttData*1e9, bins=ttBins)
        test_result['y_values'] = hist.tolist()
        test_result['n_bins'] = len(hist)
        test_result['fit_x_min'] = np.min(plotC)
        test_result['fit_x_max'] = np.max(plotC)
        test_result['fit_y_values'] = fitVals.tolist()
        test_result['fit_n_bins'] = len(fitVals)
        test_result['fit_function'] = funcStr
        test_result['fit_params'] = [norm, peak, tts]
        test_result['title'] = f'PMT Timing Test - Fit Width: {tts:.2f} ns'
        test_result['type'] = 'digital'
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name'] = 'pmt-timing-resolution-chi2'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = chi2
        test_result['label'] = 'Fit Chi2'
        test_result['temperature'] = temperature
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('pmt-timing-resolution-chi2')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_double_pulse_result(self,
                                 average_peak_separation,
                                 average_peak_to_valley1,
                                 average_peak_to_valley2,
                                 ndFilter,
                                 burstFrequency,
                                 aveT,
                                 aveV,
                                 temperature=None):
        ##make the goalpost relevant file
        add_infos = dict()
        add_infos['meas_name']  = 'double-pulse-separation'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = average_peak_separation
        test_result['label'] = 'Average peak separation / ns'
        test_result['ndFilter'] = ndFilter
        test_result['laserFrequency'] = burstFrequency
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')

        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('double-pulse-separation')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        ##make the goalpost relevant file
        add_infos = dict()
        add_infos['meas_name']  = 'double-pulse-peak-to-valley1'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = average_peak_to_valley1[0]
        test_result['error1sig'] = average_peak_to_valley1[1]
        test_result['label'] = 'Average peak to valley - Peak 1'
        test_result['ndFilter'] = ndFilter
        test_result['laserFrequency'] = burstFrequency
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('double-pulse-peak-to-valley1')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        ##make the goalpost relevant file
        add_infos = dict()
        add_infos['meas_name']  = 'double-pulse-peak-to-valley2'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = average_peak_to_valley2[0]
        test_result['error1sig'] = average_peak_to_valley2[1]
        test_result['label'] = 'Average peak to valley - Peak 2'
        test_result['ndFilter'] = ndFilter
        test_result['laserFrequency'] = burstFrequency
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')
        test_result['type'] = 'digital'
        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('double-pulse-peak-to-valley2')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())
        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        ##make the display file
        add_infos = dict()
        add_infos['meas_name'] = 'double-pulse-info'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'graph'
        test_result['x_values'] = aveT.tolist()
        test_result['y_values'] = aveV.tolist()
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')

        test_result['x_label'] = 'Time / ns'
        test_result['y_label'] = 'Amplitude / mV'
        test_result['title'] = f'Ave separation: {average_peak_separation:.2f} ns'
        test_result['type'] = 'digital'

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)


    def _add_laser_visibility_result(self, high_voltage, high_v_at_1e7_gain, temperature, c_npes, npe_width,
                                     npeData, npeBins, plotC, fitVals, funcStr,
                                     norm, peak, width):
        if high_v_at_1e7_gain == -1 or high_v_at_1e7_gain == 1500:
            add_infos = dict()
            add_infos['meas_name'] = 'laser-visibility-npe-width-pre-calibration'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = npe_width
            test_result['npe'] = c_npes
            test_result['hv1e7gain'] = -1
            test_result['temperature'] = np.mean(temperature)
            test_result['label'] = 'Width of Fitted NPE @ Max Laser Intensity'
            test_result['type'] = 'digital'

            test_result['goalpost'] = []
            goalpost = Goalpost.find_goalpost('average-laser-output-range')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

        elif high_v_at_1e7_gain >= 1000:
            add_infos = dict()
            add_infos['meas_name'] = 'laser-visibility-npe-width'
            add_infos['meas_class'] = 'derived'

            test_result = dict()
            test_result['data_format'] = 'value'
            test_result['value'] = npe_width
            test_result['npe'] = c_npes
            test_result['hv1e7gain'] = high_v_at_1e7_gain
            test_result['temperature'] = np.mean(temperature)
            test_result['label'] = 'Width of Fitted NPE @ Max Laser Intensity'
            test_result['type'] = 'digital'

            test_result['goalpost'] = []
            goalpost = Goalpost.find_goalpost('average-laser-output-range')
            test_result['goalpost'].append(goalpost.get_goalpost_dict())

            self.result_dict_adds.append(add_infos)
            self.test_results.append(test_result)

        else:
            raise ValueError(f'HV of {high_v_at_1e7_gain} seems to be invalid!')

        test_result = dict()
        test_result['data_format'] = 'hist-with-fit'
        test_result['x_min'] = np.min(npeBins)
        test_result['x_max'] = np.max(npeBins)
        test_result['x_label'] = 'Observed NPE'
        hist, edges = np.histogram(npeData, bins=npeBins)
        test_result['y_values'] = hist.tolist()
        test_result['n_bins'] = len(hist)
        test_result['fit_x_min'] = np.min(plotC)
        test_result['fit_x_max'] = np.max(plotC)
        test_result['fit_y_values'] = fitVals.tolist()
        test_result['fit_n_bins'] = len(fitVals)
        test_result['fit_function'] = funcStr
        test_result['fit_params'] = [norm, peak, width]
        test_result['title'] = f'PMT Laser Visiblity Test'
        test_result['type'] = 'digital'
        if temperature is not None:
            test_result['temperature'] = temperature
        else:
            raise ValueError(
                'Temperature needs to be supplied for the json file.')

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_flasher_result(
                        self,
                        ledmask,
                        ledbias,
                        maxcharge,
                        numPass,
                        xvals,
                        yvals,
                        temperature):
        add_infos = dict()
        add_infos['meas_name']  = 'led-flasher-functionality'
        add_infos['meas_class'] = 'derived'

        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = int(numPass)
        test_result['label'] = f'Num. LEDs Exceeding Minimum Light Production Measured by PMT'
        test_result['type'] = 'digital'
        test_result['temperature'] = float(temperature)

        test_result['goalpost'] = []
        goalpost = Goalpost.find_goalpost('number-of-flasher-leds-working')
        test_result['goalpost'].append(goalpost.get_goalpost_dict())

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name']  = 'led-flasher-plot'
        add_infos['meas_class'] = 'derived'
        test_result = dict()
        test_result['data_format'] = 'shared-x-multi-graph'
        test_result['x_label'] = 'LED Bias'
        test_result['y_label'] = 'Relative Intensity'
        test_result['temperature'] = float(temperature)
        test_result['title'] = ' '
        test_result['x_values'] = xvals.tolist()
        yValsList = []
        for _led, _y in zip(ledmask, yvals):
            _new_y = []
            for __y in _y:
                _new_y.append(float(__y))

            _dict = {'label': f'{_led}',
                    'values': _new_y}
                    #'values': _y}
            yValsList.append(_dict)
        test_result['y_data'] = yValsList

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        ## for future cases with more granularity?
        # for i in range(len(maxChargeList)):
        #     test_result = dict()
        #     test_result['data_format'] = 'value'
        #     test_result['value'] = maxChargeList[i]
        #     test_result['label'] = f'LED {fixedledmask[i]} Max Charge / pC'
        #     test_result['type'] = 'digital'

        #     test_result['goalpost'] = []
        #     goalpost = Goalpost.find_goalpost('led-flasher-functionality')
        #     test_result['goalpost'].append(goalpost.get_goalpost_dict())

        #     self.result_dict_adds.append(add_infos)
        #     self.test_results.append(test_result)


    # I believe this code should now be retired and this is supposed to be
    # handled by the RunHandler
    def to_database(self, dry_run=False):
        '''Uses the 'result_filenames' from 'to_json'
        and inserts these files into the database
        via the DatabaseHelper.
        '''
        dbh = DatabaseHelper()
        for result_filename in self.result_filenames:
            dbh.mongo_insert(result_filename, dry_run)


class RunHandler(object):
    '''
    This class can be used to move data to the data warehouse,
    insert raw data from measurements, and then finally insert
    the derived measurements and link them to the raw data.
    '''
    def __init__(self, run_number=None, filenames=None,
                 base_path='database_jsons'):
        if run_number is None and filenames is None:
            raise ValueError(
                'Please supply either a run_number or '
                'a list of filenames.'
            )
        elif run_number is not None and filenames is not None:
            raise ValueError(
                'Please only supply either a run_number or '
                'a list of filenames, not both!'
            )
        elif run_number is not None:
            if run_number is not 'goalposts':
                self.run_number = str(run_number).zfill(16)
                self.file_names = self.find_filenames(os.path.join(
                    os.path.abspath(base_path),
                    f'run_{self.run_number}'))
            else:
                self.file_names = self.find_filenames(os.path.join(
                    os.path.abspath(base_path),
                    run_number))
        elif filenames is not None:
            if not isinstance(filenames, np.ndarray):
                raise TypeError(
                    f'filenames must be a np.array of strings'
                    f'instead of {type(filenames)}.'
                )
            else:
                self.file_names = filenames

        self.files = self.load_jsons(self.file_names)
        self.dbh = DatabaseHelper()
        self.ssh_client = SSHClient(hostname='data',
                                    username='mmeier')

    def find_filenames(self, path):
        files = glob(os.path.join(path, '*.json'))
        return np.array(files)

    def load_jsons(self, file_names):
        files = []
        for file_name in file_names:
            with open(file_name, 'r') as open_file:
                try:
                    data = json.load(open_file)
                except json.decoder.JSONDecodeError:
                    print(f'JSONDecodeError in {file_name}.')
                    raise
            files.append(data)
        return np.array(files)

    def write_json(self, file_name, data):
        with open(file_name, 'w') as open_file:
            json.dump(data, open_file, indent=4)

    def organize_files_by_key(self, key):
        vals = np.array([file_i[key] for file_i in self.files])
        u_vals, indices = np.unique(vals, return_inverse=True)
        return u_vals, indices

    def submit_based_on_meas_class(self):
        '''
        1. Submit everything categorized as "display"
        2. Check all derived measurements and submit their
           derived_from jsons -> replace derived_from json
           path with object id
        3. Submit all the derived measurements
        4. Gather all files that need to be copied to the warehouse
        5. Ship a tarball
        '''
        files_to_transfer = []
        local_files = []
        print(self.files, len(self.files))
        for file_i in self.files:
            supp_files = file_i.get('support_files', None)
            if supp_files is not None:
                for supp_file in supp_files:
                    path = supp_file.get('pathname', None)
                    local_path = supp_file.get('local_path', None)
                    if path is not None:
                        files_to_transfer.append(path)
                        local_files.append(local_path)

        # Identify remote dirnames
        remote_dirnames = [os.path.dirname(fname) for fname in files_to_transfer]
        u_dirnames = np.unique(remote_dirnames)
        if len(u_dirnames) > 1:
            raise ValueError('There should only be one remote dirname. Instead '
                             f'unique remote_dirnames are {u_dirnames}!')
        # Create the remote dir
        self.ssh_client.run_cmd(f'mkdir -p "{u_dirnames[0]}"')

        for remote_file, local_file in tqdm(
                zip(files_to_transfer, local_files),
                desc='Copying files'):
            try:
                self.ssh_client.send_file(local_file, remote_file)
            except ValueError as err:
                if (err.__str__() ==
                        'Remote file already exists (use "force" to override)'):

                    print('Remote file already exists! Skipping it.')
                    pass
                else:
                    raise

        u_vals, indices = self.organize_files_by_key(key='meas_class')
        print(u_vals)

        if 'display' in u_vals:
            u_idx = np.where(u_vals == 'display')[0][0]
            mask = indices == u_idx
            self.to_database(self.file_names[mask])

        if 'derived' in u_vals:
            print('In derived')
            u_idx = np.where(u_vals == 'derived')[0][0]
            mask = indices == u_idx

            derived_sources = []
            for derived_i in self.files[mask]:
                derived_sources.extend(derived_i['derived_source'])
            unique_sources = np.unique(derived_sources)
            unique_sources = list(map(os.path.abspath, unique_sources))
            unique_sources = [unique_source
                              for unique_source in unique_sources
                              if os.path.isfile(unique_source)]
            print(unique_sources)
            obj_ids = self.to_database(unique_sources)
            path_to_obj_id = dict(zip(unique_sources, obj_ids))
            print(obj_ids)

            for der_file, der_filename in zip(
                    self.files[mask], self.file_names[mask]):
                der_file['derived_source'] = \
                    [str(path_to_obj_id[der_source_i])
                     if os.path.isfile(der_source_i)
                     else der_source_i
                     for der_source_i in der_file['derived_source']]
                self.write_json(der_filename, der_file)

            self.to_database(self.file_names[mask])

    def to_database(self, file_names, dry_run=False):
        obj_id = self.dbh.mongo_insert(file_names, dry_run)
        return obj_id

