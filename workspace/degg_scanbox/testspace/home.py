import serial
import time

mot = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.01, parity=serial.PARITY_EVEN,stopbits=serial.STOPBITS_ONE) # COMポートは自分の奴を入れる
size = 16 # 適当にサイズを区切る
print(mot.name)

cmd = b"\x01\x06\x00\x7d\x00\x10\x18\x1e"
mot.write(cmd)
res = mot.read(size)
print(res)

time.sleep(10)

cmd = b"\x01\x06\x00\x7d\x00\x00\x19\xd2"
mot.write(cmd)
res = mot.read(size)
print(res)