#!/usr/bin/env python

import os
import argparse
import datetime
import time

# py2-3 compat
try:
    input = raw_input
except NameError:
    pass

from fatcat_db.utils import *
from fatcat_db.filetools import globJSONFiles
from fatcat_db.forwarder import Tunnel
from fatcat_db.mongoreader import MongoReader
from fatcat_db.runchecks import RunChecks, Insert
_here = os.path.dirname(os.path.abspath(__file__))


def main():

    cmdParser = argparse.ArgumentParser()
    cmdParser.add_argument(dest='jsonfiles', type=str, nargs='+',
                           help='Specify one or multiple json files. '
                           'Multiple paths and wildcards are excepted.')
    cmdParser.add_argument('-i', '--insert', dest='insert', action='store_true',
                           help='Insert data into the mongo database')
    cmdParser.add_argument('-p', '--production', dest='production', action='store_true',
                           help='Force use of the production database')
    cmdParser.add_argument('-nt', '--no-tunnel', dest='tunnel', action='store_false',
                           help='Do not port forward mongodb server')
    cmdParser.add_argument('-q', '--quiet', dest='quiet', action='store_true',
                           help='Only show warnings and errors')
    cmdParser.add_argument('-d', '--debug', dest='debug', action='store_true',
                           help='Show debug output')
    cmdParser.add_argument('-t', '--timer', dest='timer', action='store_true',
                           help='Time the RunChecks/Insert operation')

    args = cmdParser.parse_args()

    # quiet the output
    if args.quiet: setVerbosity('warning')
    # show debug output
    if args.debug: setVerbosity('debug')

    # glob the files
    jsonfiles = globJSONFiles(args.jsonfiles)
    if not jsonfiles:
        print('No file(s) found')
        return

    # open ssh tunnel to mongo port
    if args.tunnel:
        tunnel = Tunnel()

    # connect to mongo
    if args.production:
        mongo = MongoReader(database='production_calibration')
    else:
        mongo = MongoReader()
    if not mongo.isConnected:
        return

    nowstr = (datetime.datetime.now()).strftime("%Y-%m-%d_%H%M%S")

    for jsonfile in jsonfiles:
        if args.insert:
            if args.timer:
                tstart = time.time()
            rc = Insert(jsonfile, mongo)
            if args.timer:
                tstop = time.time()
                print('Timer = {0} seconds'.format(round(tstop-tstart, 1)))
            if rc.ObjectId is not None:
                print("ObjectId = {0}".format(rc.ObjectId))
                if rc.json_type == 'measurement':
                    # write measurement object ids to file
                    with open(os.path.join(_here, 'object-ids_'+nowstr+'.dat'), 'a') as idf:
                        idf.write('{0}, {1}\n'.format(jsonfile, rc.ObjectId))
            else:
                # write failed json filenames to file
                with open(os.path.join(_here, 'failed-inserts_'+nowstr+'.dat'), 'a') as ff:
                    ff.write('{0}\n'.format(jsonfile))

        else:
            if args.timer:
                tstart = time.time()
            rc = RunChecks(jsonfile, mongo)
            if args.timer:
                tstop = time.time()
                print('Timer = {0} seconds'.format(round(tstop-tstart, 1)))
            if rc.passed:
                print(Color.bold+'Use -i or --insert to really insert'+Color.reset)

    return


if __name__ == "__main__":
    main()

