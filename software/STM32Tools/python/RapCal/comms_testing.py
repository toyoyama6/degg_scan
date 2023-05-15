"""
Created on Wed Sep 16 10:04:55 2020

@author: meures
"""


import serial
import serial.tools.list_ports
import struct
import numpy as np
import sys
import time


class comms_testing_device(object):
    
    def __init__(self, PORT="COM10", baud_rate=3000000, rtscts=True, timeout=0, writeTimeout=0, address=0x7):        
        portList = [comport.device for comport in serial.tools.list_ports.comports()]
        print(portList)
        self.s = 0
        self.addr = address
        try:
            self.s = serial.Serial(PORT, baud_rate, rtscts=rtscts, timeout=timeout, writeTimeout=writeTimeout)
            self.s.flushInput()
        except:
            print("Unable to connect to FPGA.")
            sys.exit()

    def close(self):
        self.s.close()

    def flush_Buffer(self):
        self.s.flushInput()
    
    def unpackData(buf, structure):
        package=[]
        unpackStruct=['B','H', '>L', 'Q']
        counter=0
        for i in structure:
                k= struct.unpack(unpackStruct[int(np.log2(i))], buf[counter:counter+i])
                package.append(int(k[0]))
                counter+=i
        return package
    

    #Write_reg: Will write data to a register in the reconfiguration module
    #Inputs:
    #address: int register address
    #value: int Value to be written
    #Return: none
    def write_reg(self, module_addr, reg_addr, length, data):
        
        read_cmd = struct.pack('>B', 0x9)
        tx_length =  struct.pack('>H', length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)        
        #data1 = struct.pack('>B', 0x0)
        #data2 = struct.pack('>B', data)
        
        
        transmission = read_cmd + tx_length + mod_dest_add + reg_dest_add
        if(length>5):
            for i in range(length-5):
                data2 = struct.pack('>B', data[i])
                transmission+=data2
        
        
        
        self.s.write(transmission)        
                
        #bytes_to_read=0
        #count=0
        #while(bytes_to_read==0 and count<1):
        #    bytes_to_read = self.s.inWaiting()
        #    count+=1
        #    #time.sleep(0.001)    
        #
        #if(bytes_to_read>0):
        #    line=self.s.read(bytes_to_read)
        #    print(list(line))
        #    return(list(line)[0])
        #else:
        #    print("Bytes in read buffer:",bytes_to_read)
        return -1


    #read_reg: Will read data from a register in the reconfiguration module
    #Inputs:
    #address: int register address
    #Return: int register content // -1 when read failed.
    def read_reg(self, module_addr, reg_addr, rx_length, pr=0):
        
        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', rx_length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)
        
        transmission = read_cmd + length + mod_dest_add + reg_dest_add  #+ mod_src_add + reg_src_add
                
        self.s.write(transmission)        
        #time.sleep(0.1)                 
        bytes_to_read=0
        count=0
        while(bytes_to_read==0 and count<300):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.01)    
        
        if(bytes_to_read>0):
            time.sleep(0.01)
            bytes_to_read = self.s.inWaiting()
            line=self.s.read(bytes_to_read)
            data_package = ( comms_testing_device.unpackData(line, [1]*bytes_to_read) )
            if(pr==1):                
                print(list(line))
                print([hex(k) for k in data_package]) 
            return(data_package)            
        else:
            print("Bytes in read buffer:",bytes_to_read)
            return [-1]
        
    def read_reg_no_resp(self, module_addr, reg_addr, rx_length, pr=1):
        
        read_cmd = struct.pack('>B', 0x8)
        length =  struct.pack('>H', rx_length)
        mod_dest_add = struct.pack('>B', module_addr)
        reg_dest_add = struct.pack('>B', reg_addr)
        
        transmission = read_cmd + length + mod_dest_add + reg_dest_add  #+ mod_src_add + reg_src_add
                
        self.s.write(transmission)        
        #time.sleep(0.1)                 
    #Write_spi_bytes: Will write several bytes of data to the serial port
    #Inputs:    
    #value: multiple data bytes to be written
    #Return: none 
    def write_spi_bytes(self, value):                
        self.s.write(value)
    
    def read_uart(self):
        count=0
        bytes_to_read=0
        while(bytes_to_read==0 and count<100):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.01)    
        
        if(bytes_to_read>0):
            line=self.s.read(bytes_to_read)
            return(list(line))            
        #else:
        #    #print("Bytes in read buffer:",bytes_to_read)
        #    return [-1]

    def read_uart_resp(self):
        count=0
        bytes_to_read=0
        while(bytes_to_read==0 and count<4):
            bytes_to_read = self.s.inWaiting()
            count+=1
            time.sleep(0.0001)    
        
        if(bytes_to_read>0):
            line=self.s.read(bytes_to_read)
            return(list(line))            
        else:
            #print("Bytes in read buffer:",bytes_to_read)
            return [-1]
   
if __name__=="__main__":
  
    
    
    # Read comms where devices are connected 
    argList = sys.argv    
    PORT_hub = argList[1]    
    
    hub = comms_testing_device(PORT_hub,address=0x8)    
 
    hub.flush_Buffer()
    hub.read_reg(0x8, 0xff, 6)
    time.sleep(1)    
    hub.read_reg(0x7, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x6, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x5, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x4, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x3, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x2, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x1, 0xff, 6)
    time.sleep(1)
    hub.read_reg(0x0, 0xff, 6)
    
    hub.close()
    
    
    tx_count = 0
    err_count = 0 

    
    # Read comms where devices are connected 
    argList = sys.argv    
    PORT_hub = argList[1]
    PORT_ice = argList[2]
    
    #Starting the serial device for    
    hub = comms_testing_device(PORT_hub,address=0x8)
    ice = comms_testing_device(PORT_ice,address=0x7)
    
    time.sleep(1)
    
    hub.flush_Buffer()
    ice.flush_Buffer()

    hub_fw_val = hub.read_reg(hub.addr, 0xff, 6)
    print("Hub firmware ID:", (hub_fw_val))
    
    ice_fw_val = ice.read_reg(ice.addr, 0xff, 6)
    print("Ice firmware ID:", (ice_fw_val))    
    
    
    packet_size= 4000
    start_t = time.time()
    for i in range(250):
        
        #Write to ice UART from hub 
        data_in = [i]*packet_size + list(range(11))
        txrs = hub.write_reg(ice.addr, 0xa, 5+len(data_in), data_in)
        tx_count +=1
        time.sleep(0.001);
        #interrupt:
        data_count=1
        
        #while(data_count>0):
        test_rsp=-1
        int_count=0
        while(test_rsp==-1 and int_count<100):
            rsp = ice.read_uart()
            test_rsp = rsp[0]          
            int_count+=1
        #rsp = ice.read_uart()
        #print(rsp)
        rsp = ice.read_reg(hub.addr, 0x9, 6)
        data_count = rsp[5]+256*rsp[4]
        #print("Sent ", rsp[5]+256*rsp[4], "bytes")
        data_resp = ( ice.read_reg(hub.addr, 0x8, 4+rsp[5]+256*rsp[4], pr=0) )
        if(len(data_resp)<data_count):
            time.sleep(0.001)
            data_resp += ice.read_uart()
        #print("IceBuffer: ")
        #print(data_resp[-100:])  
        #print("\n")
    
        if data_resp[-(len(data_in)):] == data_in:
            print("Found Mathching Data ", i)
        else:
            print("Data is all messed up")
            print(data_resp[-100:])  
            err_count += 1
        
        #rsp = ice.read_uart()
    
    
        #Write to hub UART from ice 
        #data_in = [i]*packet_size + list(range(11))
        txrs = ice.write_reg(hub.addr, 0xa, 5+len(data_in), data_in)
        tx_count +=1
        time.sleep(0.001);
        #interrupt:
        data_count=1
        
        #while(data_count>0):
        test_rsp=-1
        int_count=0
        while(test_rsp==-1 and int_count<100):
            rsp = hub.read_uart()
            test_rsp = rsp[0]    
            int_count+=1
        #print(rsp)
        rsp = hub.read_reg(ice.addr, 0x9, 6)
        data_count = rsp[5]+256*rsp[4]
        #print("Sent ", rsp[5]+256*rsp[4], "bytes")
        data_resp = ( hub.read_reg(ice.addr, 0x8, 4+rsp[5]+256*rsp[4], pr=0) )
        if(len(data_resp)<data_count):
            time.sleep(0.001)
            data_resp += hub.read_uart()
        
        #print("IceBuffer: ")
        #print(data_resp[-100:])  
        #print("\n")
    
        if data_resp[-(len(data_in)):] == data_in:
            print("Found Mathching Data ", i)
        else:
            print("Data is all messed up")
            print(data_resp[-100:])  
            err_count += 1
        
        #rsp = hub.read_uart()

    stop_t = time.time()
    print("Packets transferred:",tx_count, "Errors found:", err_count, "Within", stop_t-start_t, "seconds.")
    print("Transfer speed (kSPS):", round(tx_count/(stop_t - start_t)*(packet_size+11)*8/1000.0, 1), "Total amount of data:", tx_count*(packet_size+11)/1000.0, "kB." )
        
    hub.close()
    ice.close()    
    
    
