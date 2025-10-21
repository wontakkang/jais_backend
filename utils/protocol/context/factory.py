"""
팩토리 및 래퍼 클래스 모듈

MCU 노드 통신을 위한 데이터 블록 및 컨텍스트 생성 팩토리들을 제공합니다.
네임 패턴을 표준화하고 재사용성을 높인 팩토리 패턴을 구현합니다.
"""

from typing import Dict, Any, Union, Optional, Type, Callable
import json
from .config import (
    ProtocolType, DEFAULT_REGISTER_COUNT, DEFAULT_REGISTER_VALUE, 
    DEFAULT_START_ADDRESS, JSON_SERIALIZATION_SETTINGS,
    get_protocol_config, ContextConfig
)
from .store import BaseRegistersDataBlock, SequentialRegistersDataBlock, JSONRegistersDataBlock
from .context import BaseSlaveContext, SlaveContext, ServerContext, ContextException

# =============================================================================
# JSON 블록 래퍼 클래스
# =============================================================================

class JSONBlockWrapper:
    """JSON 레지스터 데이터 블록을 위한 래퍼 클래스
    
    JSON 직렬화/역직렬화 및 추가 기능들을 제공하는 래퍼입니다.
    """
    
    def __init__(self, json_block: JSONRegistersDataBlock, metadata: Optional[Dict[str, Any]] = None):
        """JSON 블록 래퍼 초기화
        
        Args:
            json_block: 래핑할 JSON 데이터 블록
            metadata: 추가 메타데이터
        """
        if not isinstance(json_block, JSONRegistersDataBlock):
            raise ContextException("JSONBlockWrapper는 JSONRegistersDataBlock만 래핑할 수 있습니다.")
        
        self._block = json_block
        self._metadata = metadata or {}
        self._creation_time = None
        self._last_modified = None
        
    @property
    def block(self) -> JSONRegistersDataBlock:
        """래핑된 JSON 데이터 블록을 반환합니다"""
        return self._block
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """메타데이터를 반환합니다"""
        return self._metadata.copy()
    
    def set_metadata(self, key: str, value: Any) -> None:
        """메타데이터를 설정합니다"""
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """메타데이터를 조회합니다"""
        return self._metadata.get(key, default)
    
    def remove_metadata(self, key: str) -> bool:
        """메타데이터를 제거합니다"""
        if key in self._metadata:
            del self._metadata[key]
            return True
        return False
    
    def to_json_string(self, **json_kwargs) -> str:
        """JSON 문자열로 직렬화합니다"""
        json_settings = JSON_SERIALIZATION_SETTINGS.copy()
        json_settings.update(json_kwargs)
        
        data = {
            "block_data": self._block.to_json(),
            "metadata": self._metadata,
            "wrapper_info": {
                "type": self.__class__.__name__,
                "creation_time": self._creation_time,
                "last_modified": self._last_modified
            }
        }
        
        return json.dumps(data, **json_settings)
    
    @classmethod
    def from_json_string(cls, json_str: str) -> 'JSONBlockWrapper':
        """JSON 문자열에서 인스턴스를 생성합니다"""
        try:
            data = json.loads(json_str)
            block_data = data.get("block_data", {})
            metadata = data.get("metadata", {})
            
            json_block = JSONRegistersDataBlock.from_json(block_data)
            wrapper = cls(json_block, metadata)
            
            # 래퍼 정보 복원
            wrapper_info = data.get("wrapper_info", {})
            wrapper._creation_time = wrapper_info.get("creation_time")
            wrapper._last_modified = wrapper_info.get("last_modified")
            
            return wrapper
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ContextException(f"JSON 래퍼 역직렬화 실패: {e}")
    
    def copy(self) -> 'JSONBlockWrapper':
        """래퍼의 깊은 복사본을 생성합니다"""
        # JSON 블록 복사
        block_json = self._block.to_json()
        new_block = JSONRegistersDataBlock.from_json(block_json)
        
        # 메타데이터 복사
        new_metadata = self._metadata.copy()
        
        return JSONBlockWrapper(new_block, new_metadata)
    
    def merge_with(self, other: 'JSONBlockWrapper', merge_strategy: str = "update") -> 'JSONBlockWrapper':
        """다른 래퍼와 병합합니다
        
        Args:
            other: 병합할 다른 래퍼
            merge_strategy: 병합 전략 ("update", "preserve", "overwrite")
            
        Returns:
            병합된 새로운 래퍼
        """
        if not isinstance(other, JSONBlockWrapper):
            raise ContextException("JSONBlockWrapper끼리만 병합할 수 있습니다.")
        
        # 새 래퍼 생성
        merged = self.copy()
        
        # 메타데이터 병합
        if merge_strategy == "update":
            merged._metadata.update(other._metadata)
        elif merge_strategy == "preserve":
            for key, value in other._metadata.items():
                if key not in merged._metadata:
                    merged._metadata[key] = value
        elif merge_strategy == "overwrite":
            merged._metadata = other._metadata.copy()
        
        # 블록 데이터 병합 (다른 블록의 값으로 업데이트)
        for key, value in other._block.values.items():
            merged._block.values[key] = value
        
        return merged
    
    def __str__(self) -> str:
        return f"JSONBlockWrapper(block_size={self._block.get_size()}, metadata_keys={len(self._metadata)})"
    
    def __repr__(self) -> str:
        return f"JSONBlockWrapper(block={repr(self._block)}, metadata={self._metadata})"

# =============================================================================
# 데이터 블록 팩토리 함수들
# =============================================================================

def create_json_block(count: int = DEFAULT_REGISTER_COUNT,
                     value: Any = DEFAULT_REGISTER_VALUE,
                     address: int = DEFAULT_START_ADDRESS,
                     with_wrapper: bool = False,
                     metadata: Optional[Dict[str, Any]] = None) -> Union[JSONRegistersDataBlock, JSONBlockWrapper]:
    """JSON 데이터 블록을 생성합니다
    
    Args:
        count: 레지스터 개수
        value: 초기값
        address: 시작 주소
        with_wrapper: 래퍼 사용 여부
        metadata: 래퍼 메타데이터 (with_wrapper=True일 때만)
        
    Returns:
        생성된 JSON 데이터 블록 또는 래퍼
    """
    try:
        json_block = JSONRegistersDataBlock.create(count=count, value=value, address=address)
        
        if with_wrapper:
            return JSONBlockWrapper(json_block, metadata)
        
        return json_block
    except Exception as e:
        raise ContextException(f"JSON 블록 생성 실패: {e}")

def create_sequential_block(count: int = DEFAULT_REGISTER_COUNT,
                          value: Any = DEFAULT_REGISTER_VALUE,
                          address: int = DEFAULT_START_ADDRESS) -> SequentialRegistersDataBlock:
    """순차적 데이터 블록을 생성합니다
    
    Args:
        count: 레지스터 개수
        value: 초기값  
        address: 시작 주소
        
    Returns:
        생성된 순차적 데이터 블록
    """
    try:
        return SequentialRegistersDataBlock.create(count=count, value=value, address=address)
    except Exception as e:
        raise ContextException(f"순차적 블록 생성 실패: {e}")

def create_datablock_by_type(block_type: str, **kwargs) -> BaseRegistersDataBlock:
    """타입별 데이터 블록을 생성합니다
    
    Args:
        block_type: 블록 타입 ("json", "sequential")
        **kwargs: 블록 생성 인자
        
    Returns:
        생성된 데이터 블록
    """
    block_type = block_type.lower().strip()
    
    if block_type in ["json", "json_block"]:
        return create_json_block(**kwargs)
    elif block_type in ["sequential", "seq", "modbus"]:
        return create_sequential_block(**kwargs)
    else:
        raise ContextException(f"지원하지 않는 블록 타입: {block_type}")

# =============================================================================
# 컨텍스트 팩토리 함수들
# =============================================================================

def create_context_for_protocol(protocol: str, **kwargs) -> SlaveContext:
    """프로토콜별 슬레이브 컨텍스트를 생성합니다
    
    Args:
        protocol: 프로토콜 이름 (MODBUS, LS_XGT_TCP, MCU_node)
        **kwargs: 컨텍스트 생성 인자
        
    Returns:
        생성된 슬레이브 컨텍스트
    """
    try:
        protocol = protocol.upper().strip()
        
        # 프로토콜별 기본 설정 가져오기
        protocol_config = get_protocol_config(protocol)
        if not protocol_config:
            raise ContextException(f"지원하지 않는 프로토콜: {protocol}")
        
        # 기본 설정과 사용자 인자 병합
        merged_kwargs = protocol_config.copy()
        merged_kwargs.update(kwargs)
        
        # 프로토콜별 컨텍스트 생성
        if protocol == ProtocolType.MODBUS.value:
            return _create_modbus_context(**merged_kwargs)
        elif protocol == ProtocolType.LS_XGT_TCP.value:
            return _create_ls_xgt_tcp_context(**merged_kwargs)
        elif protocol == ProtocolType.MCU_NODE.value:
            return _create_mcu_node_context(**merged_kwargs)
        else:
            raise ContextException(f"프로토콜 컨텍스트 생성기 미구현: {protocol}")
            
    except Exception as e:
        raise ContextException(f"프로토콜 컨텍스트 생성 실패 ({protocol}): {e}")

def _create_modbus_context(**kwargs) -> SlaveContext:
    """MODBUS 프로토콜용 컨텍스트 생성"""
    zero_mode = kwargs.get("zero_mode", True)
    use_json = kwargs.get("use_json", False)
    
    def modbus_memory_factory(**factory_kwargs):
        merged = kwargs.copy()
        merged.update(factory_kwargs)
        if use_json:
            return create_json_block(**merged)
        return create_sequential_block(**merged)
    
    return SlaveContext(create_memory=modbus_memory_factory, zero_mode=zero_mode, **kwargs)

def _create_ls_xgt_tcp_context(**kwargs) -> SlaveContext:
    """LS XGT TCP 프로토콜용 컨텍스트 생성"""
    memory_types = kwargs.get("memory_types", ["%MB", "%RB", "%WB"])
    use_json = kwargs.get("use_json", False)
    
    def ls_xgt_memory_factory(**factory_kwargs):
        store = {}
        merged = kwargs.copy()
        merged.update(factory_kwargs)
        
        for memory_type in memory_types:
            if use_json:
                store[memory_type] = create_json_block(**merged)
            else:
                store[memory_type] = create_sequential_block(**merged)
        return store
    
    return SlaveContext(create_memory=ls_xgt_memory_factory, **kwargs)

def _create_mcu_node_context(**kwargs) -> SlaveContext:
    """MCU 노드 프로토콜용 컨텍스트 생성"""
    use_json = kwargs.get("use_json", True)
    auto_save = kwargs.get("auto_save", True)
    
    def mcu_memory_factory(**factory_kwargs):
        merged = kwargs.copy()
        merged.update(factory_kwargs)
        
        if use_json:
            block = create_json_block(with_wrapper=True, **merged)
            if auto_save:
                block.set_metadata("auto_save", True)
            return block
        return create_sequential_block(**merged)
    
    return SlaveContext(create_memory=mcu_memory_factory, **kwargs)

# =============================================================================
# 서버 컨텍스트 팩토리
# =============================================================================

def create_server_context(protocol: str, slave_configs: Optional[Dict[int, Dict[str, Any]]] = None,
                         single_mode: bool = True, **default_kwargs) -> ServerContext:
    """서버 컨텍스트를 생성합니다
    
    Args:
        protocol: 프로토콜 이름
        slave_configs: 슬레이브별 설정 (slave_id -> config)
        single_mode: 단일 모드 여부
        **default_kwargs: 기본 설정
        
    Returns:
        생성된 서버 컨텍스트
    """
    slaves = {}
    
    if slave_configs:
        for slave_id, config in slave_configs.items():
            if not ContextConfig.is_valid_slave_id(slave_id):
                continue
            
            merged_config = default_kwargs.copy()
            merged_config.update(config)
            
            slaves[slave_id] = create_context_for_protocol(protocol, **merged_config)
    else:
        # 기본 슬레이브 생성
        default_slave = create_context_for_protocol(protocol, **default_kwargs)
        slaves[1] = default_slave
    
    return ServerContext(slaves, single=single_mode)

# =============================================================================
# 설정 기반 팩토리
# =============================================================================

def create_from_config(config: Dict[str, Any]) -> Union[BaseRegistersDataBlock, SlaveContext, ServerContext]:
    """설정 딕셔너리로부터 객체를 생성합니다
    
    Args:
        config: 생성 설정
            - type: "datablock", "slave_context", "server_context"
            - protocol: 프로토콜 이름 (컨텍스트인 경우)
            - block_type: 데이터 블록 타입 (데이터블록인 경우)
            - 기타 생성 인자들
            
    Returns:
        생성된 객체
    """
    obj_type = config.get("type", "").lower()
    
    if obj_type == "datablock":
        block_type = config.get("block_type", "sequential")
        return create_datablock_by_type(block_type, **config)
    
    elif obj_type == "slave_context":
        protocol = config.get("protocol", "MODBUS")
        return create_context_for_protocol(protocol, **config)
    
    elif obj_type == "server_context":
        protocol = config.get("protocol", "MODBUS")
        slave_configs = config.get("slave_configs")
        single_mode = config.get("single_mode", True)
        
        return create_server_context(
            protocol, slave_configs, single_mode, 
            **{k: v for k, v in config.items() if k not in ["type", "protocol", "slave_configs", "single_mode"]}
        )
    
    else:
        raise ContextException(f"지원하지 않는 객체 타입: {obj_type}")

# =============================================================================
# 빌더 패턴 클래스
# =============================================================================

class ContextBuilder:
    """컨텍스트 생성을 위한 빌더 패턴 클래스"""
    
    def __init__(self, protocol: str):
        """빌더 초기화
        
        Args:
            protocol: 프로토콜 이름
        """
        self._protocol = protocol.upper().strip()
        self._config = get_protocol_config(self._protocol).copy()
        
    def with_count(self, count: int) -> 'ContextBuilder':
        """레지스터 개수 설정"""
        self._config["count"] = count
        return self
        
    def with_value(self, value: Any) -> 'ContextBuilder':
        """초기값 설정"""  
        self._config["value"] = value
        return self
        
    def with_address(self, address: int) -> 'ContextBuilder':
        """시작 주소 설정"""
        self._config["address"] = address
        return self
        
    def with_json_mode(self, use_json: bool = True) -> 'ContextBuilder':
        """JSON 모드 설정"""
        self._config["use_json"] = use_json
        return self
        
    def with_zero_mode(self, zero_mode: bool = True) -> 'ContextBuilder':
        """제로 모드 설정"""
        self._config["zero_mode"] = zero_mode
        return self
        
    def with_config(self, **kwargs) -> 'ContextBuilder':
        """추가 설정"""
        self._config.update(kwargs)
        return self
        
    def build_slave_context(self) -> SlaveContext:
        """슬레이브 컨텍스트 생성"""
        return create_context_for_protocol(self._protocol, **self._config)
        
    def build_server_context(self, single_mode: bool = True) -> ServerContext:
        """서버 컨텍스트 생성"""
        slave = self.build_slave_context()
        return ServerContext({1: slave}, single=single_mode)

# =============================================================================
# 하위 호환성을 위한 별칭 (Deprecated)
# =============================================================================
JSONRegistersBlockWrapper = JSONBlockWrapper
json_block_factory = create_json_block

# =============================================================================
# 팩토리 레지스트리
# =============================================================================

FACTORY_REGISTRY: Dict[str, Callable] = {
    "json_block": create_json_block,
    "sequential_block": create_sequential_block,
    "datablock": create_datablock_by_type,
    "slave_context": create_context_for_protocol,
    "server_context": create_server_context,
    "from_config": create_from_config
}

def get_factory(name: str) -> Callable:
    """팩토리 함수를 이름으로 조회합니다"""
    if name not in FACTORY_REGISTRY:
        raise ContextException(f"등록되지 않은 팩토리: {name}")
    return FACTORY_REGISTRY[name]

def register_factory(name: str, factory: Callable) -> None:
    """새로운 팩토리를 등록합니다"""
    FACTORY_REGISTRY[name] = factory
