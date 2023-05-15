import serial
import time

class AZD_AD():

    def __init__(self, port=None, bps=115200, t_out=0.01, size=64):

        self._driver = serial.Serial(port, bps, timeout=t_out, parity=serial.PARITY_EVEN,stopbits=serial.STOPBITS_ONE)

        self.size = 64

    def to2Int(self, x):
        # argument: int (>=0, <65536)
        # return upper int and lower int
        if (x < 0 or x >= 16**4):
            print("error: cannot convert " + str(x) + " into 2 bytes")
            return
        
        return [x//(16**2), x%(16**2)]

    def to4Int(self, x):
        # argument: int (>= -16**8/2, < 16**8/2)
        if (x < -16**8/2 or x >= 16**8/2):
            print("error: cannot convert " + str(x) + " into 4 bytes")
            return
        
        if(x >= 0):
            pass
        else:
            x += 16**8

        res = []
        for _ in range(4):
            res.append(x%(16**2))
            x //= 16**2
        res.reverse()

        return res

    def calcCRC(self, command):
        # calculate last 2 bytes of command (= CRC-16 error check)
        # argument is command without error check (type: bytes)
        res = 0xFFFF

        for byte in command:
            res ^= byte
            cnt = 0
            while(cnt < 8):
                if (res&1):
                    res >>= 1
                    cnt += 1
                    res ^= 0xA001
                else:
                    res >>= 1
                    cnt += 1

        res = self.to2Int(res)
        # upper byte <-> lower byte
        res.reverse()
        res = bytes(res)

        return command + res

    def genCommand(self, slaveAddress, functionCode, dataStart, dataNum, data):
        # generate command
        
        # array of int
        res = []
        res += [slaveAddress]
        res += [functionCode]

        # dataStart, dataNum: 2 byte
        res += self.to2Int(dataStart)
        res += self.to2Int(dataNum)

        res += [2*dataNum]

        # e in data: 4 byte?
        for e in data:
            res += self.to4Int(e)

        res = bytes(res)
        res = self.calcCRC(res)

        return res

    def genCommand2(self, slaveAddress, functionCode, dataStart, data):
        # generate command (ZHOME)
        
        # array of int
        res = []
        res += [slaveAddress]
        res += [functionCode]

        # dataStart, dataNum: 2 byte
        res += self.to2Int(dataStart)

        # e in data: 2 byte
        for e in data:
            res += self.to2Int(e)

        res = bytes(res)
        res = self.calcCRC(res)

        return res

    def moveRelative(self, slaveAddress, dist):
        data = [dist]
        command = self.genCommand(slaveAddress, 10, 0, 2, data)
        self._driver.write(command)
        self._driver.read(self.size)
        return command

    def ZHOMEOn(self, slaveAddress):
        functinoCode = 0x06
        dataStart = 0x007D
        data = [0x0010]
        command = self.genCommand2(slaveAddress, functinoCode, dataStart, data)
        self._driver.write(command)
        self._driver.read(self.size)
        return command

    def ZHOMEOff(self, slaveAddress):
        functinoCode = 0x06
        dataStart = 0x007D
        data = [0x0000]
        command = self.genCommand2(slaveAddress, functinoCode, dataStart, data)
        self._driver.write(command)
        self._driver.read(self.size)
        return command

    def moveToHome(self, slaveAddress):
        self.ZHOMEOn(slaveAddress)
        time.sleep(5)
        self.ZHOMEOff(slaveAddress)

    def moveRelative(self, slaveAddress, distance):

        if(slaveAddress==1 or slaveAddress==3):
            displacement = int(distance * 500/3)
        elif(slaveAddress==2 or slaveAddress==4):
            displacement = int(distance * 500)
        elif(slaveAddress==5):
            displacement = int(distance * 100)
            
        functionCode = 0x10
        dataStart = 0x0058
        dataNum = 16

        driveData = 0 # No.
        driveWay = 2 # 2: relative
        velocity = 500
        startRate = 400
        stopRate = 400
        electricCurrent = 1000 # >=0, <=1000
        reflection = 1 # 1: reflect all data

        data = [driveData, driveWay, displacement, velocity, startRate, stopRate, electricCurrent, reflection]

        command = self.genCommand(slaveAddress, functionCode, dataStart, dataNum, data)
        self._driver.write(command)
        self._driver.read(self.size)
        return command