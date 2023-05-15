import numpy as np
import tables
import matplotlib.pyplot as plt

loc = '/home/scanbox/data/develop/flasher_baseline_scaler/20210422_02/'

config = -1
led_configs = [0x0001,
               -0x0001, 0x0002,
               -0x0002, 0x0004,
               -0x0004, 0x0008,
               -0x0008, 0x0010,
               -0x0010, 0x0020,
               -0x0020, 0x0040,
               -0x0040, 0x0080,
               -0x0080, 0x0100,
               -0x0100, 0x0200,
               -0x0200, 0x0400,
               -0x0400, 0x0800,
               -0x0800]
'''
led_bias_powers = [0x3FFF, 0x4FFF, 0x5FFF, 0x6FFF, 0x7FFF,
                   #0x8FFF, 0x9FFF, 0xAFFF, 0xBFFF]
                   0x8FFF, 0x9FFF, 0xAFFF, 0xBFFF, 0xCFFF]
'''
led_bias_powers = [0x4FFF, 0x5AFF, 0x60FF, 0x6AFF, 0x6FFF, 0x7AFF, 0x7FFF, 0xCFFF]

tracker = [1] * len(led_configs)

pmt = "SQ0406"

i = 1
for led_config in led_configs:
    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()
    print(f"Config {hex(led_config)}")

    for led_bias_power in led_bias_powers:
    
        pwr = int(led_bias_power)
        config = int(led_config)
        print(f"Power {hex(pwr)}")
        f = loc + f"{pmt}_{pwr}_{config}_{i}_WFs.hdf5"
        print(f)
        try:
            t = tables.open_file(f) 
        except:
            print("break!")
            break
        nn = t.get_node("/data")
        mean_wf = np.zeros(len(nn.col("waveform")[0])) 
        #print(f'Num wfs: {len(nn.col("waveform"))}')
        for wf in nn.col("waveform"): 
            wf = np.array(wf) 
            mean_wf += wf 
        mean_wf = mean_wf/len(nn.col("waveform"))  

        ##null measurement
        if led_config < 0:
            ax1.plot(nn.col("time")[0], mean_wf, label=f'{hex(led_bias_power)}') 
        else:
            ax2.plot(nn.col("time")[0], mean_wf, label=f'{hex(led_bias_power)}') 
    tracker[i] = tracker[i] + 1
    i += 1

    if led_config < 0:
        ax1.legend(loc=0, title='LED Power')
        ax1.set_title(f"{pmt}: {config}") 
        fig1.savefig(loc + f"null_{pmt}_{config}.pdf")
        plt.close(fig1)
    
    else:
        ax2.legend(loc=0, title='LED Power')
        ax2.set_title(f"{pmt}: {config}") 
        fig2.savefig(loc + f"on_{pmt}_{config}.pdf")
        plt.close(fig2)

##end
