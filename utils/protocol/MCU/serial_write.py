import json
import struct

# 새로운 config 시스템 사용
from .config import CommandCode, get_command_format, get_start_byte, get_mcu_config

# 로거 설정
logger = get_mcu_config().get_logger()

from utils.protocol import all_dict as checksum_methods
from utils.protocol.MCU.utils import to_bytes

from .pdu import DE_MCU_Request, DE_MCU_Response


class Serial_Write_RequestBase(DE_MCU_Request):
    """
    DE-MCU 시리얼 쓰기 요청 PDU 생성 클래스
    """

    name = "SERIAL_WRITE_REQ"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 새로운 config 시스템에서 명령어 코드와 포맷 가져오기
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

        # 안전한 데이터 추출
        data_field = self.req_data.get("Data", "")
        bytes_list = []
        # 대체 처리: bytes/bytearray면 그대로 사용; str이면 각 문자를 ord()로 변환
        if isinstance(data_field, str):
            # '0I!' 같은 ASCII 문자열을 [0x30, 0x49, 0x21]로 변환
            bytes_list = [ord(ch) for ch in data_field]
        else:
            try:
                bytes_list = [int(x) for x in data_field]
            except Exception:
                bytes_list = []
        logger.debug(f"Parsed bytes for SERIAL_WRITE_REQ: {bytes_list}")

        # variable 포맷인 경우 동적으로 처리
        if len(self.command_format) > 3 and self.command_format[3].size == "variable":
            # format에 바이트 단위 포맷을 추가
            self.format.append("B" * len(bytes_list))
            # 기존 코드의 의도대로 data_length에 추가된 필드(예: 채널/타임아웃 등)를 반영
            self.data_length = len(bytes_list) + 3

        # Resolve checksum function
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            raise ValueError(f"알 수 없는 체크섬 타입: {self.checksum_type}")

        try:
            # Command, DataLength
            self.byte_frame += bytes([self.command]) + bytes([self.data_length])
            # Channel (optional)
            self.byte_frame += bytes([self.req_data.get("Channel", 0x01)])
            # Timeout (2 bytes, unsigned short)
            timeout_val = int(self.req_data.get("Timeout", 100)) & 0xFFFF
            self.byte_frame += struct.pack("<H", timeout_val)
            # Data payload
            for byte in bytes_list:
                self.byte_frame += bytes([int(byte)])

        except Exception as exc:  # pragma: no cover - 에러 메시지 보존
            raise ValueError(f"Command/DataLength 직렬화 실패: {exc}") from exc

        # 체크섬 계산 및 추가
        self.checksum = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", self.checksum)


class Serial_Write_Request(Serial_Write_RequestBase):
    """
    DE-MCU 시리얼 쓰기 요청 PDU 생성 클래스
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        return self.byte_frame


class Serial_Write_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 시리얼 쓰기 응답 PDU 생성 클래스
    """

    name = "SERIAL_WRITE_RES"

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
        except Exception as exc:
            raise ValueError(f"Command 직렬화 실패: {exc}") from exc

        # Compute checksum over current frame
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            func = checksum_methods.get("checksum_sum")
        chk = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", chk)
        return self.byte_frame


class Serial_Write_Response(Serial_Write_ResponseBase):
    """
    DE-MCU 시리얼 쓰기 응답 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def deserialize(self, data):
        processed_data = {}
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

        return data[2:2+data_length]  # Return relevant data portion
