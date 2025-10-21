import struct
import time
from .config import CommandCode, get_command_format, get_start_byte, get_mcu_config
from utils.protocol import all_dict as checksum_methods
from .pdu import DE_MCU_Request, DE_MCU_Response
from .utils import to_bytes, bytes_to_hex
logger = get_mcu_config().get_logger()
import re

class Digital_Output_Write_All_RequestBase(DE_MCU_Request):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스
    """
    name = "DO_WRITE_ALL_REQ"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command = getattr(CommandCode, self.name)
        # CommandFormat 속성: name, size, format_string
        self.command_format = get_command_format(self.command)
        if "req_data" in kwargs and kwargs["req_data"] is not None:
            self.data = str(kwargs.get("req_data")).zfill(self.command_format[3].size)
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
            
    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        # Resolve checksum function
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            logger.error(f"Unknown checksum type: {self.checksum_type}")
            raise ValueError(
                f"{self.name} : 알 수 없는 체크섬 타입: {self.checksum_type}"
            )
        try:
            if self.data_length == 0:
                self.byte_frame += bytes([self.command]) + bytes([self.data_length])
            else:
                self.byte_frame += bytes([self.command]) + bytes([self.data_length])
                for char in self.data:
                    self.byte_frame += bytes([int(char)])
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise ValueError(
                f"{self.name} : Command/DataLength 직렬화 실패: {e}"
            ) from e
        self.checksum = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", self.checksum)
    
    
class Digital_Output_Write_All_Request(Digital_Output_Write_All_RequestBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        return self.byte_frame
        
class Digital_Output_Write_All_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 노드 선택 응답 PDU 생성 클래스
    """
    name = "DO_WRITE_ALL_RES"
    
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
            logger.error(f"Command serialization failed: {e}")
            raise ValueError(f"{self.name} : Command 직렬화 실패: {e}") from e

        # Compute checksum over current frame
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            logger.warning(f"Unknown checksum type: {self.checksum_type}, using default")
            func = checksum_methods.get("checksum_sum")
        chk = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", chk)
        return self.byte_frame


class Digital_Output_Write_All_Response(Digital_Output_Write_All_ResponseBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    # convenience: human-readable hex for frames
    def deserialize(self, data):
        is_selected =True
        processed_data = {}
        logger.debug(f"{self.name} : Deserializing data: {bytes_to_hex(data)}")
        data_length = struct.unpack("<B", data[2:3])[0]
        start_byte = get_start_byte()
        
        if [start_byte] != list(data[:1]):
            logger.error(
                f"{self.name} : Invalid start byte: expected {start_byte}, got {data[:1]}"
            )
            return None
        if self.command != struct.unpack("<B", data[1:2])[0]:
            logger.error(
                f"{self.name} : Invalid command byte: expected {self.command}, got {struct.unpack('<B', data[1:2])[0]}"
            )
            return None
        
        
        bit_arr = []
        for ch in str(self.req_data):
            bit_arr.append(1 if ch == '1' else 0)
        processed_data["depth"] = 2
        if is_selected:
            processed_data.setdefault("SETUP", {}).setdefault("Digital_Output", {
                "DO1": {
                    "Id": 1, "Value": bit_arr[0],
                },
                "DO2": {
                    "Id": 2, "Value": bit_arr[1], 
                },
                "DO3": {
                    "Id": 3, "Value": bit_arr[2],
                },
                "DO4": {
                    "Id": 4, "Value": bit_arr[3],
                },
                "DO5": {
                    "Id": 5, "Value": bit_arr[4],
                },
                "DO6": {
                    "Id": 6, "Value": bit_arr[5],
                },
                "DO7": {
                    "Id": 7, "Value": bit_arr[6],
                },
                "DO8": {
                    "Id": 8, "Value": bit_arr[7],
                },
            })
        return processed_data