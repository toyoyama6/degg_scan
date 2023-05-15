import time
import sys
import click
from termcolor import colored

def power_switch(option):
    print("Operating Power Switch")
    if(option.lower() == "on"):
        ison = True
    elif(option.lower() == "off"):
        ison = False
    else:
        raise ValueError('No valid power option (on/off)!')

    try:
        import board
        import digitalio
        minFH = digitalio.DigitalInOut(board.C0)
        minFH.direction = digitalio.Direction.OUTPUT
        minFH.value = ison
    except:
        print(colored('CRITICAL ERROR - Could Not Set MFH Power (Switch)!', 'red'))
        raise IOError('Control of MFH via power switch failed!')

    time.sleep(0.2)
    return option

@click.command()
@click.option('--power', type=click.Choice(['on', 'off'], case_sensitive=False))
def main(power):
    print(f"Executing MFH Power Switch: {power}")
    out = power_switch(power)
    print(out)

if __name__ == "__main__":
    main()

