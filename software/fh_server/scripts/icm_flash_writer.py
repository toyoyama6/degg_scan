#!/usr/bin/env python
#
# ICM flash writer class.  Connects to domnet
# and reprograms a flash image from a specified
# .mcs[.gz] file.
#
import sys
import socket
import time
import datetime
import struct
import gzip

from icmnet import ICMNet

class ICMFlashWriterError(Exception):
  pass

class ICMFlashWriter():

    MAX_IMAGE_ID = 7    
    MCS_DATA_SIZE = 3337647
    MCS_LINE_LENGTH = 43
    MCS_SYNC_LINE = 4
    MCS_SYNC_WORD = "AA995566"

    FW_MAJOR_VERSION_REQUIRED = 21
    RCFG_STAT_READY_FOR_DATA = 0x2
    RCFG_STAT_ERROR = 0x1
    RCFG_STAT_FP_DONE = 0x20
    RCFG_STAT_DONE = 0x80
    RCFG_ERR_ERASE_FAIL = 0x4

    RCFG_READY_TIMEOUT_SEC = 15

    def __init__(self, cmdport, dev, host="localhost", verbose=False):
        """
        Create an ICM flash writer object for a specific device
        and connect to domnet cmdport on a particular host.
        """
        self.host = host
        self.cmdport = cmdport
        self.dev = dev
        self.verbose = verbose
        self.mcu_reset = False
        
        # Connect to command server
        self.icms = ICMNet(self.cmdport, host=self.host)

    def _log(self, msg):
        """Log progress messages"""
        if self.verbose:
            sys.stdout.write(msg)
            sys.stdout.flush()                

    def _read_mcs_file(self, filename):
        """
        Read an ICM firmware MCS file and sanity-check the data.
        Return the data lines in an array.
        """
        # Check for gzip file
        if filename.endswith(".gz"):
            with gzip.open(filename, "rt") as f:
                lines = f.readlines()
        else:
            with open(filename) as f:
                lines = f.readlines()

        data = []
        size = 0
        lineno = 1
        for line in lines:
            line = line.strip()
            if not line.startswith(':'):
                raise ICMFlashWriterError('image %s line %d does not start with ":"' % (filename, lineno))
            length = len(line)
            if length > ICMFlashWriter.MCS_LINE_LENGTH:
                raise ICMFlashWriterError("image %s line %d too long" % (filename, lineno))
            size += length
            data.append(line)
            lineno += 1
            
        if size != ICMFlashWriter.MCS_DATA_SIZE:
            raise ICMFlashWriterError("image %s data size %d != %d" % (filename, size, ICMFlashWriter.MCS_DATA_SIZE))

        return data

    def _cleanup(self):
        """
        Take care of any cleanup steps, even if we didn't make it to the
        end of reprogramming.
        """
        if self.mcu_reset:
          reply = self.icms.request("mcu_reset_n %d" % self.dev)
          if reply['status'] == 'OK':
              self.mcu_reset = False

    def program(self, filename, image_id):
        """
        Program the ICM with the specified firmware to flash slot
        image_id. Throw an exception if an error occurs.
        """
        # Read and validate the MCS data
        mcs_data = self._read_mcs_file(filename)

        # Check the firmware major version
        reply = self.icms.request("read %d FW_VERS" % self.dev)
        if (reply['status'] == "OK") and ("value" in reply):
            fw_val = int(reply['value'], 16)
            if (fw_val >> 8) != ICMFlashWriter.FW_MAJOR_VERSION_REQUIRED:
                self._cleanup()
                raise ICMFlashWriterError("unsupported firmware major version (%d)" % (fw_val >> 8))
            self._log("Firmware check OK: 0x%04x\n" % fw_val)
        else:
            self._cleanup()
            raise ICMFlashWriterError("could not get firmware version: %s" % reply['status'])
                
        # Reset reconfiguration interface
        reply = self.icms.request("icm_reconfig_reset %d" % self.dev)
        if reply['status'] != 'OK':
            self._cleanup()
            raise ICMFlashWriterError("could not reset reconfiguration module: %s" % reply['status'])        
        time.sleep(1)
        
        # Set the programming image ID
        reply = self.icms.request("set_reprogram_image_id %d %d" % (self.dev, image_id))
        if reply['status'] != 'OK':
            self._cleanup()          
            raise ICMFlashWriterError("could not set image ID: %s" % reply['status'])

        # Put the MCU into reset if we're on a remote ICM
        if (self.dev != ICMNet.FH_DEVICE_NUM):
            reply = self.icms.request("mcu_reset %d" % self.dev)
            if reply['status'] != 'OK':
                self._cleanup()              
                raise ICMFlashWriterError("could not put MCU in reset: %s" % reply['status'])
            self.mcu_reset = True
            
        # Send the reprogramming command
        reply = self.icms.request("icm_reprogram_enable %d" % self.dev)
        if reply['status'] != 'OK':
            self._cleanup()          
            raise ICMFlashWriterError("could not start reprogramming: %s" % reply['status'])

        self._log("Reprogramming device %d slot %d with image %s\n" % (self.dev, image_id, filename))

        # Wait for status register to show ready_for_data
        ready = False
        ready_start = datetime.datetime.now()
        while ((datetime.datetime.now() - ready_start).total_seconds() < \
                 ICMFlashWriter.RCFG_READY_TIMEOUT_SEC):
            reply = self.icms.request("read %d RCFG_STAT" % self.dev)
            if (reply['status'] == 'OK') and ("value" in reply):
                rcfg_stat = int(reply["value"], 16)
            else:
                self._cleanup()              
                raise ICMFlashWriterError("could not read RCFG_STAT: %s" % reply['status'])
            if (rcfg_stat & 0x3 == ICMFlashWriter.RCFG_STAT_READY_FOR_DATA):
                ready = True
                break

            time.sleep(0.2)

        if not ready:
            # Check for error
            reply = self.icms.request("read %d RCFG_ERR" % self.dev)
            rcfg_err = int(reply["value"], 16)
            self._cleanup()            
            if (rcfg_err & ICMFlashWriter.RCFG_ERR_ERASE_FAIL != 0):
              raise ICMFlashWriterError("device erase failed, is flash unlocked?")
            else:
              raise ICMFlashWriterError("device never reported ready for data"+\
                                          " (RCFG_STAT: 0x%04x RCFG_ERR: 0x%04x)" \
                                          % (rcfg_stat, rcfg_err))
        
        self._log("Ready for data, sending bitstream...\n")

        # Get dropped packet count (at the FH)
        reply = self.icms.request("read %d CERR" % ICMNet.FH_DEVICE_NUM)
        if (reply['status'] == 'OK') and ("value" in reply):
            dropped_packets = int(reply["value"], 16)        
        else:
            self._cleanup()          
            raise ICMFlashWriterError("could not get FH dropped packet count: %s" % reply['status'])

        lineno = 0
        start_time = time.time()        
        total_line_cnt = 0
        write_sync = 0
        wrap_around = 0
        total_byte_cnt = 0
        
        # Loop over the mcs lines        
        for l in (mcs_data[:]):

            # Send the actual dataline to the reconfiguration module
            # skip the SYNC and EOF lines
            if (lineno == ICMFlashWriter.MCS_SYNC_LINE):
                if not ICMFlashWriter.MCS_SYNC_WORD in l:
                    self._cleanup()                  
                    raise ICMFlashWriterError("MCS sync word found on wrong line")
            elif (lineno != len(mcs_data) - 1):
                total_line_cnt += 1
                # Send the MCS data line
                reply = self.icms.request("write %d RCFG_DATA 0x%s" % (self.dev, l[1:]))
                if (reply['status'] != "OK"):
                    self._cleanup()                  
                    raise ICMFlashWriterError("Error writing MCS data to device (line %d): %s" % (lineno, reply['status']))

            lineno += 1
                 
            # Just a status bar...
            if ((lineno % 1000 == 0) or (lineno == len(mcs_data))):            
                self._log('\r')
                self._log("[%-40s] %d%%" % \
                          ('='*int(0.5+(lineno)*40.0/len(mcs_data)), \
                           int(0.5+(lineno)*100.0/len(mcs_data))))

            # Workaround for ZMQ bug (?), periodically cycle the socket
            # to prevent dropped replies at the ZMQ layer
            if (lineno % 100 == 0):
                self.icms.reset()
                # Temporary workaround for fh_icm_api issue #43
                # Garbage characters from ICM (overflow?) if transmit
                # too fast?
                time.sleep(0.05)                

            # Check periodically for errors            
            if ((lineno % 4000 == 0) or (lineno == len(mcs_data))):

                # Check the status register
                reply = self.icms.request("read %d RCFG_STAT" % self.dev)
                if (reply['status'] == 'OK') and ("value" in reply):
                    rcfg_stat = int(reply["value"], 16)
                else:
                    self._cleanup()                  
                    raise ICMFlashWriterError("could not read RCFG_STAT: %s" % reply['status'])                

                # Check for new dropped packets
                reply = self.icms.request("read %d CERR" % ICMNet.FH_DEVICE_NUM)
                if (reply['status'] == 'OK') and ("value" in reply):
                    new_dropped_packets = int(reply["value"], 16)        
                else:
                    self._cleanup()                  
                    raise ICMFlashWriterError("could not get FH dropped packet count: %s" % reply['status'])

                # Check for any errors reported by reconfiguration module
                if (rcfg_stat & ICMFlashWriter.RCFG_STAT_ERROR != 0):
                    reply = self.icms.request("read %d RCFG_ERR" % self.dev)
                    self._cleanup()                    
                    raise ICMFlashWriterError("Reconfiguration module error %s" % reply['value'])
                elif (new_dropped_packets > dropped_packets):
                    self._cleanup()                  
                    raise ICMFlashWriterError("Packets lost during transfer: %d" %
                                              (new_dropped_packets - dropped_packets))
                else:
                    reply = self.icms.request("read %d RCFG_LINE_CNT" % self.dev)
                    if (reply['status'] == 'OK') and ("value" in reply):
                        line_count_val = int(reply['value'], 16)
                    else:
                        self._cleanup()                      
                        raise ICMFlashWriterError("could not get reconfiguration line count: %s" % reply['status'])
                    # Wow this is hokey, fix it
                    if (line_count_val > 55000):
                        wrap_around=65536

        self._log("\n")
        time.sleep(1)

        # Check that all lines were written
        reply = self.icms.request("read %d RCFG_LINE_CNT" % self.dev)
        if (reply['status'] == 'OK') and ("value" in reply):
            line_count_val = int(reply['value'], 16)
        else:
            self._cleanup()          
            raise ICMFlashWriterError("could not get reconfiguration line count: %s" % reply['status'])
        if(total_line_cnt != line_count_val+wrap_around):
            self._cleanup()          
            raise ICMFlashWriterError("lines dropped at flash writer")

        # Write beginning up to sync word and EOF
        self._log("Sending SYNC lines...\n")
        for l in mcs_data[0:ICMFlashWriter.MCS_SYNC_LINE+1] + mcs_data[len(mcs_data)-1:len(mcs_data)]:
            # Send the MCS data line
            reply = self.icms.request("write %d RCFG_DATA 0x%s" % (self.dev, l[1:]))
            if (reply['status'] != "OK"):
                self._cleanup()              
                raise ICMFlashWriterError("Error writing MCS sync data to device")
            total_line_cnt+=1

        time.sleep(1)
        
        # Just for monitoring
        dt = time.time() - start_time
        self._log("Elapsed time: %ds (%.1f kbps)\n" % (dt, ICMFlashWriter.MCS_DATA_SIZE*8/1e3/dt))

        reply = self.icms.request("read %d CERR" % ICMNet.FH_DEVICE_NUM)
        if (reply['status'] == 'OK') and ("value" in reply):
            new_dropped_packets = int(reply["value"], 16)        
        else:
            self._cleanup()          
            raise ICMFlashWriterError("could not get FH dropped packet count: %s" % reply['status'])
        if (new_dropped_packets - dropped_packets != 0):
            self._log("WARNING: Dropped CRC packets during programming: %d" % (new_dropped_packets - dropped_packets))

        # Check the status register
        reply = self.icms.request("read %d RCFG_STAT" % self.dev)
        if (reply['status'] == 'OK') and ("value" in reply):
            rcfg_stat = int(reply["value"], 16)
        else:
            self._cleanup()          
            raise ICMFlashWriterError("could not read RCFG_STAT: %s" % reply['status'])                

        if (rcfg_stat & ICMFlashWriter.RCFG_STAT_ERROR != 0) or \
           (rcfg_stat & ICMFlashWriter.RCFG_STAT_FP_DONE == 0) or \
           (rcfg_stat & ICMFlashWriter.RCFG_STAT_DONE == 0):
            reply = self.icms.request("read %d RCFG_ERR" % self.dev)
            self._log("Unexpected status register\n")
            self._log("RCFG_STAT: 0x%0x\nRCFG_ERR: %s\n" % (rcfg_stat, reply['value']))
            self._cleanup()            
            raise ICMFlashWriterError("Reconfiguration module did not complete successfully")
        else:
            self._log("Done.\n")
        
        # Clean up
        self._cleanup()
