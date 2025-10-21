from utils.protocol import all_dict as checksum_methods

from ..accelerometer import *
from ..analog_input_read import *
from ..analog_input_read_all import *
# 새로운 config 시스템 사용
from ..config import get_logging_config
from ..digital_input_output_all_read import *
from ..digital_output_write_all import *
from ..digital_input_read import *
from ..digital_input_threshold_write import *
from ..digital_output_read import *
from ..digital_output_write import *
from ..exceptions import DE_MCU_Exception
from ..firmware_read import *
from ..firmware_update import *
from ..GPS import *
from ..node_select import *
from ..serial_setup_read import *
from ..serial_setup import *
from ..serial_write import *
from ..utils import to_bytes

# 새로운 config 시스템에서 상수 가져오기
INTERNAL_ERROR = "Internal error"


class DE_MCU_Mixin:
    """
    DE-MCU 프로토콜 관련 믹스인 클래스
    - 이 믹스인은 모든 명령 입력 파라미터의 유효성 검사와 논리적 검사를 담당합니다.
    - 실제 요청 객체(Node_Select_Request 등)의 생성은 여전히 각 명령 모듈에 위임하지만,
      입력 검증과 정규화는 여기서 수행됩니다.
    """

    def __init__(self, **kwargs):
        """Initialize cooperatively for multiple inheritance chains."""
        try:
            super().__init__(**kwargs)
        except Exception:
            # Ignore if no further super init exists
            pass

    def NODE_SELECT_REQ(
        self,
        command: str = "NODE_SELECT_REQ",
        serial_number=None,
        checksum_type: str = "xor_simple",
    ):
        """
        Create a Node_Select_Request after validating and normalizing inputs.
        :param command: command name (default 'NODE_SELECT_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Node_Select_Request instance
        """
        try:
            # command validation
            if command != "NODE_SELECT_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")

            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            # serial normalization
            if serial_number is None:
                raise ValueError("serial_number 매개변수가 필요합니다.")
            normalized = to_bytes(serial_number, endian="<")
            if len(normalized) != 8:
                raise ValueError(f"serial_number는 정확히 8바이트여야 합니다.({len(normalized)})")

            # 직접 Node_Select_Request 객체를 생성하여 반환
            return Node_Select_Request(
                serial_number=normalized, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def NODE_SELECT_RES(self, bytes=None, checksum_type: str = "xor_simple"):
        """
        Create a Node_Select_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Node_Select_Response instance
        """
        try:
            response = Node_Select_Response(checksum_type=checksum_type)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def ACCEL_READ_REQ(self, **kwargs):
        command = kwargs.get("command", "ACCEL_READ_REQ")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create an ACCEL_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'ACCEL_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: ACCEL_READ_Request instance
        """
        try:
            # command validation
            if command != "ACCEL_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")

            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            # 직접 ACCEL_READ_Request 객체를 생성하여 반환
            return ACCEL_READ_Request(checksum_type=checksum_type)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def ACCEL_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", b"")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create an ACCEL_READ_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: ACCEL_READ_Response instance
        """
        try:
            response = Accel_Read_Response(checksum_type=checksum_type)
            if res_bytes is None or res_bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def GPS_READ_REQ(self, **kwargs):
        command = kwargs.get("command", "GPS_READ_REQ")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a GPS_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'GPS_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: GPS_READ_Request instance
        """
        try:
            # command validation
            if command != "GPS_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")

            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            # 직접 GPS_READ_Request 객체를 생성하여 반환
            return GPS_READ_Request(checksum_type=checksum_type)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def GPS_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", b"")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a GPS_READ_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: GPS_READ_Response instance
        """
        try:
            response = GPS_Read_Response(**kwargs)
            if res_bytes is None or res_bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DI_READ_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Input_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'DI_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Digital_Input_READ_Request instance
        """
        try:
            # command validation
            if command != "DI_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Input_Read_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DI_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Input_Read_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Input_Read_Response instance
        """
        try:
            response = Digital_Input_Read_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DO_READ_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Output_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'DO_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Digital_Output_READ_Request instance
        """
        try:
            # command validation
            if command != "DO_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Output_Read_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DO_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Output_Read_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Output_Read_Response instance
        """
        try:
            response = Digital_Output_Read_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DO_WRITE_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Output_WRITE_Request after validating and normalizing inputs.
        :param command: command name (default 'DO_WRITE_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Digital_Output_WRITE_Request instance
        """
        try:
            # command validation
            if command != "DO_WRITE_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Output_Write_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DO_WRITE_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Output_Write_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Output_Write_Response instance
        """
        try:
            response = Digital_Output_Write_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def ANALOG_READ_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create an Analog_Input_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'ANALOG_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Analog_Input_READ_Request instance
        """
        try:
            # command validation
            if command != "ANALOG_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Analog_Input_READ_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def ANALOG_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Analog_Input_Read_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Analog_Input_Read_Response instance
        """
        try:
            response = Analog_Input_Read_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def FIRMWARE_VERSION_READ_REQ(self, **kwargs):
        command = kwargs.get("command", "FIRMWARE_VERSION_READ_REQ")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a FIRMWARE_VERSION_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'FIRMWARE_VERSION_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: FIRMWARE_VERSION_READ_Request instance
        """
        try:
            # command validation
            if command != "FIRMWARE_VERSION_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")

            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            # 직접 FIRMWARE_VERSION_READ_Request 객체를 생성하여 반환
            return Firmware_Version_Read_Request(checksum_type=checksum_type)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def FIRMWARE_VERSION_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", b"")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a FIRMWARE_VERSION_READ_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: FIRMWARE_VERSION_READ_Response instance
        """
        try:
            response = Firmware_Version_Read_Response(checksum_type=checksum_type)
            if res_bytes is None or res_bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def FIRMWARE_VERSION_UPDATE_REQ(self, **kwargs):
        command = kwargs.get("command", "FIRMWARE_VERSION_UPDATE_REQ")
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a FIRMWARE_VERSION_UPDATE_Request after validating and normalizing inputs.
        :param command: command name (default 'FIRMWARE_VERSION_UPDATE_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: FIRMWARE_VERSION_UPDATE_Request instance
        """
        try:
            # command validation
            if command != "FIRMWARE_VERSION_UPDATE_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")

            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            # 직접 FIRMWARE_VERSION_UPDATE_Request 객체를 생성하여 반환
            return Firmware_Version_Update_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def FIRMWARE_VERSION_UPDATE_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", b"")
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a FIRMWARE_VERSION_UPDATE_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: FIRMWARE_VERSION_UPDATE_Response instance
        """
        try:
            response = Firmware_Version_Update_Response(checksum_type=checksum_type)
            if res_bytes is None or res_bytes == b"":
                return False
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def SERIAL_SETUP_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Serial_Setup_Request after validating and normalizing inputs.
        :param command: command name (default 'SERIAL_SETUP_REQ')
        :param checksum_type: checksum algorithm name
        :return: Serial_Setup_Request instance
        """
        try:
            # command validation
            if command != "SERIAL_SETUP_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Serial_Setup_Request(req_data=req_data, checksum_type=checksum_type)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def SERIAL_SETUP_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Serial_Setup_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Serial_Setup_Response instance
        """
        try:
            response = Serial_Setup_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def SERIAL_WRITE_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Serial_Write_Request after validating and normalizing inputs.
        :param command: command name (default 'SERIAL_WRITE_REQ')
        :param checksum_type: checksum algorithm name
        :return: Serial_Write_Request instance
        """
        try:
            # command validation
            if command != "SERIAL_WRITE_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Serial_Write_Request(req_data=req_data, checksum_type=checksum_type)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def SERIAL_WRITE_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Serial_Write_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Serial_Write_Response instance
        """
        try:
            response = Serial_Write_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DI_THRESHOLD_WRITE_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Input_Threshold_WRITE_Request after validating and normalizing inputs.
        :param command: command name (default 'DI_THRESHOLD_WRITE_REQ')
        :param checksum_type: checksum algorithm name
        :return: Digital_Input_Threshold_WRITE_Request instance
        """
        try:
            # command validation
            if command != "DI_THRESHOLD_WRITE_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Input_Threshold_Write_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DI_THRESHOLD_WRITE_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Input_Threshold_Write_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Input_Threshold_Write_Response instance
        """
        try:
            response = Digital_Input_Threshold_Write_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)

    def DIO_READ_ALL_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Input_Output_ALL_READ_Request after validating and normalizing inputs.
        :param command: command name (default 'DIO_READ_ALL_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Digital_Input_Output_ALL_READ_Request instance
        """
        try:
            # command validation
            if command != "DIO_READ_ALL_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Input_Output_All_Read_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def DIO_READ_ALL_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Input_Output_All_Read_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Input_Output_All_Read_Response instance
        """
        try:
            response = Digital_Input_Output_All_Read_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def DO_WRITE_ALL_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Digital_Output_WRITE_ALL_Request after validating and normalizing inputs.
        :param command: command name (default 'DO_WRITE_ALL_REQ')
        :param checksum_type: checksum algorithm name
        :return: Digital_Output_WRITE_ALL_Request instance
        """
        try:
            # command validation
            if command != "DO_WRITE_ALL_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            if req_data is None:
                raise ValueError("req_data 매개변수가 필요합니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Digital_Output_Write_All_Request(
                req_data=req_data, checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def DO_WRITE_ALL_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Digital_Output_Write_All_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Digital_Output_Write_All_Response instance
        """
        try:
            response = Digital_Output_Write_All_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def ANALOG_READ_ALL_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create an Analog_Input_READ_ALL_Request after validating and normalizing inputs.
        :param command: command name (default 'ANALOG_READ_ALL_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Analog_Input_READ_ALL_Request instance
        """
        try:
            # command validation
            if command != "ANALOG_READ_ALL_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Analog_Input_Read_All_Request(
                checksum_type=checksum_type
            )
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def ANALOG_READ_ALL_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Analog_Input_Read_All_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Analog_Input_Read_All_Response instance
        """
        try:
            response = Analog_Input_Read_All_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
    
    def SERIAL_SETUP_READ_REQ(self, **kwargs):
        command = kwargs.get("command", None)
        req_data = kwargs.get("req_data", None)
        checksum_type = kwargs.get("checksum_type", "xor_simple")
        """
        Create a Serial_Setup_Read_Request after validating and normalizing inputs.
        :param command: command name (default 'SERIAL_SETUP_READ_REQ')
        :param serial_number: bytes/hex-str/list/int - will be normalized to bytes
        :param checksum_type: checksum algorithm name
        :return: Serial_Setup_Read_Request instance
        """
        try:
            # command validation
            if command != "SERIAL_SETUP_READ_REQ":
                raise NotImplementedError(f"명령 '{command}'는 지원되지 않습니다.")
            # checksum validation
            if checksum_type is None:
                checksum_type = "xor_simple"
            if checksum_type not in checksum_methods:
                raise ValueError(f"알 수 없는 checksum_type: {checksum_type}")

            return Serial_Setup_Read_Request(**kwargs)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)
        
    def SERIAL_SETUP_READ_RES(self, **kwargs):
        res_bytes = kwargs.get("res_bytes", None)
        """
        Create a Serial_Setup_Read_Response instance, optionally parsing provided bytes.
        :param bytes: raw response bytes to parse (optional)
        :return: Serial_Setup_Read_Response instance
        """
        try:
            response = Serial_Setup_Read_Response(**kwargs)
            if bytes is None or bytes == b"":
                return response
            return response.deserialize(data=res_bytes)
        except Exception as e:
            raise DE_MCU_Exception(INTERNAL_ERROR, exc=e)