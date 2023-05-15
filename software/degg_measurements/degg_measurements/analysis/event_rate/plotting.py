from matplotlib import pyplot as plt
import os
import numpy as np
import click


def plot_charge_histogram(charges_list, legend_entries, plot_name, bins=None):
    fig, ax = plt.subplots()

    n_waveforms_per_file = [len(charges) for charges in charges_list]

    if not np.all(n_waveforms_per_file == n_waveforms_per_file[0]):
        scaling_factors = [n_waveforms_per_file[0]/n_waveforms_per_file_i
                           for n_waveforms_per_file_i in n_waveforms_per_file]
    else:
        scaling_factors = np.ones_like(n_waveforms_per_file)

    for i, charges in enumerate(charges_list):
        if bins is None:
            bins = np.linspace(np.min(charges),
                               np.max(charges),
                               51)

        hist, edges = np.histogram(charges, bins)
        center = (edges[1:] + edges[:-1]) * 0.5

        ax.errorbar(center, hist*scaling_factors[i],
                    xerr=np.diff(edges)*0.5,
                    yerr=np.sqrt(hist)*scaling_factors[i],
                    fmt='o', markersize=0,
                    color='C{}'.format(i),
                    label=legend_entries[i].upper(),
                    lw=2)
        ax.hist(center, bins=bins,
                weights=hist*scaling_factors[i],
                color='C{}'.format(i),
                histtype='step', lw=2)
    ax.set_xlabel('Charge / pC')
    ax.set_ylabel('Entries')
    ax.set_yscale('log')
    ax.legend()
    if plot_name is None:
        plt.show()
    else:
        plt.savefig(plot_name, bbox_inches='tight')


@click.command()
@click.argument('input_file', nargs=-1)
@click.option('--plot_name', '-n', default=None)
def main(input_file, plot_name):
    bins = np.linspace(-1, 4, 51)
    plot_charge_histogram(input_file, plot_name, bins=bins)


if __name__ == '__main__':
    main()
    
