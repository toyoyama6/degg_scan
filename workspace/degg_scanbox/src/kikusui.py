import vxi11
import time
import sys

class PMX70_1A:

    def __init__(self, ip):

        self._ip = ip

    def connect_instrument(self):
        try:
            ps = vxi11.Instrument(self._ip)
            print('Get this power supply\n -->> ' + ps.ask('*IDN?') + '\n')

        except:
            print('IP address ERROR.\nPlease check PY File you ran.')
            sys.exit()

        time.sleep(2)

    def set_volt_current(self, volt, current):

        if volt <= 10 and current <= 0.1:
            print('Voltage & Currnt setting is GOOD.  KEEP GOING!!')

        else:
            print('Voltage & Currnt setting is BAD!!\nPlease check PY File you ran!!')
            sys.exit()

        try:
            ps = vxi11.Instrument(self._ip)

        except:
            print('IP address ERROR.\nPlease check PY File you ran.')
            sys.exit()

        print(ps.ask("*IDN?"))
        ps.write("VOLT " + str(volt))
        ps.write("CURR " + str(current))
        ps.write("OUTP 1")
        time.sleep(3)
        res = ps.ask("MEAS:ALL?")
        print('current and volt -->> ' + res + '\n')
        return res

    def change_volt_current(self, volt, current):

        if volt <= 10 and current <= 0.1:
            print('Voltage & Currnt setting is GOOD.  KEEP GOING!!')

        else:
            print('Voltage & Currnt setting is BAD!!\nPlease check PY File you ran!!')
            sys.exit()
        
        try:
            ps = vxi11.Instrument(self._ip)

        except:
            print('IP address ERROR.\nPlease check PY File you ran.')
            sys.exit()

        ps = vxi11.Instrument(self._ip)
        ps.write("VOLT " + str(volt))
        ps.write("CURR " + str(current))
        time.sleep(1)
        res = ps.ask("MEAS:ALL?")
        print(res + '\n')
        return res

    def turn_off(self):

        try:
            ps = vxi11.Instrument(self._ip)

        except:
            print('IP address ERROR.\nPlease check PY File you ran.')
            sys.exit()

        ps = vxi11.Instrument(self._ip)
        ps.write("OUTP 0")
        print("turn off the device\n")

