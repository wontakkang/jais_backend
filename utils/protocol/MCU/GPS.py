import struct
import time
from .config import DE_MCU_constants, get_mcu_config
logger = get_mcu_config().get_logger()
from utils.protocol import all_dict as checksum_methods

from .pdu import DE_MCU_Request, DE_MCU_Response
from .utils import bytes_to_hex, to_bytes

# NOTE: _to_bytes implementation removed — use to_bytes from utils.py for normalization


class GPS_Read_RequestBase(DE_MCU_Request):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스
    """

    name = "GPS_READ_REQ"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # serial_number는 bytes 또는 hex 문자열 등 허용. 내부적으로 bytes로 변환
        self.cmd = getattr(DE_MCU_constants, self.name)
        self.cmd_fmt = getattr(DE_MCU_constants, f"{self.name}_FORMAT", None)
        self.serial_number = kwargs.get("serial_number")
        self.data = to_bytes(self.serial_number)
        # 데이터 길이 검증은 serializer에서 수행되므로 여기서는 수행하지 않음
        self.data_length = len(self.data)
        self.checksum_type = kwargs.get("checksum_type", "xor_simple")
        # 요구 길이: ACCEL_READ_REQ_FORMAT의 Data 항목 길이(8바이트)
        self.format.append(self.cmd_fmt[1][2])  # Command format
        self.format.append(self.cmd_fmt[2][2])  # Data Length format

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        # Resolve checksum function
        func = checksum_methods.get(self.checksum_type)
        if not callable(func):
            raise ValueError(f"알 수 없는 체크섬 타입: {self.checksum_type}")

        try:
            self.byte_frame += bytes([self.cmd]) + bytes([self.data_length])
        except Exception as e:
            raise ValueError(f"Command/DataLength 직렬화 실패: {e}") from e
        self.checksum = int(func(self.byte_frame)) & 0xFF
        self.byte_frame += struct.pack("<B", self.checksum)


class GPS_READ_Request(GPS_Read_RequestBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self):
        # Build PDU: START already added by DE_MCU_PDU.serialize()
        super().serialize()
        return self.byte_frame


class GPS_Read_ResponseBase(DE_MCU_Response):
    """
    DE-MCU 노드 선택 응답 PDU 생성 클래스
    """

    name = "GPS_READ_RES"

    def __init__(self, data=b"", **kwargs):
        if data is None:
            data = b""
        self.cmd = getattr(DE_MCU_constants, self.name)
        self.cmd_fmt = getattr(DE_MCU_constants, f"{self.name}_FORMAT", None)
        self.checksum_type = kwargs.get("checksum_type")

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


class GPS_Read_Response(GPS_Read_ResponseBase):
    """
    DE-MCU 노드 선택 요청 PDU 생성 클래스 (serial_number를 HEX 문자열로 입력받음)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # convenience: human-readable hex for frames
    def deserialize(self, data):
        processed_data = {}
        data_fields = [
            "hour",
            "minute",
            "second",
            "latitude",
            "south_flag",
            "altitude",
            "west_flag",
            "position_fix",
        ]
        data_length = struct.unpack("<B", data[2:3])[0]
        if [DE_MCU_constants.START_BYTE] != list(data[:1]):
            logger.error(
                f"Invalid start byte: expected {DE_MCU_constants.START_BYTE}, got {data[:1]}"
            )
            return None
        if self.cmd != struct.unpack("<B", data[1:2])[0]:
            logger.error(
                f"Invalid command byte: expected : {self.cmd == struct.unpack('<B', data[1:2])[0]} : {self.cmd}, got {struct.unpack('<B', data[1:2])[0]}"
            )
            return None
        if data_length != self.cmd_fmt[3][1]:  # 3 floats, 4 bytes each
            # DE_MCU_constants.GPS_READ_RES_FORMAT[3][2] is "<3f"
            logger.error(
                f"Invalid data length: expected {self.cmd_fmt[3][1]}, got {data_length}"
            )
            return None
        data = struct.unpack(self.cmd_fmt[3][2], data[3 : 3 + data_length])
        if len(data) != len(data_fields):
            logger.error(
                f"Invalid data length after unpacking: expected 3 floats, got {len(data)}"
            )
            return None
        for i in enumerate(data):
            if data_fields[i[0]] in ["latitude", "altitude"]:
                processed_data[data_fields[i[0]]] = float(i[1])
            else:
                processed_data[data_fields[i[0]]] = i[1]
        return processed_data
