import time
from datetime import datetime, timedelta
import os, sys
from degg_measurements import FH_SERVER_SCRIPTS
sys.path.append(FH_SERVER_SCRIPTS)
from icmnet import ICMNet
from RapCal import rapcal as rp

from degg_measurements.utils.icm_manipulation import enable_external_osc
from degg_measurements.utils.icm_manipulation import run_rapcal_all
from degg_measurements.timing.setupHelper import deggContainer


##RapCal related helper functions
def setupRapCalData(rapcal_ports):
    icmConnectList = []
    for icm_port in rapcal_ports:
        print(f"--- ICM {icm_port} ---")
        icms = ICMNet(icm_port, host='localhost')
        icms.request('write 8 0 0x0100')
        icms.request('gps_enable')
        ##THIS IS NEEDED FOR PPS TO UPDATE SETTINGS
        ##DO NOT REMOVE
        time.sleep(1.3)
        if icms.request('get_gps_ctrl')['value'] != '0x0002':
            raise RuntimeError(f'GPS Time Not Valid!: {icms.request("get_gps_ctrl")}')
        if icms.request('get_gps_status')['value'] != '0x000e':
            raise RuntimeError(f'GPS not locked: {icms.request("get_gps_status")}')
        icmConnectList.append(icms)
    return icmConnectList

def getRapCalData(icms, icm_port, deggBatch=None, nRepeat=2, verbose=False,
                  externalTime=[], ALT_FITTING=False):
    if deggBatch == None:
        return
    if deggBatch == []:
        return
    if verbose == True:
        print(f'Starting RapCal Procedure for {icm_port}')
        ##get blocking locks for relevant D-Eggs
    for degg in deggBatch:
        if verbose == True:
            print(f'Acquiring Lock {degg.port} ({icm_port})')
        degg.lock.acquire()

    ##This is basically depricated
    ##Always pass the combination of ICM time and UTC time
    if len(externalTime) != 2:
        print("Using Internal Timing - this is basically depricated")
        icm_time = icms.request('get_icm_time 8')['value']
        utc_time_str = icms.request('read 8 0x2B')['value']
        utc_time_str = utc_time_str.split('T')
        ##Years, days, hours, min, sec
        years   = int(utc_time_str[0].split('-')[0])
        days    = int(utc_time_str[0].split('-')[1])
        hours   = int(utc_time_str[1].split(':')[0])
        minutes = int(utc_time_str[1].split(':')[1])
        seconds = int(utc_time_str[1].split(':')[2])
        dt = datetime(years, 1, 1, hours, minutes, seconds) + timedelta(days=(days-1))
    if len(externalTime) == 2:
        ##this is still in base 16
        icm_time = externalTime[0]
        ##this is still a datetime object
        dt = externalTime[1]

    ##run RapCal twice to build the RapCalPair
    for i in range(nRepeat):
        icms.request('rapcal_all')
        ##get rapcal info
        for degg in deggBatch:
            session = degg.session
            header_info = rp.RapCalEvent.parse_rapcal_header(session.read_n(4))
            rapcal_pkt = session.read_n(header_info['size'])
            if not header_info.get('size'):
                raise Exception(header_info['error'])
            event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
            event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
            try:
                fitResult = event.fitResult
                degg.fitResult.append(fitResult)
            ##old data does not have this
            except:
                pass
            #rapcals = degg.rapcals
            degg.rapcals.add_rapcal(event)
            DEFAULT_TIME = event.Trx_dor_corrected

            if ALT_FITTING == True:
                event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
                _result = event.analyze(rp.RapCalEvent.ALGO_LINEAR_FIT)
                try:
                    degg.rapcals_LINEAR.add_rapcal(event)
                    if _result['success'] != True:
                        print(_result['error'])
                    print(degg.port, f'LINEAR:{DEFAULT_TIME - event.Trx_dor_corrected}')
                except:
                    print(degg.port)
                    raise AttributeError(f'{degg.port}')

                event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
                _result = event.analyze(rp.RapCalEvent.ALGO_QUAD_FIT)
                if _result['success'] != True:
                    print(_result['error'])
                print(degg.port, f'QUAD:{DEFAULT_TIME - event.Trx_dor_corrected}')
                degg.rapcals_QUAD.add_rapcal(event)

                event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
                _result = event.analyze(rp.RapCalEvent.ALGO_QUAD_FIT_MOD)
                if _result['success'] != True:
                    print(_result['error'])
                print(degg.port, f'QUAD_MOD:{DEFAULT_TIME - event.Trx_dor_corrected}')
                degg.rapcals_QUAD_MOD.add_rapcal(event)

                event = rp.RapCalEvent((header_info['version'], rapcal_pkt))
                _result = event.analyze(rp.RapCalEvent.ALGO_RICHARD_FIT)
                if _result['success'] != True:
                    print(_result['error'])
                print(degg.port, f'RICHARD:{DEFAULT_TIME - event.Trx_dor_corrected}')
                degg.rapcals_RICHARD.add_rapcal(event)

            degg.rapcal_utcs.append(dt.timestamp())
            degg.rapcal_icms.append(icm_time)
    ##release their locks
    for degg in deggBatch:
        if verbose == True:
            print(f"Releasing Locks {degg.port} ({icm_port})")
        degg.lock.release()

    #return True

def offset(deggsList, method):
    print("WARN - rapCalHelper::offset functionality may be outdated!")
    mfhTimeList = []
    offset_datetime = datetime(2022, 1, 1)
    t_offset_datetime = offset_datetime.timestamp()
    ##loop over the D-Eggs
    for degg in deggsList:
        rapcals = degg.rapcals
        thresholdList = [degg.threshold0, degg.threshold1]
        if len(rapcals.rapcals) < 2:
            raise RuntimeError(f'Not enough RapCals recorded for D-Egg on port {degg.port}')
        if len(rapcals.rapcals) >= 2:
            rp_pair = rp.RapCalPair(rapcals.rapcals[0], rapcals.rapcals[1],
                                    utc=[degg.rapcal_utcs[0]],
                                    icm=degg.rapcal_icms[0],
                                    utc_is_seconds=True,
                                    icm_is_base16=True)
            print(f'Port: {degg.port}, {len(degg.info0)}, {len(degg.info1)}')
            for infoList in [degg.info0, degg.info1]:
                for info in infoList:
                    if method == 'charge_stamp':
                        timestamp = info.timestamp
                    elif method == 'waveform':
                        timestamps = info.timestamp
                        ##NOTE: still in units of ADCs
                        charges = info.charge
                        channel = info.channel
                        threshold = thresholdList[channel]
                        timestamp = getWaveformTimestamp(timestamps, charges, threshold)
                    else:
                        raise NotImplementedError(f'Method {method} not valid - \
                                                use charge_stamp or waveform')

                    mfh_t, delta = rp_pair.dom2surface(timestamp,
                                                             device_type='DEGG',
                                                             deggMode=True)
                    info.datetime_offset = t_offset_datetime
                    info.mfh_t = mfh_t
                    info.delta = delta
                    info.clockDrift  = rp_pair.epsilon
                    info.cableDelay0 = rp_pair.cable_delays[0]
                    info.cableDelay1 = rp_pair.cable_delays[1]
                    mfhTimeList.append(mfh_t)
    if len(mfhTimeList) == 0:
        raise ValueError("No times calculated!")

##same functionality as offset - but should be run at the end
##NOTE: If data was collected with the charge stamp ---
##for each 'info' (measurement) there is a corresponding DOM timestamp
##NOTE: If data was collected with the waveform stream ---
##for each 'info' (measuement) there is a corresponding list
##of DOM timestamps. Use an algorithm to determine the trigger time

##Convert the timestamp into MFH time
##This means all DOMs on the same WP are now 'synchronised'
##And this is a 'universal' time - so all MFHs are also synchronised
def calculateTimingInfoAfterDataTaking(deggsList, method, ALT_FITTING=False):

    ##use a universl offset to make times a bit smaller
    offset_datetime = datetime(2022, 1, 1)
    t_offset_datetime = offset_datetime.timestamp()

    ##loop over the D-Eggs
    for degg in deggsList:
        thresholdList = [degg.threshold0, degg.threshold1]
        valid_times = False

        ##check if enough rapcals were taken to make the pair
        rapcals = degg.rapcals

        if len(rapcals.rapcals) < 2:
            raise RuntimeError(f'Not enough RapCals for D-Egg:{degg.port} - fix at DAQ side')
        for i_pair in range(len(rapcals.rapcals)//2):

            ##build RapCalPair for this event
            rp_pair = rp.RapCalPair(rapcals.rapcals[2*i_pair], rapcals.rapcals[(2*i_pair)+1],
                                    utc=[(degg.rapcal_utcs[2*i_pair]-t_offset_datetime)],
                                    icm=degg.rapcal_icms[2*i_pair],
                                    utc_is_seconds=True,
                                    icm_is_base16=True)

            if ALT_FITTING == True:
                alt_rapcal_list = [degg.rapcals_LINEAR,
                                   degg.rapcals_QUAD,
                                   degg.rapcals_QUAD_MOD,
                                   degg.rapcals_RICHARD]
                alt_rp_pairs = []
                for rapcals in alt_rapcal_list:
                    rp_pair = rp.RapCalPair(rapcals.rapcals[2*i_pair],
                                            rapcals.rapcals[(2*i_pair)+1],
                                        utc=[(degg.rapcal_utcs[2*i_pair]-t_offset_datetime)],
                                        icm=degg.rapcal_icms[2*i_pair],
                                        utc_is_seconds=True,
                                        icm_is_base16=True)
                    alt_rp_pairs.append(rp_pair)

            ##get trigger info for Ch0 and Ch1
            for infoList in [degg.info0, degg.info1]:

                ##loop over all triggers taken for these RapCals
                for i_info, info in enumerate(infoList):

                    ##make sure the iteration numbers match
                    if info.i_pair != i_pair:
                        continue

                    ##get the timestamp based on how the data was collected
                    timestamp = getEventTimeStamp(info, method)

                    ##extract time and offset
                    mfh_t, delta = rp_pair.dom2surface(timestamp,
                                                       device_type='DEGG',
                                                       deggMode=True)
                    ##int cast to preserve precision
                    ##mfh_t2 = mfh_t -- preserve legacy code
                    info.mfh_t = int(mfh_t*1e15) #[fs]
                    info.mfh_t2 = int(mfh_t*1e15)
                    info.datetime_offset = t_offset_datetime
                    info.delta = delta #[s]
                    info.clockDrift  = rp_pair.epsilon
                    info.cable_delay0 = rp_pair.cable_delays[0]
                    info.cable_delay1 = rp_pair.cable_delays[1]

                    if ALT_FITTING == True:
                        # alt_mfh_list = [info.mfh_LINEAR,
                        #                 info.mfh_QUAD,
                        #                 info.mfh_QUAD_MOD,
                        #                 info.mfh_RICHARD]
                        # alt_clk_list = [info.clockDrift_LINEAR,
                        #                 info.clockDrift_QUAD,
                        #                 info.clockDrift_QUAD_MOD,
                        #                 info.clockDrift_RICHARD]
                        # alt_del0_list = [info.delay0_LINEAR,
                        #                  info.delay0_QUAD,
                        #                  info.delay0_QUAD_MOD,
                        #                  info.delay0_RICHARD]
                        # alt_del1_list = [info.delay1_LINEAR,
                        #                  info.delay1_QUAD,
                        #                  info.delay1_QUAD_MOD,
                        #                  info.delay1_RICHARD]
                        #for _i, _rp_pair in enumerate(alt_rp_pairs):
                            #_mfh_t, _delta = _rp_pair.dom2surface(timestamp,
                        #                                       device_type='DEGG',
                        #                                       deggMode=True)
                            #alt_mfh_list[_i]  = int(_mfh_t*1e15)
                            #alt_clk_list[_i]  = _rp_pair.epsilon
                            #alt_del0_list[_i] = _rp_pair.cable_delays[0]
                            #alt_del1_list[_i] = _rp_pair.cable_delays[1]

                        # info.mfh_LINEAR   = alt_mfh_list[0]
                        # info.mfh_QUAD     = alt_mfh_list[1]
                        # info.mfh_QUAD_MOD = alt_mfh_list[2]
                        # info.mfh_RICHARD  = alt_mfh_list[3]

                        # info.delay0_LINEAR   = alt_del0_list[0]
                        # info.delay0_QUAD     = alt_del0_list[1]
                        # info.delay0_QUAD_MOD = alt_del0_list[2]
                        # info.delay0_RICHARD  = alt_del0_list[3]

                        # info.delay1_LINEAR   = alt_del1_list[0]
                        # info.delay1_QUAD     = alt_del1_list[1]
                        # info.delay1_QUAD_MOD = alt_del1_list[2]
                        # info.delay1_RICHARD  = alt_del1_list[3]

                        # info.clockDrift_LINEAR   = alt_clk_list[0]
                        # info.clockDrift_QUAD     = alt_clk_list[1]
                        # info.clockDrift_QUAD_MOD = alt_clk_list[2]
                        # info.clockDrift_RICHARD  = alt_clk_list[3]
                        _mfh_t, _delta = alt_rp_pairs[0].dom2surface(timestamp,
                                                           device_type='DEGG',
                                                           deggMode=True)
                        info.mfh_LINEAR          = int(_mfh_t*1e15)
                        info.delay0_LINEAR       = alt_rp_pairs[0].cable_delays[0]
                        info.delay1_LINEAR       = alt_rp_pairs[0].cable_delays[1]
                        info.clockDrift_LINEAR   = alt_rp_pairs[0].epsilon

                        _mfh_t, _delta = alt_rp_pairs[1].dom2surface(timestamp,
                                                           device_type='DEGG',
                                                           deggMode=True)
                        info.mfh_QUAD          = int(_mfh_t*1e15)
                        info.delay0_QUAD       = alt_rp_pairs[1].cable_delays[0]
                        info.delay1_QUAD       = alt_rp_pairs[1].cable_delays[1]
                        info.clockDrift_QUAD   = alt_rp_pairs[1].epsilon

                        _mfh_t, _delta = alt_rp_pairs[2].dom2surface(timestamp,
                                                           device_type='DEGG',
                                                           deggMode=True)
                        info.mfh_QUAD_MOD          = int(_mfh_t*1e15)
                        info.delay0_QUAD_MOD       = alt_rp_pairs[2].cable_delays[0]
                        info.delay1_QUAD_MOD       = alt_rp_pairs[2].cable_delays[1]
                        info.clockDrift_QUAD_MOD   = alt_rp_pairs[2].epsilon

                        _mfh_t, _delta = alt_rp_pairs[3].dom2surface(timestamp,
                                                           device_type='DEGG',
                                                           deggMode=True)
                        info.mfh_RICHARD          = int(_mfh_t*1e15)
                        info.delay0_RICHARD       = alt_rp_pairs[3].cable_delays[0]
                        info.delay1_RICHARD       = alt_rp_pairs[3].cable_delays[1]
                        info.clockDrift_RICHARD   = alt_rp_pairs[3].epsilon


                    valid_times = True

    ##make sure some times are valid!
    if valid_times == False:
        raise ValueError(f"No times calculated! - D-Egg:{degg.port}")

def getEventTimeStamp(info, method):
    if method == 'charge_stamp':
        timestamp = info.timestamp
    elif method == 'waveform':
        timestamps = info.timestamp
        ##NOTE: still in units of ADCs
        charges = info.charge
        channel = info.channel
        threshold = thresholdList[channel]
        timestamp = getWaveformTimestamp(timestamps, charges, threshold)
    else:
        raise NotImplementedError(f'Method {method} not valid - \
                                        use charge_stamp or waveform')
    return timestamp

##end
