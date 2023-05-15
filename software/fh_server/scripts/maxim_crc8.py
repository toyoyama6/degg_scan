"""
    Dallas Maxim 1-Wire CRC8 algorithm.
    http://www.electronics-base.com/general-description/communication/128-crc-calculation-for-maxim-ibutton-device
"""

import re


class MaximCRC8:
    # Map of UUID _family to Upgrade board, Maxim chip
    _families = {0x23: {'chip': 'DS24B33', 'board': 'DEgg, MMBv2'},
                 0x2d: {'chip': 'DS2431', 'board': 'ICM, mDOMv2'},
                 0x42: {'chip': 'DS28Ea00', 'board': 'mDOMv3, MMBv3'}}

    # Maxim CRC8 table
    _crcTable = [0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163,
                 253, 31, 65, 157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227,
                 189, 62, 96, 130, 220, 35, 125, 159, 193, 66, 28, 254, 160,
                 225, 191, 93, 3, 128, 222, 60, 98, 190, 224, 2, 92, 223, 129,
                 99, 61, 124, 34, 192, 158, 29, 67, 161, 255, 70, 24, 250, 164,
                 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7, 219,
                 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196,
                 154, 101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69,
                 198, 152, 122, 36, 248, 166, 68, 26, 153, 199, 37, 123, 58,
                 100, 134, 216, 91, 5, 231, 185, 140, 210, 48, 110, 237, 179,
                 81, 15, 78, 16, 242, 172, 47, 113, 147, 205, 17, 79, 173, 243,
                 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80, 175,
                 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82,
                 176, 238, 50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76,
                 18, 145, 207, 45, 115, 202, 148, 118, 40, 171, 245, 23, 73, 8,
                 86, 180, 234, 105, 55, 213, 139, 87, 9, 235, 181, 54, 104,
                 138, 212, 149, 203, 41, 119, 244, 170, 72, 22, 233, 183, 85,
                 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
                 116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215,
                 137, 107, 53]

    def __init__(self, hexString):
        self._status = False
        self._bytes = None
        self._family = None
        self._serial = None
        self._canonicalizeUuid(hexString)
        self._analyze()

    def _canonicalizeUuid(self, hexString):
        """ Ensure input hex string is in required format
        """
        self._bytes = []
        if type(hexString) is str:
            hex = hexString
        elif type(hexString[0]) is str:
            hex = hexString[0]
        else:
            raise Exception('unknown input type', type(hexString))

        hex = re.sub('0x', '', hex, flags=re.IGNORECASE)
        hex = re.sub(',', '', hex, flags=re.IGNORECASE)
        self._bytes += bytearray.fromhex(hex)

        if len(self._bytes) != 8:
            raise Exception('input not 8 _bytes')

        # Hex string from ICM is in reverse byte order
        self._bytes.reverse()
        if self._bytes[0] not in self._families.keys():
            raise Exception('no valid Dallas Maxim _family byte found')

    def _crc8(self):
        """ Maxim's 1-Wire CRC8 algorithm
        """
        crc = 0

        for i in range(7):
            tmp = crc ^ self._bytes[i]
            crc = self._crcTable[tmp]

        if crc == self._bytes[7]:
            self._status = True
        else:
            self._status = False

    def _analyze(self):
        self._family = self._bytes[0]
        self._serial = self._bytes[1:7]
        self._crc8()

    def getBytes(self):
        return self._bytes

    def boardIsIcm(self):
        return self.getChip() == 'DS2431'

    def getChip(self):
        return self._families[self._family]['chip']

    def getSerial(self):
        return self._serial

    def getStatus(self):
        return self._status
