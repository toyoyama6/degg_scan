import time
import sys, os
import click
import threading

#########
##timing imports
from degg_measurements.timing.gainCheckHelper import checkDEggGain
from degg_measurements.timing.setupHelper import deggContainer, infoContainer
from degg_measurements.timing.setupHelper import parseRunFile, overwriteCheck, makeBatches
from degg_measurements.timing.setupHelper import configureDEggHV, deggListInitialize
from degg_measurements.timing.setupHelper import recreateDEggStreams, getEventDataParallel
from degg_measurements.timing.rapcalHelper import setupRapCalData
from degg_measurements.timing.rapcalHelper import getRapCalData
from degg_measurements.timing.rapcalHelper import offset
#########

def run(run_file='/home/scanbox/data/json/run/run_00122.json',
        method='charge_stamp', overwrite=False, loop=1, m_num=1):

    extra_burn_in = 60 * 60 * 2

    ##to grab the gain fit params to extrapolate new HV for different gain
    measurement_key = 'GainMeasurement_08'

    loop_vals = [0.9, 1.0, 1.1, 1.2, 1.3]
    loop_val = loop_vals[loop]
    print("WARNING - RUNNING WITH MODIFIED GAIN VALUES!")

    ports     = [5000, 5001, 5002, 5003,
                 5004, 5005, 5006, 5007,
                 5008, 5009, 5010, 5011,
                 5012, 5013, 5014, 5015]
    icm_ports = [6000, 6000, 6000, 6000,
                 6004, 6004, 6004, 6004,
                 6008, 6008, 6008, 6008,
                 6012, 6012, 6012, 6012]
    rapcal_ports = [icm_ports[0], icm_ports[4], icm_ports[8], icm_ports[12]]
    dac_value = 30000
    period = 100000
    deadtime = 24
    n_rapcals = 5000
    nevents = 2000
    deggList, hvSetList, thresholdList, baselineList, peakHeightList = parseRunFile(run_file, loop_val, measurement_key)
    ##fill DEgg class with info
    ##create session objects
    deggsList = deggListInitialize(degg_list=deggList, ports=ports, icm_ports=icm_ports,
                           hvSetList=hvSetList, thresholdList=thresholdList, dacValue=dac_value,
                           period=period, deadtime=deadtime, baselineList=baselineList,
                           _type='degg', nevents=nevents, overwrite=overwrite, loop=loop)
    ##ramping will happen in background
    configureDEggHV(deggsList)
    print("Finished initialisation")
    ##do gain/baseline checks
    checkDEggGain(deggsList, overwrite)
    ##configure readout for dark rates
    recreateDEggStreams(deggsList)

    print("Sleeping extra for burn in")
    time.sleep(extra_burn_in)
    print("Done burning in!")

    deggBatches = makeBatches(deggsList)
    icmConnectList = setupRapCalData(rapcal_ports)
    for i in range(n_rapcals):
        threads = []
        for deggBatch, icmConnect, rapcal_port in zip(deggBatches, icmConnectList, rapcal_ports):
            threads.append(threading.Thread(target=getRapCalData, args=[icmConnect, rapcal_port, deggBatch]))
        for deggBatch in deggBatches:
            for degg in deggBatch:
                threads.append(threading.Thread(target=getEventDataParallel, args=[degg, nevents, method, i]))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f'N RapCal: {i}')
        ##fill deggs with converted times
        offset(deggsList, method)
        for degg in deggsList:
            ##write the converted times to file
            for ch in [0, 1]:
                degg.saveInfo(ch)
            ##clear degg info
            degg.resetInfo()

@click.command()
@click.option('--method', '-m', default='charge_stamp')
@click.option('--overwrite', '-o', is_flag=True)
@click.option('--loop', '-l', default=1)
@click.option('--num', '-n', default=1)
def main(method, overwrite, loop, num):
    loop = int(loop)
    num = int(num)
    run(method=method, overwrite=overwrite, loop=loop, m_num=num)

if __name__ == "__main__":
    main()

##end
