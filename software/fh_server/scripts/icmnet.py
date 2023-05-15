#
# Class implementing the JSON over ZMQ REQ/REP interface
# to domnet.
#
import zmq

class ICMError(Exception):
  pass

class ICMNet():

  # FieldHub device number
  FH_DEVICE_NUM = 8
  # Device / command port offset
  FH_PORT_OFFSET = 1000
  
  def __init__(self, port, host="localhost"):
    self.host = host
    self.port = port
    self.socket = None
    self.context = zmq.Context()
    self.connect()

  def __del__(self):
    if (self.socket is not None):
      self.socket.close()
    if (self.context is not None):
      self.context.term()
    
  def connect(self):      
    self.socket = self.context.socket(zmq.REQ)
    self.socket.RCVTIMEO = 11000
    self.socket.LINGER = 0
    self.socket.connect("tcp://%s:%s" % (self.host,self.port))

  def reset(self):
    if (self.socket is not None):
      self.socket.close()
    self.connect()

  def request(self, cmd):
    # Command can be string or dict
    if isinstance(cmd, dict):
      req = cmd
    else:
      # Try to parse request as string
      # All commands are 
      #  <cmd> <device> [<value>]
      # except the generic read/write which are
      #  <cmd> <device> <register> [<value>]
      # In general the syntax will be checked
      # by the receiver
      args = cmd.split()
      req = {}
      try:
        req['command'] = args[0].lower()
        req['device'] = args[1].lower()
        if (req['command'].lower() != "write") and (req['command'].lower() != "read"):
          req['value'] = args[2].lower()
        else:
          req['register'] = args[2].lower()
          req['value'] = args[3].lower()
      except IndexError:
        pass      
    self.socket.send_json(req)
    try:
      reply = self.socket.recv_json()
    except zmq.error.Again:
      self.reset()
      reply = { "status" : "?NOREPLY" }
    return reply
