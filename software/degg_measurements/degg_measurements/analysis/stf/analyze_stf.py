import click
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_pdf import PdfPages
from tqdm import tqdm
import json
import glob
import os,sys

from degg_measurements.utils import extract_runnumber_from_path

StfItems = ["AccelerometerSensor",
            "ADCComms-channel-0",
            "ADCComms-channel-1",
            "BaselineStability-channel-0",
            "BaselineStability-channel-1",
            "CameraCombinations-fast",
            "CameraComms-camera-1",
            "CameraComms-camera-2",
            "CameraComms-camera-3",
            "DACScan-channel-0",
            "DACScan-channel-1",
            "DPRAM",
            "FieldHub",
            "Flash",
            "FPGAMemTest",
            "HVMonitors-base-channel-0",
            "HVMonitors-base-channel-1",
            "Icm-base",
            "IcmFpgaSync",
            "IcmFwAudit",
            "IcmWriteProtect",
            "Interlock",
            "LightSensor-inside-freezer",
            "Magnetometer",
            "PowerLVS",
            "PowerRails",
            "PressureSensor",
            "RAPCal",
            "ScalerScan-base-channel-0",
            "ScalerScan-base-channel-1",
            "TempCompare"]

#@click.group()
#def cli():
#    pass

@click.command(short_help='make STF summary plot')
@click.argument('runconfig')
@click.option('--stfnumber',default=None)
@click.option('--omit',default=None,help='Omit items from counting good modules. Separate by ","')
def main(runconfig, stfnumber, omit):
    stf_ana(runconfig, stfnumber, omit)

def stf_ana(runconfig, stfnumber=None, omit=None):
    try:
        os.path.exists(runconfig)
    except:
        print('Run json file not found')
        sys.exit(1)

    #runnum = int(runconfig.split('/')[-1].split('run_')[-1].split('.json')[0])
    runnum =  extract_runnumber_from_path(runconfig)
    if stfnumber is not None:
        runnum = f'{runnum}_{stfnumber}'
        print(runnum)
    with open(runconfig,'r') as f:
        jsonfile = json.load(f)
    comment = jsonfile['comment']

    if omit is not None:
        omititems = omit.split(',')
        print(omititems)
    else:
        omititems = []

    passfail = np.zeros(len(StfItems)+1)
    errored  = np.zeros(len(StfItems)+1)
    nmodules = np.zeros(len(StfItems)+1)
    gooddoms = np.zeros(len(StfItems)+1)
    failports = ["" for i in StfItems]
    errorports = ["" for i in StfItems]
    for key in jsonfile:
        if 'DEgg' not in key:
            continue
        with open(jsonfile[key],'r') as f:
            deggjson = json.load(f)
        deggserialnumber = deggjson['DEggSerialNumber']
        opendir = ""
        for testitem in deggjson:
            if 'STF' not in testitem:
                continue
            if stfnumber is not None:
                if f'{int(stfnumber):02}' in testitem:
                    opendir = deggjson[testitem]['Folder']
                    print(testitem)
            else:
                opendir = deggjson[testitem]['Folder']
        if (opendir == "") or (opendir == 'None'):
            print(f"{deggserialnumber}: File not found")
        else:
            goodmodule = 1
            for i, item in enumerate(StfItems):
                dirlist = glob.glob(f'{opendir}/{item}*.json')
                if len(dirlist) < 1:
                    goodmodule = 0
                    continue
                with open(dirlist[0],'r') as f:
                    data = json.load(f)
                outcome = data['outcome']
                nmodules[i] += 1
                if (outcome == 'FAIL'):
                    passfail[i] += 1
                    failports[i] += f"{data['metadata']['stf_config']['iceboot']['port']}\n"
                    if omit is None:
                        goodmodule = 0
                    else:
                        skip = False
                        for omitkeyword in omititems:
                            if omitkeyword in item:
                                skip = True
                                break
                        if not skip:
                            goodmodule = 0
                elif (outcome == 'ERROR'):
                    errored[i] += 1
                    errorports[i] += f"{data['metadata']['stf_config']['iceboot']['port']}\n"
                    if omit is None:
                        goodmodule = 0
                    else:
                        skip = False
                        for omitkeyword in omititems:
                            if omitkeyword in item:
                                skip = True
                                break
                        if not skip:
                            goodmodule = 0
            gooddoms[-1] += goodmodule
    print(failports)
    isProblem = passfail + errored
    isProblem[-1] = 1
    fig, ax = plt.subplots(figsize=(10,3.5))
    failedStfItems = [StfItems[i] if len(StfItems[i].split('-base-channel-'))==1 else StfItems[i].split('-base-channel-')[0] + ' ch' + StfItems[i].split('-base-channel-')[1] for i in range(len(StfItems)) if isProblem[i]]
    failedStfItems.append("All Passed" if omit is None else f"Passed exc. {omit}")
    x = np.arange(len(failedStfItems))
    p1 = ax.bar(x,passfail[isProblem>0],label='FAIL')
    p2 = ax.bar(x,errored[isProblem>0],label='ERROR',bottom=passfail[isProblem>0])
    p3 = ax.bar(x,gooddoms[isProblem>0],color='green',bottom=passfail[isProblem>0]+errored[isProblem>0])
    ax.set_xticks(x,failedStfItems,rotation=30,ha='right')
    part_failports = [failports[i] for i in range(len(failports)) if isProblem[i]]
    part_failports.append('')
    part_errorports = [errorports[i] for i in range(len(failports)) if isProblem[i]]
    part_errorports.append('')
    plt.title(f'Run#{runnum}: {comment}')
    plt.ylabel('# of Modules')
    ax.set_ylim(0,19.8)
    ax.set_xlim(-.5,len(x)-.5)
    ax.axvline(len(x)-1.5,color='black',linewidth=.5,alpha=0.7)
    ax.axhline(int(max(nmodules)),color='magenta',linestyle=':',alpha=0.7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    for i, bar1, bar2 in zip(range(len(p1)),p1,p2):
        ax.annotate(part_failports[i]+part_errorports[i],
                    xy=(bar1.get_x() + bar1.get_width()/2, bar1.get_height() + bar2.get_height()),
                    xytext=(0,2),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=10, color='red')
    ax.bar_label(p3)
    plt.legend(ncol=2)
    plt.tight_layout()
    os.makedirs('plots',exist_ok=True)
    plt.savefig(f"plots/detail-run{runnum}.pdf")
    plt.show()
    return

#@cli.command()
#@click.option('--runconfig',type=str,required=True)
#@click.option('--stfnumber',default=None)
def hvsmon(runconfig,stfnumber):
    validators = ['HVS_VMon_Fit_R2', 'HVS_VMon_Fit_Slope', 'HVS_IMon_Fit_R2', 'HVS_IMon_Fit_Slope']
    try:
        os.path.exists(runconfig)
    except:
        print('Run json file not found')
        sys.exit(1)

    runnum = int(runconfig.split('/')[-1].split('run_')[-1].split('.json')[0])
    if stfnumber is not None:
        runnum = f'{runnum}_{stfnumber}'
    with open(runconfig,'r') as f:
        jsonfile = json.load(f)

    deggdata = {}
    expectedValues = {}
    for validator in validators:
        deggdata[validator] = []
    for key in jsonfile:
        if 'DEgg' not in key:
            continue
        with open(jsonfile[key],'r') as f:
            deggjson = json.load(f)
        deggserialnumber = deggjson['DEggSerialNumber']
        opendir = ""
        for testitem in deggjson:
            if 'STF' not in testitem:
                continue
            if stfnumber is not None:
                if stfnumber in testitem:
                    opendir = deggjson[testitem]['Folder']
            else:
                opendir = deggjson[testitem]['Folder']
        if opendir == "":
            print(f"{key}: File not found")
        else:
            for channel in range(2):
                item = f'HVMonitors-base-channel-{channel}'
                dirlist = glob.glob(f'{opendir}/{item}*.json')
                if len(dirlist) < 1:
                    continue
                with open(dirlist[0],'r') as f:
                    data = json.load(f)
                for validator in validators:
                    deggdata[validator].append(data['phases'][2]['measurements'][validator]['measured_value'])
                    expectedValues[f'{validator}_min'] = data['metadata']['test_config']['expectedValues'][f'{validator}_min']
                    expectedValues[f'{validator}_max'] = data['metadata']['test_config']['expectedValues'][f'{validator}_max']
    pdf = PdfPages(f'plots/hvsmon-run{runnum}.pdf')
    fig = plt.figure()
    for validator in validators:
        plt.title(f'Run#{runnum}: {validator}')
        plt.hist(deggdata[validator])
        plt.axvline(expectedValues[f'{validator}_min'],linestyle=':',color='magenta')
        plt.axvline(expectedValues[f'{validator}_max'],linestyle=':',color='magenta')
        pdf.savefig()
        fig.clear()
    pdf.close()

#@cli.command()
#@click.option('--runnumbers',type=str,required=True)
def hvsmon_combine(runnumbers):
    validators = ['HVS_VMon_Fit_R2', 'HVS_VMon_Fit_Slope', 'HVS_IMon_Fit_R2', 'HVS_IMon_Fit_Slope']
    hist_min = [0.995,0.9,0.9,0.001]
    hist_max = [1,1.05,1,0.02]
    offset = 0.1

    defaultpath = os.path.expanduser('~/data/json/run/')
    runconfigs = []
    runnums = runnumbers.split(',')
    for runnum in runnums:
        runconfig = defaultpath + f'run_{int(runnum.split("-")[0]):05}.json'
        try:
            os.path.exists(runconfig)
        except:
            print('Run json file not found')
            sys.exit(1)
        runconfigs.append(runconfig)

    alldata = []
    deggdata = {}
    expectedValues = {}
    for runconfig, runnum in zip(runconfigs, runnums):
        for validator in validators:
            deggdata[validator] = []
        runnum_ = runnum.split('-')
        if len(runnum_) == 1:
            stfnumber = None
        else:
            stfnumber = runnum_[-1]
        with open(runconfig,'r') as f:
            jsonfile = json.load(f)

        for key in jsonfile:
            if 'DEgg' not in key:
                continue
            with open(jsonfile[key],'r') as f:
                deggjson = json.load(f)
            deggserialnumber = deggjson['DEggSerialNumber']
            opendir = ""
            for testitem in deggjson:
                if 'STF' not in testitem:
                    continue
                if stfnumber is not None:
                    if stfnumber in testitem:
                        opendir = deggjson[testitem]['Folder']
                        break
                else:
                    opendir = deggjson[testitem]['Folder']
            if opendir == "":
                print(f"{key}: File not found")
            else:
                for channel in range(2):
                    item = f'HVMonitors-base-channel-{channel}'
                    dirlist = glob.glob(f'{opendir}/{item}*.json')
                    if len(dirlist) < 1:
                        for validator in validators:
                            deggdata[validator].append(-1)
                        continue
                    with open(dirlist[0],'r') as f:
                        data = json.load(f)
                    for validator in validators:
                        deggdata[validator].append(data['phases'][2]['measurements'][validator]['measured_value'])
                        expectedValues[f'{validator}_min'] = data['metadata']['test_config']['expectedValues'][f'{validator}_min']
                        expectedValues[f'{validator}_max'] = data['metadata']['test_config']['expectedValues'][f'{validator}_max']
        alldata.append(deggdata.copy())

    fig = plt.figure()
    with PdfPages(f'plots/hvsmon-runs{runnumbers}.pdf') as pdf:
        for validator, hmin, hmax in zip(validators, hist_min, hist_max):
            plt.title(f'Runs#{runnumbers}: {validator}')
            for deggdata in alldata:
                plt.hist(deggdata[validator],bins=30, range=(hmin,hmax),histtype='step')
            plt.axvline(expectedValues[f'{validator}_min'],linestyle=':',color='magenta',lw=.5)
            plt.axvline(expectedValues[f'{validator}_max'],linestyle=':',color='magenta',lw=.5)
            pdf.savefig()
            fig.clear()

    if len(alldata)==2:
        figure = plt.figure(figsize=(6,6))
        with PdfPages(f'plots/hvsmon-runs{runnumbers}_scatter.pdf') as pdf:
            for validator, hmin, hmax in zip(validators, hist_min, hist_max):
                plt.title(f'Runs#{runnumbers}: {validator}')
                plt.plot(np.linspace(hmin,hmax,20),np.linspace(hmin,hmax,20),color='gray',lw=1)
                plt.plot(alldata[0][validator],alldata[1][validator],marker='o',lw=0)
                plt.xlabel(runnums[0])
                plt.ylabel(runnums[1])
                plt.xlim(hmin,hmax)
                plt.ylim(hmin,hmax)
                pdf.savefig()
                figure.clear()

def getHVdata():
    alldata = []
    deggdata = {}
    expectedValues = {}
    for runconfig, runnum in zip(runconfigs, runnums):
        for validator in validators:
            deggdata[validator] = []
        runnum_ = runnum.split('-')
        if len(runnum_) == 1:
            stfnumber = None
        else:
            stfnumber = runnum_[-1]
        with open(runconfig,'r') as f:
            jsonfile = json.load(f)

        for key in jsonfile:
            if 'DEgg' not in key:
                continue
            with open(jsonfile[key],'r') as f:
                deggjson = json.load(f)
            deggserialnumber = deggjson['DEggSerialNumber']
            opendir = ""
            for testitem in deggjson:
                if 'STF' not in testitem:
                    continue
                if stfnumber is not None:
                    if stfnumber in testitem:
                        opendir = deggjson[testitem]['Folder']
                        break
                else:
                    opendir = deggjson[testitem]['Folder']
            if opendir == "":
                print(f"{key}: File not found")
            else:
                for channel in range(2):
                    item = f'HVMonitors-base-channel-{channel}'
                    dirlist = glob.glob(f'{opendir}/{item}*.json')
                    if len(dirlist) < 1:
                        continue
                    with open(dirlist[0],'r') as f:
                        data = json.load(f)
                    for validator in validators:
                        deggdata[validator].append(data['phases'][2]['measurements'][validator]['measured_value'])
                        expectedValues[f'{validator}_min'] = data['metadata']['test_config']['expectedValues'][f'{validator}_min']
                        expectedValues[f'{validator}_max'] = data['metadata']['test_config']['expectedValues'][f'{validator}_max']
        alldata.append(deggdata.copy())
    return alldata

#@cli.command()
def imonslope():
    with open('imon_slope.dat','r') as f:
        datalist = f.readlines()
    values = []
    for data in datalist:
        d = data.split('\n')
        value = float(d[0])
        values.append(value)

    ax = plt.figure().gca()
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.hist(values,bins=40,range=(0,0.02),label="Vendor (batch-2)")
    plt.ylabel('# of channels')
    plt.xlabel('HVS_IMon_Fit_Slope')
    plt.axvline(0.001,ls=':',color='magenta')
    plt.axvline(0.01,ls=':',color='magenta')
    ax.set_xticks(np.linspace(0,0.02,6))
    plt.legend()
    plt.tight_layout()
    plt.savefig('imon_slope.pdf')
    plt.show()

#@cli.command()
def cameraspi():
    with open('camera_spi_failure.dat','r') as f:
        datalist = f.readlines()
    values = []
    for data in datalist:
        d = data.split('\n')
        value = float(d[0])
        values.append(value if value>0 else 1e-5)

    values = np.array(values)
    ax = plt.figure().gca()
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.hist(np.log10(values),bins=50,range=(-5,0),label='Cycles-3 & 4')
    plt.ylabel('# of camera modules')
    plt.xlabel('$\log_{10}$(spi_failure_rate)')
    plt.axvline(-4,ls=':',color='magenta')
    plt.xlim(-5,0)
    plt.yscale('log')
    plt.legend()
    plt.tight_layout()
    plt.savefig('camera_spi_failure.pdf')
    plt.show()

#@cli.command()
#@click.option('--jsonlist',required=True)
def imonmeas(jsonlist):
    idata = []
    setvdata = []
    with open(jsonlist,'r') as f:
        fnames = f.readlines()
    for fname_ in fnames:
        for channel in range(2):
            fname = fname_.split('\n')[0]
            with open(glob.glob(f'{fname}/HVMonitors-base-channel-{channel}*.json')[0],'r') as f:
                data = json.load(f)
                setv  = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
                measi = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current']
                plt.plot(setv,measi)
    plt.xlabel('Set Voltage [V]')
    plt.ylabel('Measured Current [$\mu$A]')
    plt.xlim(500,1600)
    plt.ylim(0,15)
    plt.tight_layout()
    plt.savefig('Imon_curves.pdf')
    plt.show()

#@cli.command()
#@click.option('--jsonlink',required=True)
#@click.option('--prod',is_flag=True,default=False)
def icurvechannel(jsonlink,prod):
    pdf = PdfPages(f'plots/Icurve_{jsonlink.split("/")[-1]}.pdf')
    fig = plt.figure()
    if prod:
        for i in ['icehap-mouse2-1','icecube-X4-i5Chiba1']:
            for channel in range(2):
                for link in tqdm(glob.iglob(f'{jsonlink}/*/degg-*')):
                    snum, data = getHVMonData(link, channel)
                    if snum is None:
                        continue
                    try:
                        station = data['metadata']['config']['station_id']
                    except:
                        continue
                    if station != i:
                        continue
                    setv  = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
                    measi = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current']
                    plt.plot(setv,measi)
                plt.xlabel('Set Voltage [V]')
                plt.ylabel('Measured Current [$\mu$A]')
                plt.xlim(0,1600)
                plt.ylim(0,18)
                plt.title(f'Channel-{channel}')
                pdf.savefig()
                fig.clear()
    else:
        for channel in range(2):
            for link in tqdm(glob.iglob(f'{jsonlink}/*/degg-*')):
                snum, data = getHVMonData(link, channel)
                if snum is None:
                    continue
                setv  = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
                measi = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current']
                plt.plot(setv,measi)
            plt.xlabel('Set Voltage [V]')
            plt.ylabel('Measured Current [$\mu$A]')
            plt.xlim(0,1600)
            plt.ylim(0,18)
            plt.title(f'Channel-{channel}')
            pdf.savefig()
            fig.clear()
    pdf.close()
    return

#@cli.command('singleivcurve',short_help='make IV curve plot of <port> from <runconfig>')
#@click.option('--runconfig',type=str,required=True)
#@click.option('--stfnumber',type=int,required=True)
#@click.option('--port',type=int,required=True)
#@click.option('--channel',type=int,required=True)
def singleivcurve(runconfig, stfnumber, port, channel):
    try:
        os.path.exists(runconfig)
    except:
        print('Run json file not found')
        sys.exit(1)

    runnum = int(runconfig.split('/')[-1].split('run_')[-1].split('.json')[0])
    if stfnumber is not None:
        runnum = f'{runnum}_{stfnumber}'
        print(runnum)
    with open(runconfig,'r') as f:
        jsonfile = json.load(f)
    comment = jsonfile['comment']

    for key in jsonfile:
        if 'DEgg' not in key:
            continue
        with open(jsonfile[key],'r') as f:
            deggjson = json.load(f)
        deggserialnumber = deggjson['DEggSerialNumber']
        opendir = ""
        for testitem in deggjson:
            if 'STF' not in testitem:
                continue
            if stfnumber is not None:
                if f'{int(stfnumber):02}' in testitem:
                    opendir = deggjson[testitem]['Folder']
                    print(testitem)
            else:
                opendir = deggjson[testitem]['Folder']
        if (opendir == "") or (opendir == 'None'):
            print(f"{deggserialnumber}: File not found")
        else:
            dirlist = glob.glob(f'{opendir}/HVMonitors-base-channel-{channel}*.json')
            if len(dirlist) < 1:
                continue
            with open(dirlist[0],'r') as f:
                data = json.load(f)
            if data['metadata']['stf_config']['iceboot']['port'] != port:
                continue
            break

    setv  = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
    measi = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current']
    measv = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_voltage']

    fig = plt.figure(figsize=(9.6,4.8))
    ax1 = fig.add_subplot(111)
    ax1.plot(setv,measv,marker='o',label='Voltage',color='tab:blue')
    ax2 = ax1.twinx()
    ax2.plot(setv,measi,marker='o',label='Current',color='tab:orange')

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1+h2, l1+l2, loc='upper left')

    plt.title(f'Run#{runnum}, port {port}, channel {channel}')
    ax1.set_xlabel('Set Voltage [V]')
    ax1.set_ylabel('Measured Voltage [V]')
    ax2.set_ylabel('Measured Current [$\mu$A]')
    ax2.set_ylim(0,20)
    plt.tight_layout()
    plt.savefig(f'plots/IVsingle_{runnum}_{port}_{channel}.pdf')
    plt.show()


#@cli.command()
#@click.option('--jsonlink',required=True)
#@click.option('--channel',required=True)
#def singleivcurve(jsonlink,channel):
#    with open(glob.glob(f'{jsonlink}/HVMonitors-base-channel-{channel}*.json')[0],'r') as f:
#        data = json.load(f)
#    setv  = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
#    measi = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current']
#    measv = data['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_voltage']
#    fig = plt.figure(figsize=(9.6,4.8))
#    ax1 = fig.add_subplot(111)
#    ax1.plot(setv,measv,marker='o',label='Voltage',color='tab:blue')
#    ax2 = ax1.twinx()
#    ax2.plot(setv,measi,marker='o',label='Current',color='tab:orange')
#
#    h1, l1 = ax1.get_legend_handles_labels()
#    h2, l2 = ax2.get_legend_handles_labels()
#    ax1.legend(h1+h2, l1+l2, loc='upper left')
#
#    ax1.set_xlabel('Set Voltage [V]')
#    ax1.set_ylabel('Measured Voltage [V]')
#    ax2.set_ylabel('Measured Current [$\mu$A]')
#    plt.tight_layout()
#    plt.savefig('IVsingle.pdf')
#    plt.show()


#@cli.command()
#@click.option('--jsonlist',required=True)
def imonparam(jsonlist):
    vr2 = []
    ir2 = []
    with open(jsonlist,'r') as f:
        fnames = f.readlines()
    for fname_ in fnames:
        fname = fname_.split('\n')[0]
        for channel in range(2):
            with open(glob.glob(f'{fname}/HVMonitors-base-channel-{channel}*.json')[0],'r') as f:
                data = json.load(f)
            vmonr2 = data['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
            imonr2 = data['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
            if vmonr2 < 0.999:
                print(data['metadata']['device']['dut_serial'], vmonr2)
            vr2.append(vmonr2)
            ir2.append(imonr2)
    plt.hist(vr2,bins=10000,range=(0,1),label='VMon')
    plt.hist(ir2,bins=10000,range=(0,1),label='IMon')
    plt.xlabel('$R^2$')
    plt.ylabel('Entry')
    plt.axvline(1,lw=1,ls=':',color='black')
    plt.axvline(0.9,lw=1,ls=':',color='tab:orange')
    plt.axvline(0.999,lw=1,ls=':',color='tab:blue')
    plt.xlim(.89,1.01)
    plt.yscale('log')
    plt.legend(loc='upper left')
    plt.tight_layout()
    plt.savefig('r2.pdf')
    plt.show()

#@cli.command()
#@click.option('--rsquared',type=str,default=None,help='"fat", "nme", or "measurements" (fat-nme).')
def ivcurves(rsquared):
    pdf = PdfPages(f'plots/compareR2_{rsquared}.pdf' if rsquared is not None else 'plots/compareIV.pdf')
    if rsquared is not None:
        fig = plt.figure(figsize=(6.4,6.4))
        plt.subplots_adjust(left=0.12, right=0.92, top=0.92, bottom=0.12)
    else:
        fig = plt.figure()
        plt.subplots_adjust(left=0.12, right=0.9, top=0.92, bottom=0.1)

    ax1 = fig.add_subplot(111)
    for nmedir in tqdm(glob.iglob('data/NME-Sealing/*/degg-*')):
        for channel in range(2):
            snum, nmedata = getHVMonData(nmedir, channel)
            if snum is None:
                continue
            fatsnum = None
            prodsnum = None
            for fatdir in glob.iglob('data/DEgg-FAT/*/degg-*'):
                fatsnum, fatdata = getHVMonData(fatdir, channel)
                if fatsnum is None:
                    continue
                if snum == fatsnum:
                    break
            for proddir in glob.iglob('data/DEgg-MB-Prod/*/degg-*'):
                prodsnum, proddata = getHVMonData(proddir, channel)
                if prodsnum is None:
                    continue
                if snum == prodsnum:
                    break
            if prodsnum is None:
                for proddir in glob.iglob('data/DEgg-MB-Prod_batch1/*/degg-*'):
                    prodsnum, proddata = getHVMonData(proddir, channel)
                    if prodsnum is None:
                        continue
                    if snum == prodsum:
                        break
            #if snum!=fatsnum:
            #    continue
            if snum!=prodsnum:
                continue

            if rsquared is not None:
                if rsquared == 'nme':
                    prodVRsq = 1-proddata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                    prodIRsq = 1-proddata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                    try:
                        VRsq = 1-nmedata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                        IRsq = 1-nmedata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                    except KeyError:
                        continue
                elif rsquared == 'fat':
                    prodVRsq = 1-proddata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                    prodIRsq = 1-proddata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                    VRsq = 1-fatdata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                    IRsq = 1-fatdata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                elif rsquared == 'measurements':
                    try:
                        prodVRsq = 1-nmedata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                        prodIRsq = 1-nmedata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                    except KeyError:
                        continue
                    VRsq = 1-fatdata['phases'][2]['measurements']['HVS_VMon_Fit_R2']['measured_value']
                    IRsq = 1-fatdata['phases'][2]['measurements']['HVS_IMon_Fit_R2']['measured_value']
                else:
                    continue

                ax1.plot([prodVRsq],[VRsq],marker='o',color='tab:blue')
                ax1.plot([prodIRsq],[IRsq],marker='o',color='tab:orange')
                continue

            ax2 = ax1.twinx()

            ax1.set_xlabel('Set Voltage [V]')
            ax1.set_ylabel('Measured Voltage [V]')
            ax2.set_ylabel('Measured Current [$\mu$A]')
            try:
                nmesetv  = nmedata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
            except KeyError:
                fig.clear()
                ax1 = fig.add_subplot(111)
                continue
            ax1.plot(nmesetv,nmedata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_voltage'],color='tab:blue',ls='solid')
            ax2.plot(nmesetv,nmedata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current'],color='tab:orange',ls='solid')

            ax2.plot([],[],color='gray',ls='solid',label='NME')
            if snum==fatsnum:
                fatsetv  = fatdata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
                ax1.plot(fatsetv,fatdata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_voltage'],color='tab:blue',ls='--')
                ax2.plot(fatsetv,fatdata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current'],color='tab:orange',ls='--')
                ax2.plot([],[],color='gray',ls='--',label='FAT')
            if snum==prodsnum:
                prodsetv  = proddata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['set_voltage']
                ax1.plot(prodsetv,proddata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_voltage'],color='tab:blue',ls=':')
                ax2.plot(prodsetv,proddata['phases'][2]['measurements']['HVS_Monitors']['measured_value']['meas_current'],color='tab:orange',ls=':')
                ax2.plot([],[],color='gray',ls=':',label='Prod')

            legend = ax2.legend(loc='lower right')
            ax1.set_xlabel('Set Voltage [V]')
            ax1.set_ylabel('Measured Voltage [V]',color='tab:blue')
            ax2.set_ylabel('Measured Current [$\mu$A]',color='tab:orange')
            plt.title(f'{snum}: HVMonitors for channel-{channel}')
            ax1.set_xlim(0,1600)
            ax1.set_ylim(0,1600)
            ax2.set_ylim(0,16)
            ax2.spines['left'].set_color('tab:blue')
            ax2.spines['right'].set_color('tab:orange')
            ax1.tick_params(axis='y',colors='tab:blue')
            ax2.tick_params(axis='y',colors='tab:orange')
            pdf.savefig()
            fig.clear()
            ax1 = fig.add_subplot(111)

    if rsquared is not None:
        ax1.set_xlim(1.e-7,1)
        ax1.set_ylim(1.e-7,1)
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.invert_xaxis()
        ax1.invert_yaxis()
        label = 'NME' if rsquared == 'measurements' else 'PULAX'
        ax1.set_xlabel(f'$(1-R^2)$ at {label}')
        label = 'NME' if rsquared == 'nme' else 'FAT'
        ax1.set_ylabel(f'$(1-R^2)$ at {label}')
        ax1.plot([],[],marker='o',lw=0,color='tab:blue',label='Voltage')
        ax1.plot([],[],marker='o',lw=0,color='tab:orange',label='Current')
        ax1.legend()
        pdf.savefig()
    pdf.close()
    return

def getHVMonData(dirname, channel):
    lslist = glob.glob(f'{dirname}/HVMonitors-base-channel-{channel}*.json')
    if len(lslist) < 1:
        return None, None
    with open(lslist[0],'r') as f:
        data = json.load(f)
    try:
        snum = data['metadata']['device']['dut_serial']
    except KeyError:
        return None, None
    return snum, data


#@cli.command()
#@click.option('--jsonlist',required=True)
#@click.option('--dep',is_flag=True)
def lvsmeas(jsonlist,dep):
    ch0 = []
    ch1 = []
    ch2 = []
    ch3 = []
    ch4 = []
    with open(jsonlist,'r') as f:
        fnames = f.readlines()
    for fname_ in fnames:
        fname = fname_.split('\n')[0]
        with open(glob.glob(f'{fname}/PowerLVS*.json')[0],'r') as f:
            data = json.load(f)
            v0 = data['phases'][2]['measurements']['chan_00']['measured_value']
            v1 = data['phases'][2]['measurements']['chan_01']['measured_value']
            v2 = data['phases'][2]['measurements']['chan_02']['measured_value']
            v3 = data['phases'][2]['measurements']['chan_03']['measured_value']
            v4 = data['phases'][2]['measurements']['chan_04']['measured_value']
            ch0.append(v0 if v0 is not None else -60)
            ch1.append(v1 if v1 is not None else -60)
            ch2.append(v2 if v2 is not None else -60)
            ch3.append(v3 if v3 is not None else -60)
            ch4.append(v4 if v4 is not None else -60)

    v = [ch0,ch1,ch2,ch3,ch4]

    if dep:
        ax = plt.figure().gca()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        for i in range(len(v)):
            plt.plot(np.arange(len(v[i])),v[i],label=f'Ch-{i}',marker='o')
        plt.xlabel('Test Number')
        plt.ylabel('Monitored Current [mA]')
        plt.ylim(0,1200)
        plt.legend()
        plt.tight_layout()
        plt.savefig('lvs_dep.pdf')
        plt.show()
        return

    for i in range(len(v)):
        plt.hist(v[i], bins=210,range=(-60,1200),label=f'Ch-{i}',histtype='step',lw=1)
    plt.xlabel('Monitored Current [mA]')
    plt.ylabel('Entry')
    plt.legend()
    plt.tight_layout()
    plt.savefig('lvsmeas.pdf')
    plt.show()

if __name__=='__main__':
    #cli()
    main()
