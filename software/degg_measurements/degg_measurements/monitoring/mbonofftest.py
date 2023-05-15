import subprocess
import time
import click

def mb_powercycle(port):
    wirepairaddress = int(port-5000) % 4
    icmport = 1000 + int(port) - wirepairaddress
    subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/mb_off.py -p {icmport} -w {wirepairaddress}'.split())
    time.sleep(2)
    subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/icm_probe.py -p {icmport} -w {wirepairaddress}'.split())
    subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/mb_on.py -p {icmport} -w {wirepairaddress}'.split())
    time.sleep(2)
    subprocess.run(f'python3 /home/scanbox/mcu_dev/fh_server/scripts/icm_probe.py -p {icmport} -w {wirepairaddress}'.split())

@click.command()
@click.option('--port', default=5000)
def main(port):
    mb_powercycle(port)

if __name__ == '__main__':
    main()
