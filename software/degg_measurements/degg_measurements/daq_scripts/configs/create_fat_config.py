import os, sys
from configparser import ConfigParser
import click

DM='degg_measurements'

def save_file(config, savefile):
    # save to a file
    with open(savefile, 'w') as configfile:
        config.write(configfile)
    print(f'Saved file: {savefile}')

def write_header(config, run_file, verbose):
    config.add_section('constants')
    config.set('constants', 'run_file', f'{run_file}')
    config.set('constants', 'verbose',  f'{verbose}')
    return config

def write_meas(config, sw_dir, pkg, task, count, **kwargs):

    package = f'{DM}.{sw_dir}.{pkg}'
    if task == 'bootmon':
        mode = kwargs['mode']
        config.add_section(f'{task}_{count}_{mode}')
        config.set(f'{task}_{count}_{mode}', 'package', package)
        config.set(f'{task}_{count}_{mode}', 'task', task)
        for l in kwargs:
            config.set(f'{task}_{count}_{mode}', f'{l}', f'{kwargs[l]}')
    elif task == 'trigger_remote_wrapper':
        anaStr = kwargs['analysis']
        config.add_section(f'{task}_{anaStr}_{count}')
        config.set(f'{task}_{anaStr}_{count}', 'package', package)
        config.set(f'{task}_{anaStr}_{count}', 'task', task)
        for l in kwargs:
            config.set(f'{task}_{anaStr}_{count}', f'{l}', f'{kwargs[l]}')
    else:
        config.add_section(f'{task}_{count}')
        config.set(f'{task}_{count}', 'package', package)
        config.set(f'{task}_{count}', 'task', task)
        for l in kwargs:
            config.set(f'{task}_{count}', f'{l}', f'{kwargs[l]}')

    count += 1
    return config, count

def status(config, n):
    config, n = write_meas(config, 'daq_scripts', 'fat_master',
                        'status_check', count=n,
                        verbose=True, reboot=False)
    return config, n

def stf(config, n, comment=''):
    config, n = write_meas(config, 'daq_scripts', 'measure_stf',
                        'measure_stf', count=n,
                        comment=comment, n_jobs=4)
    return config, n

def stf_ana(config, n):
    config, n = write_meas(config, 'analysis.stf', 'analyze_stf',
                           'stf_ana', count=n)
    return config, n

def gain(config, n_gain, comment='room temp'):
    config, n_gain = write_meas(config, 'daq_scripts', 'measure_gain_online',
                                'measure_gain', count=n_gain,
                                comment=comment, n_jobs=4,
                                resume=False, run_backup=False)
    return config, n_gain

def gain_ana(config, n_gain_ana):
    config, n_gain_ana = write_meas(config, 'analysis.gain', 'analyze_gain',
                                'analysis_wrapper', count=n_gain_ana,
                                pdf=False, mode='gain_scan',
                                measurement_number='latest',
                                offline=False, simple=False)
    return config, n_gain_ana

def gain_ready(config, n_gain_ready):
    config, n_gain_ready = write_meas(config, 'daq_scripts', 'fat_master',
                                'validate_gain', count=n_gain_ready,
                                verbose=True)
    return config, n_gain_ready

def man_input(config, n_input, message=''):
    config, n_input = write_meas(config, 'daq_scripts', 'fat_master',
                                'manual_input', count=n_input,
                                message=message)
    return config, n_input

def freezer(config, n, t_now, t_delta):
    config, n = write_meas(config, 'utils', 'freezer_control_wrapper',
                                'dummy_wrapper', count=n,
                                fcurrent=t_now, fdelta=t_delta)
    return config, n

def mon_scan(config, n, max_i=1):
    config, n = write_meas(config, 'monitoring', 'recall',
                           'slowmon', count=n,
                           max_i=max_i, n_jobs=4,
                           use_fir=True, run_backup=False)
    return config, n

def mon_fixed(config, n, max_i=1, use_fir=True, ignoreWarn=False):
    config, n = write_meas(config, 'monitoring', 'ritual',
                           'constant_monitor', count=n,
                           max_i=max_i, n_jobs=4,
                           use_fir=use_fir, verbose=True,
                           ignoreWarn=ignoreWarn,
                           run_backup=False)
    return config, n

def reboot(config, n, mode='reboot'):
    config, n = write_meas(config, 'monitoring', 'regrowth',
                           'bootmon', count=n,
                           mode=mode)
    return config, n

def darkrate(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_scaler',
                           'measure_scaler', count=n,
                           comment=f'FAT {n}',
                           n_jobs=4,  use_alt_thresholds=False,
                           no_hv=False, use_fir=True)
    return config, n

def dt(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_dt',
                           'measure_spe', count=n,
                           comment='fir trigger for dt at cold temp FAT test',
                           n_jobs=4,  n_events=10000,
                           use_fir=True)
    return config, n

def camera_dr(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_camera_darknoise',
                           'measure_camera', count=n, comment='FAT',
                           n_jobs=4, plot=True, test=False)
    return config, n

def camera_off(config, n):
    config, n = write_meas(config, 'utils', 'disable_camera_lights',
                           'disable_all_lights', count=n)

    return config, n

def camera_copy(config, n):
    config, n = write_meas(config, 'utils', 'camera_checker',
                           'camera_file_checker', count=n)

    return config, n

def linearity(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_linearity',
                           'measure_linearity', count=n,
                           comment='10 fw settings, 100 Hz',
                           n_jobs=4, run_backup=False)
    return config, n

def pulsed(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_pulsed_waveform',
                           'measure_pulsed_waveform', count=n,
                           comment='double burst 0.05fw, 100 Hz',
                           strength0=0.05, strength1=1.0,
                           n_jobs=4,
                           mode='double', run_backup=False)
    return config, n

def tts(config, n):
    config, n = write_meas(config, 'timing', 'get_offset',
                           'run_timing', count=n,
                           comment='spe level tts -40',
                           n_jobs=4,
                           method='charge_stamp', overwrite=True,
                           verbose=False)

    return config, n

def leds(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_flasher_caltrig_chargestamp',
                           'measure_baseline_flasher', count=n,
                           comment='FAT test', n_jobs=4)
    return config, n

def camera_pattern(config, n):
    config, n = write_meas(config, 'daq_scripts', 'measure_camera_pattern',
                           'measure_pattern', count=n,
                           comment='FAT test', n_jobs=4)
    return config, n

def bolt(config, n, boltStat):
    valid_stats = ['moving', 'very_cold0', 'very_cold1', 'kinda_cold0',
                   'very_cold0_postIllumination', 'very_cold1_postIllumination',
                   'kinda_cold0_postIllumination']
    if boltStat not in valid_stats:
        raise ValueError(f'{boltStat} must be one of {valid_stats}')
    config, n = write_meas(config, 'monitoring', 'bolt',
                           'online_mon', count=n,
                           comment='quick online monitoring',
                           n_repeat=3, hv_status=boltStat)
    return config, n

def hvTest(config, n):
    config, n = write_meas(config, 'utils', 'hv_check', 'measure_hv', count=n)
    return config, n

##run_json should be filled automatically
##when the master script parses the config file
def remoteAna(config, n, anaStr):
    anaList = ['darkrate', 'double_pulse', 'flasher_chargestamp', 'gain',
               'linearity', 'quick_monitoring', 'detailed_monitoring',
               'gainscan_monitoring', 'reboot_monitoring', 'spe',
               'tts', 'dt', 'detailed_monitoring']
    if anaStr not in anaList:
        raise ValueError(f'{anaStr} not in {anaList}!')
    config, n = write_meas(config, 'analysis', 'trigger_remote_analysis',
                           'trigger_remote_wrapper', n, analysis=anaStr)
    return config, n

@click.command()
@click.argument('run_file')
@click.argument('config_name')
@click.option('--no_hv', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
def main(run_file, config_name, no_hv, verbose):
    if no_hv:
        hv = False
    else:
        hv = True

    config = ConfigParser()
    config = write_header(config, run_file, verbose)

    ##keep count of each measurement
    disable_laser = 0
    n_status      = 0
    n_stf         = 0
    n_gain        = 0
    n_gain_ana    = 0
    n_gain_ready  = 0
    n_input       = 0
    n_freezer     = 0
    n_mon_scan    = 0
    n_mon_fixed   = 0
    n_bolt        = 0
    n_warm_boot   = 0
    n_darkrate    = 0
    n_dt          = 0
    n_camera_dr   = 0
    n_linearity   = 0
    n_pulsed      = 0
    n_tts         = 0
    n_leds        = 0
    n_camera_pt   = 0
    n_cold_boot   = 0
    n_hv          = 0
    n_camera_off  = 0
    n_camera_copy = 0
    n_done        = 0
    ##analysis counters
    n_r_gain_ana  = 0
    n_gs_mon_ana  = 0
    n_q_mon_ana   = 0
    n_f_mon_ana   = 0
    n_dr_ana      = 0
    n_dt_ana      = 0
    n_lin_ana     = 0
    n_double_ana  = 0
    n_tts_ana     = 0
    n_led_ana     = 0
    n_stf_ana     = 0
    n_const_mon_ana = 0

    config, disable_laser = write_meas(config, 'utils', 'disable_laser',
                        'disable_laser', count=disable_laser)
    config, n_status      = status(config, n_status)
    config, n_stf         = stf(config, n_stf, comment='room temp')
    config, n_stf_ana     = stf_ana(config, n_stf_ana)
    config, n_status      = status(config, n_status)
    config, n_gain        = gain(config, n_gain)
    config, n_r_gain_ana  = remoteAna(config, n_r_gain_ana, 'gain')
    config, n_status      = status(config, n_status)
    config, n_gain_ana    = gain_ana(config, n_gain_ana)
    config, n_gain_ready  = gain_ready(config, n_gain_ready)
    config, n_input       = man_input(config, n_input,
                                      message='Are the gain and STF OK? If so, continue')
    config, n_freezer     = freezer(config, n_freezer, t_now=20, t_delta=-60)

    ##do monitoring for about 20 hours:
    for i in range(20):
        config, n_mon_scan    = mon_scan(config, n_mon_scan, max_i=1)
        config, n_gs_mon_ana  = remoteAna(config, n_gs_mon_ana, 'gainscan_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
        config, n_warm_boot   = reboot(config, n_warm_boot, mode='reboot')

    ##now at -40 degrees - first tests without light sources
    config, n_gain        = gain(config, n_gain, comment='cooled down to -40')
    config, n_r_gain_ana  = remoteAna(config, n_r_gain_ana, 'gain')
    config, n_status      = status(config, n_status)
    config, n_gain_ana    = gain_ana(config, n_gain_ana)
    config, n_gain_ready  = gain_ready(config, n_gain_ready)

    ##let new HV stabilise a bit at -40
    firMode = [True, False, True]
    for i in range(3):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=2,
                                          use_fir=firMode[i], ignoreWarn=False)
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    config, n_darkrate    = darkrate(config, n_darkrate)
    config, n_dr_ana      = remoteAna(config, n_dr_ana, 'darkrate')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    config, n_dt          = dt(config, n_dt)
    config, n_dt_ana      = remoteAna(config, n_dt_ana, 'dt')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##now light source tests
    ##first linearity
    config, n_linearity   = linearity(config, n_linearity)
    config, n_lin_ana     = remoteAna(config, n_lin_ana, 'linearity')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##double pulse
    config, n_pulsed      = pulsed(config, n_pulsed)
    config, n_double_ana  = remoteAna(config, n_double_ana, 'double_pulse')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##tts/sptr
    config, n_tts         = tts(config, n_tts)
    config, n_tts_ana     = remoteAna(config, n_tts_ana, 'tts')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##turn off the laser for now
    config, disable_laser = write_meas(config, 'utils', 'disable_laser',
                        'disable_laser', count=disable_laser)

    ##calibration sub-system tests
    ##camera test - dark rate
    config, n_camera_dr   = camera_dr(config, n_camera_dr)
    config, n_status      = status(config, n_status)

    ##turn off the cameras for sure
    config, n_camera_off  = camera_off(config, n_camera_off)

    ##led test
    config, n_leds        = leds(config, n_leds)
    config, n_status      = status(config, n_status)
    config, n_led_ana     = remoteAna(config, n_led_ana, 'flasher_chargestamp')

    ##camera test - pattern
    config, n_camera_pt   = camera_pattern(config, n_camera_pt)
    config, n_status      = status(config, n_status)

    ##turn off the cameras for sure
    config, n_camera_off  = camera_off(config, n_camera_off)

    ##copy camera data & check valid files
    config, n_camera_copy = camera_copy(config, n_camera_copy)

    config, n_bolt        = bolt(config, n_bolt, 'very_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    config, n_status      = status(config, n_status)

    ##fill some time with monitoring
    firMode = [True, False]
    ignoreSetting = [True, False]
    for i in range(2):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=2,
                                          use_fir=firMode[i], ignoreWarn=ignoreSetting[i])
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
        config, n_status      = status(config, n_status)

    ##run stf for -40 degrees
    config, n_stf         = stf(config, n_stf, comment='fat cold')
    config, n_stf_ana     = stf_ana(config, n_stf_ana)
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##do the cold boot
    config, n_cold_boot   = reboot(config, n_cold_boot, mode='coldboot')
    config, n_status      = status(config, n_status)

    ##monitor a bit after
    ##hv is reset due to the cold boot
    firMode = [True, False]
    ignoreSetting = [True, False]
    for i in range(2):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=2,
                                          use_fir=firMode[i], ignoreWarn=ignoreSetting[i])
        #config, n_f_mon_ana   = remoteAna(config, n_f_mon_ana, 'detailed_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
        config, n_status      = status(config, n_status)

    ##change the freezer temp
    config, n_freezer     = freezer(config, n_freezer, t_now=-40, t_delta=20)

    config, n_bolt        = bolt(config, n_bolt, 'very_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    config, n_status      = status(config, n_status)

    ##do monitoring for about 10 hours while changing temp
    for i in range(16):
        config, n_mon_scan    = mon_scan(config, n_mon_scan, max_i=1)
        config, n_gs_mon_ana  = remoteAna(config, n_gs_mon_ana, 'gainscan_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
        config, n_warm_boot   = reboot(config, n_warm_boot, mode='reboot')

    ##now at -20
    config, n_gain        = gain(config, n_gain, comment='now at -20')
    config, n_r_gain_ana  = remoteAna(config, n_r_gain_ana, 'gain')
    config, n_status      = status(config, n_status)
    config, n_gain_ana    = gain_ana(config, n_gain_ana)
    config, n_gain_ready  = gain_ready(config, n_gain_ready)

    ##let new HV stabilise a bit at -20
    for i in range(16):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=2)
        #config, n_f_mon_ana   = remoteAna(config, n_f_mon_ana, 'detailed_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##repeat dark rate
    config, n_darkrate    = darkrate(config, n_darkrate)
    config, n_dr_ana      = remoteAna(config, n_dr_ana, 'darkrate')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##repeat dt
    config, n_dt          = dt(config, n_dt)
    config, n_dt_ana      = remoteAna(config, n_dt_ana, 'dt')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##now light source tests at -20
    ##linearity
    config, n_linearity   = linearity(config, n_linearity)
    config, n_lin_ana     = remoteAna(config, n_lin_ana, 'linearity')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##double pulse
    config, n_pulsed      = pulsed(config, n_pulsed)
    config, n_double_ana  = remoteAna(config, n_double_ana, 'double_pulse')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##tts/sptr
    config, n_tts         = tts(config, n_tts)
    config, n_tts_ana     = remoteAna(config, n_tts_ana, 'tts')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##disable laser
    config, disable_laser = write_meas(config, 'utils', 'disable_laser',
                        'disable_laser', count=disable_laser)

    ##run stf for -20
    config, n_stf         = stf(config, n_stf, comment='fat cold')
    config, n_stf_ana     = stf_ana(config, n_stf_ana)
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'kinda_cold0')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##change the freezer temp
    config, n_freezer     = freezer(config, n_freezer, t_now=-20, t_delta=40)

    ##do monitoring for about 12 hours:
    for i in range(18):
        config, n_mon_scan    = mon_scan(config, n_mon_scan, max_i=1)
        config, n_gs_mon_ana  = remoteAna(config, n_gs_mon_ana, 'gainscan_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_warm_boot   = reboot(config, n_warm_boot, mode='reboot')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    config, n_input       = man_input(config, n_input,
                                      message='Pausing DAQ for room temperature repairs!')
    ##change the freezer temp
    config, n_freezer     = freezer(config, n_freezer, t_now=20, t_delta=-60)

    ##do monitoring for about 20 hours:
    for i in range(26):
        config, n_mon_scan    = mon_scan(config, n_mon_scan, max_i=1)
        config, n_gs_mon_ana  = remoteAna(config, n_gs_mon_ana, 'gainscan_monitoring')
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
        config, n_warm_boot   = reboot(config, n_warm_boot, mode='reboot')


    ##let new HV stabilise a bit at -40
    firMode = [True, True, True, False]
    for i in range(4):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=2, use_fir=firMode[i])
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    if hv == True:
        config, n_hv          = hvTest(config, n_hv)
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'moving')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##now at -40 degrees - again tests without light sources
    config, n_gain        = gain(config, n_gain, comment='again at -40')
    config, n_r_gain_ana  = remoteAna(config, n_r_gain_ana, 'gain')
    config, n_status      = status(config, n_status)
    config, n_gain_ana    = gain_ana(config, n_gain_ana)
    config, n_gain_ready  = gain_ready(config, n_gain_ready)

    config, n_darkrate    = darkrate(config, n_darkrate)
    config, n_dr_ana      = remoteAna(config, n_dr_ana, 'darkrate')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    config, n_dt          = dt(config, n_dt)
    config, n_dt_ana      = remoteAna(config, n_dt_ana, 'dt')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##fill with monitoring for ~36+ hours
    for i in range(54):
        config, n_mon_fixed   = mon_fixed(config, n_mon_fixed, max_i=1)
        config, n_status      = status(config, n_status)
        config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
        config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##trigger the const analysis
    ##just run at the end!
    config, n_const_mon_ana = remoteAna(config, n_const_mon_ana, 'detailed_monitoring')

    config, n_darkrate    = darkrate(config, n_darkrate)
    config, n_dr_ana      = remoteAna(config, n_dr_ana, 'darkrate')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    config, n_dt          = dt(config, n_dt)
    config, n_dt_ana      = remoteAna(config, n_dt_ana, 'dt')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##now light source tests at the end, again at -40
    ##linearity
    config, n_linearity   = linearity(config, n_linearity)
    config, n_lin_ana     = remoteAna(config, n_lin_ana, 'linearity')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##double pulse
    config, n_pulsed      = pulsed(config, n_pulsed)
    config, n_double_ana  = remoteAna(config, n_double_ana, 'double_pulse')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    ##tts/sptr
    config, n_tts         = tts(config, n_tts)
    config, n_tts_ana     = remoteAna(config, n_tts_ana, 'tts')
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1_postIllumination')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##disable laser
    config, disable_laser = write_meas(config, 'utils', 'disable_laser',
                        'disable_laser', count=disable_laser)

    config, n_stf         = stf(config, n_stf, comment='fat cold')
    config, n_stf_ana     = stf_ana(config, n_stf_ana)
    config, n_status      = status(config, n_status)
    config, n_bolt        = bolt(config, n_bolt, 'very_cold1')
    config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')

    ##change the freezer temp
    config, n_freezer     = freezer(config, n_freezer, t_now=-40, t_delta=60)

    ##returning to room temperature
    if hv == False:
        for i in range(24):
            config, n_mon_scan    = mon_scan(config, n_mon_scan, max_i=1)
            config, n_gs_mon_ana  = remoteAna(config, n_gs_mon_ana, 'gainscan_monitoring')
            config, n_status      = status(config, n_status)
            config, n_bolt        = bolt(config, n_bolt, 'moving')
            config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    elif hv == True:
        for i in range(36):
            config, n_hv          = hvTest(config, n_hv)
            config, n_status      = status(config, n_status)
            config, n_bolt        = bolt(config, n_bolt, 'moving')
            config, n_q_mon_ana   = remoteAna(config, n_q_mon_ana, 'quick_monitoring')
    else:
        raise ValueError("There was a problem with setting hv flag?")

    config, n_done    = write_meas(config, 'daq_scripts', 'fat_master',
                        'manual_input', count=disable_laser,
                        message='Run is Finished, install dehumidifiers!')

    savefile = f'{config_name}'
    save_file(config, savefile)
    ##to print the contents
    #os.system(f'cat {savefile}')

if __name__ == "__main__":
    main()
##end
