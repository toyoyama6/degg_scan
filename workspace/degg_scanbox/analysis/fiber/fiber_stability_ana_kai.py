import click
import pandas as pd
import matplotlib.pyplot as plt


def analysis(data_dir, plotfilename):

    df = pd.read_csv(f'{data_dir}time_charge.csv')

    x = df['time']
    y = df['charge']

    plt.figure()
    plt.scatter(x, y)
    plt.title('time vs charge', fontsize=18)
    plt.ylabel('charge (pC)', fontsize=18)
    plt.xlabel('time (s)', fontsize=18)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.ylim(25, 100)
    plt.savefig(f'/home/icecube/Workspace/degg_scan/fiber_calibrations/graph/stability/{plotfilename}_kai.png', bbox_inches='tight')
    plt.close()



@click.command()
@click.argument('data_dir')
@click.argument('plotfilename')
def main(data_dir, plotfilename):
    analysis(data_dir, plotfilename)
if __name__ == '__main__':
    main()