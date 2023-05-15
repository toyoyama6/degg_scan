import tables
import numpy as np
from matplotlib import pyplot as plt
import click
import scipy.stats as scs
from scipy.optimize import minimize

PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs_time')

def neg_llh(lmd, data):
    llh = np.sum(scs.poisson.logpmf(data, lmd))
    return -llh


def plot_and_fit_poisson(scaler_count):
    result = minimize(neg_llh,
                      x0=np.mean(scaler_count),
                      args=(scaler_count,))
    print(result)

    new_x = np.arange(np.min(scaler_count),
                      np.max(scaler_count)+1)

    low_percentile = (1 - 0.6827) / 2.
    high_percentile = 1 - low_percentile
    print(low_percentile, high_percentile,
          high_percentile - low_percentile)

    fig, ax = plt.subplots()
    ax.hist(scaler_count, histtype='step', lw=2, density=True)
    ax.plot(new_x, scs.poisson.pmf(new_x, result.x))
    ax.axvline(np.quantile(scaler_count, low_percentile), color='C2')
    ax.axvline(np.quantile(scaler_count, high_percentile), color='C2')
    ax.set_xlabel('Scaler count')
    ax.set_ylabel('PDF')
    fig.savefig(os.path.join(PLOT_DIR, 'figs_time/scaler_hist.pdf'))


@click.command()
@click.argument('file_name', type=click.Path(exists=True))
def main(file_name):
    if not os.path.exists(PLOT_DIR):
        os.mkdir(PLOT_DIR)
        print(f'Created directory: {PLOT_DIR}')

    f = tables.open_file(file_name)
    data = f.get_node('/data')
    event_id = data.col('event_id')
    scaler_count = data.col('scaler_count')

    plot_and_fit_poisson(scaler_count)

    fig, ax = plt.subplots()
    ax.scatter(event_id, scaler_count)
    fig.savefig(os.path.join(PLOT_DIR, 'scaler_scatter.pdf'))


if __name__ == '__main__':
    main()

