import time

def to2Int(x):
    # argument: int (>=0, <65536)
    # return upper int and lower int
    if (x < 0 or x >= 16**4):
        print("error: cannot convert " + str(x) + " into 2 bytes")
        return
    
    return [x//(16**2), x%(16**2)]

def to4Int(x):
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

def calcCRC(command):
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

    res = to2Int(res)
    # upper byte <-> lower byte
    res.reverse()
    res = bytes(res)

    return command + res

def genCommand(slaveAddress, functionCode, dataStart, dataNum, data):
    # generate command
    
    # array of int
    res = []
    res += [slaveAddress]
    res += [functionCode]

    # dataStart, dataNum: 2 byte
    res += to2Int(dataStart)
    res += to2Int(dataNum)

    res += [2*dataNum]

    # e in data: 4 byte?
    for e in data:
        res += to4Int(e)

    res = bytes(res)
    res = calcCRC(res)

    return res

def genCommand2(slaveAddress, functionCode, dataStart, data):
    # generate command (ZHOME)
    
    # array of int
    res = []
    res += [slaveAddress]
    res += [functionCode]

    # dataStart, dataNum: 2 byte
    res += to2Int(dataStart)

    # e in data: 2 byte
    for e in data:
        res += to2Int(e)

    res = bytes(res)
    res = calcCRC(res)

    return res

"""
slaveAddress = 1
functinoCode = 0x10
dataStart = 0x1802 #6146
dataNum = 4
displacement = 1000
velocity = 5000
data = [displacement, velocity]
command = genCommand(slaveAddress, functinoCode, dataStart, dataNum, data)
print(command)

res = to4Int(5000)
print(res)
res = bytes(res)
print(res)
"""

print(bytes(to4Int(-5000)))

def moveRelative(slaveAddress, dist):
    data = [dist]
    command = genCommand(slaveAddress, 10, 0, 2, data)
    # cliant.write(command)
    print(command)

def ZHOMEOn(slaveAddress):
    functinoCode = 0x06
    dataStart = 0x007D
    data = [0x0010]
    command = genCommand2(slaveAddress, functinoCode, dataStart, data)
    print(command)

def ZHOMEOff(slaveAddress):
    functinoCode = 0x06
    dataStart = 0x007D
    data = [0x0000]
    command = genCommand2(slaveAddress, functinoCode, dataStart, data)
    print(command)

def moveToHome(slaveAddress):
    ZHOMEOn(1)
    time.sleep(5)
    ZHOMEOff(1)

moveToHome(1)