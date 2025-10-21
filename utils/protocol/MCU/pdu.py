import struct
import time
from .config import DE_MCU_constants, get_mcu_config

import utils.protocol.checksum as checksum

logger = get_mcu_config().get_logger()

class DE_MCU_PDU:
    """DE-MCU PDU 생성 및 파싱 유틸리티

    Methods:
    - build_pdu(command:int, data:bytes, checksum_type:str='checksum_sum') -> bytes
    - parse_pdu(pdu:bytes, checksum_type:str='checksum_sum') -> dict
    """

    # 클래스 속성은 유지하되, 인스턴스별 상태를 __init__에서 초기화합니다.
    format = ["<"]
    byte_frame = b""

    def __init__(self, **kwargs):
        # cooperative initialization: 부모 체인에 kwargs를 전달하려 시도하되,
        # object.__init__는 추가 인자를 받지 않으므로 TypeError 발생 시 빈 호출로 안전하게 폴백합니다.
        try:
            super().__init__(**kwargs)
        except TypeError:
            try:
                super().__init__()
            except Exception:
                # 최종 폴백: 아무 작업도 하지 않음
                pass
        # 인스턴스별로 format과 byte_frame을 초기화하여 인스턴스 간 상태 공유를 방지
        self.format = ["<"]
        self.byte_frame = b""
        self.logger = logger

    def serialize(self):
        """PDU를 바이트로 직렬화합니다.
        프로토콜의 구조(시작 바이트, 명령어, 데이터 길이, 데이터, 체크섬)에 따라
        데이터를 특정 바이트 시퀀스로 직렬화(serializing)하는 과정을 의미합니다.
        `build_pdu` 메소드가 이 역할을 수행합니다.
        """
        # START_BYTE는 정수로 정의되어 있으므로 bytes로 변환하여 연결
        self.byte_frame = bytes([DE_MCU_constants.START_BYTE])
        # START_BYTE_FORMAT은 리스트/튜플 구조이므로 올바른 인덱스 접근으로 포맷 문자열을 얻음
        try:
            fmt = DE_MCU_constants.START_BYTE_FORMAT[0][2]
        except Exception:
            fmt = "B"
        self.format.append(fmt)
        # return the current byte frame for callers
        return self.byte_frame


class DE_MCU_Request(DE_MCU_PDU):
    """DE-MCU 요청 PDU 생성 클래스"""

    def __init__(self, **kwargs):
        # 부모 클래스인 DE_MCU_PDU의 __init__ 메소드를 호출합니다.
        super().__init__(**kwargs)
        # 인스턴스별로 format과 byte_frame을 초기화하여 인스턴스 간 상태 공유를 방지
        self.format = ["<"]
        self.byte_frame = b""

    def serialize(self):
        # 부모 클래스인 DE_MCU_PDU의 serialize 메소드를 호출합니다.
        # 이를 통해 DE_MCU_PDU.serialize()에 정의된 로직(START_BYTE 추가 등)을 먼저 실행하고,
        # 그 다음에 DE_MCU_Request 클래스만의 로직을 추가할 수 있습니다. (메소드 오버라이딩 및 확장)
        super().serialize()
        return self.byte_frame


class DE_MCU_Response(DE_MCU_PDU):
    """DE-MCU 요청 PDU 생성 클래스"""

    should_respond = True
    fail_cmd = 0x23

    def __init__(self, **kwargs):
        # 부모 클래스인 DE_MCU_PDU의 __init__ 메소드를 호출합니다.
        super().__init__(**kwargs)

    def serialize(self):
        # 네, 이것은 부모 클래스(DE_MCU_PDU)의 serialize() 메소드를 호출하는 것입니다.
        # 자식 클래스에서 부모 클래스의 메소드를 그대로 사용하지 않고,
        # 새로운 기능을 추가하거나 변경하고 싶을 때(메소드 오버라이딩),
        # 부모 클래스의 원래 기능도 함께 실행해야 할 경우 super()를 사용합니다.
        # 즉, DE_MCU_PDU의 serialize 로직을 실행한 후, DE_MCU_Response만의 serialize 로직을 추가할 수 있습니다.
        super().serialize()
        return self.byte_frame
