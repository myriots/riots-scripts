#!/usr/bin/python
'''
 This file is part of Riots.
 Copyright (C) 2016 Riots Global OY <copyright@myriots.com>

 Riots is free software; you can redistribute it and/or modify it under the terms of the GNU Lesser General Public License
 as published by the Free Software Foundation; either version 2.1 of the License, or (at your option) any later version.

 Riots is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more details.

 You should have received a copy of the GNU Lesser General Public License along with Riots.
 If not, see <http://www.gnu.org/licenses/>.
'''
from __future__ import division

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import Int8StringReceiver
from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
import serial

from Crypto.Cipher import AES
import random
import math

serInst = None
tcpInst = None
ser = None

usbports= [ "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3","/dev/ttyAMA0" ]

class RiotsSerial(Int8StringReceiver):
  def __init__(self):
    global serInst, tcpInst
    serInst = self
    self.databuf = []
    self.tracebuf = {}
    self.empty_buffer = True
    self.session_crypto = None
    self.state = "NO_KEYS"

  def connectionMade(self):
    plain = "24" # SERVER_REQUESTS_INTRODUCTION
    msg = plain.decode("hex")
    self.sendString(msg)

  def stringReceived(self, data):
    buf = data.encode('hex')
    mama_op = buf[0:2]
    # CLIENT_INTRODUCTION
    if mama_op == "01":
      # Introduction
      self.base = buf[2:10]
      self.core = buf[10:18]
      self.chal = buf[18:26]
      self.block = 0
      print "STATUS: Core =",self.core
      print "STATUS: Base =",self.base
      self.tcp = tcpInst
      if self.tcp:
        self.tcp.mac = self.base
        self.tcp.core = self.core
        self.tcp.chal = self.chal
        self.tcp.clientInit()
      else:
        print "TCP not set"
      # Clear data buffer
      self.databuf = []
      self.empty_buffer = True

    elif mama_op == "02":
      print "STATUS: INTRODUCTION COMPLETE"
      self.tcp.sendData(data)

    #  CLIENT_DATA_POST, CLIENT_SAVED_DATA_POST
    elif mama_op == "03" or mama_op == "04":
      #verification
      if self.tcp:
        if self.state == "KEYS_RECEIVED":
          self.msg_len = int(data[2].encode("hex"), 16)
          if "80" == data[1].encode("hex"):
            debug_id = int(data[14].encode("hex")*256 + data[15].encode("hex"), 16)
            if self.msg_len < 12:
              debug_data = data[4:3+self.msg_len]
            packet_count = int(data[3].encode("hex"))
            if packet_count > 1:
              #more data coming, push to table
              if debug_id in self.tracebuf:
                #new trace, while previous is not complete
                print "OLD OTA DEBUG id="+str(debug_id)+":", self.tracebuf[debug_id]['data']
              self.tracebuf[debug_id] = {'data':debug_data, 'pkg_count':packet_count}
            else:
              print "OTA DEBUG id="+str(debug_id)+":", debug_data
          elif "81" == data[1].encode("hex"):
            debug_id = int(data[14].encode("hex")*256 + data[15].encode("hex"), 16)
            if debug_id in self.tracebuf:
              if self.msg_len < 12:
                debug_data = data[4:4+self.msg_len]
              packet_nro = int(data[3].encode("hex"))
              self.tracebuf[debug_id]['data'] = self.tracebuf[debug_id]['data'] + debug_data
              if packet_nro +1 == self.tracebuf[debug_id]['pkg_count']:
                # received everything
                print "OTA DEBUG id="+str(debug_id)+":", self.tracebuf[debug_id]['data'][:-1]
                del(self.tracebuf[debug_id])
          else:
            #
            # This is the place for integrating other systems to the riots system.
            #
            # Data received from RIOTS is found at this point in the DATA[] array.
            # Specific information about the data can be found from the support pages
            #
            #  LEN = 1      Len = 1         Len = 1      Len=1  Len=4     LEN=1
            # [Mama OP][Type of message][Len of message][Value][DATA][Coefficient]
            #
            # Measured data from the sensors will use following format
            # Mama OP       = 0x21
            # Type          = 0x1
            # LEN           = 0x5/0x6
            # Data          = XXXXXXXX
            # Coefficient   = 0-255
            #
            #print "RIOTS:", data[1:].encode("hex")
            self.tcp.sendData(data[0]+self.session_crypto.encrypt(data[1:17]))
        else:
          print "RIOTS:", data.encode("hex")
          self.tcp.sendData(data)
    # MAMA_SERIAL_DEBUG
    elif mama_op == "dd":
      print "DEVICE DEBUG:", data[1:]
    # MAMA_SERIAL_SEND_MORE_DATA
    elif mama_op == "ed":
      if len(self.databuf) > 0:
        #print "STATUS: Buffers left", len(self.databuf)
        self.sendOneFromBuffer()
      else:
        #print "STATUS: No more buffers to proceed"
        self.empty_buffer = True
    # Re-connect
    elif mama_op == "ad":
      print "STATUS: Mama connection renewal"
      plain = "24" # SERVER_REQUESTS_INTRODUCTION
      msg = plain.decode("hex")
      self.databuf = []
      self.empty_buffer = True
      self.sendString(msg)

    elif mama_op == "07":
      print "STATUS: Keys =", data[1:17].encode("hex")
      self.state = "KEYS_RECEIVED"
      self.session_crypto = AES.new(data[1:17], AES.MODE_ECB)

    else:
      print "UNKNOWN OP:", mama_op
      print "data", data.encode("hex")

  def sendData(self, msg):
    op = msg[0:1]
    # Remove operation from message
    msg = msg[1:]

    # Chop message
    for i in range(int(math.ceil(len(msg)/32))):
      if len(msg) > 32:
        self.databuf.append(op+msg[0:32])
        msg = msg[32:]
      else:
        self.databuf.append(op+msg)

    if self.empty_buffer:
      self.sendOneFromBuffer()

    self.empty_buffer = False

  def sendOneFromBuffer(self):
    send_msg = self.databuf.pop(0)
    if self.state == "KEYS_RECEIVED":
      self.sendString(send_msg[0]+self.session_crypto.decrypt(send_msg[1:]))
    else:
      self.sendString(send_msg)

class Riots(Int8StringReceiver):
  def __init__(self):
    global serInst, tcpInst
    tcpInst = self
    self.state = "INIT"
    self.session_crypto = None
    self.shared = None
    self.prev_op = ""

    print "Attach RIOTS usb"
    ser = None
    while ( ser == None ):
      for usbport in usbports:
        try:
          ser = serial.Serial(usbport, baudrate=38400, timeout=1)
        except:
          pass
        if ser:
          print "Device connected to port:" + usbport
          ser.close()
          SerialPort(RiotsSerial(), usbport, reactor, baudrate=38400)
          break
    self.ser = serInst

  def sendData(self, msg):
    self.sendString(msg)

  def connectionMade(self):
    #print "TCP connected!"
    if self.ser:
      self.state = "CONNECTED"
    else:
      print "No serial yet!"

  def connectionLost(self, reason):
    print "Disconnected"
    self.ser.state = "INIT"
    self.state = "INIT"

  def stringReceived(self, msg):
    buf = msg.encode('hex')
    serInst.sendData(msg);

  def clientInit(self):
    self.ser.state = "INIT"
    self.state = "INIT"
    # Client introduction
    op = "01"
    msg = (op+self.mac+self.core+self.chal).decode("hex")
    self.sendString(msg)

class RiotsClientFactory(ReconnectingClientFactory):
  def startedConnecting(self, connector):
    self.maxDelay = 5

  def buildProtocol(self, addr):
    self.resetDelay()
    return Riots()

  def clientConnectionLost(self, connector, reason):
    print 'Lost connection.'
    ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

  def clientConnectionFailed(self, connector, reason):
    print 'Connection failed.'
    ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

print "Starting Riots twisted client"
reactor.connectTCP("mama.riots.fi", 8000, RiotsClientFactory())
reactor.run()
