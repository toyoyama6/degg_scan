import pandas as pd
import matplotlib.pyplot as plt
import click

@click.command()
@click.argument('file')

def main(file):
    df = pd.read_hdf(file)
    print(df)


if __name__ == '__main__':
    main()
