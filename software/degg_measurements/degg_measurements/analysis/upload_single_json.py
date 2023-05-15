from fatcat_db.forwarder import Tunnel
from fatcat_db.runchecks import RunChecks
from fatcat_db.runchecks import Insert

import click

@click.command()
@click.argument('json_filename')
@click.option('--submit', is_flag=True)
def main(json_filename, submit):
    tunnel = Tunnel()

    if submit:
        ret = Insert(json_filename)
    else:
        ret = RunChecks(json_filename)


if __name__ == '__main__':
    main()

