#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# golden_image_control.py
#
# Reprogramming of ICM FPGA, multiboot booting, toggling
# golden image write protect, etc.
# 
"""
Created on Wed Sep 16 10:04:55 2020
@author: meures
"""

import serial
import struct
import sys
import time
import math

MAX_IMAGE_ID = 7
MCS_DATA_SIZE = 3337647


def fatal(msg):
    # TODO bypasses serial port close. Is this an issue?
    sys.stderr.write(msg.rstrip() + '\n')
    sys.exit(1)

def read_mcs_file(mcs):
    with open(mcs) as f:
        lines = f.readlines()
    data = []
    size = 0
    lineno = 1
    for line in lines:
        line = line.strip()
        if not line.startswith(':'):
            fatal(f'image {mcs} line {lineno} does not start with ":"')
        length = len(line)
        if length > 43:
            fatal(f'image {mcs} line {lineno} length {length}> 43')
        size += length
        data.append(line)
        lineno += 1
    if size != MCS_DATA_SIZE:
        fatal(f'image {mcs} data size {size} != {MCS_DATA_SIZE}')

    return data


class golden_image_control(object):
    
    def __init__(self, port, baud_rate=3000000, rtscts=True, timeout=0, writeTimeout=0):        
        self.s = 0    
        self.pck_ct = 0        
        self.s = serial.Serial(port, baud_rate, rtscts=rtscts,
                               timeout=timeout, writeTimeout=writeTimeout)
        self.s.flushInput()

    def close(self):
        self.s.close()

    def flush_buffer(self):
        self.s.flushInput()


    def resetPCK_CT(self):
        self.pck_ct=0

    #Write_reg: Will write data to a register in the reconfiguration module
    #Inputs:
    #address: int register address
    #value: int Value to be written
    #Return: none
    def write_reg(self, module_addr, reg_addr, data, debug=False):
        self.pck_ct+=1
        read_cmd = struct.pack('>B', 0x9)
        length =  struct.pack('>H', 0x7)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)
        data1 = struct.pack('>B', 0x0)
        data2 = struct.pack('>B', data)
                
        transmission = read_cmd + length + mod_dest_add + reg_dest_add + data1 + data2
                
        self.s.write(transmission)        
                
        bytes_to_read=0
        count=0
        while(bytes_to_read==0 and count<2):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.2)    
        
        if(bytes_to_read>0):
            line=self.s.read(bytes_to_read)
            if debug:
                print(list(line))
            return(asciival(line[0]))
        else:
            if debug:
                print("Bytes in read buffer: %d" % bytes_to_read)
            return -1

    def write_reg_full(self, module_addr, reg_addr, length, data):
        
        read_cmd = struct.pack('>B', 0x9)
        tx_length =  struct.pack('>H', length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)        
        
        transmission = read_cmd + tx_length + mod_dest_add + reg_dest_add
        if(length>5):
            for i in range(length-5):
                data2 = struct.pack('>B', data[i])
                transmission+=data2
        
        self.s.write(transmission)                
        return -1

    #read_reg: Will read data from a register in the reconfiguration module
    #Inputs:
    #address: int register address
    #Return: int register content // -1 when read failed.
    def read_reg(self, module_addr, reg_addr, debug=False):
        self.pck_ct+=1
        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', 0x6)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)
        
        transmission = read_cmd + length + mod_dest_add + reg_dest_add  
        #+ mod_src_add + reg_src_add
                
        self.s.write(transmission)        
        time.sleep(0.1)                 
        bytes_to_read=0
        count=0
        while(bytes_to_read==0 and count<10):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.1)    
        
        if(bytes_to_read>0):
            line=self.s.read(bytes_to_read)
            if debug:
                print(list(line))
            return(asciival(line[5]))            
        else:
            print("Read failed!")
            print("Bytes in read buffer: %d" % bytes_to_read)
            return -1        

    def unpackData(self, buf, structure):
        package=[]
        unpackStruct=['B','H', '>L', 'Q']
        counter=0
        for i in structure:
                k= struct.unpack(unpackStruct[int(math.log(i,2))], buf[counter:counter+i])
                package.append(int(k[0]))
                counter+=i
        return package

    def read_reg_list(self, module_addr, reg_addr, rx_length, debug=False):
        self.pck_ct+=1
        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', rx_length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)
        
        transmission = read_cmd + length + mod_dest_add + reg_dest_add  
        #+ mod_src_add + reg_src_add
                
        self.s.write(transmission)        
        time.sleep(0.1)                 
        bytes_to_read=0
        count=0
        while(bytes_to_read==0 and count<10):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.1)    
        
        if(bytes_to_read>0):
            line=self.s.read(bytes_to_read)
            data_package = ( self.unpackData(line, [1]*bytes_to_read) )
            if debug:
                print(list(line))
            return(data_package)            
        else:
            print("Read failed!")
            print("Bytes in read buffer: %d" % bytes_to_read)
            return [-1]  


        
    #Write_spi_bytes: Will write several bytes of data to the serial port
    #Inputs:    
    #value: multiple data bytes to be written
    #Return: none 
    def write_spi_bytes(self, value):        
        self.pck_ct+=1                
        self.s.write(value)

    def read_uart(self, debug=False):
        bytes_to_read = self.s.inWaiting()
        if(bytes_to_read>1):
            time.sleep(0.01)
            val = self.s.read(bytes_to_read)
            if(debug):
                print(list(val))
            return (list(val))
        else: 
            return [0]




# Helper function for ord() since Python2 vs Python3 behavior is different
# Python3 indexing into byte array gives integer so no translation is needed
def asciival(x):
    try:
        # Python2 version
        return ord(x)
    except TypeError:
        # Python3 
        return x
    
def usage(progname):
    print("Usage: %s <port> <addr> <cmd> <fw_rev> <im ID> [MCS file]" % progname)
    print("  port    serial port (e.g. /dev/ttyUSBn)")
    print("  addr    wire pair address (device ICM 0-7, or FieldHub 8)") 
    print("   cmd    r = [r]eboot (into multiboot image)")
    print("          p = [p]program ICM firmware with specified MCS file")
    print("          s = [s]et write protection of ICM golden image")
    print("          u = [u]nset write potection of ICM golden image")
    print("          g = reboot into [g]olden image")
    print("          [f]og[0] = [f]orce [o]verwrite [g]olden image id0")
    print("          [f]og1 = [f]orce [o]verwrite [g]olden image id1")
    print("          rf = [r]ead [f]irmware revision")
    print("          ei = [e]rase [i]mage only. TODO unreliable")
    print(" fw_rev   current major in-ice revision (possible values: 20, 21)")
    print(" im ID    image position in Flash memory for runtime reboot or program.") 

def main():
    # Check command-line arguments
    if (len(sys.argv) != 5) and (len(sys.argv) != 6) and (len(sys.argv) != 7):
        usage(sys.argv[0])
        sys.exit(1)

    # Serial port
    port = sys.argv[1]

    # Device address
    wp_addr = None
    try:
        wp_addr = int(sys.argv[2])
    except ValueError:
        fatal("Bad device address %s, exiting." % sys.argv[2])

    if (wp_addr < 0) or (wp_addr > 8):
        fatal("Valid device addresses are 0-8, exiting.")

    # Command
    cmd = sys.argv[3].lower()
    image_id = 1
    prog_boot = None
    wrap_around = 0
    if ((cmd == 'r') or (cmd == 'g')):
        prog_boot = 0
        if (len(sys.argv) != 6):
            fatal("Please specify image ID to reboot from.")
        else:
            image_id = int(sys.argv[5])
            assert 0 <= image_id <= MAX_IMAGE_ID, 'invalid image Id'
        if (cmd == 'g'):
            image_id = 0
    elif (cmd == 'p'):
        prog_boot = 1
        if (len(sys.argv) != 7):
            fatal("Please specify image ID and mcs file for writing.")
        else:
            image_id = int(sys.argv[5])
            assert 0 <= image_id <= MAX_IMAGE_ID, 'invalid image Id'
            if(image_id <= 1):
                fatal("Attempting to overwrite golden image ID 0 or 1"
                      ". Use command '[f]og[01]' instead to overwrite golden "
                      "image.")
    elif (cmd == 'og' or cmd == 'fog' or cmd == 'og0' or cmd == 'fog0'):
        prog_boot = 1
        image_id = 0
        if cmd.startswith('f'):
            print("FORCING overwrite of golden image0")
        else:
            ret = input("Are you sure to erase and overwrite golden image0 ("
                        "YES/NO): ")
            if (ret == "YES"):
                print("Moving on.")
            else:
                fatal("aborting golden image0 overwrite")
    elif (cmd == 'og1' or cmd == 'fog1'):
        prog_boot = 1
        image_id = 1
        if cmd.startswith('f'):
            print("FORCING overwrite of golden image1")
        else:
            ret = input("Are you sure to erase and overwrite golden image1 ("
                        "YES/NO): ")
            if(ret=="YES"):
                print("Moving on.")
            else:
                fatal("aborting golden image1 overwrite")
    elif (cmd == 's'):
        prog_boot = 2
    elif (cmd == 'u'):
        prog_boot = 3
    elif (cmd == 'rf'):
        prog_boot = 4
    elif (cmd == 'ei'):
        prog_boot = 5
    else:
        fatal("Bad command '%s', exiting." % cmd)

    # Check for MCS file
    data = None
    if (prog_boot == 1):
        if (len(sys.argv) != 7):
            fatal("Please specify MCS file for reprogramming.")
        mcs_file = sys.argv[6]
        # Read mcs file
        data = read_mcs_file(mcs_file)

    fw_rev = sys.argv[4]

    #Starting the serial device    
    fpga = golden_image_control(port)    
    time.sleep(1)
    fpga.flush_buffer()
    
    if(fw_rev=="21"):
        #fpga.write_reg_full(0x8, 0xed, 7, [0x0, 8])
        #time.sleep(0.5)
        #fpga.write_reg_full(0x8, 0x33, 7, [0x45, 0x4e])
        time.sleep(0.5)
        #fpga.write_reg_full(0x8, 0xb, 7, [0x0, 0x0])
        #time.sleep(0.5)        
        #fpga.write_reg_full(0x8, 0xee, 7, [0x4, 0x0])
        #time.sleep(0.5)
        #fpga.write_reg_full(0x8, 0x0, 7, [0x0, 0x2])
        #time.sleep(0.5)
        fpga.read_uart()
        
        val = fpga.read_reg_list(wp_addr, 0xff, 6)
        if( len(val)==6):
            if(val[4]==21):
                gi_ind = fpga.read_reg(wp_addr, 0xfe)
                print("Ready to run with in-ice firmware revision: "
                      "%2.2d.%1.1d.%d  GI indicator: 0x%04x" %
                      (val[4], (val[5] >>4)&0xf, val[5]&0xf, gi_ind))
            else:
                print("Detected unexpected firmware", val[4], ".", (val[5]
                                                                >>4)&0xf, ".", val[5]&0xf, ". Exiting.")
                sys.exit(1)
        else:
            fatal("Communications to in-ice device could not be established. "
              "Exiting.")
    elif(fw_rev=="20"):
        fpga.write_reg_full(0x8, 0xed, 7, [0x0, 40])
        time.sleep(0.5)
        fpga.write_reg_full(0x8, 0xb, 7, [0x0, 0x1])
        time.sleep(0.5)
        #fpga.write_reg_full(0x8, 0x33, 7, [0x45, 0x4e])
        time.sleep(0.5)
        fpga.write_reg_full(0x8, 0xee, 7, [0x4, 0x0])
        time.sleep(0.5)
        fpga.write_reg_full(0x8, 0x0, 7, [0x0, 0x2])
        time.sleep(0.5)
        fpga.read_uart()
    
        val = fpga.read_reg_list(wp_addr, 0xff, 6)
        if( len(val)==6):
            if(val[4]==20):
                print("Ready to run with in-ice firmware revision: %2.2d.%1.1d.%d" % (val[4], (val[5] >>4)&0xf, val[5]&0xf) )
            else:
                print("Detected unexpected firmware", val[4], ".", (val[5]
                                                                >>4)&0xf, ".", val[5]&0xf, ". Exiting.")
                sys.exit(1)
        else:
            fatal("Communications to in-ice device could not be established. "
              "Exiting.")
    else:
        fatal("Entered invalid firmware revision %s. Possible values are '20' "
          "and '21'." % fw_rev)

    #Reset reconfiguration interface
    fpga.write_reg(wp_addr, 0x10,  0x10)    
    time.sleep(1)

    #Write values to registers:
    #SPI-FP configuration:
    # erase and write new image to image section selected
    # of the memory (golden image is in section 0).
    if prog_boot == 5:
        exit_val = 0
        if (len(sys.argv) != 6):
            fatal("Please specify image ID")
        image_id = int(sys.argv[5])
        assert 0 <= image_id <= MAX_IMAGE_ID, 'invalid image Id'
        print("Erasing Image at location %d"%image_id)
        if image_id >1:
            fpga.write_reg(wp_addr, 0x11, image_id+128)
            fpga.write_reg(wp_addr, 0x10, 0x9c)
            status_val = 0
            count = 0
            while status_val == 0 and count < 100:
                status_val = fpga.read_reg(wp_addr, 0x14)
                time.sleep(0.3)
                count += 1
            if status_val != 0xa0:
                print('unable to erase image %d after %f s, rcfg status 0x%04x'
                      % (image_id, count * 0.3, status_val))
                exit_val = 1
        else:
            print("Cannot erase golden image location")
            exit_val = 1
        status_val = fpga.read_reg(wp_addr, 0x14)
        print("Status:\t\t0x%02x" % status_val)
        error_val = fpga.read_reg(wp_addr, 0x15)
        print("Error:\t\t0x%02x" % error_val)
        sys.exit(exit_val or error_val)
    else:
         fpga.write_reg(wp_addr, 0x11, image_id)
    
    #Write multiboot register:
    #set to reboot from image ID selected.
    fpga.write_reg(wp_addr, 0x12, image_id)        
   

    #print("Putting the MCU into reset.")
    ctrl1_val = fpga.read_reg(wp_addr, 0x0)
    fpga.write_reg(wp_addr, 0x0, ctrl1_val | 0x04)

    #Read firmware ID:
    fw_val = fpga.read_reg(wp_addr, 0xff)
    print("firmware ID:\t0x%02x" % fw_val)

    #Read back multiboot ID:
    mb_val = fpga.read_reg(wp_addr, 0x12)
    print("Multiboot ID:\t0x%02x" % mb_val)

    #Read SPI-FP configuration:
    spi_conf_val = fpga.read_reg(wp_addr, 0x11)
    print("SPI-FP config:\t0x%02x" % spi_conf_val)

    #Read status:
    status_val = fpga.read_reg(wp_addr, 0x14)
    print("Status:\t\t0x%02x" % status_val)

    #Read error register:
    error_val = fpga.read_reg(wp_addr, 0x15)
    print("Error:\t\t0x%02x" % error_val)

    #Write desired command to control register:
    if(prog_boot==0):
        print("Rebooting...")
        fpga.write_reg(wp_addr, 0x10, 0xab)    
        time.sleep(3)
        sys.exit()
        
    elif(prog_boot==1):
        print("Reprogramming...")
        fpga.write_reg(wp_addr, 0x10, 0x9c)
        
    elif(prog_boot==2):
        print("Setting write protection...")
        fpga.write_reg(wp_addr, 0x10, 0xb5)          
           
    elif(prog_boot==3):
        print("Releasing write protection...")
        fpga.write_reg(wp_addr, 0x10, 0xb2)      
        
    elif(prog_boot==4):
        sys.exit()
        
    if(prog_boot==1):
        val=0
        count =0
        #Wait for status register to show ready_for_data:
        while ((val & 0x3 == 0x0) and count<100):
            val = fpga.read_reg(wp_addr, 0x14)
            count+=1
        
        #Check if ready for data (bit1=1, bit0=0)
        if( val & 0x3 == 0x2 ):
            print("Ready for data, sending bitstream...")
            sys.stdout.flush()

            val = fpga.read_reg_list(0x8, 0x4, 6)
            dropped_packets = val[4]*256 + val[5]
            print("Starting with dropped packet count (CRC):", dropped_packets)

            val = fpga.read_reg_list(0x8, 0xe, 8)
            sent_packets = val[4]*1048576 + val[5]*65536 + val[6]*256 + val[7]
            print("Starting with SENT packet count (UART):", sent_packets)

            fpga.resetPCK_CT()
            print("Starting with transfer packets (pyserial): ", fpga.pck_ct)
        


            counter = 0
            start_time = time.time()        
            total_write_count = 0
            #Loop mcs lines     
            tx_fifo_full = 0
            write_sync=0
            for l in (data[:]):
                 
                #Just a status bar...
                if(counter%1000==0):
                    sys.stdout.write('\r')
                    sys.stdout.write("[%-40s] %d%%" %
                       ('='*int(0.5+(counter)*40.0/len(data)),
                        int(0.5+(counter)*100.0/len(data))))
                    sys.stdout.flush()

                # Strip newline
                #l = l.strip()

                #Packing the dataline to be sent with address and write command: 10000111=0x87.
                dataline = b''                
                dataline+=struct.pack('<B', 0x9)
                datalength = 5+int( len(l[1:])/2)
                dataline+=struct.pack('<B', 0x0)                
                dataline+=struct.pack('<B', datalength)
                dataline+=struct.pack('<B', wp_addr)                
                dataline+=struct.pack('<B', 0x16)                
                
                for k in range(int( len(l[1:])/2) ):
                    dataline += struct.pack('<B', int(l[k*2+1:k*2+3],16))
                
                
                    
                # Wait until previous data are written
                while(fpga.s.out_waiting > 0):
                    time.sleep(0.0001)

                # Send the actual dataline to the reconfiguration module   
                if(counter==4):
                    sync_word = "AA995566"
                    match = sync_word in l
                    if(match):
                        print("skipped SYNC word", l)
                    else:
                        print("Skipped the wrong line!", l)
                        break
                    
                    
                elif(counter==len(data)-1):
                    print("skip EOF:", l)
                else:
                    total_write_count+=1
                    fpga.write_spi_bytes(dataline)
                
                #CHeck if tx_fifo_full_flag is set:
                interrupt = fpga.read_uart()
                if(len(interrupt)>1):
                    if(interrupt[-2]&0x2 ==2):
                        tx_fifo_full=1
                    else:
                        tx_fifo_full=0
                
                while(tx_fifo_full==1):
                    interrupt = fpga.read_uart()
                    if(len(interrupt)>1):
                        if(interrupt[-2]&0x2 ==2):
                            tx_fifo_full=1
                        else:
                            tx_fifo_full=0                    
                    
                                                                       
                counter+=1
                if(counter%4000==0 or counter ==len(data)):
                    # Only check sporadically for errors, otherwise 
                    # the interface is slowed down too much in this implementation.
                    #Check resonfiguration error:

                    fpga.read_uart()
                    while(fpga.s.out_waiting > 0):
                        time.sleep(0.0001)
                    fpga.read_uart()
                    while(fpga.s.out_waiting > 0):
                        time.sleep(0.0001)
                    fpga.read_uart()
                    val_s = fpga.read_reg_list(wp_addr, 0x14, 6)          
                    while(len(val_s)<5):
                        val_s = fpga.read_reg_list(wp_addr, 0x14, 6)          
                    val = val_s[5]
                    while(val==0xff):
                        val_s = fpga.read_reg_list(wp_addr, 0x14, 6)          
                        val = val_s[5]
                    #Check dropped packets at CRC:
                    val2 = fpga.read_reg_list(0x8, 0x4, 6)
                    new_dropped_packets = val2[4]*256 + val2[5]
                    #Check for dropped packets at UART:
                    val3 = fpga.read_reg_list(0x8, 0xe, 8)            
                    sent_spi_packets = val3[4]*1048576 + val3[5]*65536 + val3[6]*256 + val3[7]
                    
                    
                    
                    if(  (val & 0x1)==1 or new_dropped_packets>dropped_packets or (sent_spi_packets-sent_packets)!=fpga.pck_ct ):
                        #Exit if error is detected:
                        print("\nDetected error: %s counter %d" % (hex(val), counter))
                        print("Packets lost during transfer:", new_dropped_packets - dropped_packets)
                        print("Number of packets written to UART:", sent_spi_packets - sent_packets, fpga.pck_ct) 
                        break
                    else:
                        val_l = fpga.read_reg_list(wp_addr, 0x13,6)
                        line_count_val = val_l[4]*256 + val_l[5]
                        if(line_count_val>55000):
                            wrap_around=65536
                        #print("Line count:\t\t%d" % line_count_val)
                        if(counter==len(data)):
                            print("All data successfully written to flash. Ready to write SYNC word.")
                            write_sync = 1
                    
            time.sleep(1)        
            counter = 0


            val_l = fpga.read_reg_list(wp_addr, 0x13,6)
            line_count_val = val_l[4]*256 + val_l[5]
            print("Flash programmer Line count:\t\t%d" % (line_count_val+wrap_around) )
            print("Total number of lines written in software: %d" % (total_write_count) )
            if(total_write_count > line_count_val+wrap_around):
                write_sync = 0
                print("Lines dropped at Flash-writer.")

            #Write sync word:
            if(write_sync==1):
                for ll in range(7):
                    l = data[counter]
    
                    
                    # Strip newline
                    #l = l.strip()
    
                    #Packing the dataline to be sent with address and write command: 10000111=0x87.
                    dataline = b''                
                    dataline+=struct.pack('<B', 0x9)
                    datalength = 5+int( len(l[1:])/2)
                    dataline+=struct.pack('<B', 0x0)                
                    dataline+=struct.pack('<B', datalength)
                    dataline+=struct.pack('<B', wp_addr)                
                    dataline+=struct.pack('<B', 0x16)     
                    
                    
                    for k in range(int( len(l[1:])/2) ):            
                        dataline += struct.pack('<B', int(l[k*2+1:k*2+3],16))                        
                    #print(dataline, datalength)                    
                    #Send the actual dataline to the reconfiguration module   
                    if(counter==5):
                        print("jump", l)
                        counter = len(data)-2
                    else:
                        fpga.write_spi_bytes(dataline)
                        total_write_count+=1
                    #print(dataline)
                    #print(dataList)
                    #time.sleep(0.0001)                                                       
                    counter+=1                
                    
                    
                        
            stop_time = time.time()        
            #Just for monitoring:
            print("\nElapsed time is: %ds" % (stop_time - start_time))
            val2 = fpga.read_reg_list(0x8, 0x4, 6)
            new_dropped_packets = val2[4]*256 + val2[5]
            print("Dropped CRC packets during programming:", new_dropped_packets - dropped_packets)
            #Check for dropped packets at UART:
            val3 = fpga.read_reg_list(0x8, 0xe, 8)                
            sent_spi_packets = val3[4]*1048576 + val3[5]*65536 + val3[6]*256 + val3[7]
            print("Dropped UART data during programming:", sent_spi_packets - sent_packets - fpga.pck_ct)                
            print("Total number of lines written in software: %d" % (total_write_count) )
        else:
            print("Error occured during erase operation.")
            error_val = fpga.read_reg(wp_addr, 0x15)
            print("Error: 0x%02x" % error_val)
            
    time.sleep(1)
    # Since the status has only been checked sporadically, there might me 
    # some data left in the receive buffer. The following command will flush it.
    #val = fpga.wait_for_bytes(20)
    #print(hex(val[0]))
    fpga.flush_buffer()




    #To make sure everything went ok: check the status and error 
    # (in principle the status should be enough):

    val_l = fpga.read_reg_list(wp_addr, 0x13,6)
    line_count_val = val_l[4]*256 + val_l[5]
    if (prog_boot == 1):
        print("Flash programmer Line count:\t\t%d" % (line_count_val+wrap_around) )

    status_val = fpga.read_reg(wp_addr, 0x14)
    print("Status:\t\t0x%02x" % status_val)

    error_val = fpga.read_reg(wp_addr, 0x15)
    print("Error:\t\t0x%02x" % error_val)

    fpga.close()

    if prog_boot == 0:
        # r = [r]eboot OR g = reboot into [g]olden
        pass
    elif prog_boot == 1:
        # p = [p]program OR og = [o]verwrite [g]olden image,
        rcfg_stat = 0xa0
        assert status_val == rcfg_stat, f'rcfg stat == {rcfg_stat}'
    elif prog_boot == 2:
        # s = [s]et write protection of ICM golden image
        rcfg_stat = 0xc0
        assert status_val == rcfg_stat, f'rcfg stat == {rcfg_stat}'
    elif prog_boot == 3:
        # u = [u]nset write potection of ICM golden image
        rcfg_stat = 0xc0
        assert status_val == rcfg_stat, f'rcfg stat == {rcfg_stat}'
    elif prog_boot == 4:
        # rf = [r]ead [f]irmware revision
        pass
    elif prog_boot == 5:
        # ei = [e]rase [i]mage only
        pass

    if (error_val):
        fatal("error detected")






    print("Done.")
    sys.exit(0)

if __name__=="__main__":
    main()
