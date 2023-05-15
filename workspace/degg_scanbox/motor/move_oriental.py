from src.oriental_motor import AZD_AD
import click


@click.command()
@click.argument('slave_address')
@click.argument('distance')
@click.option('--direction', '-d', default='positive')
def main(slave_address, distance, direction):
    driver = AZD_AD(port='/dev/ttyUSB0')
    if(direction=='positive'):
        driver.moveRelative(int(slave_address), float(distance))
    if(direction=='negative'):
        driver.moveRelative(int(slave_address), -float(distance))

if __name__ == '__main__':
    main()
