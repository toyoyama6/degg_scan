import numpy as np
import matplotlib.pyplot as plt
import datetime
import time
import pickle
from iceboot.iceboot_session import getIcebootSession

def irq_to_samplerate(irq) -> float:
    return 4.823e7 / (irq + 3.5) - 71.7

AR_config = {"gain"                : 100,
             "n_samples"           : 10000}

print("initializing AM...")
s = getIcebootSession(host="localhost", port=5000)
s.AMInit()
time.sleep(1)

print("discharging capacitor bank...")
s.AMdischargeOn()
time.sleep(1)

print("setting neutral output state...")
s.AMsetFB_neutral()

# print("setting ground output state...")
# s.AMsetFB_GND()

print("looking fo rsensor base address")
s.ARfindBaseAddress()

print("setting receive mode...")
s.AMsetReceiveMode()

print("receiver status: ", s.ARgetStatus())

print("setting n samples to "+ str(AR_config["n_samples"]) + "...")
s.ARsetWaveformSample(AR_config["n_samples"])

# s.ARsetPretriggerSample(5000)

print("setting gain to "+ str(AR_config["gain"]) +"...")
s.ARsetGain(AR_config["gain"])

print("getting samplerate...")
irq = s.ARgetSampleIRQ()
fs = irq_to_samplerate(irq)

print("getting gain...")
gain = s.ARgetGain()

f1 = plt.figure("f1", figsize=(10,8))
ax1 = f1.add_subplot(111)

for i in range(10):
    print("\n", i)

    print("sending software trigger...")
    s.ARsendSWTrigger()

    # print("sending hardware trigger...")
    # s.ARsendHWTrigger()

    time.sleep(0.3) #  wait for waveform recording to finish (0.1 ms waveform duration)

    print("reading waveform...")
    wf = np.array(s.ARgetWaveformData())
    t = np.linspace(0, len(wf)/fs, len(wf))
    print("mean = ", np.mean(wf))
    print("std = ", np.std(wf))
    # wf = wf - np.mean(wf)

    time.sleep(0.1) # wait for waveform transfer to finish

    status = s.ARgetStatus()
    print("receiver status: ", status)
    if status != "2":
        print("problem occured!")

    ax1.plot(t, wf+(i*1000), label=str(i))
    data = np.array([t, wf])
    np.save("data/wf_" + str(i)+".npy", data)

name = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
# n_samples = AR_config["n_samples"]
# data_dict = {"n_samples" : n_samples, "samplerate" : fs, "gain" : gain, "t" : t, "wf" : wf}
# f = open("data/receiver/wf_"+name+".pkl", "wb")
# f.close()

ax1.set_title("gain ="+str(AR_config["gain"])+", n ="+str(AR_config["n_samples"])+", samplerate ="+str(int(fs)))
ax1.set_xlabel("t / s")
ax1.set_ylabel("ADC")
ax1.legend()
f1.savefig("plots/receiver/wf_"+name+".png")
f = open("data/receiver/wf_"+name+".pkl", "wb")
pickle.dump(f1, f)
f.close()
