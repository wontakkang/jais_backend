"""
DE-MCU 프로토콜 설정 관리 모듈

이 모듈은 DE-MCU 프로토콜의 모든 설정을 중앙 집중식으로 관리합니다.
- 시리얼 통신 설정
- 프로토콜 명령어 설정
- 응답 대기 시간 설정
- 체크섬 방법 설정
- 재시도 정책 설정
- 센서별 설정
"""

import os
import utils.logger as logger_module 
from typing import Dict, Any, Optional, Union, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path


class SerialType(Enum):
    """
    시리얼 통신 타입 정의
    """
    RS232 = 0x01
    RS422 = 0x02
    RS485 = 0x03
    DDI = 0x04
    SDI = 0x05

class Baudrate(Enum):
    """
    시리얼 통신 속도 정의
    """
    BAUD_1200 = 1200
    BAUD_2400 = 2400
    BAUD_4800 = 4800
    BAUD_9600 = 9600
    BAUD_19200 = 19200
    BAUD_38400 = 38400
    BAUD_57600 = 57600
    BAUD_115200 = 115200
    BAUD_230400 = 230400
    BAUD_460800 = 460800

class Parity(Enum):
    """
    패리티 설정 정의
    """
    NONE = 0x00
    ODD = 0x01
    EVEN = 0x02


class DataBits(Enum):
    """
    데이터 비트 설정 정의
    """
    SEVEN_BITS = 0x07
    EIGHT_BITS = 0x08


class StopBits(Enum):
    """
    스톱 비트 설정 정의
    """
    ONE_BIT = 0x01
    TWO_BITS = 0x02


class FlowControl(Enum):
    """
    플로우 컨트롤 설정 정의
    """
    NONE = 0x00
    CTS_RTS = 0x01
    XON_XOFF = 0x02


class ChecksumMethod(Enum):
    """
    체크섬 방법 정의
    """
    XOR_SIMPLE = "xor_simple"
    CHECKSUM_SUM = "checksum_sum"
    CRC16 = "crc16"
    CRC32 = "crc32"


class CommandCode(IntEnum):
    """
    DE-MCU 프로토콜 명령 코드 정의
    """
    # 노드 선택
    NODE_SELECT_REQ = 0x20
    NODE_SELECT_RES = 0x21
    
    # 디지털 입력
    DI_READ_REQ = 0x30
    DI_READ_RES = 0x40
    DI_THRESHOLD_WRITE_REQ = 0x31
    DI_THRESHOLD_WRITE_RES = 0x24
    
    # 디지털 출력
    DO_READ_REQ = 0x32
    DO_READ_RES = 0x41
    DO_WRITE_REQ = 0x33
    DO_WRITE_RES = 0x24
    DO_WRITE_ALL_REQ = 0x44
    DO_WRITE_ALL_RES = 0x24
    
    # 디지털 입출력 통합
    DIO_READ_ALL_REQ = 0x42
    DIO_READ_ALL_RES = 0x43
    
    # 아날로그 입력
    ANALOG_READ_REQ = 0x50
    ANALOG_READ_RES = 0x60
    ANALOG_READ_ALL_REQ = 0x51
    ANALOG_READ_ALL_RES = 0x61
    
    # 시리얼 설정
    SERIAL_SETUP_REQ = 0x70
    SERIAL_SETUP_RES = 0x24
    SERIAL_SETUP_READ_REQ = 0x71
    SERIAL_SETUP_READ_RES = 0x82
    
    # 시리얼 쓰기
    SERIAL_WRITE_REQ = 0x80
    SERIAL_WRITE_RES = 0x81
    
    # 센서 데이터
    ACCEL_READ_REQ = 0x90
    ACCEL_READ_RES = 0x91
    GPS_READ_REQ = 0x92
    GPS_READ_RES = 0x93
    
    # 펌웨어
    FIRMWARE_VERSION_READ_REQ = 0xA0
    FIRMWARE_VERSION_READ_RES = 0xA1
    FIRMWARE_VERSION_UPDATE_REQ = 0xA2
    FIRMWARE_VERSION_UPDATE_RES = 0x24


@dataclass
class SerialConfig:
    """
    시리얼 통신 설정 클래스
    
    Attributes:
        baudrate: 통신 속도 (bps)
        bytesize: 데이터 비트 수
        parity: 패리티 설정 ('N', 'E', 'O')
        stopbits: 스톱 비트 수
        timeout: 읽기 타임아웃 (초)
        write_timeout: 쓰기 타임아웃 (초)
        rts: RTS 신호 설정
        dtr: DTR 신호 설정
    """
    baudrate: int = 19200
    bytesize: int = 8
    parity: str = 'N'  # None, Even, Odd
    stopbits: Union[int, float] = 1
    timeout: Optional[float] = 5.0
    write_timeout: Optional[float] = 5.0
    rts: Optional[bool] = None
    dtr: Optional[bool] = None
    
    def __post_init__(self):
        """설정값 유효성 검증"""
        if self.baudrate not in [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800]:
            raise ValueError(f"지원하지 않는 통신 속도: {self.baudrate}")
        if self.bytesize not in [7, 8]:
            raise ValueError(f"지원하지 않는 데이터 비트: {self.bytesize}")
        if self.parity not in ['N', 'E', 'O']:
            raise ValueError(f"지원하지 않는 패리티: {self.parity}")
        if self.stopbits not in [1, 1.5, 2]:
            raise ValueError(f"지원하지 않는 스톱 비트: {self.stopbits}")


@dataclass
class ProtocolConfig:
    """
    프로토콜 설정 클래스
    
    Attributes:
        start_byte: 프레임 시작 바이트
        checksum_method: 체크섬 계산 방법
        max_retry_count: 최대 재시도 횟수
        retry_delay_ms: 재시도 간격 (밀리초)
        response_timeout_ms: 응답 대기 시간 (밀리초)
        firmware_response_timeout_ms: 펌웨어 응답 대기 시간 (밀리초)
        max_packet_size: 최대 패킷 크기 (바이트)
    """
    start_byte: int = 0x7E
    checksum_method: ChecksumMethod = ChecksumMethod.XOR_SIMPLE
    max_retry_count: int = 1
    retry_delay_ms: int = 100
    response_timeout_ms: int = 3000
    firmware_response_timeout_ms: int = 100
    max_packet_size: int = 1024
    
    def __post_init__(self):
        """설정값 유효성 검증"""
        if not 0 <= self.start_byte <= 0xFF:
            raise ValueError(f"시작 바이트는 0x00-0xFF 범위여야 합니다: 0x{self.start_byte:02X}")
        if self.max_retry_count < 0:
            raise ValueError(f"재시도 횟수는 0 이상이어야 합니다: {self.max_retry_count}")
        if self.retry_delay_ms < 0:
            raise ValueError(f"재시도 간격은 0 이상이어야 합니다: {self.retry_delay_ms}")


@dataclass
class LoggingConfig:
    """
    로깅 설정 클래스
    
    Attributes:
        module_name: 로거 모듈 이름
        log_file: 로그 파일 경로
        log_level: 로깅 레벨
        backup_days: 백업 보관 일수
        enable_console: 콘솔 출력 활성화 여부
        enable_file: 파일 출력 활성화 여부
    """
    module_name: str = "MCUnode"
    log_file: str = "log/de_mcu.log"
    log_level: str = "DEBUG"
    backup_days: int = 7
    enable_console: bool = True
    enable_file: bool = True


@dataclass
class SensorConfig:
    """
    센서 설정 클래스
    
    Attributes:
        accelerometer_enabled: 가속도계 활성화 여부
        gps_enabled: GPS 활성화 여부
        analog_channels: 아날로그 채널 수
        digital_input_channels: 디지털 입력 채널 수
        digital_output_channels: 디지털 출력 채널 수
        sensor_read_interval_ms: 센서 읽기 간격 (밀리초)
    """
    accelerometer_enabled: bool = True
    gps_enabled: bool = True
    analog_channels: int = 4
    digital_input_channels: int = 8
    digital_output_channels: int = 8
    sensor_read_interval_ms: int = 1000


@dataclass
class CommandFormat:
    """
    명령어 포맷 정의 클래스
    
    Attributes:
        name: 필드 이름
        size: 필드 크기 (바이트)
        format_string: 구조체 포맷 문자열
    """
    name: str
    size: Union[int, str]
    format_string: str


class MCUProtocolConfig:
    """
    DE-MCU 프로토콜 통합 설정 관리 클래스
    
    프로토콜의 모든 설정을 중앙에서 관리하고 환경별 설정을 제공합니다.
    """
    
    def __init__(self, 
                 config_file: Optional[str] = None,
                 environment: str = "development"):
        """
        설정 초기화
        
        Args:
            config_file: 설정 파일 경로 (선택사항)
            environment: 실행 환경 (development, testing, production)
        """
        self.environment = environment
        self.config_file = config_file
        
        # 기본 설정 로드
        self._load_default_configs()
        
        # 환경별 설정 적용
        self._apply_environment_configs()
        
        # 설정 파일에서 로드 (있는 경우)
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)
        
        # 환경 변수 설정 적용
        self._apply_environment_variables()
        
        # 명령어 포맷 초기화
        self._initialize_command_formats()
        
        # 로거 초기화
        self._logger = None
    
    def get_logger(self):
        """
        MCU 프로토콜용 로거를 반환합니다.
        
        Returns:
            설정된 로거 인스턴스
        """
        if self._logger is None:
            self._logger = logger_module.setup_logger(name=self.logging.module_name, log_file=self.logging.log_file, level=self.logging.log_level, backup_days=self.logging.backup_days)
        return self._logger

    def _load_default_configs(self) -> None:
        """
        기본 설정값들을 로드합니다.
        """
        self.serial = SerialConfig()
        self.protocol = ProtocolConfig()
        self.logging = LoggingConfig()
        self.sensor = SensorConfig()
    
    def _apply_environment_configs(self) -> None:
        """
        환경별 특화 설정을 적용합니다.
        """
        if self.environment == "development":
            self._apply_development_config()
        elif self.environment == "testing":
            self._apply_testing_config()
        elif self.environment == "production":
            self._apply_production_config()
    
    def _apply_development_config(self) -> None:
        """
        개발 환경 설정을 적용합니다.
        """
        self.logging.log_level = "DEBUG"
        self.logging.enable_console = True
        self.protocol.response_timeout_ms = 5000  # 개발 중 긴 타임아웃
    
    def _apply_testing_config(self) -> None:
        """
        테스트 환경 설정을 적용합니다.
        """
        self.logging.log_level = "WARNING"
        self.logging.enable_console = False
        self.protocol.response_timeout_ms = 1000  # 빠른 테스트를 위한 짧은 타임아웃
        self.protocol.max_retry_count = 0  # 테스트 시 재시도 없음
    
    def _apply_production_config(self) -> None:
        """
        운영 환경 설정을 적용합니다.
        """
        self.logging.log_level = "INFO"
        self.logging.enable_console = False
        self.protocol.response_timeout_ms = 3000
        self.protocol.max_retry_count = 3  # 운영 환경에서는 여러 번 재시도
    
    def _load_from_file(self, config_file: str) -> None:
        """
        설정 파일에서 설정을 로드합니다.
        
        Args:
            config_file: 설정 파일 경로
        """
        # TODO: JSON, YAML, INI 파일 지원 추가
        pass
    
    def _apply_environment_variables(self) -> None:
        """
        환경 변수에서 설정값을 읽어와 적용합니다.
        """
        # 시리얼 설정
        if baudrate := os.getenv('MCU_BAUDRATE'):
            self.serial.baudrate = int(baudrate)
        if timeout := os.getenv('MCU_TIMEOUT'):
            self.serial.timeout = float(timeout)
        
        # 프로토콜 설정
        if retry_count := os.getenv('MCU_RETRY_COUNT'):
            self.protocol.max_retry_count = int(retry_count)
        if response_timeout := os.getenv('MCU_RESPONSE_TIMEOUT'):
            self.protocol.response_timeout_ms = int(response_timeout)
        
        # 로깅 설정
        if log_level := os.getenv('MCU_LOG_LEVEL'):
            self.logging.log_level = log_level.upper()
    
    def _initialize_command_formats(self) -> None:
        """
        명령어 포맷을 초기화합니다.
        """
        self.command_formats = {
            # 공통 필드
            "start_byte": CommandFormat("Start byte", 1, "B"),
            "command": CommandFormat("Command", 1, "B"),
            "data_length": CommandFormat("Data Length", 1, "B"),
            "checksum": CommandFormat("Checksum", 1, "B"),
            
            # 노드 선택
            CommandCode.NODE_SELECT_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 8, "8B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.NODE_SELECT_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            
            # 디지털 입력 읽기
            CommandCode.DI_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DI_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DI_THRESHOLD_WRITE_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DI_THRESHOLD_WRITE_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            # 디지털 출력 읽기/쓰기
            CommandCode.DO_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DO_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 3, "BH"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DO_WRITE_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 2, "BB"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DO_WRITE_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DO_WRITE_ALL_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 8, "BBBBBBBB"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DO_WRITE_ALL_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            # 디지털 입출력 통합 읽기
            CommandCode.DIO_READ_ALL_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.DIO_READ_ALL_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 32, "BBBBBBBBBBBBBBBBHHHHHHHH"),
                CommandFormat("Checksum", 1, "B"),
            ],
            
            # 아날로그 입력 읽기
            CommandCode.ANALOG_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.ANALOG_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 4, "Hh"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.ANALOG_READ_ALL_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.ANALOG_READ_ALL_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 16, "HHHHhhhh"),
                CommandFormat("Checksum", 1, "B"),
            ],
            # 가속도계 읽기
            CommandCode.ACCEL_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.ACCEL_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 8, "ff"),
                CommandFormat("Checksum", 1, "B"),
            ],
            
            # GPS 읽기
            CommandCode.GPS_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.GPS_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 22, "BBBdBdBB"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.FIRMWARE_VERSION_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.FIRMWARE_VERSION_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 3, "BBB"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.FIRMWARE_VERSION_UPDATE_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 'variable', 's'),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.FIRMWARE_VERSION_UPDATE_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_SETUP_READ_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_SETUP_READ_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 10, "BBIBBBB"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_SETUP_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 1, "B"),
                CommandFormat("Data", 10, 'BBIBBBB'),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_SETUP_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_WRITE_REQ: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 'variable', "B"),
                CommandFormat("Data", 'variable', 's'),
                CommandFormat("Checksum", 1, "B"),
            ],
            CommandCode.SERIAL_WRITE_RES: [
                CommandFormat("Start byte", 1, "B"),
                CommandFormat("Command", 1, "B"),
                CommandFormat("Data Length", 'variable', "B"),
                CommandFormat("Data", 'variable', 's'),
                CommandFormat("Checksum", 1, "B"),
            ],
        }
    
    def get_command_format(self, command_code: CommandCode) -> List[CommandFormat]:
        """
        명령어 코드에 해당하는 포맷을 반환합니다.
        
        Args:
            command_code: 명령어 코드
            
        Returns:
            명령어 포맷 리스트
        """
        return self.command_formats.get(command_code, [])
    
    def get_serial_config(self, **overrides) -> Dict[str, Any]:
        """
        시리얼 통신 설정을 반환합니다.
        
        Args:
            **overrides: 기본 설정을 오버라이드할 설정값들
        
        Returns:
            시리얼 통신 설정 딕셔너리
        """
        config = {
            'baudrate': self.serial.baudrate,
            'bytesize': self.serial.bytesize,
            'parity': self.serial.parity,
            'stopbits': self.serial.stopbits,
            'timeout': self.serial.timeout,
            'write_timeout': self.serial.write_timeout,
            'rts': self.serial.rts,
            'dtr': self.serial.dtr,
        }
        config.update(overrides)
        return config
    
    def get_protocol_config(self) -> Dict[str, Any]:
        """
        프로토콜 설정을 반환합니다.
        
        Returns:
            프로토콜 설정 딕셔너리
        """
        return {
            'start_byte': self.protocol.start_byte,
            'checksum_method': self.protocol.checksum_method.value,
            'max_retry_count': self.protocol.max_retry_count,
            'retry_delay_ms': self.protocol.retry_delay_ms,
            'response_timeout_ms': self.protocol.response_timeout_ms,
            'firmware_response_timeout_ms': self.protocol.firmware_response_timeout_ms,
            'max_packet_size': self.protocol.max_packet_size,
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        로깅 설정을 반환합니다.
        
        Returns:
            로깅 설정 딕셔너리
        """
        return {
            'module_name': self.logging.module_name,
            'log_file': self.logging.log_file,
            'log_level': self.logging.log_level,
            'backup_days': self.logging.backup_days,
            'enable_console': self.logging.enable_console,
            'enable_file': self.logging.enable_file,
        }
    
    def get_sensor_config(self) -> Dict[str, Any]:
        """
        센서 설정을 반환합니다.
        
        Returns:
            센서 설정 딕셔너리
        """
        return {
            'accelerometer_enabled': self.sensor.accelerometer_enabled,
            'gps_enabled': self.sensor.gps_enabled,
            'analog_channels': self.sensor.analog_channels,
            'digital_input_channels': self.sensor.digital_input_channels,
            'digital_output_channels': self.sensor.digital_output_channels,
            'sensor_read_interval_ms': self.sensor.sensor_read_interval_ms,
        }
    
    def get_baudrate_options(self) -> Dict[str, int]:
        """
        지원되는 통신 속도 옵션을 반환합니다.
        
        Returns:
            통신 속도 옵션 딕셔너리
        """
        return {
            "1200": 1200,
            "2400": 2400,
            "4800": 4800,
            "9600": 9600,
            "19200": 19200,
            "38400": 38400,
            "57600": 57600,
            "115200": 115200,
            "230400": 230400,
            "460800": 460800,
        }
    
    def get_serial_type_options(self) -> Dict[str, int]:
        """
        지원되는 시리얼 타입 옵션을 반환합니다.
        
        Returns:
            시리얼 타입 옵션 딕셔너리
        """
        return {
            "RS232": SerialType.RS232.value,
            "RS422": SerialType.RS422.value,
            "RS485": SerialType.RS485.value,
            "DDI": SerialType.DDI.value,
            "SDI": SerialType.SDI.value,
        }
    
    def validate_config(self) -> bool:
        """
        설정값들의 유효성을 검증합니다.
        
        Returns:
            설정이 유효하면 True, 그렇지 않으면 False
        
        Raises:
            ValueError: 설정값이 잘못된 경우
        """
        # 시리얼 설정 검증은 SerialConfig.__post_init__에서 수행
        # 프로토콜 설정 검증은 ProtocolConfig.__post_init__에서 수행
        
        # 로그 디렉토리 생성
        log_dir = Path(self.logging.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def save_to_file(self, file_path: str) -> None:
        """
        현재 설정을 파일에 저장합니다.
        
        Args:
            file_path: 저장할 파일 경로
        """
        # TODO: JSON, YAML 형태로 설정 저장 기능 구현
        pass
    
    def __repr__(self) -> str:
        """설정 정보를 문자열로 반환합니다."""
        return (
            f"MCUProtocolConfig(environment={self.environment}, "
            f"baudrate={self.serial.baudrate}, "
            f"timeout={self.protocol.response_timeout_ms}ms)"
        )


# 전역 설정 인스턴스 생성
def get_environment() -> str:
    """
    환경 변수에서 실행 환경을 확인하고 반환합니다.
    
    Returns:
        환경 문자열 (development, testing, production)
    """
    return os.getenv('MCU_ENV', 'development').lower()


# 전역 설정 인스턴스
mcu_config = MCUProtocolConfig(environment=get_environment())

# 설정 유효성 검증
mcu_config.validate_config()


def get_mcu_config() -> MCUProtocolConfig:
    """
    전역 MCU 설정 인스턴스를 반환합니다.
    
    Returns:
        MCUProtocolConfig 인스턴스
    """
    return mcu_config


def reload_mcu_config(environment: Optional[str] = None, 
                     config_file: Optional[str] = None) -> MCUProtocolConfig:
    """
    MCU 설정을 다시 로드합니다.
    
    Args:
        environment: 새로운 환경 설정 (None이면 현재 환경 유지)
        config_file: 설정 파일 경로 (선택사항)
    
    Returns:
        새로 로드된 MCUProtocolConfig 인스턴스
    """
    global mcu_config
    if environment is None:
        environment = mcu_config.environment
    mcu_config = MCUProtocolConfig(environment=environment, config_file=config_file)
    mcu_config.validate_config()
    return mcu_config


# 편의를 위한 설정 접근 함수들
def get_serial_config(**overrides) -> Dict[str, Any]:
    """시리얼 통신 설정을 반환합니다."""
    return mcu_config.get_serial_config(**overrides)


def get_protocol_config() -> Dict[str, Any]:
    """프로토콜 설정을 반환합니다."""
    return mcu_config.get_protocol_config()


def get_logging_config() -> Dict[str, Any]:
    """로깅 설정을 반환합니다."""
    return mcu_config.get_logging_config()


def get_sensor_config() -> Dict[str, Any]:
    """센서 설정을 반환합니다."""
    return mcu_config.get_sensor_config()


def get_command_format(command_code: CommandCode) -> List[CommandFormat]:
    """명령어 포맷을 반환합니다."""
    return mcu_config.get_command_format(command_code)


def get_start_byte() -> int:
    """프레임 시작 바이트를 반환합니다."""
    return mcu_config.protocol.start_byte


def get_checksum_method() -> str:
    """체크섬 방법을 반환합니다."""
    return mcu_config.protocol.checksum_method.value


def get_response_timeout() -> int:
    """응답 대기 시간을 반환합니다 (밀리초)."""
    return mcu_config.protocol.response_timeout_ms


def get_max_retry_count() -> int:
    """최대 재시도 횟수를 반환합니다."""
    return mcu_config.protocol.max_retry_count


# 하위 호환성을 위한 상수 클래스
class Defaults:
    """
    기존 constants.py의 Defaults 클래스와 호환성을 위한 클래스
    """
    @property
    def BAUD_RATE(self) -> int:
        return mcu_config.serial.baudrate
    
    @property
    def BYTESIZE(self) -> int:
        return mcu_config.serial.bytesize
    
    @property
    def PARITY(self) -> str:
        return mcu_config.serial.parity
    
    @property
    def STOPBITS(self) -> Union[int, float]:
        return mcu_config.serial.stopbits
    
    @property
    def START_BYTE(self) -> int:
        return mcu_config.protocol.start_byte
    
    @property
    def RESPONSE_WAIT_MS(self) -> int:
        return mcu_config.protocol.response_timeout_ms
    
    @property
    def FIRMWARE_RESPONSE_WAIT_MS(self) -> int:
        return mcu_config.protocol.firmware_response_timeout_ms
    
    @property
    def SERIAL_RETRY_COUNT(self) -> int:
        return mcu_config.protocol.max_retry_count
    
    @property
    def SERIAL_RETRY_DELAY_MS(self) -> int:
        return mcu_config.protocol.retry_delay_ms
    
    # 명령어 코드들
    NODE_SELECT_REQ = CommandCode.NODE_SELECT_REQ
    NODE_SELECT_RES = CommandCode.NODE_SELECT_RES
    DI_READ_REQ = CommandCode.DI_READ_REQ
    DI_READ_RES = CommandCode.DI_READ_RES
    ANALOG_READ_REQ = CommandCode.ANALOG_READ_REQ
    ANALOG_READ_RES = CommandCode.ANALOG_READ_RES
    ACCEL_READ_REQ = CommandCode.ACCEL_READ_REQ
    ACCEL_READ_RES = CommandCode.ACCEL_READ_RES
    GPS_READ_REQ = CommandCode.GPS_READ_REQ
    GPS_READ_RES = CommandCode.GPS_READ_RES
    # ... 기타 명령어 코드들


# 하위 호환성을 위한 인스턴스
DE_MCU_constants = Defaults()


# 사용 예제 및 문서화
if __name__ == "__main__":
    # 설정 사용 예제
    print("=== DE-MCU 프로토콜 설정 ===")
    print(f"환경: {mcu_config.environment}")
    print(f"통신 속도: {mcu_config.serial.baudrate} bps")
    print(f"응답 대기 시간: {mcu_config.protocol.response_timeout_ms} ms")
    print(f"체크섬 방법: {mcu_config.protocol.checksum_method.value}")
    print(f"최대 재시도: {mcu_config.protocol.max_retry_count}회")
    
    # 시리얼 설정 사용 예제
    serial_config = get_serial_config()
    print(f"시리얼 설정: {serial_config}")
    
    # 커스텀 시리얼 설정 예제
    custom_serial = get_serial_config(baudrate=115200, timeout=10.0)
    print(f"커스텀 시리얼 설정: {custom_serial}")
    
    # 명령어 포맷 확인 예제
    node_select_format = get_command_format(CommandCode.NODE_SELECT_REQ)
    print(f"노드 선택 요청 포맷: {[f.name for f in node_select_format]}")