# Periodically print DEgg temperatures
import datetime
import time
import sys
from iceboot.iceboot_session import getParser, startIcebootSession

def loadFPGA(session):
    fwfile_name = "degg_fw_v0x101.rbf"
    session.flashConfigureCycloneFPGA(fwfile_name)
    vn = session.fpgaVersion()
    if (vn == 0xffff):
        sys.stderr.write("FPGA load failure\n")
        sys.exit(1)

    

def main():
    parser = getParser()
    (options, args) = parser.parse_args()
    session = startIcebootSession(parser)
    loadFPGA(session)

    # Loop forever
    while (1):
        delay = 60
        TempSLOADC = session.sloAdcReadChannel(7)
        TempAcc = session.readAccelerometerTemperature()
        TempMag = session.readMagnetometerTemperature()
        TempPres = session.readPressureSensorTemperature()
        print("%s: %s: %.2f %s: %.2f %s: %.2f %s: %.2f" %
            (datetime.datetime.utcnow(), "TMP235", TempSLOADC, "Accel",
            TempAcc, "Magnet", TempMag, "Press", TempPres) )
        sys.stdout.flush()
        time.sleep(delay)


if __name__ == "__main__":
    main()
