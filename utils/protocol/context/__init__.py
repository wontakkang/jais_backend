"""
Context 패키지 초기화 모듈

MCU 노드 통신을 위한 컨텍스트 관리 시스템을 제공합니다.
네임 패턴을 표준화하고 모듈별 역할을 명확히 분리하여 가독성과 재사용성을 높였습니다.
"""

from typing import Dict, Any

# =============================================================================
# 전역 레지스트리 (정의 위치를 manager import 이전으로 이동하여 순환 import 문제 방지)
# 애플리케이션 간 공유되는 전역 레지스트리
CONTEXT_REGISTRY: Dict[str, Any] = {}

# =============================================================================
# 설정 및 구성
# =============================================================================
from .config import (
    # 열거형 및 상수
    ProtocolType,
    MemoryType,
    FileExtension,
    
    # 기본 설정값
    DEFAULT_REGISTER_COUNT,
    DEFAULT_REGISTER_VALUE,
    DEFAULT_START_ADDRESS,
    DEFAULT_ZERO_MODE,
    
    # 프로토콜 관련
    LS_XGT_TCP_MEMORY_TYPES,
    SUPPORTED_PROTOCOLS,
    PROTOCOL_DEFAULT_CONFIGS,
    
    # 파일 및 디렉토리
    CONTEXT_STORE_DIR_NAME,
    STATE_FILE_NAME,
    META_FILE_NAME,
    BACKUP_DIR_NAME,
    
    # 백업 정책
    DEFAULT_BACKUP_POLICY,
    BackupEnvVars,
    
    # JSON 설정
    JSON_SERIALIZATION_SETTINGS,
    
    # 슬레이브 설정
    SLAVE_ID_MIN,
    SLAVE_ID_MAX,
    
    # 설정 관리 클래스
    ContextConfig,
    
    # 편의 함수들
    get_backup_policy,
    get_log_file_path,
    get_context_store_path,
    get_protocol_config,
    is_valid_slave_id,
    parse_bytes_string,
    
    # 하위 호환성 유지용
    SLAVE_ID_RANGE,
    JSON_SETTINGS,
    BACKUP_ENV_VARS
)

# =============================================================================
# 예외 클래스
# =============================================================================
from .context import (
    ContextException,
    NoSuchSlaveException,
    NoSuchMemoryException
)

# =============================================================================
# 데이터 저장소 클래스
# =============================================================================
from .store import (
    BaseRegistersDataBlock,
    SequentialRegistersDataBlock,
    JSONRegistersDataBlock
)

# =============================================================================
# 핵심 컨텍스트 클래스
# =============================================================================
from .context import (
    BaseSlaveContext,
    SlaveContext,
    ServerContext
)

# =============================================================================
# 팩토리 및 래퍼 클래스
# =============================================================================
from .factory import (
    JSONBlockWrapper,
    create_json_block,
    create_context_for_protocol
)

# =============================================================================
# 컨텍스트 관리자
# =============================================================================
from .manager import (
    ContextManager,
    
    # 앱 및 컨텍스트 스토어 관리
    discover_apps,
    ensure_context_store_for_apps,
    
    # 파일 생성 및 관리
    create_or_update_file_for_app,
    ensure_json_file_for_app,
    list_context_store_files,
    
    # JSON 블록 저장 및 로딩
    save_json_block_for_app,
    load_all_json_blocks_for_app,
    load_most_recent_json_block_for_app,
    restore_json_blocks_to_slave_context,
    
    # 상태 저장 및 업데이트
    upsert_processed_data_into_state,
    upsert_processed_block_into_state,
    save_status_with_meta,
    save_status_nested,
    save_status_path,
    save_block_top_level,
    save_setup,
    
    # 레지스트리 관리
    get_or_create_registry_entry,
    autosave_all_contexts,
    persist_registry_state,
    
    # 백업 관리
    backup_state_for_app,
    backup_all_states,
    generate_meta_from_state_for_apps
)

# =============================================================================
# 스케줄러 함수
# =============================================================================
from .scheduler import (
    ContextScheduler,
    autosave_job,
    restore_contexts,
    persist_all_registry_states,
    cleanup_contexts,
    get_context_stats
)

# =============================================================================
# 메타데이터 마이그레이션
# =============================================================================
from .migrate_meta import (
    MetaMigrator,
    migrate_meta_files
)

# =============================================================================
# 하위 호환성을 위한 별칭 (Deprecated - 향후 제거 예정)
# =============================================================================
# 기존 클래스명 별칭
RegistersSlaveContext = SlaveContext
RegistersServerContext = ServerContext
RegistersBaseSlaveContext = BaseSlaveContext
RegistersSequentialDataBlock = SequentialRegistersDataBlock
JSONRegistersBlockWrapper = JSONBlockWrapper
json_block_factory = create_json_block

# 기존 예외 별칭
Context_Exception = ContextException

# =============================================================================
# 패키지 공개 API
# =============================================================================
__all__ = [
    # === 설정 및 구성 ===
    # 열거형
    "ProtocolType",
    "MemoryType", 
    "FileExtension",
    
    # 기본 설정
    "DEFAULT_REGISTER_COUNT",
    "DEFAULT_REGISTER_VALUE",
    "DEFAULT_START_ADDRESS",
    "DEFAULT_ZERO_MODE",
    
    # 프로토콜 관련
    "LS_XGT_TCP_MEMORY_TYPES",
    "SUPPORTED_PROTOCOLS",
    "PROTOCOL_DEFAULT_CONFIGS",
    
    # 파일 및 디렉토리
    "CONTEXT_STORE_DIR_NAME",
    "STATE_FILE_NAME",
    "META_FILE_NAME",
    "BACKUP_DIR_NAME",
    
    # 백업 및 JSON 설정
    "DEFAULT_BACKUP_POLICY",
    "BackupEnvVars",
    "JSON_SERIALIZATION_SETTINGS",
    
    # 슬레이브 설정
    "SLAVE_ID_MIN",
    "SLAVE_ID_MAX",
    
    # 설정 관리
    "ContextConfig",
    "get_backup_policy",
    "get_log_file_path",
    "get_context_store_path",
    "get_protocol_config",
    "is_valid_slave_id",
    "parse_bytes_string",
    
    # === 예외 클래스 ===
    "ContextException",
    "NoSuchSlaveException",
    "NoSuchMemoryException",
    
    # === 데이터 저장소 ===
    "BaseRegistersDataBlock",
    "SequentialRegistersDataBlock",
    "JSONRegistersDataBlock",
    
    # === 핵심 컨텍스트 ===
    "BaseSlaveContext",
    "SlaveContext", 
    "ServerContext",
    
    # === 팩토리 및 래퍼 ===
    "JSONBlockWrapper",
    "create_json_block",
    "create_context_for_protocol",
    
    # === 컨텍스트 관리 ===
    "ContextManager",
    
    # 앱 및 컨텍스트 스토어 관리
    "discover_apps",
    "ensure_context_store_for_apps",
    
    # 파일 관리
    "create_or_update_file_for_app",
    "ensure_json_file_for_app", 
    "list_context_store_files",
    
    # JSON 블록 관리
    "save_json_block_for_app",
    "load_all_json_blocks_for_app",
    "load_most_recent_json_block_for_app",
    "restore_json_blocks_to_slave_context",
    
    # 상태 관리
    "upsert_processed_data_into_state",
    "upsert_processed_block_into_state",
    "save_status_with_meta",
    "save_status_nested",
    "save_status_path",
    "save_block_top_level",
    "save_setup",
    
    # 레지스트리 관리
    "get_or_create_registry_entry",
    "autosave_all_contexts",
    "persist_registry_state",
    
    # 백업 관리
    "backup_state_for_app",
    "backup_all_states", 
    "generate_meta_from_state_for_apps",
    
    # === 스케줄링 ===
    "ContextScheduler",
    "autosave_job",
    "restore_contexts",
    "persist_all_registry_states",
    "cleanup_contexts",
    "get_context_stats",
    
    # === 메타데이터 마이그레이션 ===
    "MetaMigrator",
    "migrate_meta_files",
    
    # === 전역 레지스트리 ===
    "CONTEXT_REGISTRY",
    
    # === 하위 호환성 (Deprecated) ===
    "RegistersSlaveContext",
    "RegistersServerContext", 
    "RegistersBaseSlaveContext",
    "RegistersSequentialDataBlock",
    "JSONRegistersBlockWrapper",
    "json_block_factory",
    "Context_Exception",
    "SLAVE_ID_RANGE",
    "JSON_SETTINGS",
    "BACKUP_ENV_VARS",
]

# =============================================================================
# 패키지 정보
# =============================================================================
__version__ = "2.0.0"
__author__ = "MCUnode Development Team"
__description__ = "MCU 노드 통신을 위한 개선된 컨텍스트 관리 시스템"

# =============================================================================
# 버전별 변경사항
# =============================================================================
__changelog__ = {
    "2.0.0": [
        "네임 패턴 표준화",
        "설정 집중화 및 ContextConfig 클래스 도입",
        "열거형을 통한 타입 안전성 개선",
        "모듈별 역할 명확화",
        "하위 호환성 유지를 위한 별칭 제공",
        "체계적인 __all__ 구성"
    ]
}

# =============================================================================
# 패키지 초기화 함수
# =============================================================================
def get_package_info() -> Dict[str, Any]:
    """패키지 정보를 반환합니다."""
    return {
        "name": "context",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "supported_protocols": list(SUPPORTED_PROTOCOLS),
        "default_config": {
            "register_count": DEFAULT_REGISTER_COUNT,
            "register_value": DEFAULT_REGISTER_VALUE,
            "start_address": DEFAULT_START_ADDRESS,
            "zero_mode": DEFAULT_ZERO_MODE
        }
    }