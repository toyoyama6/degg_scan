"""Legacy API for getting Acoustic module sessions from the generic
getIcebootSession() factory.

This factory method will always return an Acoustic module session
regardless of the target device identification jumper configuration.
"""
from .iceboot_session import getIcebootSession


def startAM_Session(host=None, port=None, devFile=None, baudRate=None,
                    debug=False):
    return getIcebootSession(host=host, port=port, devFile=devFile,
                             baudRate=baudRate, debug=debug,
                             class_name='Acoustic')
