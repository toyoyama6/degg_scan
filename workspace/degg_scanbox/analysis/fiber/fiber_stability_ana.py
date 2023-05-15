import click
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
import glob
import numpy as np




def analysis(data_file, graph_name, graph_dir):
    df = pd.read_csv(data_file)
    time = df['time']
    charge = df['charge']

    plt.figure()
    plt.title('LD stability', fontsize=18)
    plt.xlabel('time (s)', fontsize=16)
    plt.ylabel('charge(pC)', fontsize=16)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.scatter(time, charge)
    plt.savefig(f'{graph_dir}{graph_name}.png', bbox_inches='tight')




@click.command()
@click.argument('data_dir')
@click.argument('graph_name')
@click.option('--graph_dir', '-g', default='/home/icecube/Workspace/degg_scan/fiber_calibrations/graph/stability/')
def main(data_dir, graph_name, graph_dir):

    graph_dir = graph_dir + graph_name + '/'
    try:
        os.mkdir(graph_dir)
    except:
        ans = input('Overwrite ??? (y/n): ')
        if(ans=='y'):
            print('OK!!')
        else:
            sys.exit()
    
    analysis(data_dir, graph_dir)


if __name__ == "__main__":
    main()
##end