import sys
import vxi11
import time
import struct

import numpy as np
import matplotlib.pyplot as plt


# config paramters

IP = "10.25.121.219"
TIMESTEP = "1.4e-3"
SHOWONLINE = False#True
#RANGE="DMAX"
RANGE="MAX"
#RANGE="DEF"

#time.sleep(1200)


def init(ip):

	instr = vxi11.Instrument(ip)
	return instr

def reset(instr):
	instr.write("*RST")

def set_DAQ(instr, readch):
	
	print("set config", readch)
	instr.write("ACQ:POIN {}".format("20000000"))
	# instr.write("ACQ:POIN {}".format("1000000"))
	
	cmd1 = "CHAN{0}:TYPE HRES".format(readch)
	cmd2 = "CHAN{0}:DATA:POIN {1}".format(readch, RANGE)

	instr.write(cmd1)
	instr.write("ACQ:POIN:AUT OFF")
	instr.write("TIM:SCAL {}".format(TIMESTEP))
	instr.write("FORM REAL")
	instr.write("FORM:BORD LSBF")
	instr.write(cmd2)

	instr.write("ACQ:POIN?")
	print(instr.read_raw())
	print(readch)
	print("HEAD=",instr.ask("CHAN{0}:DATA:HEAD?".format(readch)))
	print("POIN=",instr.ask("CHAN{0}:DATA:POIN?".format(readch)))
	print("OK")


def get_singleWFM(instr, readch):
	instr.ask("SING;*OPC?")
	
	header = instr.ask("CHAN{0}:DATA:HEAD?".format(readch))
	instr.write("CHAN{0}:DATA?".format(readch))
	return header, instr.read_raw()


nbin = 100
ran = (-0.3, 0.25)
debug = False

delts = []

ids = []
ts = []
peakHs = []
chgs = []




def main():
	
	st = time.time()
	argv = sys.argv	
	argc = len(argv)
	
	readch = int(argv[1])
	outputfile = argv[2]
	nwfm = int(argv[3])
	

	instr = init(IP)
	print(instr.ask("*IDN?"))


	set_DAQ(instr, readch)

	t_start  = -1
	t_end    = -1
	n_sample = -1
	for c in range(nwfm):

		header, data = get_singleWFM(instr, readch)
		header = header.split(',')
		t_start = float(header[0])
		t_end   = float(header[1])
		n_sample = int(header[2])

		T = np.linspace(t_start, t_end, n_sample)
		delt = (t_end-t_start)/n_sample
		print(delt)
		
		dig = struct.unpack('B',data[1:2])[0]-48
		length_arr = [j-48 for j in struct.unpack('{}B'.format(dig),data[2:2+dig])]
		length_arr.reverse()


		sum = 0
		for j in range(len(length_arr)):
			sum += (10**j)*length_arr[j]

		sum //= 4

		arr = np.array(struct.unpack('{}f'.format(sum), data[2+dig:2+dig+4*sum]),dtype=np.float32)
		hist, bin = np.histogram(arr, bins=nbin, range=ran)
		x = (bin[1:]+bin[:-1])/2
		ped = x[np.argmax(hist)]
		
		if(debug==True):
			hist, bin = np.histogram(arr-ped, bins=nbin, range=ran)
			x = (bin[1:]+bin[:-1])/2
			plt.hist(np.linspace(ran[0], ran[1], nbin), range=ran, bins=nbin, weights=hist, color="blue", edgecolor="black", histtype="stepfilled", alpha=0.5)
			plt.yscale("log")
			plt.show()

		hit = np.where(arr<ped-0.003)[0]

		narr = len(arr)
		peak = []
		peakH = []
		chg = []
		npz_wfm = []
		npz_delts = []
		for ihit in hit:
			if(ihit<10 or ihit>narr-10):
				break
			wfm = arr[ihit-10:ihit+10]
			wfm2 = arr[ihit-50:ihit+50]
			# npz_wfm.append(wfm)
			# np.savetxt('{}.txt'.format(ihit), wfm)
			
			smswfm = np.convolve(wfm, np.ones(5)/5.0, mode="same")
			if(smswfm[9]>smswfm[10]<smswfm[11]):
				peak.append(ihit)
				chg.append((ped*len(wfm)-np.sum(wfm))*delt*1e12/50/10)
				peakH.append(1000.0*(ped-np.min(wfm)))
				npz_wfm.append(wfm2)
			#plt.plot(smswfm)
			#plt.show()
		peak = np.float32(peak)

		delts.append(-1)
		delts.extend(delt*(peak[1:]-peak[:-1]))

		npz_delts.append(-1)
		npz_delts.extend(delt*(peak[1:]-peak[:-1]))

		ts.extend(peak*delt)
		chgs.extend(chg)
		peakHs.extend(peakH)
		ids.extend(np.int32(np.ones(len(chg))*c+0.001))
		#print(delts)

		#print(chgs)

		print("c=", c , "(", 100.0*c/nwfm,"%)")

		np.savez_compressed('{0}_{1}'.format(outputfile, c), npz_wfm, npz_delts)

		del data
		del arr

	fout = open(outputfile+".txt", "w")
	fout.write("ID\tTime\tDelt\tCharge\tPeakH\n")
	for i in range(len(ids)):
		fout.write("{0}\t{1:.4g}\t{2:.4g}\t{3:.3f}\t{4:.3f}\n".format(ids[i],ts[i], delts[i],chgs[i], peakHs[i]))
	fout.close()
	if(debug==True):
		#print(peakHs)
		plt.clf()
		plt.hist(peakHs, bins=nbin, range=(-1, 200), color="blue", edgecolor="black", histtype="stepfilled", alpha=0.5)
		plt.yscale("log")
		plt.show()

		#print(chgs)
		plt.clf()
		plt.hist(chgs, bins=nbin, range=(-1, 10), color="blue", edgecolor="black", histtype="stepfilled", alpha=0.5)
		plt.yscale("log")
		plt.show()

		plt.clf()
		plt.hist(delts, bins=nbin, range=(0, 1e-3), color="blue", edgecolor="black", histtype="stepfilled", alpha=0.5)
		plt.yscale("log")
		plt.show()
	ed = time.time()
	print(str(ed-st))




if(__name__=="__main__"):
	main()

