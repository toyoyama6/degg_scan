import sys
import vxi11
import time
import struct

import numpy as np
import matplotlib.pyplot as plt


# config paramters

IP = "10.25.121.219"
TIMESTEP = "10e-8"
SHOWONLINE = False#True

#RANGE="DMAX"
#RANGE="MAX"
RANGE="DEF"


def init(ip):

	instr = vxi11.Instrument(ip)
	return instr

def reset(instr):
	instr.write("*RST")

def set_DAQ(instr, readch):

	print("set config")
	cmd1 = ""
	cmd2 = ""
	ini = 0
	for i in range(4):
		if((readch & (2**i))>0):
			if(ini!=0):
				cmd1 = cmd1 + ";:"
				cmd2 = cmd2 + ";:"
				ini = 1
			cmd1 = cmd1 + "CHAN{}:TYPE HRES".format(i+1)
			cmd2 = cmd2 + "CHAN{0}:DATA:POIN {1}".format(i+1, RANGE)

	instr.write(cmd1)
	instr.write("TIM:SCAL {}".format(TIMESTEP))
	instr.write("FORM REAL")
	instr.write("FORM:BORD LSBF")
	instr.write(cmd2)
	print("end config")

def get_singleWFM(instr, readch):
	instr.ask("SING;*OPC?")
	
	header = ""
	for i in range(4):
		if((readch & (2**i))>0):
			header = instr.ask("CHAN{}:DATA:HEAD?".format(i+1))
			break

	data = [0]*4	
	for i in range(4):
		if((readch & (2**i))>0):
			instr.write("CHAN{}:DATA?".format(i+1))
			data[i] = instr.read_raw()
	
	return header, data




def main():
	

	argv = sys.argv	
	argc = len(argv)

	outputfile = "dat"
	nwfm = 0
	readch = 0
	if(argc==4):
		readch     = int(argv[1])
		outputfile = argv[2]
		nwfm = int(argv[3])
	else:
		print("usage: [recording chIDs in binary (ex. 1+3 chs --> 1+4=5] [filename] [# of wfm]")
		exit(0)

	fouts = [0]*4
	print(fouts)
	for i in range(4):
		if((readch & (2**i))>0):

			print("record: ch=", i)
			fouts[i] = open("{0}_ch{1}.txt".format(outputfile,str(i)), 'w')
			


	instr = init(IP)

	print(instr.ask("*IDN?"))
	time.sleep(1)

	


	set_DAQ(instr, readch)


	t_start  = -1
	t_end    = -1
	n_sample = -1
	for c in range(nwfm):

		header, data_chs = get_singleWFM(instr, readch)

		arr = [0]*4

		if(c==0):
			header = header.split(',')
			for i in range(4):
				if((readch & (2**i))>0):
					fouts[i].write("\t".join(header))
					fouts[i].write("\n")
			t_start = float(header[0])
			t_end   = float(header[1])
			n_sample = int(header[2])


		for i in range(4):
			if((readch & (2**i))>0):

				data = data_chs[i]
				
				dig = struct.unpack('B',data[1:2])[0]-48
				length_arr = [j-48 for j in struct.unpack('{}B'.format(dig),data[2:2+dig])]
				length_arr.reverse()

				sum = 0
				for j in range(len(length_arr)):
					sum += (10**j)*length_arr[j]

				sum //= 4

				arr[i] = struct.unpack('{}f'.format(sum), data[2+dig:2+dig+4*sum])

				strarr = [ "{:.8f}".format(s) for s in arr[i]]

				fouts[i].write("\t".join(strarr))
				fouts[i].write("\n")


		if((c%10)==0):
			print("c=", c , "(", 100.0*c/nwfm,"%)")

		if(SHOWONLINE==True):
			x = np.linspace(t_start, t_end, n_sample)

			for i in range(4):
				if((readch & (2**i))>0):
					volt = np.array(arr[i])
					plt.plot(x,volt)

			plt.pause(0.1)
			plt.clf()

	for i in range(4):
		if((readch & (2**i))>0):
			fouts[i].close()





if(__name__=="__main__"):
	main()










