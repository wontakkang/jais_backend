import binascii, ast, socket
import struct
from .constants import LSIS_XGT_constants
from .pdu import LSIS_XGT_Request, LSIS_XGT_Response


class Single_Write_RequestBase(LSIS_XGT_Request):
    instruction = [""]
    command = LSIS_XGT_constants.ContinuousWriteRequest
    response = LSIS_XGT_constants.ContinuousWriteRecv

    def __init__(self, data_type, block_cnt, blockArray, **kwargs):
        super().__init__(**kwargs)
        #: A list of register values
        self.registers = []
        self.dataType = LSIS_XGT_constants.SingleDataType[data_type]
        self.block_CNT = ["H", int(block_cnt, 16)]
        self.blockArray = []
        for block in blockArray:
            self.blockArray.append([
                ["H", len(block['address'])],
                [str(len(block['address'])) + "s", block['address'].encode()],
                ["H", block['count']],
                [block['format'], block['values']],
            ])
    # 데이터이므로 데이터 크기 가져오기, 데이터 타입이 Bool 인 경우 읽은 데이터는 HEX 로 한 Byte 로 표시합니다. 즉 BIT 값이0 이면 h’00 으로, 1 이면 h’01 로 표시됩니다.
    def encode(self):
        self.instruction = ["<"]
        super(Single_Write_RequestBase, self).encode()
        self.instruction[0] += self.command[0]
        self.instruction.append(self.command[1])
        self.instruction[0] += self.dataType[0]
        self.instruction.append(self.dataType[1])
        self.instruction[0] += "H"  # Reserved
        self.instruction.append(0x00)  # Reserved
        self.instruction[0] += self.block_CNT[0]
        self.instruction.append(self.block_CNT[1])

        for block in self.blockArray:
            self.instruction[0] += block[0][0]
            self.instruction.append(block[0][1])
            self.instruction[0] += block[1][0]
            self.instruction.append(block[1][1])
        for block in self.blockArray:
            self.instruction[0] += block[2][0]
            self.instruction.append(block[2][1])
            self.instruction[0] += block[3][0]
            self.instruction.append(block[3][1])
        self.header[6] = struct.calcsize(
            self.instruction[0]
        )  # Length Instruction BYTE SUM

    def decode(self, data):
        addr_length = struct.unpack("H", data[8:10])[0]
        self.instruction = ["<"]
        self.instruction[0] += Single_Write_RequestBase.command[0]
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


class Single_Write_Request(Single_Write_RequestBase):
    name = "SingleWriteRequest"

    def __init__(self, data_type, block_cnt, blockArray, **kwargs):
        super().__init__(data_type, block_cnt, blockArray, **kwargs)

    def execute(self, store):
        memory = (self.variable).decode()[:3]
        address = int((self.variable).decode()[3:])
        values = store.setValues(
            memory, address, values=self.values, raddr=self.address
        )
        print('SingleWriteRequest execute')
        response = Single_Write_Response(values=values)
        return response


class Single_Write_ResponseBase(LSIS_XGT_Response):
    command = LSIS_XGT_constants.ContinuousWriteRecv

    def __init__(self, values, **kwargs):
        super().__init__(values, **kwargs)
        #: A list of register values
        self.registers = values or []
        self.instruction = [""]
        self.command = self.command

    def encode(self):
        print("Single_Write_Response encode")
        self.instruction = [""]
        super(Single_Write_ResponseBase, self).encode()
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
        self.instruction = [""]
        self.instruction[0] += Single_Write_ResponseBase.command[0]
        self.instruction[0] += "H"
        self.instruction[0] += "H" # Reserved
        self.instruction[0] += "H" # Error
        if len(data):
            self.instruction[0] += "H"
        else:
            self.instruction[0] += "B"
        self.instruction.append(data)
        return struct.unpack(*self.instruction)

    def errorCode(self, index):
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


class Single_Write_Response(Single_Write_ResponseBase):
    name = "Single_Write_Response"

    def __init__(self, values=None, address="", count=0, **kwargs):
        super().__init__(values, **kwargs)
        print("Single_Write_Response __init__")
        self.dataType = LSIS_XGT_constants.SingleDataType
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
    "Single_Write_Request",
    "Single_Write_Response",
]
