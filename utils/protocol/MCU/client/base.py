import time
from dataclasses import dataclass

from utils.protocol import checksum as checksum_mod

from ..exceptions import ConnectionException
from .mixin import DE_MCU_Mixin

# 새로운 config 시스템 사용
from ..config import get_mcu_config, get_serial_config, get_protocol_config, get_start_byte, get_logging_config, CommandCode

# 로거 설정
logger = get_mcu_config().get_logger()


class DE_MCU_SerialClient(DE_MCU_Mixin):
    """DE-MCU 직렬 통신 클라이언트. DE_MCU_Mixin을 직접 상속하도록 단순화.

    - 이전에는 DE_MCU_BaseClient + DE_MCU_SerialClient로 분리되어 있었으나,
      재구성되어 SerialClient가 믹스인과 직접 결합됩니다.
    - 내부적으로 self.params 인스턴스를 보유하며 기존 인터페이스를 유지합니다.
    - NODE_SELECT_REQ 명령으로 노드 선택에 대한 요청을 하고 NODE_SELECT_RES 응답이 오면 connect된 상태입니다.
    - 새로운 config 시스템을 사용하여 환경별 설정 지원
    """

    @dataclass
    class _params:  # pylint: disable=too-many-instance-attributes
        port: str = ""
        baudrate: int = 19200  # config에서 가져올 기본값
        bytesize: int = 8
        parity: str = "N"
        stopbits: int = 1

    def __init__(
        self,
        port: str,
        baudrate: int = None,
        bytesize: int = None,
        parity: str = None,
        stopbits: int = None,
        serial_module=None,
        **kwargs,
    ) -> None:
        """
        DE-MCU 시리얼 클라이언트 초기화
        
        Args:
            port: 시리얼 포트 경로
            baudrate: 통신 속도 (None이면 config에서 가져옴)
            bytesize: 데이터 비트 수 (None이면 config에서 가져옴)
            parity: 패리티 설정 (None이면 config에서 가져옴)
            stopbits: 스톱 비트 수 (None이면 config에서 가져옴)
            serial_module: 사용할 시리얼 모듈 (테스트용)
            **kwargs: 추가 설정
        """
        # 믹스인이 kwargs를 받는 경우를 지원하기 위한 cooperative super 호출
        try:
            super().__init__(**kwargs)
        except TypeError:
            try:
                super().__init__()
            except Exception:
                pass

        # 새로운 config 시스템에서 설정 가져오기
        self._mcu_config = get_mcu_config()
        serial_config = get_serial_config()
        protocol_config = get_protocol_config()

        self.params = self._params()
        self.params.port = port
        # None이면 config에서, 아니면 사용자 지정값 사용
        self.params.baudrate = baudrate if baudrate is not None else serial_config['baudrate']
        self.params.bytesize = bytesize if bytesize is not None else serial_config['bytesize']
        self.params.parity = parity if parity is not None else serial_config['parity']
        self.params.stopbits = stopbits if stopbits is not None else serial_config['stopbits']
        self.params.kwargs = kwargs

        # 프로토콜 설정 적용
        self._protocol_config = protocol_config
        self._serial_config = serial_config

        self.socket = None
        self.last_response = None
        self.last_response_parsed = None
        self.last_error = None
        self.serial = None
        self._serial_module = serial_module
        # RS485 미지원 경고 반복 방지 플래그
        self._rs485_warned = False
        # 시작 바이트 및 체크섬 함수 기본값(트랜잭트별로 덮어쓸 수 있음)
        self.start_byte = protocol_config['start_byte']
        self.checksum_func = None
        
        logger.info(
            f"DE-MCU Client initialized with port: {self.params.port}, "
            f"baudrate: {self.params.baudrate}, environment: {self._mcu_config.environment}"
        )

    @property
    def connected(self):
        return bool(
            getattr(self, "serial", None) and getattr(self.serial, "is_open", False)
        )

    def _get_serial_module(self):
        if self._serial_module:
            return self._serial_module
        try:
            import serial as _serial

            return _serial
        except Exception as e:
            raise ConnectionException(
                f"pyserial import failed: {e}",
                exc=e,
                endpoint=self.params.port,
                retryable=False,
            )

    async def __aexit__(self, klass, value, traceback):
        self.close()

    def close(self):
        try:
            if getattr(self, "serial", None) and getattr(self.serial, "is_open", False):
                self.serial.close()
        except Exception as e:
            logger.error(f"Error while closing serial port {self.params.port}: {e}")
        finally:
            self.serial = None

    def transact(self, retry_forever: bool = False, **kwargs):
        """
        MCU 장치와 트랜잭션을 수행합니다.
        
        새로운 config 시스템을 사용하여 환경별 타임아웃과 재시도 정책을 적용합니다.
        """
        serial_number = kwargs.get("serial_number", None)
        checksum_type = kwargs.get("checksum_type", self._protocol_config['checksum_method'])
        command = kwargs.get("command", "NODE_SELECT_REQ")
        attempt = 0
        req_bytes = None
        res_bytes = None
        result = dict
        try:
            serial_mod = self._get_serial_module()

            bytesize_map = {
                8: serial_mod.EIGHTBITS,
                7: serial_mod.SEVENBITS,
                6: serial_mod.SIXBITS,
                5: serial_mod.FIVEBITS,
            }
            parity_map = {
                "N": serial_mod.PARITY_NONE,
                "E": serial_mod.PARITY_EVEN,
                "O": serial_mod.PARITY_ODD,
            }
            stopbits_map = {
                1: serial_mod.STOPBITS_ONE,
                1.5: serial_mod.STOPBITS_ONE_POINT_FIVE,
                2: serial_mod.STOPBITS_TWO,
            }

            bs = bytesize_map.get(self.params.bytesize, serial_mod.EIGHTBITS)
            pr = parity_map.get(str(self.params.parity).upper(), serial_mod.PARITY_NONE)
            sb = stopbits_map.get(self.params.stopbits, serial_mod.STOPBITS_ONE)

            # 새로운 config 시스템에서 타임아웃 설정 가져오기
            open_timeout = float(self._serial_config.get('timeout', 5.0))

            # 이 트랜잭션에서 사용할 시작 바이트와 체크섬 함수를 설정
            self.start_byte = self._protocol_config['start_byte']
            self.checksum_func = self._make_checksum_callable(checksum_type)

            # Open a temporary serial port for handshake only
            self.serial = serial_mod.Serial(
                port=self.params.port,
                baudrate=self.params.baudrate,
                bytesize=bs,
                parity=pr,
                stopbits=sb,
                timeout=open_timeout,
                write_timeout=self._serial_config.get('write_timeout', 5.0),
            )
            req_pdu = self.NODE_SELECT_REQ(
                serial_number=serial_number, checksum_type=checksum_type
            )
            if command == "FIRMWARE_VERSION_UPDATE_REQ":
                firm_bytes_list = kwargs.get("req_data").decode("utf-8").split(":")
                for idx, firm_bytes in enumerate(firm_bytes_list, start=1):
                    logger.info(
                        "Processing firmware index %d/%d", idx, len(firm_bytes_list)
                    )
                    isSelected = False
                    req_pdu = None
                    if len(firm_bytes) != 0:
                        try:
                            req_pdu = self.NODE_SELECT_REQ(
                                serial_number=serial_number, checksum_type=checksum_type
                            )
                            req_bytes = req_pdu.serialize()
                            self.serial.reset_input_buffer()
                            self.serial.reset_output_buffer()
                            self.serial.write(req_bytes)
                            self.serial.flush()  # 버퍼 비우기 (즉시 전송)
                            res_bytes = self.receive_bytes(
                                self.serial,
                                timeout=(
                                    self._protocol_config['firmware_response_timeout_ms'] / 1000.0
                                ),
                            )
                            isSelected = self.NODE_SELECT_RES(
                                bytes=res_bytes, checksum_type=checksum_type
                            )
                            if isSelected:
                                req = getattr(self, command)(**kwargs)
                                req_bytes = req.serialize(
                                    data=firm_bytes
                                )  # Validate command existence
                                logger.debug(
                                    f"{command} : TX -> {bytes(req_bytes).hex(' ').upper() if req_bytes else 'No Request'}"
                                )
                                self.serial.reset_input_buffer()
                                self.serial.reset_output_buffer()
                                self.serial.write(req_bytes)
                                self.serial.flush()  # 버퍼 비우기 (즉시 전송)
                                res_bytes = self.receive_bytes(
                                    self.serial,
                                    timeout=(
                                        self._protocol_config['firmware_response_timeout_ms'] / 1000.0
                                    ),
                                )
                                logger.debug(
                                    f"{command.replace('REQ', 'RES')} : RX <- {bytes(res_bytes).hex(' ').upper() if res_bytes else 'No Response'}"
                                )
                                if getattr(self, command.replace("REQ", "RES"))(
                                    **kwargs
                                ):
                                    logger.error(
                                        f"Firmware update failed at index {idx}: {len(firm_bytes_list)}"
                                    )
                                    break
                        except Exception as e:
                            raise ConnectionException(
                                f"NODE_SELECT_REQ 빌드 실패: {e}",
                                exc=e,
                                endpoint=self.params.port,
                                retryable=False,
                            )
            else:
                try:
                    req_bytes = req_pdu.serialize()
                    # serialize should return bytes; log hex representation
                    if not isinstance(req_bytes, (bytes, bytearray)):
                        raise TypeError("요청 PDU 직렬화 결과가 바이트가 아닙니다")
                    try:
                        logger.debug(
                            "NODE_SELECT_REQ : TX -> %s",
                            bytes(req_bytes).hex(" ").upper(),
                        )
                    except Exception:
                        logger.error("NODE_SELECT_REQ : TX -> (unable to format)")
                except Exception as e:
                    raise ConnectionException(
                        f"NODE_SELECT_REQ 빌드 실패: {e}",
                        exc=e,
                        endpoint=self.params.port,
                        retryable=False,
                    )

                try:
                    self.serial.reset_input_buffer()
                    self.serial.reset_output_buffer()
                    self.serial.write(req_bytes)
                    self.serial.flush()  # 버퍼 비우기 (즉시 전송)
                    res_bytes = self.receive_bytes(
                        self.serial,
                        timeout=(self._protocol_config['response_timeout_ms'] / 1000.0) + 1.0,
                    )
                    logger.debug(
                        f"NODE_SELECT_RES : RX <- {bytes(res_bytes).hex(' ').upper() if res_bytes else 'No Response'}"
                    )
                    isSelected = self.NODE_SELECT_RES(
                        bytes=res_bytes, checksum_type=checksum_type
                    )
                    self.last_response = res_bytes
                    result = {
                        "request": (
                            req_bytes.hex(" ").upper() if req_bytes else "No Resquest"
                        ),
                        "response": (
                            res_bytes.hex(" ").upper()
                            if self.last_response
                            else "No Response"
                        ),
                    }
                    if not res_bytes:
                        logger.error(
                            f"No response received on {self.params.port} for NODE_SELECT_REQ"
                        )
                        return result
                    if not isSelected:
                        logger.error(
                            f"Invalid NODE_SELECT_RES response on {self.params.port}: {res_bytes.hex(' ').upper() if res_bytes else 'empty'}"
                        )
                        return result
                    result["selected_node"] = isSelected
                    if command != "NODE_SELECT_REQ":
                        req_bytes = getattr(self, command)(
                            **kwargs
                        ).serialize()  # Validate command existence
                        logger.debug(
                            f"{command} : TX -> {bytes(req_bytes).hex(' ').upper() if req_bytes else 'No Request'}"
                        )
                        self.serial.reset_input_buffer()
                        self.serial.reset_output_buffer()
                        self.serial.write(req_bytes)
                        result["request"] = (
                            req_bytes.hex(" ").upper() if req_bytes else "No Resquest"
                        )
                        self.serial.flush()  # 버퍼 비우기 (즉시 전송)
                        res_bytes = self.receive_bytes(
                            self.serial,
                            timeout=(self._protocol_config['response_timeout_ms'] / 1000.0) + 1.0,
                        )
                        logger.debug(
                            f"{command.replace('REQ', 'RES')} : RX <- {bytes(res_bytes).hex(' ').upper() if res_bytes else 'No Response'}"
                        )
                        kwargs["res_bytes"] = res_bytes
                        processed_data = getattr(self, command.replace("REQ", "RES"))(
                            **kwargs
                        )
                        self.serial.reset_input_buffer()
                        self.serial.reset_output_buffer()
                        self.serial.flush()  # 버퍼 비우기 (즉시 전송)
                        result["processed_data"] = processed_data
                        result["response"] = (
                            res_bytes.hex(" ").upper()
                            if self.last_response
                            else "No Response"
                        )
                    else:
                        result["processed_data"] = "존재하지 않는 명령입니다."
                    # (제거됨) 이전에 사용하던 예외 캐치-로깅의 주석 처리된 중복 코드 삭제
                    return result
                finally:
                    try:
                        self.serial.close()
                    except Exception:
                        pass

        except ConnectionException as e:
            attempt += 1
            self.last_error = str(e)
            logger.warning(f"Handshake failed on {self.params.port}: {e}")
            if not retry_forever or not getattr(e, "retryable", True):
                raise
            # 새로운 config 시스템에서 재시도 설정 가져오기
            base_delay_ms = self._protocol_config['retry_delay_ms']
            max_delay_ms = self._protocol_config.get('max_retry_delay_ms', 5000)
            delay = (
                min(base_delay_ms * (2 ** max(0, attempt - 1)), max_delay_ms) / 1000.0
            )
            logger.info(f"Retrying handshake in {delay:.3f}s (attempt {attempt}) ...")
            time.sleep(delay)
        except Exception as e:
            # non-retryable unexpected errors
            self.last_error = str(e)
            logger.exception(f"Unexpected error during connect: {e}")
            raise ConnectionException(
                str(e), exc=e, endpoint=self.params.port, retryable=False
            )

    def build_request_pdu(self, **kwargs):
        # Mixin의 execute()가 제거되어 각 명령별 편의 메서드를 직접 호출합니다.
        cmd = kwargs.get("command")
        if not cmd:
            raise ValueError("command 매개변수가 필요합니다")

        # 명령명과 동일한 메서드가 믹스인에 정의되어 있으면 호출
        # 예: 'NODE_SELECT_REQ' -> self.NODE_SELECT_REQ(...)
        method = getattr(self, cmd, None)
        if callable(method):
            # 전달 인자는 mixin에서 정규화되어 처리됩니다.
            return method(**kwargs)

        # 지원되지 않는 명령인 경우 명확한 예외
        raise NotImplementedError(f"명령 '{cmd}'는 지원되지 않습니다.")

    async def __aenter__(self):
        if not self.transact():
            raise ConnectionException(f"Failed to connect[{self.__str__()}]")
        return self

    def receive_bytes(self, ser, timeout):
        """시작바이트와 데이터 길이 및 체크섬(선택)을 사용하여 프레임을 빠르게 읽음."""
        if self.start_byte is None:
            self.start_byte = get_start_byte()
        if self.checksum_func is None:
            # 인스턴스에 정의된 checksum_func를 사용하려고 시도
            self.checksum_func = getattr(self, "checksum_func", None)

        end_time = time.time() + timeout

        # read loop: 시작 바이트를 찾고 전체 프레임을 읽은 후 체크섬 검사
        while time.time() < end_time:
            buf = bytearray()

            # 1) 시작 바이트 검색
            while time.time() < end_time:
                try:
                    b = ser.read(1)
                except Exception as re:
                    raise re
                if not b:
                    time.sleep(0.01)
                    continue
                if b[0] == self.start_byte:
                    buf.extend(b)
                    break

            if not buf:
                # 타임아웃으로 시작 바이트를 찾지 못함
                logger.debug("receive_bytes RX <- (no start byte found)")
                return bytes()

            # 2) 헤더(Command + DataLen)
            needed_header = 2
            while len(buf) < 1 + needed_header and time.time() < end_time:
                try:
                    chunk = ser.read((1 + needed_header) - len(buf))
                except Exception as re:
                    raise re
                if chunk:
                    buf.extend(chunk)
                else:
                    time.sleep(0.01)

            if len(buf) < 3:
                try:
                    # 헤더 불완전: 부분 데이터 반환
                    resp = bytes(buf)
                except Exception:
                    logger.debug("receive_bytes (unable to format)")
                return resp

            data_len = buf[2]
            # 방어 로직: 과도한 길이로부터 보호 (config에서 최대 패킷 크기 사용)
            max_len = self._protocol_config.get('max_packet_size', 1024)
            if data_len > max_len:
                logger.warning(
                    "receive_bytes RX <- data_len %d exceeds max_packet_size %d, skipping frame",
                    data_len,
                    max_len,
                )
                # 버퍼 버리고 다음 프레임 검색
                continue

            total_expected = 1 + 1 + 1 + data_len + 1

            # 3) 남은 바이트 읽기
            while len(buf) < total_expected and time.time() < end_time:
                try:
                    to_read = total_expected - len(buf)
                    chunk = ser.read(to_read)
                except Exception as re:
                    raise re
                if chunk:
                    buf.extend(chunk)
                else:
                    time.sleep(0.01)

            if len(buf) < total_expected:
                try:
                    # 불완전 프레임: 반환
                    resp = bytes(buf)
                except Exception:
                    logger.debug("receive_bytes RX <- (unable to format)")
                return resp

            try:
                resp = bytes(buf)

                # 4) 체크섬 검증(선택)
                if self.checksum_func:
                    try:
                        chk_res = self.checksum_func(resp)
                        if isinstance(chk_res, bool):
                            valid = chk_res
                        elif isinstance(chk_res, int):
                            # 단일 바이트 체크섬(또는 정수로 반환하는 경우) 비교
                            valid = (chk_res & 0xFF) == resp[-1]
                        elif isinstance(chk_res, (bytes, bytearray)):
                            # 멀티바이트 체크섬 비교: 프레임의 끝부분과 비교
                            clen = len(chk_res)
                            valid = resp[-clen:] == bytes(chk_res)
                        else:
                            valid = False
                    except Exception as e:
                        logger.warning("Checksum function raised exception: %s", e)
                        valid = False

                    if not valid:
                        logger.warning(
                            "Received frame failed checksum, skipping. Frame: %s",
                            resp.hex(" ").upper(),
                        )
                        # 체크섬 불일치 프레임은 무시하고 다음 프레임으로
                        continue
            except Exception:
                logger.debug("receive_bytes RX <- (unable to format)")
            return resp
        # 전체 타임아웃
        logger.debug("receive_bytes RX <- (timeout)")
        return bytes()

    def _make_checksum_callable(self, checksum_type: str):
        """체크섬 타입 문자열로부터 receive_bytes에 전달할 callable을 만듭니다.

        반환되는 callable은 frame: bytes -> bool|int|bytes 를 반환합니다.
        - bool: 유효/무효
        - int: 기대되는 1바이트 체크섬 값
        - bytes: 기대되는 체크섬 바이트 시퀀스
        """
        if not checksum_type:
            return None
        ct = str(checksum_type).lower()

        if ct in ("xor_simple", "xor"):
            return lambda frame: checksum_mod.xor_simple(frame[:-1])
        if ct in ("sum", "checksum_sum"):
            return lambda frame: checksum_mod.checksum_sum(frame[:-1])
        if ct in ("lrc", "checksum_lrc"):
            return lambda frame: checksum_mod.checksum_lrc(frame[:-1])
        if ct in ("crc16modbus", "crc16_modbus"):
            return lambda frame: checksum_mod.crc16_modbus(
                frame[:-2], return_bytes=True, byteorder="little", length=2
            )
        if ct in ("crc16ccitt", "crc16_ccitt"):
            return lambda frame: checksum_mod.crc16_ccitt(
                frame[:-2], return_bytes=True, byteorder="little", length=2
            )
        if ct in ("crc32",):
            return lambda frame: checksum_mod.crc32(
                frame[:-4], return_bytes=True, byteorder="little", length=4
            )
        if ct in ("adler32",):
            return lambda frame: checksum_mod.adler32(
                frame[:-4], return_bytes=True, byteorder="little", length=4
            )
        # fallback: no checksum callable
        return None
