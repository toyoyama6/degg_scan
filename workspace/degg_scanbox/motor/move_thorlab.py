from src.thorlabs_hdr50 import *
import click


@click.command()
@click.argument('distance')
@click.option('--direction', '-d', default='positive')
def main(distance, direction):
    stage = HDR50(serial_number="40106754", home=False, swap_limit_switches=False)
    if(direction=='negative'):
        stage.move_relative(-int(distance))
    else:
        stage.move_relative(int(distance))
    stage.wait_up()
    print(stage.status)

if __name__ == '__main__':
    main()
