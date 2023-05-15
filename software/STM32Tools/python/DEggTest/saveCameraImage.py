from iceboot.iceboot_session import getParser, startIcebootSession
from optparse import OptionParser

IMAGEFILE = 'ArduCAM_WINDOWCROP_480p.raw.gz'

def main():
    parser = getParser()
    parser.add_option("--camera", dest="camera",
                      help="Camera Selector", default="1")
    parser.add_option("--gain", dest="gain",
                      help="Camera Gain", default="2")
    parser.add_option("--exposure", dest="exposure",
                      help="Camera Exposure time, ms", default="30")
    parser.add_option("--file", dest="file",
                      help="Camera Image Raw file", default=IMAGEFILE)

    (options, args) = parser.parse_args()

    camera = int(options.camera)
    rawFile = options.file
    gain = int(options.gain)
    exposure = int(options.exposure)

    s = startIcebootSession(parser)

    s.enableCalibrationPower()

    s.setCalibrationSlavePowerMask(camera)

    s.setCameraEnableMask(0xff)

    s.initCamera(camera)

    s.setCameraGain(camera, gain)

    s.setCameraExposureMs(camera, exposure)

    s.captureCameraImage(camera)

    s.saveCameraImageFile(camera, rawFile)
    s.flashFileGet(rawFile)
    s.printLogOutput()


if __name__ == "__main__":
    main()
