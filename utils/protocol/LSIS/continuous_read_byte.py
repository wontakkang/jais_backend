import struct
from .constants import LSIS_XGT_constants
from .pdu import LSIS_XGT_Request, LSIS_XGT_Response


class Continuous_Read_RequestBase(LSIS_XGT_Request):
    instruction = [""]
    command = LSIS_XGT_constants.ContinuousReadRequest
    response = LSIS_XGT_constants.ContinuousReadRecv

    def __init__(self, address, count, **kwargs):
        super().__init__(**kwargs)
        self.dataType = LSIS_XGT_constants.ContinuousDataType
        self.block_CNT = ["H", 0x01]
        self.var_Length = ["H", len(address)]
        self.var = [str(len(address)) + "s", address.encode()]
        self.data_Cnt = ["H", count]
        self.instruction = [""]

    def encode(self):
        self.instruction = [""]
        super(Continuous_Read_RequestBase, self).encode()
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
        self.header[6] = struct.calcsize(
            self.instruction[0]
        )  # Length Instruction BYTE SUM

    def decode(self, data):
        addr_length = struct.unpack("H", data[8:10])[0]
        self.instruction = [""]
        self.instruction[0] += Continuous_Read_RequestBase.command[0]
        self.instruction[0] += LSIS_XGT_constants.ContinuousDataType[0]
        self.instruction[0] += "H"  # Reserved
        self.instruction[0] += "H"
        self.instruction[0] += "H"
        self.instruction[0] += str(addr_length) + "s"
        self.instruction[0] += "H"
        self.instruction.append(data[: struct.calcsize(self.instruction[0])])
        return struct.unpack(*self.instruction)


class Continuous_Read_Request(Continuous_Read_RequestBase):
    name = "ContinuousReadRequest"

    def __init__(self, address, count, **kwargs):
        super().__init__(address, count, **kwargs)

    def execute(self, store):
        memory = (self.variable).decode()[:3]
        address = int((self.variable).decode()[3:])
        values = store.getValues(memory, address, count=self.dataCount)
        response = Continuous_Read_Response(values=values)
        return response


class Continuous_Read_ResponseBase(LSIS_XGT_Response):
    command = LSIS_XGT_constants.ContinuousReadRecv

    def __init__(self, values, **kwargs):
        super().__init__(values, **kwargs)
        #: A list of register values
        self.registers = values or []
        self.instruction = [""]

    def encode(self):
        self.instruction = [""]
        super(Continuous_Read_ResponseBase, self).encode()
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
        self.instruction[0] += self.data_Cnt[0]
        self.instruction.append(self.data_Cnt[1])
        self.instruction[0] += self.values[0]
        self.instruction += self.values[1:]
        self.header[6] = struct.calcsize(
            self.instruction[0]
        )  # Length Instruction BYTE SUM

    def decode(self, data):
        self.instruction = [""]
        self.instruction[0] += Continuous_Read_ResponseBase.command[0]
        self.instruction[0] += LSIS_XGT_constants.ContinuousDataType[0]
        self.instruction[0] += "H"  # Reserved
        self.instruction[0] += "H"
        self.instruction[0] += "H"
        self.instruction[0] += "H"
        self.instruction[0] += "B" * (len(data) - struct.calcsize(self.instruction[0]))
        self.instruction.append(data)
        return struct.unpack(*self.instruction)

    def getRegister(self, index):
        print("Continuous_Read_ResponseBase getRegister")
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


class Continuous_Read_Response(Continuous_Read_ResponseBase):
    name = "Continuous_Read_Response"

    def __init__(self, values=None, address="", count=0, **kwargs):
        super().__init__(values, **kwargs)
        self.dataType = LSIS_XGT_constants.ContinuousDataType
        self.block_CNT = ["H", 0x01]
        self.var_Length = ["H", len(address)]
        self.var = [str(len(address)) + "s", address.encode()]
        self.data_Cnt = ["H", count]
        self.values = ["b" * len(values), *values]

    def __name__(self):
        return f"{self.__class__.__name__} : {self.command[1]}"


# ---------------------------------------------------------------------------#
#  Exported symbols
# ---------------------------------------------------------------------------#
__all__ = [
    "Continuous_Read_Request",
    "Continuous_Read_Response",
]
