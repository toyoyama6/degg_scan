
from xdomapp_data import decodeString
import struct

class Datatype(object):
  UNSIGNED_INT     = 1
  SIGNED_INT       = 2
  FLOAT            = 3
  DOUBLE           = 4
  VOID             = 5
  STRING           = 6
  BYTEARRAY        = 7


def define_opcode(opcode, datatype, datasize=None, timeout=1):
    ret = {}
    ret["opcode"] = opcode
    ret["datatype"] = datatype
    ret["timeout"] = timeout
    if datasize != None:
        ret["datasize"] = datasize
    return ret


def define_fifo(fifo, ack, size, reset):
    ret = {}
    ret["fifo"] = fifo
    ret["ack"] = ack
    ret["size"] = size
    ret["reset"] = reset
    return ret


def check_datasize(opcode_def):
    dtype = opcode_def["datatype"]
    # Integer and string types must include a datasize
    if dtype in [Datatype.UNSIGNED_INT,
                 Datatype.SIGNED_INT,
                 Datatype.STRING]:
        if "datasize" not in opcode_def:
            raise Exception("Bad opcode: %s: Missing datasize." % opcode_def)
        if opcode_def["datasize"] == 0:
            raise Exception("Bad datasize: %s" % opcode_def["datasize"])


def get_unsigned_pack_str(dsz):
    if dsz == 1:
        return "<B"
    if dsz == 2:
        return "<H"
    if dsz == 4:
        return "<I"
    if dsz == 8:
        return "<Q"
    raise Exception("Unsupported unsigned data size: %d" % dsz)


def get_signed_pack_str(dsz):
    if dsz == 1:
        return "<b"
    if dsz == 2:
        return "<h"
    if dsz == 4:
        return "<i"
    if dsz == 8:
        return "<q"
    raise Exception("Unsupported signed data size: %d" % dsz)


def from_bytearray(opcode_def, ba):
    
    check_datasize(opcode_def)
    dtype = opcode_def["datatype"]
    # Datatype.STRING is allowed to truncate on poll
    if "datasize" in opcode_def and dtype != Datatype.STRING:
        dsz = opcode_def["datasize"]
        if dsz != len(ba):
            raise Exception("Reply length %s.  Expected %s" % (len(ba), dsz))

    if dtype == Datatype.BYTEARRAY:
        # Do nothing here
        return ba
    if dtype == Datatype.UNSIGNED_INT:
        return struct.unpack(
                  get_unsigned_pack_str(opcode_def["datasize"]), ba)[0]
    if dtype == Datatype.SIGNED_INT:
        return struct.unpack(
                  get_signed_pack_str(opcode_def["datasize"]), ba)[0]
    if dtype == Datatype.FLOAT:
        return struct.unpack("<f", ba)[0]
    if dtype == Datatype.DOUBLE:
        return struct.unpack("<d", ba)[0]
    if dtype == Datatype.VOID:
        return None
    if dtype == Datatype.STRING:
        return decodeString(ba)


def _to_bytearray(opcode_def, value):
    
    check_datasize(opcode_def)
    dtype = opcode_def["datatype"]
    if dtype == Datatype.BYTEARRAY:
        return value
    if dtype == Datatype.UNSIGNED_INT:
        return struct.pack(
                 get_unsigned_pack_str(opcode_def["datasize"]), int(value))
    if dtype == Datatype.SIGNED_INT:
        return struct.pack(
                 get_signed_pack_str(opcode_def["datasize"]), int(value))
    if dtype == Datatype.FLOAT:
        return struct.pack("<f", float(value))
    if dtype == Datatype.DOUBLE:
        return struct.pack("<d", float(value))
    if dtype == Datatype.VOID:
        return bytearray()
    if dtype == Datatype.STRING:
        if len(value) > (opcode_def["datasize"] - 1):
            raise Exception("Error: String %s is longer than opcode "
                            "field length %s" % (value, opcode_def))
        ret = bytearray(value)
        ret.append('\0')
        return ret


def to_bytearray(opcode_def, value):
    return bytearray(_to_bytearray(opcode_def, value))
            
        

