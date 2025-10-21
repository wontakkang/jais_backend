import struct
from utils.protocol import all_dict as checksum_methods
from .pdu import DE_MCU_Request, DE_MCU_Response

# 새로운 config 시스템 사용
from .config import CommandCode, get_command_format, get_start_byte, get_mcu_config

# 로거 설정
logger = get_mcu_config().get_logger()


class Serial_Setup_Read_RequestBase(DE_MCU_Request):
    """
    DE-MCU 시리얼 설정 읽기 요청 PDU 생성 클래스
    """

    name = "SERIAL_SETUP_READ_REQ"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command = getattr(CommandCode, self.name)
        self.command_format = get_command_format(self.command)
        if "req_data" in kwargs and kwargs["req_data"] is not None:
            self.data = str(kwargs.get("req_data"))
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


class Serial_Setup_Read_Request(Serial_Setup_Read_RequestBase):
    """
    DE-MCU 시리얼 설정 읽기 요청 PDU 생성 클래스
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        return self.byte_frame


class Serial_Setup_Read_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 시리얼 설정 읽기 응답 PDU 생성 클래스
    """

    name = "SERIAL_SETUP_READ_RES"

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


class Serial_Setup_Read_Response(Serial_Setup_Read_ResponseBase):
    """
    DE-MCU 시리얼 설정 읽기 응답 PDU 생성 클래스
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 시리얼 설정 옵션 (config.py에서 가져올 수 있지만 여기서는 하드코딩)
        self.options = {
            "Baudrate": {
                "1200": 1200, "2400": 2400, "4800": 4800, "9600": 9600,
                "19200": 19200, "38400": 38400, "57600": 57600, "115200": 115200,
                "230400": 230400, "460800": 460800,
            },
            "Type": {
                "RS232": 0x01, "RS422": 0x02, "RS485": 0x03, "DDI": 0x04, "SDI": 0x05
            },
            "Data_Bit": {
                "7 Bit": 0x07, "8 Bit": 0x08,
            },
            "Parity": {
                "NONE": 0x00, "ODD": 0x01, "EVEN": 0x02,
            },
            "Stop_Bit": {
                "1 Bit": 0x01, "2 Bit": 0x02,
            },
            "Flow_Control": {
                "NONE": 0x00, "CTS_RTS": 0x01, "XON_XOFF": 0x02,
            },
        }

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
        
        # 포맷 정보에서 데이터 길이 확인
        format_string = self.command_format[3].format_string
        Type, Channel = struct.unpack('BB', data[3 : 5])
        res_data = struct.unpack('<IBBBB', data[5 : 3+ data_length])
        # 응답 데이터 처리
        processed_data["depth"] = 3
        def _find_key_by_value(d, value):
            for k, v in d.items():
                if v == value:
                    return k
            return value  # fallback to raw value if no match
        processed_data.setdefault("STATUS", {}).setdefault("Serial_Setup", {
            "Channel": Channel,
            "Type": _find_key_by_value(self.options['Type'], Type),
            "Baudrate": _find_key_by_value(self.options['Baudrate'], res_data[0]),
            "Data_Bit": _find_key_by_value(self.options['Data_Bit'], res_data[1]),
            "Parity": _find_key_by_value(self.options['Parity'], res_data[2]),
            "Stop_Bit": _find_key_by_value(self.options['Stop_Bit'], res_data[3]),
            "Flow_Control": _find_key_by_value(self.options['Flow_Control'], res_data[4]),
        })
        
        return processed_data
