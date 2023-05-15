"""
Dallas Maxim 1-Wire CRC8 algorithm
http://www.electronics-base.com/general-description/communication/128-crc-calculation-for-maxim-ibutton-device
https://github.com/WIPACrepo/fh_icm_api/blob/main/maxim_crc8.py
"""

import re
from fatcat_db.utils import pfprint
from fatcat_db.datatypes import isHexString


class MaximCRC8:

    degg = 'DEgg-MB or MMBv2'
    mdom = 'mDOM-MB or ICM'
    pdom = 'pDOM-MB or MMBv3'
    
    ds24B33  = 'DS24B33'
    ds2431   = 'DS2431'
    ds28ea00 = 'DS28EA00'

    # Map of UUID family to Upgrade board, Maxim chip
    families = {
        0x23: {
                  'board':  degg,
                  'chip':   ds24B33
              },
        0x2d: {
                  'board':  mdom,
                  'chip':   ds2431
              },
        0x42: {
                  'board':  pdom,
                  'chip':   ds28ea00
              },
    }

    # Maxim CRC8 table
    crcTable = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53
    ]

    def __init__(self, hexString):
        self.hexString = hexString
        self.expected = None
        

    def isValid(self):
        if self.canonicalizeUuid():
            self.analyze()
            return self.getStatus()
        else:
            return False
        
        
    def canonicalizeUuid(self):

        if self.hexString.startswith('0x'):
            pfprint(20, 'remove \"0x\" from eeprom hex string [{0}]'
                    .format(self.hexString))
            return False
        
        if not isHexString(self.hexString):
            pfprint(20, 'eeprom id [{0}] is not a hex string'
                    .format(self.hexString))
            return False
        
        if len(self.hexString)%2 != 0:
            pfprint(20, 'eeprom hex string length not a factor of 2')
            return False
        
        self.bytes = bytearray.fromhex(self.hexString)
        
        if len(self.bytes) != 8:
            pfprint(20, 'eeprom id not 8 bytes')
            return False
        
        found = False
        for family in self.families:
            if self.bytes[-1] == family:
                self.bytes.reverse()
                found = True
                break
        
        if not found:
            pfprint(20, 'eeprom id has no valid Dallas Maxim byte (bytes reversed?)')
            return False

        return True

    
    def crc8(self):
        
        crc = 0

        for i in range(7):
            tmp = crc ^ self.bytes[i]
            crc = self.crcTable[tmp]

        self.expected = hex(crc)
        
        pfprint(0, '[{1}] crc from json  = {0}'.format(hex(self.bytes[7]), __name__))
        pfprint(0, '[{1}] calculated crc = {0}'.format(hex(crc), __name__))
                
        if crc == self.bytes[7]:
            self.status = True
        else:
            self.status = False


    def analyze(self):
        self.family  = self.bytes[0]
        self.serial  = self.bytes[1:6]
        self.crc8()


    def getBytes(self):
        return self.bytes


    def getBoard(self):
        return self.families[self.family]['board']


    def getChip(self):
        return self.families[self.family]['chip']


    def getSerial(self):
        return self.serial

    
    def getCRC(self):
        return self.expected

    
    def getStatus(self):
        return self.status

