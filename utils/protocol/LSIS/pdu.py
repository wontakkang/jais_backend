from .constants import LSIS_XGT_constants
import struct
from .logger import Log


class LSIS_XGT_PDU:
    """
    Set pdu size.(19)

    LSIS-XGT Application Header Format (19)
    Company ID : LSIS-XGT (8)
    Reserved : 0x00 0x00 (2)
    PLC Info : 0x00 0x00 (2)
    CPU Info : 0xA4 (1)
    Source of Frame : 0x33 (1)
    Invoke ID : 0x00 (1)
    Length : 0x00 0x00 (2)
    FEnet Position : 0x00 (1)
    Reserved2(BCC) : 0x00 (1) Application Header의 Byte Sum

    Set adu size.(Max 28)
    Command : 0x00 0x54 (2)
    DataType : 0x00 0x01 (2)
    Reserved : 0x00 0x00 (2)
    block : 0x00 0x01 (2) 1~16개
    variable Length : 0x00 0x06 (2) 1~16개
    variable : 0x00 0x06 (variable Length)
    DataCount : 0x00 0x01 (2)
    """

    companyID = LSIS_XGT_constants.companyID
    companyID_unpack = LSIS_XGT_constants.companyID_unpack
    header = [""]
    decode_Data = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def encode(self):
        self.header = [""]
        self.header[0] += self.companyID[0]
        self.header.append(self.companyID[1])

    def decode(self, data):
        self.header = [""]
        self.header[0] += self.companyID_unpack[0]


class LSIS_XGT_Request(LSIS_XGT_PDU):
    def __init__(self, **kwargs):
        super(LSIS_XGT_Request, self).__init__(**kwargs)
        self.Sorce_Of_Frame = LSIS_XGT_constants.Request_Sorce_Of_Frame
        self.InvokeID = LSIS_XGT_constants.InvokeID

    def encode(self):
        super(LSIS_XGT_Request, self).encode()
        self.header[0] += LSIS_XGT_constants.PLC_Info[0]
        self.header.append(LSIS_XGT_constants.PLC_Info[1])
        self.header[0] += LSIS_XGT_constants.CPU_Info[0]
        self.header.append(LSIS_XGT_constants.CPU_Info[1])
        self.header[0] += self.Sorce_Of_Frame[0]
        self.header.append(self.Sorce_Of_Frame[1])
        self.header[0] += LSIS_XGT_constants.InvokeID[0]
        self.header.append(LSIS_XGT_constants.InvokeID[1])
        self.header[0] += "H"  # Reserved Length Instruction BYTE SUM
        self.header.append(0x00)  # Reserved Length Instruction BYTE SUM
        self.header[0] += LSIS_XGT_constants.FEnet_Position[0]
        self.header.append(LSIS_XGT_constants.FEnet_Position[1])
        self.header[0] += "B"  # BBC Application Header Byte Sum
        self.header.append(0x00)  # BBC Application Header Byte Sum

    def decode(self, data):
        super(LSIS_XGT_Request, self).decode(data)
        self.header[0] += LSIS_XGT_constants.PLC_Info[0]
        self.header[0] += LSIS_XGT_constants.CPU_Info[0]
        self.header[0] += self.Sorce_Of_Frame[0]
        self.header[0] += LSIS_XGT_constants.InvokeID[0]
        self.header[0] += "H"  # Reserved Length Instruction BYTE SUM
        self.header[0] += LSIS_XGT_constants.FEnet_Position[0]
        self.header[0] += "B"  # BBC Application Header Byte Sum
        self.header.append(data[: struct.calcsize(self.header[0])])
        return struct.unpack(*self.header)


class LSIS_XGT_Response(LSIS_XGT_PDU):

    should_respond = True

    def __init__(self, values=None, **kwargs):
        super().__init__(**kwargs)
        super(LSIS_XGT_Response, self).__init__(**kwargs)
        self.Sorce_Of_Frame = LSIS_XGT_constants.response_Sorce_Of_Frame
        self.InvokeID = LSIS_XGT_constants.InvokeID

    def encode(self):

        super(LSIS_XGT_Response, self).encode()
        self.header[0] += LSIS_XGT_constants.PLC_Info[0]
        self.header.append(LSIS_XGT_constants.PLC_Info[1])
        self.header[0] += LSIS_XGT_constants.CPU_Info[0]
        self.header.append(LSIS_XGT_constants.CPU_Info[1])
        self.header[0] += self.Sorce_Of_Frame[0]
        self.header.append(self.Sorce_Of_Frame[1])
        self.header[0] += LSIS_XGT_constants.InvokeID[0]
        self.header.append(self.InvokeID[1])
        self.header[0] += "H"  # Reserved Length Instruction BYTE SUM
        self.header.append(0x00)  # Reserved Length Instruction BYTE SUM
        self.header[0] += LSIS_XGT_constants.FEnet_Position[0]
        self.header.append(LSIS_XGT_constants.FEnet_Position[1])
        self.header[0] += "B"  # BBC Application Header Byte Sum
        self.header.append(0x00)  # BBC Application Header Byte Sum

    def decode(self, data):
        Log.debug(f'LSIS_XGT_Response :: data : ', data)
