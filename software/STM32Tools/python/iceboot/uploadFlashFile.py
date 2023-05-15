#!/usr/bin/env python

from iceboot.iceboot_session import getParser, startIcebootSession
from optparse import OptionParser
import sys
import os


def main():
    parser = OptionParser()
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default="192.168.0.10")
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default="5012")
    parser.add_option("--debug", dest="debug", action="store_true",
                      help="Print board I/O stdout", default=False)
    parser.add_option("--file", dest="file", help="File to write to flash",
                      default=None)
    parser.add_option("--name", dest="name", default=None,
                      help="Optional name for file on flash.  Default is the filename")
    
    (options, args) = parser.parse_args()

    def bail(errMsg):
        print(errMsg)
        parser.print_help()
        sys.exit(1)

    if (options.file is None):
        bail("File not specified")

    infile = os.path.expanduser(options.file)
    if not os.path.exists(infile):
        bail("File \"%s\" does not exist" % options.file)

    flashName = infile.split('/')[-1]
    if options.name is not None:
        flashName = options.name

    if len(flashName) == 0:
        bail("Invalid zero-length flash name" % flashName)
    if len(flashName) > 32:
        bail("File name %s too long (32 characters max)" % flashName)

    session = startIcebootSession(parser)
    session.ymodemFlashUpload(flashName, infile)
    return 0

if __name__ == "__main__":
    main()