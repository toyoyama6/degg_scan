"""Legacy API for getting unmodified Mini-Mainboard sessions from the generic
getIcebootSession() factory.

This factory method will always return an unmodified MMB session
regardless of the target device identification jumper configuration.
"""
from .iceboot_session import getIcebootSession


def startMiniMainboardSession(host=None, port=None, devFile=None,
                              baudRate=None, debug=False):
    return getIcebootSession(host=host, port=port, devFile=devFile,
                             baudRate=baudRate, debug=debug,
                             class_name='UnmodifiedMMB')
