#!/usr/bin/env python

from serial import Serial
import struct
import time
import datetime

FW_VERS_REG  = 0xFF
TXBUF_REG    = 0x0A
RXBUF_BC_REG = 0x09
RXBUF_REG    = 0x08
MBPWR_REG    = 0x06

CSTAT_REG    = 0x02
CTRL2_REG    = 0x01
CTRL1_REG    = 0x00

MBPWR_ENABL  = 0x454E
MBPWR_DSABL  = 0x6469

READ_CMD     = 8
WRITE_CMD    = 9

TX_HEADER_OVH = 5
RX_HEADER_OVH = 4

MIN_ICM_WP_ADDR = 0x0
MAX_ICM_WP_ADDR = 0x8


class icm_serial():

  def __init__(self, devFile, debug=False):
    self.ser = Serial(devFile, 3000000, timeout=0,
                      writeTimeout=10, xonxoff=0, rtscts=1)
    self.debug = debug
    while len(self.serial_receive(1024)) > 0:
      pass

  def serial_send(self, data):
    if self.debug:
      print "SEND: %s" % [hex(x) for x in data]
    self.ser.write(data)


  def serial_receive(self, cnt):
    data = self.ser.read(cnt)
    if self.debug and len(data) > 0:
      print "RECV: %s" % [hex(ord(x)) for x in data]
    return data
  

  def readReg(self, icm, reg, cnt, timeout=1):
    tot = cnt + RX_HEADER_OVH
    pkt = bytearray()
    pkt.append(READ_CMD)
    pkt.extend(struct.pack(">H", tot))
    pkt.append(icm)
    pkt.append(reg)
    self.serial_send(pkt)
    ret = bytearray()
    stopTime = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout)
    while len(ret) < tot:
      ret.extend(self.serial_receive(tot - len(ret)))
      while (len(ret) >= 2) and ((ret[0] & 0x80) == 0x80):
        ret = ret[2:]
      if datetime.datetime.utcnow() > stopTime:
        raise Exception("recvMsg timed out. %s bytes received, expected %d" % (len(ret), cnt))
    ocnt = struct.unpack(">H", str(ret[:2]))[0]
    if ocnt != tot:
      raise Exception("Got message with bad byte count (%s) Expect %s" % (ocnt, tot))
    if ret[2] != icm:
      raise Exception("Got message from wrong ICM (%s) Expect %s" % (ret[2], icm))
    if ret[3] != reg:
      raise Exception("Got message from wrong reg (%s) Expect %s" % (ret[3], reg))
    return ret[4:]

  def writeReg(self, icm, reg, data):
    pkt = bytearray()
    pkt.append(WRITE_CMD)
    pkt.extend(struct.pack(">H", len(data) + TX_HEADER_OVH))
    pkt.append(icm)
    pkt.append(reg)
    pkt.extend(bytearray(data))
    self.serial_send(pkt)

  def writeOne(self, icm, reg, value):
    self.writeReg(icm, reg, struct.pack(">H", value))

  def readOne(self, icm, reg, timeout=1):
    return struct.unpack(">H", str(self.readReg(icm, reg, 2, timeout)))[0]

  def sendMsg(self, icm, data):
    maxLen = 4096 - TX_HEADER_OVH
    txData = data[:maxLen]
    self.writeReg(icm, TXBUF_REG, txData)
    if len(data) > maxLen:
      self.sendMsg(icm, data[maxLen:])
    
  def recvMsg(self, icm, cnt, timeout=1):
    ret = bytearray()
    stopTime = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout)
    while len(ret) < cnt:
      bc = self.readOne(icm, RXBUF_BC_REG)
      maxLen = 4096 - RX_HEADER_OVH
      if bc > maxLen:
        bc = maxLen
      if bc > 0:
        nr = cnt - len(ret)
        if nr > bc:
          nr = bc
        ret.extend(self.readReg(icm, RXBUF_REG, nr, timeout))
      if datetime.datetime.utcnow() > stopTime:
        raise Exception("recvMsg timed out. %s bytes received, expected %d" % (len(ret), cnt))
    return ret

  def recvAll(self, icm, t):
    ret = bytearray()
    time.sleep(t)
    ret.extend(self.readReg(icm, RXBUF_REG, self.readOne(icm, RXBUF_BC_REG)))
    return ret

  def startSession(self, icm):
    # Enable mainboard power
    self.writeOne(icm, MBPWR_REG, MBPWR_ENABL)
    # Enable MCU
    self.writeOne(icm, CTRL1_REG, 0x0000)
    while len(self.recvAll(icm, 0.2)) > 0:
      pass

  def scanWire(self):
    print("ICM Address   FW Version")
    print("-------------------------")
    for icm in range(MIN_ICM_WP_ADDR, MAX_ICM_WP_ADDR+1):
      fw = "<not found>"
      try:
        fwv = self.readOne(icm, FW_VERS_REG, 0.2)
        fw = "%d.%d.%d" % ((fwv & 0xFF00) >> 8, (fwv & 0x00F0) >> 4, fwv & 0x000F)
      except:
        pass
      print("        0x%1s   %11s" % (icm, fw))
