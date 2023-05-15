import click
from degg_measurements.analysis import RunHandler


@click.command()
@click.argument('run_number', type=int)
def main(run_number):
    run_handler = RunHandler(run_number)
    run_handler.submit_based_on_meas_class()


if __name__ == '__main__':
    main()

