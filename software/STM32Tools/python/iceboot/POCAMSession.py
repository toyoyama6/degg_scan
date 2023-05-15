"""Legacy API for getting POCAM sessions from the generic
getIcebootSession() factory.

This factory method will always return an POCAM session
regardless of the target device identification jumper configuration.
"""
from .iceboot_session import getIcebootSession


def startPOCAMSession(host=None, port=None, devFile=None, baudRate=None,
                      debug=False):
    return getIcebootSession(host=host, port=port, devFile=devFile,
                             baudRate=baudRate, debug=debug,
                             class_name='POCAM')
