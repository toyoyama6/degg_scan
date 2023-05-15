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

from degg_measurements.utils.degg_logbook import DEggLogBook
from degg_measurements.utils.database_helper import DatabaseHelper
from degg_measurements.utils.ssh_client import SSHClient

from degg_measurements.analysis import ResultBase

if (sys.version_info.major == 3 and
    sys.version_info.minor < 10):
    from collections import Iterable
else:
    from collections.abc import Iterable


class CameraResult(ResultBase):
    def __init__(self,
                 degg_id,
                 camera_id,
                 run_number=None,
                 logbook=None,
                 meas_site='chiba',
                 meas_stage='fat',
                 remote_path=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.degg_id = degg_id
        self.subdevice_id = camera_id
        if logbook is None:
            raise IOError(f'logbook is None! Must init before calling CameraResult()')
            #self.logbook = DEggLogBook()
        else:
            self.logbook = logbook
        self.meas_site = meas_site
        self.meas_stage = meas_stage
        if run_number is None and meas_stage.lower() is 'fat':
            raise ValueError('run_number is not optional for "fat", '
                             'change the measurement stage or supply '
                             'a run_rumber!')
        self.run_number = run_number
        self._setup_result_dict()

        self.remote_path = remote_path
        self.result_filenames = []
        self.data_jsons = []

    def _setup_result_dict(self):
        '''
        Setup the result_dict with the most basic information.
        The actual test result will be determined later.
        '''
        self.result_dict = dict()
        self.result_dict['device_uid'] = self.degg_id
        self.result_dict['subdevice_uid'] = self.subdevice_id
        self.result_dict['meas_site'] = self.meas_site
        self.result_dict['meas_stage'] = self.meas_stage
        self.result_dict['meas_time'] = self._extract_current_time()

        if self.run_number is not None:
            self.result_dict['run_number'] = self.run_number

    ##there are duplicates from subdevice_id! Do not use
    def _extract_device_id(self):
        pass

    def _add_test_result(self, meas_group, **kwargs):
        if meas_group == 'darknoise':
            self._add_darkrate_result(meas_group, **kwargs)
        elif meas_group == 'focus-and-alignment':
            self._add_pattern_result(meas_group, **kwargs)
        else:
            raise ValueError(f'Invalid meas_group: {meas_group}')

    def _add_darkrate_result(self, meas_group, mean_darknoise, mean_pedestal, darknoise_error,
                             n_hotpixel, mean_99pct, std_99pct, gain, exposure_time,
                             pedestal_hist, noise_hist, temperature):
        add_infos = dict()
        add_infos['meas_name'] = 'camera-darknoise'
        add_infos['meas_class'] = 'derived'
        add_infos['meas_group'] = meas_group

        test_result = dict()
        test_result['data_format'] = 'value'
        test_result['value'] = mean_darknoise
        test_result['error'] = darknoise_error
        test_result['label'] = 'Median Dark Noise'
        test_result['hotpixel_amount'] = n_hotpixel
        test_result['darknoise_mean_99pct'] = mean_99pct
        test_result['darknoise_std_99pct'] = std_99pct
        test_result['label'] = 'Dark noise'
        test_result['temperature'] = temperature

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name'] = 'camera-pedestal-hist'
        add_infos['meas_class'] = 'derived'
        add_infos['meas_group'] = meas_group

        test_result = dict()
        test_result['data_format'] = 'histogram'
        test_result['x-min'] = pedestal_hist[0]
        test_result["x-max"] = pedestal_hist[1]
        test_result["n-bins"] = pedestal_hist[2]
        test_result["y-values"] = pedestal_hist[3].tolist()
        test_result["x-label"] = pedestal_hist[4]
        test_result['temperature'] = temperature

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

        add_infos = dict()
        add_infos['meas_name'] = 'camera-darknoise-hist'
        add_infos['meas_class'] = 'derived'
        add_infos['meas_group'] = meas_group

        test_result = dict()
        test_result['data_format'] = 'histogram'
        test_result['x-min'] = noise_hist[0]
        test_result["x-max"] = noise_hist[1]
        test_result["n-bins"] = noise_hist[2]
        test_result["y-values"] = noise_hist[3].tolist()
        test_result["x-label"] = noise_hist[4]
        test_result['temperature'] = temperature

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_pattern_result(self, meas_group, temperature):
        add_infos = dict()
        add_infos['meas_name'] = 'camera-pattern'
        add_infos['meas_class'] = 'storage'
        add_infos['meas_group'] = meas_group

        test_result = dict()
        test_result['data_format'] = 'arbitrary'
        test_result['label'] = 'Camera Pattern'
        test_result['temperature'] = temperature

        self.result_dict_adds.append(add_infos)
        self.test_results.append(test_result)

    def _add_raw_data(self, meas_group, files):
        add_infos = dict()
        add_infos['meas_name'] = meas_group
        add_infos['meas_class'] = 'storage'

        # This is where charges or charge histograms would go
        meas_data = dict()

        self.supp_files = []
        for file_i in files:
            supp_dict = dict()
            supp_dict['type'] = 'image'
            supp_dict['location'] = 'warehouse'

            dirs = file_i.split('/')

            supp_dict['path'] = os.path.join(
                self.remote_path,
                f'run_{self.run_number:05d}',
                '_'.join(dirs[-3:]))
            supp_dict['local_path'] = file_i
            self.supp_files.append(supp_dict)

        self.test_results.append(meas_data)
        self.result_dict_adds.append(add_infos)
