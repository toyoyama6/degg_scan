import weakref
import json
import os
import click
from datetime import datetime

#########################################################
###NOTE:
####Do not remove any Goalposts
###Add new goal pots and run with --submit after testing
#########################################################

class Goalpost():
    _goalposts = set()

    def __init__(self,
                 testname,
                 testtype,
                 testbounds,
                 valid_date):
        self.testname = testname
        self.testtype = testtype
        self.testbounds = testbounds
        self.valid_date = valid_date
        self._goalposts.add(weakref.ref(self))

    @classmethod
    def get_instances(cls):
        dead = set()
        for ref in cls._goalposts:
            obj = ref()
            if obj is not None:
                yield obj
            else:
                dead.add(ref)
        cls._goalposts -= dead

    @classmethod
    def find_goalpost(cls, substring):
        '''
        Find goalpost instances based on a substring in the testname.
        '''
        found_gps = []
        for gp in cls.get_instances():
            if substring in gp.testname:
                found_gps.append(gp)
        if len(found_gps) == 0:
            raise ValueError(
                f'No matching goalpost found for substring "{substring}"!'
            )
        elif len(found_gps) == 1:
            return found_gps[0]
        else:
            ##this should help with partial string matches
            ##since generally some of the goalposts are
            ##goalpost-1 & goalpost-1-red
            for _i, _found_gps in enumerate(found_gps):
                if 'red' in _found_gps.testname:
                    found_gps.pop(_i)
                elif 'chi2' in _found_gps.testname:
                    found_gps.pop(_i)
            if len(found_gps) == 1:
                return found_gps[0]
            raise ValueError(
                f'Found multiple goalposts for substring "{substring}"! '
                f'This substring matches with \n {found_gps}.'
                f'Make your search string more specific to avoid confusion.'
            )

    def __str__(self):
        s = (f'{self.__class__.__name__}:\n' +
             f'\t   testname: {self.testname}\n' +
             f'\t   testtype: {self.testtype}\n' +
             f'\t testbounds: {self.testbounds}\n' +
             f'\t valid_date: {self.valid_date}\n'
            )
        return s

    def __repr__(self):
        return self.__str__()

    def to_json(self, filename):
        goalpost_dict = dict()
        goalpost_dict['goalpost_testname'] = self.testname
        goalpost_dict['goalpost_testtype'] = self.testtype
        goalpost_dict['goalpost_testbounds'] = self.testbounds
        goalpost_dict['valid_date'] = self.valid_date

        if os.path.exists(filename):
            # Try to find the next available filename
            inc_num = 1
            while os.path.exists(filename):
                with open(filename, 'r') as open_file:
                    old_json_filename = filename
                    old_json = json.load(open_file)
                if inc_num == 1:
                    filename = filename.replace('.json', '_v1.json')
                else:
                    filename = filename.replace(
                        f'_v{inc_num-1}.json',
                        f'_v{inc_num}.json'
                    )
                inc_num += 1

            if goalpost_dict == old_json:
                # Found an old json containing the same information
                # Will not write a new file
                print(f'Found an old file containig the same information: {old_json_filename}')
                return

        with open(filename, 'w') as open_file:
            json.dump(goalpost_dict, open_file, indent=4)

    def get_goalpost_dict(self):
        goalpost_dict = dict()
        goalpost_dict['testname'] = self.testname
        goalpost_dict['testtype'] = self.testtype
        return goalpost_dict


gain_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_hv-at-1e7-gain',
    testtype='in-range',
    testbounds=[1000, 2000],
    valid_date='2021-01-01')

darknoise_m20_goalpost_yellow = Goalpost(
    testname='degg_pmt_R5912-100-70_average-darknoise-at-freezing-temp',
    testtype='max',
    testbounds=2600,
    valid_date='2023-01-16')

darknoise_m20_goalpost_red = Goalpost(
    testname='degg_pmt_R5912-100-70_average-darknoise-at-freezing-temp-red',
    testtype='max',
    testbounds=4000,
    valid_date='2023-01-16')

darknoise_m20_goalpost_yellow_mid = Goalpost(
    testname='degg_pmt_R5912-100-70_average-darknoise-at-20-freezing-temp',
    testtype='max',
    testbounds=3000,
    valid_date='2023-01-16')

laser_visibility_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_average-laser-output-range',
    testtype='max',
    testbounds=20,
    valid_date='2021-01-01')

linearity_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_linearity-charge-ratio-at-200pe',
    testtype='min',
    testbounds=0.6,
    valid_date='2021-01-01')

linearity_current_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_linearity-current-ratio-at-10mA',
    testtype='min',
    testbounds=0.6,
    valid_date='2021-01-01')

spe_time_resolution_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_spe-time-resolution',
    testtype='max',
    testbounds=5.,
    valid_date='2021-01-01')

pmt_timing_resolution_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_pmt-timing-resolution',
    testtype='max',
    testbounds=3.5,
    valid_date='2022-05-09')

pmt_timing_resolution_chi2_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_pmt-timing-resolution-chi2',
    testtype='max',
    testbounds=3.6,
    valid_date='2023-01-31')

double_pulse_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_double-pulse-separation',
    testtype='in-range',
    testbounds=[18, 22],
    valid_date='2021-01-01')

double_pulse_ptv1_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_double-pulse-peak-to-valley1',
    testtype='in-range',
    testbounds=[1.5, 2.0],
    valid_date='2022-09-28')

double_pulse_ptv2_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_double-pulse-peak-to-valley2',
    testtype='in-range',
    testbounds=[1.75, 2.8],
    valid_date='2023-01-16')

flasher_ring_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_number-of-flasher-leds-working',
    testtype='equals',
    testbounds=12,
    valid_date='2021-01-01')

constant_monitoring_dark_rate = Goalpost(
    testname='degg_pmt_R5912-100-70_allowed-high-dark-rate',
    testtype='max',
    testbounds=3,
    valid_date='2023-01-12'
)

constant_monitoring_gain_peak_pos = Goalpost(
    testname='degg_pmt_R5912-100-70_allowed-high-GainPeakError-div-GainPeakPos',
    testtype='max',
    testbounds=2,
    valid_date='2023-01-12'
)

##A value of ~1% --> 0.015
##but typically we see 0.03
##set around 0.05 to find outliers
constant_monitoring_gain_peak_std_yellow = Goalpost(
    testname='degg_pmt_R5912-100-70_monitoring-spe-peak-pos-std',
    testtype='max',
    testbounds=0.055,
    valid_date='2023-01-12'
)

constant_monitoring_gain_peak_std_red = Goalpost(
    testname='degg_pmt_R5912-100-70_monitoring-spe-peak-pos-std-red',
    testtype='max',
    testbounds=0.1,
    valid_date='2023-01-30'
)

constant_monitoring_hv_std_readback = Goalpost(
    testname='degg_pmt_R5912-100-70_large-hv-std-readback',
    testtype='max',
    testbounds=1,
    valid_date='2023-01-12'
)

cold_reboot_goalpost = Goalpost(
    testname='degg_mainboard_communication-test-cold-reboot',
    testtype='max',
    testbounds=3,
    valid_date='2022-09-28')

warm_reboot_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_successive-warm-reboot-failures',
    testtype='max',
    testbounds=2,
    valid_date='2021-01-01')

camera_darkrate_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_camera-darkrate',
    testtype='in-range',
    testbounds=[200, 460],
    valid_date='2022-10-18')

camera_pattern_goalpost = Goalpost(
    testname='degg_pmt_R5912-100-70_camera-pattern-test',
    testtype='equals',
    testbounds=1,
    valid_date='2021-01-01')


@click.command()
@click.option('--submit', is_flag=True)
@click.option('--dry_run', is_flag=True)
def main(submit, dry_run):
    folder_name = 'database_jsons/goalposts'
    if not os.path.isdir(folder_name):
        os.makedirs(folder_name)
    print('The currently defined Goalposts are:')
    for gp in Goalpost.get_instances():
        if len(gp.testname) < 35:
            raise ValueError(f'{gp.testname} must be at least 35 characters,' +
                             f'or database will complain')
        print(gp)
        json_file = os.path.join(folder_name, f'Goalpost_{gp.testname}.json')
        gp.to_json(json_file)

    if submit:
        from degg_measurements.analysis import RunHandler
        run_handler = RunHandler('goalposts')
        run_handler.to_database(run_handler.file_names,
                                dry_run=dry_run)

if __name__ == '__main__':
    main()

