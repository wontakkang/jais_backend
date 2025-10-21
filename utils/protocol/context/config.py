"""
Context 패키지 설정 및 구성 관리 모듈

이 모듈은 context 패키지 전반에서 사용되는 설정값들을 중앙화하여 관리합니다.
네임 패턴을 표준화하고 가독성과 재사용성을 높였습니다.
"""

import os
from typing import Dict, Any, Optional, Tuple
from enum import Enum

# =============================================================================
# 네임 패턴 및 상수 정의
# =============================================================================

class ProtocolType(Enum):
    """지원되는 프로토콜 타입"""
    MODBUS = "MODBUS"
    LS_XGT_TCP = "LS_XGT_TCP" 
    MCU_NODE = "MCU_node"

class MemoryType(Enum):
    """메모리 타입 정의"""
    COILS = "coils"
    DISCRETE_INPUTS = "discrete_inputs"
    HOLDING_REGISTERS = "holding_registers"
    INPUT_REGISTERS = "input_registers"

class FileExtension(Enum):
    """파일 확장자 정의"""
    JSON = ".json"
    LOG = ".log"
    BACKUP = ".bak"

# =============================================================================
# 기본 설정 상수
# =============================================================================

# 레지스터 기본값
DEFAULT_REGISTER_COUNT: int = 10000
DEFAULT_REGISTER_VALUE: int = 0
DEFAULT_START_ADDRESS: int = 0
DEFAULT_ZERO_MODE: bool = True

# 슬레이브 ID 범위
SLAVE_ID_MIN: int = 0x00
SLAVE_ID_MAX: int = 0xF7

# =============================================================================
# 프로토콜별 메모리 타입 정의
# =============================================================================

# LS XGT TCP 메모리 영역
LS_XGT_TCP_MEMORY_TYPES: Tuple[str, ...] = ("%MB", "%RB", "%WB")

# 지원되는 프로토콜 리스트
SUPPORTED_PROTOCOLS: Tuple[str, ...] = tuple(p.value for p in ProtocolType)

# =============================================================================
# 파일 및 디렉토리 설정
# =============================================================================

# 디렉토리명
CONTEXT_STORE_DIR_NAME: str = "context_store"
LOG_DIR_NAME: str = "log"
BACKUP_DIR_NAME: str = "meta_backups"

# 파일명
STATE_FILE_NAME: str = "state.json"
META_FILE_NAME: str = "meta.json"

# Context 관련 로그 파일명
CONTEXT_LOG_FILES: Dict[str, str] = {
    "manager": "context_store_manager.log",
    "context": "context_logger.log"
}

# =============================================================================
# 백업 정책 설정
# =============================================================================

# 환경변수 키
class BackupEnvVars(Enum):
    """백업 관련 환경변수"""
    MAX_BYTES = "CONTEXT_BACKUP_MAX_BYTES"
    KEEP_DAYS = "CONTEXT_BACKUP_KEEP_DAYS"
    MAX_FILES = "CONTEXT_BACKUP_MAX_FILES"

# 기본 백업 정책
DEFAULT_BACKUP_POLICY: Dict[str, Any] = {
    "keep_days": 30,
    "max_files": 100,
    "max_total_bytes": "100M"
}

# =============================================================================
# JSON 직렬화 설정
# =============================================================================

JSON_SERIALIZATION_SETTINGS: Dict[str, Any] = {
    "ensure_ascii": False,
    "indent": 2,
    "sort_keys": True,
    "separators": (',', ': ')
}

# =============================================================================
# 로깅 설정
# =============================================================================

LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# 프로토콜별 기본 설정
# =============================================================================

PROTOCOL_DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    ProtocolType.MODBUS.value: {
        "count": DEFAULT_REGISTER_COUNT,
        "use_json": False,
        "zero_mode": DEFAULT_ZERO_MODE,
        "supported_functions": [1, 2, 3, 4, 5, 6, 15, 16]
    },
    ProtocolType.LS_XGT_TCP.value: {
        "count": DEFAULT_REGISTER_COUNT,
        "use_json": False,
        "memory_types": LS_XGT_TCP_MEMORY_TYPES,
        "timeout": 5.0
    },
    ProtocolType.MCU_NODE.value: {
        "count": DEFAULT_REGISTER_COUNT,
        "use_json": True,
        "default_value": DEFAULT_REGISTER_VALUE,
        "auto_save": True
    }
}

# =============================================================================
# 설정 관리 클래스
# =============================================================================

class ContextConfig:
    """Context 패키지의 설정을 관리하는 클래스"""
    
    @staticmethod
    def get_backup_policy() -> Dict[str, Any]:
        """환경변수를 고려한 백업 정책을 반환합니다."""
        policy = DEFAULT_BACKUP_POLICY.copy()
        
        # 환경변수에서 설정 읽기
        env_mappings = {
            "keep_days": BackupEnvVars.KEEP_DAYS.value,
            "max_files": BackupEnvVars.MAX_FILES.value,
            "max_bytes": BackupEnvVars.MAX_BYTES.value
        }
        
        for key, env_var in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                if key in ["keep_days", "max_files"]:
                    try:
                        policy[key] = int(env_value)
                    except ValueError:
                        continue
                else:
                    policy[key] = env_value
        
        return policy
    
    @staticmethod
    def get_log_file_path(log_type: str, base_dir: Optional[str] = None) -> str:
        """로그 파일의 전체 경로를 반환합니다."""
        if base_dir is None:
            base_dir = os.getcwd()
        
        log_file = CONTEXT_LOG_FILES.get(log_type, f"{log_type}{FileExtension.LOG.value}")
        return os.path.join(base_dir, LOG_DIR_NAME, log_file)
    
    @staticmethod
    def get_context_store_path(app_path: str) -> str:
        """앱 경로에서 context_store 디렉토리 경로를 반환합니다."""
        return os.path.join(app_path, CONTEXT_STORE_DIR_NAME)
    
    @staticmethod
    def get_protocol_config(protocol: str) -> Dict[str, Any]:
        """프로토콜별 기본 설정을 반환합니다."""
        return PROTOCOL_DEFAULT_CONFIGS.get(protocol, {}).copy()
    
    @staticmethod
    def is_valid_slave_id(slave_id: int) -> bool:
        """슬레이브 ID가 유효한 범위인지 확인합니다."""
        return SLAVE_ID_MIN <= slave_id <= SLAVE_ID_MAX
    
    @staticmethod
    def parse_bytes_string(byte_str: str) -> int:
        """바이트 문자열(예: '100M', '1G')을 바이트 수로 변환합니다."""
        if not byte_str:
            return 0
        
        try:
            byte_str = str(byte_str).strip().upper()
            
            # 단위별 변환 테이블
            unit_multipliers = {
                'G': 1024 ** 3, 'GB': 1024 ** 3,
                'M': 1024 ** 2, 'MB': 1024 ** 2,
                'K': 1024, 'KB': 1024
            }
            
            for unit, multiplier in unit_multipliers.items():
                if byte_str.endswith(unit):
                    value_str = byte_str[:-len(unit)]
                    return int(float(value_str) * multiplier)
            
            # 단위가 없으면 바이트로 간주
            return int(float(byte_str))
            
        except (ValueError, TypeError):
            return 0

# =============================================================================
# 편의 함수들 (하위 호환성 유지)
# =============================================================================

def get_backup_policy() -> Dict[str, Any]:
    """환경변수를 고려한 백업 정책을 반환합니다."""
    return ContextConfig.get_backup_policy()

def get_log_file_path(log_type: str, base_dir: Optional[str] = None) -> str:
    """로그 파일의 전체 경로를 반환합니다."""
    return ContextConfig.get_log_file_path(log_type, base_dir)

def get_context_store_path(app_path: str) -> str:
    """앱 경로에서 context_store 디렉토리 경로를 반환합니다."""
    return ContextConfig.get_context_store_path(app_path)

def get_protocol_config(protocol: str) -> Dict[str, Any]:
    """프로토콜별 기본 설정을 반환합니다."""
    return ContextConfig.get_protocol_config(protocol)

def is_valid_slave_id(slave_id: int) -> bool:
    """슬레이브 ID가 유효한 범위인지 확인합니다."""
    return ContextConfig.is_valid_slave_id(slave_id)

def parse_bytes_string(byte_str: str) -> int:
    """바이트 문자열(예: '100M', '1G')을 바이트 수로 변환합니다."""
    return ContextConfig.parse_bytes_string(byte_str)

# =============================================================================
# 슬레이브 설정 (하위 호환성 유지)
# =============================================================================

SLAVE_ID_RANGE: Dict[str, int] = {
    "min": SLAVE_ID_MIN,
    "max": SLAVE_ID_MAX
}

# JSON 설정 (하위 호환성 유지)
JSON_SETTINGS = JSON_SERIALIZATION_SETTINGS

# 백업 환경변수 (하위 호환성 유지)
BACKUP_ENV_VARS: Dict[str, str] = {
    "max_bytes": BackupEnvVars.MAX_BYTES.value,
    "keep_days": BackupEnvVars.KEEP_DAYS.value,
    "max_files": BackupEnvVars.MAX_FILES.value
}