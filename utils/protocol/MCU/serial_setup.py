import json
import struct
from utils.protocol import all_dict as checksum_methods
from .pdu import DE_MCU_Request, DE_MCU_Response

# 새로운 config 시스템 사용
from .config import CommandCode, get_command_format, get_start_byte, get_mcu_config, SerialType, Baudrate, DataBits, Parity, StopBits, FlowControl

# 로거 설정
logger = get_mcu_config().get_logger()


class Serial_Setup_RequestBase(DE_MCU_Request):
    """
    DE-MCU 시리얼 설정 요청 PDU 생성 클래스
    """

    name = "SERIAL_SETUP_REQ"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command = getattr(CommandCode, self.name)
        self.command_format = get_command_format(self.command)
        if "req_data" in kwargs and kwargs["req_data"] is not None:
            self.req_data = str(kwargs.get("req_data"))
        self.checksum_type = kwargs.get("checksum_type", "xor_simple")
        
        # 요청 데이터 처리
        if isinstance(self.req_data, str):
            try:
                self.req_data = json.loads(self.req_data)
            except Exception:
                import ast

                try:
                    self.req_data = ast.literal_eval(self.req_data)
                except Exception:
                    self.req_data = {}
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
            raise ValueError(f"알 수 없는 체크섬 타입: {self.checksum_type}")

        try:
            # Command, DataLength
            self.byte_frame += bytes([self.command]) + bytes([self.data_length])
            self.byte_frame += bytes([getattr(SerialType, self.req_data.get("SerialType", 'RS232')).value])
            self.byte_frame += bytes([self.req_data.get("Channel", 1)])
            self.byte_frame += struct.pack('<I', int(getattr(Baudrate, self.req_data.get("Baudrate", 'BAUD_9600')).value))
            self.byte_frame += bytes([getattr(DataBits, self.req_data.get("DataBits", 'SEVEN_BITS')).value])
            self.byte_frame += bytes([getattr(Parity, self.req_data.get("Parity", 'NONE')).value])
            self.byte_frame += bytes([getattr(StopBits, self.req_data.get("StopBits", 'ONE_BIT')).value])
            self.byte_frame += bytes([getattr(FlowControl, self.req_data.get("FlowControl", 'NONE')).value])
            
        except Exception as e:
            raise ValueError(f"Command/DataLength 직렬화 실패: {e}") from e
            
        # 체크섬 계산 및 추가
        self.checksum = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", self.checksum)


class Serial_Setup_Request(Serial_Setup_RequestBase):
    """
    DE-MCU 시리얼 설정 요청 PDU 생성 클래스
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        return self.byte_frame


class Serial_Setup_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 시리얼 설정 응답 PDU 생성 클래스
    """

    name = "SERIAL_SETUP_RES"

    def __init__(self, **kwargs):
        self.command = getattr(CommandCode, self.name)
        self.command_format = get_command_format(getattr(CommandCode, self.name))
        self.checksum_type = kwargs.get("checksum_type")
        if "req_data" in kwargs and kwargs["req_data"] is not None:
            self.req_data = str(kwargs.get("req_data"))
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
            self.byte_frame += struct.pack("<B", int(self.cmd) & 0xFF)
        except Exception as e:
            raise ValueError(f"Command 직렬화 실패: {e}") from e

        # Compute checksum over current frame
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            func = checksum_methods.get("checksum_sum")
        chk = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", chk)
        return self.byte_frame


class Serial_Setup_Response(Serial_Setup_ResponseBase):
    """
    DE-MCU 시리얼 설정 응답 PDU 생성 클래스
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def deserialize(self, data):
        is_selected = True
        processed_data = {}
        data_length = struct.unpack("<B", data[2:3])[0]
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
