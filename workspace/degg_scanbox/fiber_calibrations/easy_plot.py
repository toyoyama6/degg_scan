import matplotlib.pyplot as plt
import glob
import numpy as np

data_dir = './graph/volt_charge/'
dfs = ['b_x_1', 'b_y_1', 't_x_1', 't_y_1']
color_list = ['black', 'blue', 'green', 'red']
plt.figure()
plt.title('Beam intensity', fontsize=18)
plt.xlabel('supply voltage for LD', fontsize=16)
plt.ylabel('photons per pulse', fontsize=16)
plt.grid()

for counter, i in enumerate(dfs):
    df = np.load(data_dir+i+'/volt_charge.npz')

    volt = df['arr_0']
    charge = df['arr_1']*1e-12/(3e6*1.6e-19)*4
    a, b = np.polyfit(volt, charge, 1)
    xd = np.arange(3, 10, 0.01)
    plt.plot(xd, a*xd+b, ls='--', color=color_list[counter])
    plt.scatter(volt, charge, color=color_list[counter], label=i)
plt.legend()
plt.savefig('eachfiber.png', bbox_inches='tight')
plt.close()

dfs = ['b_x_1', 'b_x_1_0', 'b_x_2', 'b_x_3']

plt.figure()
plt.title('Beam intencity', fontsize=18)
plt.xlabel('supply voltage for LD', fontsize=16)
plt.ylabel('charge (pC)', fontsize=16)
plt.grid()

for i in dfs:
    df = np.load(data_dir+i+'/volt_charge.npz')

    volt = df['arr_0']
    charge = df['arr_1']
    plt.scatter(volt, charge, label=i)
plt.legend()
plt.savefig('timefiber.png', bbox_inches='tight')
plt.close()
