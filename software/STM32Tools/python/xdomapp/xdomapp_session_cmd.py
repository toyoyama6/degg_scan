
from . import xdomapp_msg
from . import opcode


XDOMAPP_N_RETRIES = 2


def _retry_cmd(cmd):
    for i in range(XDOMAPP_N_RETRIES):
        try:
            return cmd()
        except IOError as e:
            pass
    # N_RETRIES + 1 = total number of attempts
    return cmd()


class XDOMAppSessionCmd(object):

    def __init__(self, comms, **kwargs):
        # Comms object must implement send(), recv(), close(), and fileno().
        self.msg = xdomapp_msg.XDOMAppMsg(comms, **kwargs)

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        self.msg.close()

    def read_opcode(self, opcode_def, len, token1=0, token2=0):
        res = _retry_cmd(lambda: self.msg.read(opcode_def["opcode"], len,
                                               token1=token1, token2=token2,
                                               timeout=opcode_def["timeout"]))
        return opcode.from_bytearray(opcode_def, res)

    def poll_opcode(self, opcode_def, token1=0, token2=0):
        res = _retry_cmd(lambda: self.msg.poll(opcode_def["opcode"],
                                               token1=token1, token2=token2,
                                               timeout=opcode_def["timeout"]))
        return opcode.from_bytearray(opcode_def, res)

    def write_opcode(self, opcode_def, value=None, token1=0, token2=0):
        data = opcode.to_bytearray(opcode_def, value)
        _retry_cmd(lambda: self.msg.write(opcode_def["opcode"], data,
                                          token1=token1, token2=token2,
                                          timeout=opcode_def["timeout"]))

    def echo(self, data, timeout=1):
        data = bytearray(data)
        return _retry_cmd(lambda: self.msg.echo(data, timeout))

    def read_fifo(self, fifo_def, cnt, token1=0, token2=0):
        ret = self.read_opcode(fifo_def["fifo"], cnt)
        self.write_opcode(fifo_def["ack"], cnt, token1=token1, token2=token2)
        return ret

    def poll_fifo(self, fifo_def, token1=0, token2=0):
        ret = self.poll_opcode(fifo_def["fifo"], token1=token1, token2=token2)
        self.write_opcode(fifo_def["ack"], len(ret),
                          token1=token1, token2=token2)
        return ret

    def reset_fifo(self, fifo_def, token1=0, token2=0):
        self.write_opcode(fifo_def["reset"], None,
                          token1=token1, token2=token2)

    def get_fifo_available_bytes(self, fifo_def, token1=0, token2=0):
        return self.poll_opcode(fifo_def["size"], token1=token1, token2=token2)

    def write_fifo(self, fifo_def, value, token1=0, token2=0):
        self.write_opcode(fifo_def["fifo"], value,
                          token1=token1, token2=token2)
