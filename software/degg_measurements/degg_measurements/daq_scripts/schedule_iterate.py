## This is the scheduler for the gain monitoring. 

#import schedule 
import time 
from measure_gain_mon import measure_gain_mon
import click 
import datetime

@click.command()
@click.argument('filename')
@click.option('--tag',default=None)
def main(filename,tag):
    print(datetime.datetime.now())
    #schedule.every(1).minutes.do(lambda: measure_gain_mon(filename,"test",1,tag))

    while True: 
        #schedule.run_pending()
        measure_gain_mon(filename, "test", 4, tag)
        time.sleep(30)

if __name__ == "__main__":
    main()
