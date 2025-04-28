import binascii, ast, socket
import struct
from .constants import LSIS_XGT_constants
from .pdu import LSIS_XGT_Request, LSIS_XGT_Response


class Continuous_Write_RequestBase(LSIS_XGT_Request):
    instruction = [""]
    command = LSIS_XGT_constants.ContinuousWriteRequest
    response = LSIS_XGT_constants.ContinuousWriteRecv

    def __init__(self, address, count, values, **kwargs):
        print("Continuous_Write_RequestBase: ", values)
        super().__init__(address, count, values, **kwargs)
        #: A list of register values
        self.registers = values or []
        self.dataType = LSIS_XGT_constants.ContinuousDataType
        self.block_CNT = ["H", 0x01]
        self.var_Length = ["H", len(address)]
        self.var = [str(len(address)) + "s", address.encode()]
        self.data_Cnt = ["H", count]
        self.values = ["H" * len(values), values]

    def encode(self):
        self.instruction = [""]
        super(Continuous_Write_RequestBase, self).encode()
        self.instruction[0] += self.command[0]
        self.instruction.append(self.command[1])
        self.instruction[0] += self.dataType[0]
        self.instruction.append(self.dataType[1])
        self.instruction[0] += "H"  # Reserved
        self.instruction.append(0x00)  # Reserved
        self.instruction[0] += self.block_CNT[0]
        self.instruction.append(self.block_CNT[1])
        self.instruction[0] += self.var_Length[0]
        self.instruction.append(self.var_Length[1])
        self.instruction[0] += self.var[0]
        self.instruction.append(self.var[1])
        self.instruction[0] += self.data_Cnt[0]
        self.instruction.append(self.data_Cnt[1])
        self.instruction[0] += self.values[0]
        for v in self.values[1]:
            self.instruction.append(v)
        self.header[6] = struct.calcsize(
            self.instruction[0]
        )  # Length Instruction BYTE SUM

    def decode(self, data):
        addr_length = struct.unpack("H", data[8:10])[0]
        self.instruction = [""]
        self.instruction[0] += Continuous_Write_RequestBase.command[0]
        self.instruction[0] += LSIS_XGT_constants.ContinuousDataType[0]
        self.instruction[0] += "H"  # Reserved
        self.instruction[0] += "H"
        self.instruction[0] += "H"
        self.instruction[0] += str(addr_length) + "s"
        self.instruction[0] += "H"
        values = data[struct.calcsize(self.instruction[0]) :]
        self.instruction[0] += "B" * len(values)
        self.instruction.append(data)
        return struct.unpack(*self.instruction)


class Continuous_Write_Request(Continuous_Write_RequestBase):
    name = "ContinuousWriteRequest"

    def __init__(self, address, count, values, **kwargs):
        super().__init__(address, count, values, **kwargs)
        print("Continuous_Write_Request: ", values)

    def execute(self, store):
        memory = (self.variable).decode()[:3]
        address = int((self.variable).decode()[3:])
        values = store.setValues(
            memory, address, values=self.values, raddr=self.address
        )
        response = Continuous_Write_Response(values=values)
        return response


class Continuous_Write_ResponseBase(LSIS_XGT_Response):
    command = LSIS_XGT_constants.ContinuousWriteRecv

    def __init__(self, values, **kwargs):
        super().__init__(values, **kwargs)
        #: A list of register values
        self.registers = values or []
        self.instruction = [""]
        self.command = self.command

    def encode(self):
        self.instruction = [""]
        super(Continuous_Write_ResponseBase, self).encode()
        self.instruction[0] += self.command[0]
        self.instruction.append(self.command[1])
        self.instruction[0] += self.dataType[0]
        self.instruction.append(self.dataType[1])
        self.instruction[0] += "H"  # Reserved
        self.instruction.append(0x00)  # Reserved
        self.instruction[0] += "H"  # Reserved
        self.instruction.append(0x00)  # Reserved
        self.instruction[0] += self.block_CNT[0]
        self.instruction.append(self.block_CNT[1])
        self.header[6] = struct.calcsize(
            self.instruction[0]
        )  # Length Instruction BYTE SUM

    def decode(self, data):
        """Decode a register response packet.

        :param data: The request to decode
        """
        byte_count = int(data[0])
        self.registers = []
        for i in range(2, byte_count + 1, 2):
            registers = struct.unpack(">BB", data[i : i + 2])
            self.registers.append(registers[0])
            self.registers.append(registers[1])

    def getRegister(self, index):
        print("Continuous_Write_ResponseBase getRegister")
        """Get the requested register.

        :param index: The indexed register to retrieve
        :returns: The request register
        """
        return self.registers[index]

    def __str__(self):
        """Return a string representation of the instance.

        :returns: A string representation of the instance
        """
        return f"{self.__class__.__name__} ({len(self.registers)})"


class Continuous_Write_Response(Continuous_Write_ResponseBase):
    name = "Continuous_Write_Response"

    def __init__(self, values=None, address="", count=0, **kwargs):
        super().__init__(values, **kwargs)
        self.dataType = LSIS_XGT_constants.ContinuousDataType
        self.block_CNT = ["H", 0x01]
        self.var_Length = ["H", len(address)]
        self.var = [str(len(address)) + "s", address.encode()]
        self.data_Cnt = ["H", count]

    def __name__(self):
        return f"{self.__class__.__name__} : {self.command[1]}"


# ---------------------------------------------------------------------------#
#  Exported symbols
# ---------------------------------------------------------------------------#
__all__ = [
    "Continuous_Write_Request",
    "Continuous_Write_Response",
]
