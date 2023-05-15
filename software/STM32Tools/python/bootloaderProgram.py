#!/usr/bin/env python3
from optparse import OptionParser
import sys
from iceboot import iceboot_session_cmd
import ymodem
import socket
import fcntl
import os
import select

BOOTLOADER_PROMPT = "\r\n# "


def read_next(comms, n_bytes=128, timeout=1):
        rdy = select.select([comms], [], [], timeout)        

        if rdy[0]:
            recv_bytes = comms.recv(n_bytes)
            return recv_bytes
        else:
            raise IOError('Timeout!')


def read_n(comms, n_bytes, timeout=1):
        buf = bytearray()
        while len(buf) < n_bytes:
            buf.extend(read_next(comms, n_bytes - len(buf), timeout=timeout))

        return buf


def main():
    
    parser = OptionParser()
    parser.add_option("--host", dest="host", help="Ethernet host name or IP",
                      default=None)
    parser.add_option("--port", dest="port", help="Ethernet port",
                      default=None)
    parser.add_option("--file", dest="file", help="File to write to flash",
                      default=None)
    
    (options, args) = parser.parse_args()
    if options.host is None:
        print("Host not specified")
        parser.print_help()
        sys.exit(1)
    if options.port is None:
        print("Port not specified")
        parser.print_help()
        sys.exit(1)
    if options.file is None:
        print("Input file not specified")
        parser.print_help()
        sys.exit(1)

    session = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    session.connect((options.host, int(options.port)))    
    fcntl.fcntl(session, fcntl.F_SETFL, os.O_NONBLOCK)

    session.send("\r\n".encode())
    reply = bytearray()
    reboot = False
    timeout = False
    while True:
        try:
            new_data = read_next(session, timeout=3)
            reply.extend(new_data)
        except:
            if timeout:
                raise
            session.send("\r\n".encode())
            timeout = True
            
        try:
            if reply[-len(BOOTLOADER_PROMPT):].decode() == BOOTLOADER_PROMPT:
                break
            if (reply[-len(iceboot_session_cmd.PROMPT):].decode() == 
                                                   iceboot_session_cmd.PROMPT):
                if reboot:
                    raise Exception("Unable to invoke bootloader")
                session.send("reboot\r\n".encode())
                reboot = True
        except UnicodeDecodeError:
            pass

    infile = options.file
    if not os.path.exists(infile):
        print("File \"%s\" does not exist" % infile)
        return
    cmd = "update\r\n"
    session.send(cmd.encode())
    read_n(session, n_bytes=len(cmd), timeout=1)
    ymodem.ymodemImpl(session.fileno(), infile, verbose=False)
    # Remove partial prompt
    prompt = "# "
    ret = ""
    while not ret.endswith(prompt):
        try:
            next_data = read_next(session, timeout=2).decode()
            ret += next_data
            if len(next_data) == 0:
                print("Failure at end of update")
                sys.exit(1)
        except:
            pass
    

if __name__ == "__main__":
    main()
