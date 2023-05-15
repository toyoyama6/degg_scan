from iceboot.iceboot_session import getParser
from degg_measurements.utils import startIcebootSession
from iceboot.iceboot_session_cmd import stripStackSize
from optparse import OptionParser

def main():
    parser = getParser()
    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)

    get_fpga_version(session)
    get_sensor_info(session)
    get_pressure_info(session)

def get_fpga_version(session):
    ##issue a direct command through the python wrapper
    fpgaVersion = session.cmd('fpgaVersion .s drop')
    fpgaVersion = stripStackSize(fpgaVersion)
    print("FPGA Software Version")
    print(fpgaVersion)

def get_sensor_info(session):
    ##issue commands using the wrapper functions
    sensor_list = ["Light Sensor", "Temperature Sensor", "Voltage Ch0",
                   "Current Ch0", "Volage Ch1", "Current Ch1"]

    sensor_number_list = [6, 7, 8, 9, 10, 11]

    index = 0
    for channel_number in sensor_number_list:
        sensor = sensor_list[index]
        value = session.sloAdcReadChannel(channel_number)
        print(f"Sensor: {sensor}")
        print(value)
        index += 1

def get_pressure_info(session):
    print("Pressure sensor:")
    pressure = session.readPressure()
    print(pressure)

if __name__ == "__main__":
    main()

##end
