import struct
import time
from .config import CommandCode, get_command_format, get_start_byte, get_mcu_config
from utils.protocol.MCU.utils import to_bytes
from utils.protocol import all_dict as checksum_methods

from .pdu import DE_MCU_Request, DE_MCU_Response
logger = get_mcu_config().get_logger()


class Firmware_Version_Update_RequestBase(DE_MCU_Request):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스
    """

    name = "FIRMWARE_VERSION_UPDATE_REQ"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command = getattr(CommandCode, self.name)
        # CommandFormat 속성: name, size, format_string
        self.command_format = get_command_format(self.command)
        self.checksum_type = kwargs.get("checksum_type", "xor_simple")

        try:
            for cf in self.command_format:
                # cf.format_string 예: 'B', '8B' 등
                self.format.append(cf.format_string)
        except Exception:
            # 포맷 메타데이터가 예상과 다른 경우 안전하게 로그
            logger.exception("Failed to build format list from command_format")
            
        if struct.calcsize(''.join(self.format)) < 4: # 최소 크기: START(1) + CMD(1) + LEN(1) + CHK(1)
            self.data_length = 0
        else:
            self.data_length = struct.calcsize(''.join(self.format)) - 4  # START, CMD, LEN, CHK 제외

    def serialize(self, data=None):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        if "\r\n" in data:
            req_bytes = to_bytes(data.replace("\r\n", ""))
        else:
            req_bytes = to_bytes(data)

        if self.command_format[3].size == "variable":  # Data 항목이 'variable'로 지정된 경우
            self.format.append("B" * len(req_bytes))
            self.data_length = len(req_bytes)
        else:
            self.format.append(self.command_format[3].size)  # Data

        # Resolve checksum function
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            raise ValueError(f"알 수 없는 체크섬 타입: {self.checksum_type}")
        try:
            self.byte_frame += bytes([self.command]) + bytes([self.data_length]) + req_bytes
        except Exception as e:
            raise ValueError(f"Command/DataLength 직렬화 실패: {e}") from e
        self.checksum = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", self.checksum)


class Firmware_Version_Update_Request(Firmware_Version_Update_RequestBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self, data=None):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize(data=data)
        return self.byte_frame


class Firmware_Version_Update_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 노드 선택 응답 PDU 생성 클래스
    """

    name = "FIRMWARE_VERSION_UPDATE_RES"

    def __init__(self, **kwargs):
        self.command = getattr(CommandCode, self.name)
        self.command_format = get_command_format(getattr(CommandCode, self.name))
        self.checksum_type = kwargs.get("checksum_type")
        if "req_data" in kwargs and kwargs["req_data"] is not None:
            self.req_data = int(kwargs.get("req_data"))
        if "res_bytes" in kwargs and kwargs["res_bytes"] is not None:
            self.res_bytes = kwargs.get("res_bytes")
        try:
            for cf in self.command_format:
                # cf.format_string 예: 'B', '8B' 등
                self.format.append(cf.format_string)
        except Exception:
            # 포맷 메타데이터가 예상과 다른 경우 안전하게 로그
            logger.exception("Failed to build format list from command_format")
            
        if struct.calcsize(''.join(self.format)) < 4: 
            self.data_length = 0
        else:
            self.data_length = struct.calcsize(''.join(self.format)) - 4  # START, CMD, LEN, CHK 제외

    def serialize(self):
        # START already added by DE_MCU_PDU.serialize()
        super().serialize()
        # Pack command
        try:
            self.byte_frame += struct.pack("<B", int(self.command) & 0xFF)
        except Exception as e:
            raise ValueError(f"Command 직렬화 실패: {e}") from e

        # Compute checksum over current frame
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            func = checksum_methods.get("checksum_sum")
        chk = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", chk)
        return self.byte_frame


class Firmware_Version_Update_Response(Firmware_Version_Update_ResponseBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # convenience: human-readable hex for frames
    def deserialize(self, data):
        is_selected = True
        start_byte = get_start_byte()
        if [start_byte] != list(data[:1]):
            logger.error(
                f"{self.name} : Invalid start byte: expected {start_byte}, got {data[:1]}"
            )
            return False
        if self.command != struct.unpack("<B", data[1:2])[0]:
            logger.error(
                f"{self.name} : Invalid command byte: expected {self.command}, got {struct.unpack('<B', data[1:2])[0]}"
            )
            return False
        return is_selected
