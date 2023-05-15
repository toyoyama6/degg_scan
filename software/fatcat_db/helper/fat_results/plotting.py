#!/usr/bin/env python

import os
import argparse

import numpy as np
import matplotlib
from matplotlib import pyplot as plt
plt.rcParams.update({'figure.max_open_warning': 0})
from datetime import datetime
from dateutil import parser

# py2-3 compat
try:
    input = raw_input
except NameError:
    pass

from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader



def main():

    cmdParser = argparse.ArgumentParser()
    cmdParser.add_argument('-t', '--test', dest='testdb', action='store_true',
                           help='Force use of the test database')
    cmdParser.add_argument('-nt', '--no-tunnel', dest='tunnel', action='store_false',
                           help='Do not port forward mongodb server')
    
    args = cmdParser.parse_args()

    # open ssh tunnel to mongo port
    if args.tunnel:
        tunnel = Tunnel()

    # connect to mongo
    if args.testdb:
        mongo = MongoReader(database='production_calibration_test')
        run = 130
        uid = 'DEgg2020-2-033_v1'
    else:
        mongo = MongoReader(database='production_calibration')
        run = 136
        uid = 'DEgg2021-3-017_v1'
    if not mongo.isConnected:
        return

    measurements = mongo.getFatMeasurements(uid, run)
    plt.ion()
    for doc in measurements:
        ShowMeas(doc, mongo).plot()
    input('[Enter] to quit')
    
    return


def toFloat(x):
    return [float(i) for i in x]


def toFloat2d(x):
    floats = []
    for i in x:
        floats.append([float(j) for j in i])
    return floats


class ShowMeas:
    def __init__(self, meas_doc, mongo=False):
        self.meas_doc = meas_doc
        self.mongo = mongo
        self.device_uid = meas_doc['device_uid']
        if self.mongo:
            self.nickname = self.mongo.getNickname(self.device_uid)
        else:
            self.nickname = ''
        if 'subdevice_uid' in meas_doc:
            self.subdevice_uid = meas_doc['subdevice_uid']
            self.device = self.subdevice_uid
        else:
            self.subdevice_uid = ''
            self.device = self.device_uid

        self.plotsize = (18, 8)
        self.scatsize = (12, 8)
        if self.nickname:
            self.title = ('{0}  {1}'.format(self.nickname, self.device))
        else:
            self.title = ('{0}'.format(self.device))
        self.tfs = 22  # title fontsize
        self.lfs = 20  # label fontsize
        self.als = 18  # axis labelsize

        
    def plot(self):
        if self.mongo:
            for meas in self.meas_doc['meas_data']:
                if 'goalpost' in meas and meas['data_format'] == 'value':
                    self.printPassFail(meas)
                else:
                    self.plotMeasurement(meas)
        else:
            for meas in self.meas_doc['meas_data']:  
                self.plotMeasurement(meas)

                
    def printPassFail(self, meas):
        passed, goalpost = self.getPassFail(meas)
        if passed is None:
            return

        PF = 'PASS' if passed else 'FAIL'
                
        print('{0} : {1} {2} {3} ({4} = {5}) - value = {6}'
              .format(PF,
                      self.getTemp(meas),
                      self.device,
                      self.goalpost_name.split('_')[-1],
                      self.goalpost_type,
                      goalpost['goalpost_testbounds'] if goalpost else 'UNDEFINED',
                      round(meas['value'], 2)))
        
        return
    

    def getPassFail(self, meas):
        if 'goalpost' not in meas:
            return None, []

        goalpost = self.getValidGoalpost(meas)
        if not goalpost:
            return False, []

        passed = True
        if self.goalpost_type == 'in-range':
            if not (meas['value'] >= goalpost['goalpost_testbounds'][0] \
               and meas['value'] <= goalpost['goalpost_testbounds'][1]):
                passed = False
        elif self.goalpost_type == 'min':
            if not meas['value'] >= goalpost['goalpost_testbounds']:
                passed = False
        elif self.goalpost_type == 'max':
            if not meas['value'] <= goalpost['goalpost_testbounds']:
                passed = False
        elif self.goalpost_type == 'equals':
            if not meas['value'] == goalpost['goalpost_testbounds']:
                passed = False
        else:
            print('WARNING: test type [{0}] is not defined in getPassFail()'
                  .format(self.goalpost_type))
            passed = False
        
        return passed, goalpost

    
    def getValidGoalpost(self, meas):
        if 'goalpost' not in meas:
            return []
        
        self.goalpost_name = meas['goalpost'][0]['testname']
        self.goalpost_type = meas['goalpost'][0]['testtype']

        if self.mongo:
            goalposts = self.mongo.getGoalposts(self.goalpost_name, self.goalpost_type)
        else:
            print('WARNING: no connection to mongo, cannot get goalposts')
            return []

        if not goalposts:
            # this can be too verbose
            #print('WARNING: no goalpost in database for [{0}] [{1}]'
            #      .format(self.goalpost_name, self.goalpost_type))
            return []
        elif len(goalposts) == 1:
            goalpost = goalposts[0]
        else:
            goalpost = goalposts[0]
            for doc in goalposts:
                if parser.parse(doc['valid_date']) > parser.parse(goalpost['valid_date']):
                    goalpost = doc
        return goalpost


    def getTemp(self, meas):
        if 'temperature' in meas:
            TC = (round(meas['temperature'], 1))
        else:
            TC = '?'
        return '[{0} C]'.format(TC)

    
    def plotMeasurement(self, meas):
        data_format = meas['data_format']
        
        if 'title' in meas:
            # make sure it's not an empty string
            if meas['title'].split():
                self.plot_title = '{0} -- {1}'.format(self.title, meas['title'])
            else:
                self.plot_title = '{0}'.format(self.title)
        else:
            self.plot_title = '{0}'.format(self.title)
        
        # include temperature of the measurement
        TC = self.getTemp(meas)
        self.plot_title = '{0}  {1}'.format(TC, self.plot_title)
        
        if data_format == 'value':
            self.printValue(meas)

        elif data_format == 'hist':
            self.plotHist(meas)

        elif data_format == 'hist-with-fit':
            self.plotHistFit(meas)

        elif data_format == 'graph':
            self.plotGraph(meas)

        elif data_format == 'graph-with-fit':
            self.plotGraphFit(meas)

        elif data_format == 'fixed-x-graph':
            self.plotFixedXGraph(meas)

        elif data_format == 'twin-axis-graph':
            self.plotTwinAxisGraph(meas)

        elif data_format == 'shared-x-multi-graph':
            self.plotSharedXMultiGraph(meas)

        elif data_format == 'data3d':
            if 'projection' in meas:
                if meas['projection'] == 'hist2d':
                    self.plotHist2d(meas)
                elif meas['projection'] == 'bubble':
                    self.plotBubble(meas)
                elif meas['projection'] == 'scatter':
                    self.plotScatter(meas)
                else:
                    self.plotScatter(meas)
            else:
                self.plotScatter(meas)

        elif data_format == 'meshgrid':
            self.plotMeshGrid(meas)

        elif data_format == 'monitoring':
            self.plotMonitoring(meas)

        else:
            print('unknown meas data format -->', data_format)


    def printValue(self, data):
        outstring = '{0} -- {1} = {2}'.format(self.plot_title, data['label'], data['value'])
        #outstring = '{0} -- '.format(self.plot_title)
        #outstring += '{0} = {1}'.format(data['label'], data['value'])
        if 'error' in data:
            outstring += ' +/- {0}'.format(data['error'])
        #outstring += '[{0}C]'.format(data['temperature'])
        print(outstring)
        

    def plotHist(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        x = np.linspace(data['x_min'], data['x_max'], num=data['n_bins'], endpoint=False)
        y = toFloat(data['y_values'])

        plt.hist(x, weights=y, bins=data['n_bins'], range=[data['x_min'], data['x_max']],
                color='blue', histtype='step')

        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        if 'y_label' in data:
            plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        else:
            plt.ylabel('counts', fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        
        
    def plotGraph(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y = toFloat(data['y_values'])

        if 'y_errors' in data:
            plt.errorbar(x, y, yerr=data['y_errors'],
                        marker='o', linestyle='', color='blue')
        else:
            plt.plot(x, y, 
                     marker='o', linestyle='', color='blue')

        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        
        
    def plotFixedXGraph(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # create x-axis values
        x = np.linspace(data['x_min'], data['x_max'], num=data['n_points'], endpoint=False)
        y = toFloat(data['y_values'])

        if 'y_errors' in data:
            plt.errorbar(x, y, yerr=data['y_errors'],
                        marker='o', linestyle='', color='blue')
        else:
            plt.plot(x, y,
                     marker='o', linestyle='', color='blue')

        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotTwinAxisGraph(self, data):
        fig, ax1 = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y1 = toFloat(data['y1_values'])
        y2 = toFloat(data['y2_values'])

        # primary y axis data
        plt.sca(ax1)
        if 'y1_errors' in data:
            plt1 = ax1.errorbar(x, y1, yerr=data['y1_errors'], 
                        marker='o', linestyle='', color='blue',
                        label=data['y1_label'])
        else:
            plt1 = ax1.plot(x, y1, 
                    marker='o', linestyle='', color='blue',
                    label=data['y1_label'])

        ax1.set_xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        ax1.set_ylabel(data['y1_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        
        # log scale?
        #ax1.set_yscale('log')
        
        # secondary y axis data
        ax2 = ax1.twinx()
        plt.sca(ax2)
        if 'y2_errors' in data:
            plt2 = ax2.errorbar(x, y2, yerr=data['y2_errors'], 
                        marker='o', linestyle='', color='green',
                        label=data['y2_label'])
        else:
            plt2 = ax2.plot(x, y2, 
                    marker='o', linestyle='', color='green',
                    label=data['y2_label'])

        ax2.set_xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        ax2.set_ylabel(data['y2_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        
        # put labels into one legend
        plts = plt1 + plt2
        lbls = [l.get_label() for l in plts]
        ax1.legend(plts, lbls, loc='best', fontsize=18)

        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotSharedXMultiGraph(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        x = data['x_values']

        for yobj in data['y_data']:
            y = yobj['values']
            if 'errors' in yobj:
                plt.errorbar(x, y, yerr=yobj['errors'],
                             marker='o', linestyle='-', label=yobj['label'])
            else:
                plt.plot(x, y, 
                         marker='o', linestyle='-', label=yobj['label'])

        plt.legend(loc='best', fontsize=self.lfs)
        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        
        
    def plotScatter(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.scatsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y = toFloat(data['y_values'])
        z = toFloat(data['z_values'])

        plt.scatter(x, y, c=z, cmap='jet')

        cbar = plt.colorbar(pad=0.01)
        cbar.set_label(data['z_label'], fontsize=self.lfs, fontweight='bold')
        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotHist2d(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.scatsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y = toFloat(data['y_values'])
        z = toFloat(data['z_values'])

        zs, xs, ys = np.histogram2d(x, y, weights=z)
        # mask zeros for better viewing
        mask = np.ma.masked_where(zs==0, zs).T
        plt.pcolormesh(xs, ys, mask, cmap='jet')

        cbar = plt.colorbar(pad=0.01)
        cbar.set_label(data['z_label'], fontsize=self.lfs, fontweight='bold')
        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotBubble(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.scatsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y = toFloat(data['y_values'])
        z = toFloat(data['z_values'])

        plt.scatter(x, y,
                    s=np.asarray(z),
                    c=np.asarray(z),
                    alpha=0.8,
                    marker='o',
                    cmap='jet'
                    )

        cbar = plt.colorbar(pad=0.01)
        cbar.set_label(data['z_label'], fontsize=self.lfs, fontweight='bold')
        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotMeshGrid(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.scatsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        x = np.linspace(data['x_min'], data['x_max'], num=data['x_bins'], endpoint=False)
        y = np.linspace(data['y_min'], data['y_max'], num=data['y_bins'], endpoint=False)
        z = toFloat2d(data['z_values'])

        xx, yy = np.meshgrid(x, y)
        plt.pcolormesh(xx, yy, z, cmap='jet')

        cbar = plt.colorbar(pad=0.01)
        cbar.set_label(data['z_label'], fontsize=self.lfs, fontweight='bold')
        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        

    def plotMonitoring(self, data):
        moni = data['monitoring']
        times = data['moni_times']

        for obj in moni:
            varname = obj['moni_name']
            try:
                Y = toFloat(obj['moni_data'])
            except:
                print('Could not convert to float -->', varname)
                continue

            fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
            plt.sca(ax)

            plt.plot(times, Y, marker='o', linestyle='', color='blue')

            plt.xlabel('Unix Time (s)', fontsize=self.lfs, fontweight='bold')
            plt.ylabel(varname, fontsize=self.lfs, fontweight='bold')
            plt.tick_params(axis='both', which='major', labelsize=self.als)
            plt.tight_layout()
            

    def plotGraphFit(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        # cast data to float (just in case)
        x = toFloat(data['x_values'])
        y = toFloat(data['y_values'])

        if 'y_errors' in data:
            plt.errorbar(x, y, yerr=data['y_errors'],
                        marker='o', linestyle='', color='blue',
                        label='data')
        else:
            plt.plot(x, y, 
                    marker='o', linestyle='', color='blue',
                    label='data')

        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        
        # plot fit values
        fx = np.linspace(data['fit_x_min'], data['fit_x_max'], num=data['fit_n_points'], endpoint=False)
        fy = toFloat(data['fit_y_values'])
        plt.plot(fx, fy,
                marker='', linestyle='-', color='red',
                label='fit')
        plt.legend(loc='best', fontsize=18)


    def plotHistFit(self, data):
        fig, ax = plt.subplots(1, 1, figsize=self.plotsize, facecolor='w', edgecolor='k')
        plt.sca(ax)

        x = np.linspace(data['fit_x_min'], data['fit_x_max'], num=data['fit_n_bins'], endpoint=False)
        y = toFloat(data['y_values'])

        plt.hist(x, weights=y, bins=data['n_bins'], range=[data['x_min'], data['x_max']],
                color='blue', histtype='step',
                label='data')

        plt.xlabel(data['x_label'], fontsize=self.lfs, fontweight='bold')
        if 'y_label' in data:
            plt.ylabel(data['y_label'], fontsize=self.lfs, fontweight='bold')
        else:
            plt.ylabel('counts', fontsize=self.lfs, fontweight='bold')
        plt.tick_params(axis='both', which='major', labelsize=self.als)
        plt.title(self.plot_title, fontsize=self.tfs, fontweight='bold')
        plt.tight_layout()
        
        # plot fit values
        fx = np.linspace(data['fit_x_min'], data['fit_x_max'], num=data['fit_n_bins'], endpoint=False)
        fy = toFloat(data['fit_y_values'])
        plt.plot(fx, fy,
                marker='', linestyle='-', color='red',
                label='fit')
        plt.legend(loc='best', fontsize=18)


if __name__ == "__main__":
    main()

