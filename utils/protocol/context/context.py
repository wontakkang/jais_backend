"""
컨텍스트 관리 모듈

MCU 노드 통신을 위한 슬레이브 및 서버 컨텍스트 클래스를 제공합니다.
네임 패턴을 표준화하고 가독성과 재사용성을 높였습니다.
"""

import os
from typing import Dict, Any, Union, List, Optional, Callable
from .store import BaseRegistersDataBlock, SequentialRegistersDataBlock, JSONRegistersDataBlock
from .config import (
    DEFAULT_REGISTER_COUNT, DEFAULT_REGISTER_VALUE, DEFAULT_ZERO_MODE,
    LS_XGT_TCP_MEMORY_TYPES, SLAVE_ID_MIN, SLAVE_ID_MAX, ContextConfig,
    get_log_file_path
)
from utils.logger import setup_logger

# =============================================================================
# 모듈 레벨 설정
# =============================================================================
MODULE_NAME = "context_store_manager"
log_path = get_log_file_path("py_backend")
context_logger = setup_logger(name=MODULE_NAME, log_file=log_path)

# =============================================================================
# 예외 클래스
# =============================================================================

class ContextException(Exception):
    """컨텍스트 관련 기본 예외 클래스"""

    def __init__(self, message: str = "", error_code: Optional[str] = None):
        """컨텍스트 예외 초기화
        
        Args:
            message: 에러 메시지
            error_code: 에러 코드 (선택사항)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        context_logger.error(f"ContextException: {message}")

    def __str__(self) -> str:
        base_msg = f"Context Error: {self.message}"
        if self.error_code:
            return f"{base_msg} (Code: {self.error_code})"
        return base_msg


class NoSuchSlaveException(ContextException):
    """존재하지 않는 슬레이브 참조 시 발생하는 예외"""

    def __init__(self, slave_id: Optional[int] = None, message: str = ""):
        """슬레이브 없음 예외 초기화
        
        Args:
            slave_id: 슬레이브 ID
            message: 추가 메시지
        """
        if slave_id is not None:
            full_message = f"Slave {slave_id} not found"
            if message:
                full_message += f": {message}"
        else:
            full_message = message or "Slave not found"
            
        super().__init__(f"[No Such Slave] {full_message}", "SLAVE_NOT_FOUND")
        self.slave_id = slave_id


class NoSuchMemoryException(ContextException):
    """존재하지 않는 메모리 영역 참조 시 발생하는 예외"""

    def __init__(self, memory_type: Optional[str] = None, message: str = ""):
        """메모리 없음 예외 초기화
        
        Args:
            memory_type: 메모리 타입
            message: 추가 메시지
        """
        if memory_type is not None:
            full_message = f"Memory type '{memory_type}' not found"
            if message:
                full_message += f": {message}"
        else:
            full_message = message or "Memory not found"
            
        super().__init__(f"[No Such Memory] {full_message}", "MEMORY_NOT_FOUND")
        self.memory_type = memory_type


class AddressValidationException(ContextException):
    """주소 검증 실패 시 발생하는 예외"""

    def __init__(self, address: int, count: int = 1, message: str = ""):
        """주소 검증 예외 초기화
        
        Args:
            address: 검증 실패한 주소
            count: 요청된 개수
            message: 추가 메시지
        """
        full_message = f"Address validation failed for {address}"
        if count > 1:
            full_message += f" (count: {count})"
        if message:
            full_message += f": {message}"
            
        super().__init__(f"[Address Validation] {full_message}", "ADDRESS_VALIDATION_FAILED")
        self.address = address
        self.count = count

# =============================================================================
# 기본 슬레이브 컨텍스트 클래스
# =============================================================================

class BaseSlaveContext:
    """데이터 블록 팩토리 역할을 하는 기본 슬레이브 컨텍스트 클래스

    프로토콜별 초기화 메서드를 제공하고 메모리 생성을 위한 팩토리 패턴을 구현합니다.
    - create_memory: callable, dict, 또는 메서드명(string)을 지원
    - 프로토콜별 초기화 메서드: MODBUS, LS_XGT_TCP, MCU_node
    """

    def __init__(self):
        """기본 슬레이브 컨텍스트 초기화"""
        context_logger.debug(f"{self.__class__.__name__} 초기화됨")

    def create_memory(self, creator: Optional[Union[Callable, Dict, str]] = None, **kwargs) -> Dict[str, Any]:
        """메모리 맵을 생성합니다
        
        Args:
            creator: 메모리 생성자 (None, dict, callable, 또는 메서드명)
            **kwargs: 추가 인자
            
        Returns:
            생성된 메모리 맵
            
        Raises:
            ContextException: 유효하지 않은 생성자인 경우
        """
        try:
            if creator is None:
                return {}
            
            if isinstance(creator, dict):
                return creator.copy()
            
            if callable(creator):
                return creator(**kwargs) if kwargs else creator()
            
            if isinstance(creator, str) and hasattr(self, creator):
                method = getattr(self, creator)
                if callable(method):
                    return method(**kwargs) if kwargs else method()
            
            raise ContextException(f"Invalid memory creator: {type(creator)}")
            
        except Exception as e:
            context_logger.exception("메모리 생성 중 오류 발생")
            raise ContextException(f"Memory creation failed: {str(e)}")

    def create_modbus_memory(self, *args, **kwargs) -> Union[BaseRegistersDataBlock, Dict]:
        """MODBUS용 메모리를 생성합니다
        
        Args:
            **kwargs: 설정 옵션
                - count: 레지스터 개수
                - use_json: JSON 블록 사용 여부
                - zero_mode: 제로 모드 사용 여부
                
        Returns:
            생성된 데이터 블록
        """
        count = kwargs.get("count", DEFAULT_REGISTER_COUNT)
        use_json = kwargs.get("use_json", kwargs.get("json", False))
        
        if use_json:
            return JSONRegistersDataBlock.create(count=count, value=DEFAULT_REGISTER_VALUE)
        return SequentialRegistersDataBlock.create(count=count)

    def create_ls_xgt_tcp_memory(self, *args, **kwargs) -> Dict[str, BaseRegistersDataBlock]:
        """LS XGT TCP용 메모리 영역별 데이터 블록을 생성합니다
        
        Args:
            **kwargs: 설정 옵션
                - count: 레지스터 개수
                - use_json: JSON 블록 사용 여부
                - block_factory: 커스텀 블록 팩토리
                
        Returns:
            메모리 타입별 데이터 블록 딕셔너리
        """
        store = {}
        block_factory = kwargs.get("block_factory")
        use_json = kwargs.get("use_json", kwargs.get("json", False))
        count = kwargs.get("count", DEFAULT_REGISTER_COUNT)

        for memory_type in LS_XGT_TCP_MEMORY_TYPES:
            try:
                if block_factory and callable(block_factory):
                    store[memory_type] = block_factory(memory_type, count=count)
                if use_json:
                    store[memory_type] = JSONRegistersDataBlock.create(
                        count=count, value=DEFAULT_REGISTER_VALUE
                    )
                else:
                    store[memory_type] = BaseRegistersDataBlock().create(count=count)
            except Exception as e:
                context_logger.error(f"LS XGT TCP 메모리 {memory_type} 생성 실패: {e}")
                # 기본 블록으로 대체
                store[memory_type] = BaseRegistersDataBlock().create(count=count)
                
        return store

    def create_mcu_node_memory(self, *args, **kwargs) -> BaseRegistersDataBlock:
        """MCU 노드용 메모리를 생성합니다
        
        Args:
            **kwargs: 설정 옵션
                - count: 레지스터 개수
                - value: 기본값
                - use_json: JSON 블록 사용 여부
                - block_factory: 커스텀 블록 팩토리
                - seed: 초기 데이터
                
        Returns:
            생성된 데이터 블록
        """
        count = kwargs.get("count", DEFAULT_REGISTER_COUNT)
        use_json = kwargs.get("use_json", kwargs.get("json", True))
        value = kwargs.get("value", DEFAULT_REGISTER_VALUE)
        block_factory = kwargs.get("block_factory")
        seed = kwargs.get("seed")

        # 커스텀 팩토리 우선 사용
        if block_factory and callable(block_factory):
            try:
                return block_factory(
                    count=count, value=value,
                    **{k: v for k, v in kwargs.items() 
                       if k not in {"count", "value", "block_factory"}}
                )
            except Exception as e:
                context_logger.warning(f"커스텀 블록 팩토리 실패, 기본 블록으로 대체: {e}")

        # JSON 블록 또는 순차 블록 생성
        try:
            if use_json:
                block = JSONRegistersDataBlock.create(count=count, value=value)
            else:
                block = SequentialRegistersDataBlock.create(count=count, value=value)
        except Exception as e:
            context_logger.error(f"MCU 노드 블록 생성 실패: {e}")
            return {}

        # 초기 데이터 적용
        if isinstance(seed, dict) and seed:
            self._apply_seed_to_block(block, seed)

        return block

    def _apply_seed_to_block(self, block: BaseRegistersDataBlock, seed: Dict[str, Any]) -> None:
        """블록에 초기 데이터를 적용합니다"""
        try:
            if hasattr(block, "update") and callable(block.update):
                block.update(seed)
            else:
                for key, value in seed.items():
                    try:
                        block[key] = value
                    except Exception:
                        if hasattr(block, "set") and callable(block.set):
                            block.set(key, value)
        except Exception as e:
            context_logger.debug(f"시드 데이터 적용 실패: {e}")

    # 하위 호환성을 위한 별칭 메서드
    def MODBUS(self, *args, **kwargs):
        """MODBUS 메서드 (하위 호환성)"""
        return self.create_modbus_memory(*args, **kwargs)

    def LS_XGT_TCP(self, *args, **kwargs):
        """LS_XGT_TCP 메서드 (하위 호환성)"""
        return self.create_ls_xgt_tcp_memory(*args, **kwargs)

    def MCU_node(self, *args, **kwargs):
        """MCU_node 메서드 (하위 호환성)"""
        return self.create_mcu_node_memory(*args, **kwargs)

# =============================================================================
# 슬레이브 컨텍스트 클래스
# =============================================================================

class SlaveContext(BaseSlaveContext):
    """슬레이브별 데이터 저장소를 관리하는 컨텍스트
    
    - 메모리 생성 및 관리
    - 주소 변환 (zero_mode 지원)
    - 상태 저장 및 조회
    """

    def __init__(self, create_memory: Optional[Union[Callable, Dict, str]] = None, 
                 zero_mode: Optional[bool] = None, **kwargs):
        """슬레이브 컨텍스트 초기화
        
        Args:
            create_memory: 메모리 생성자
            zero_mode: 주소 변환 모드
            **kwargs: 추가 설정
        """
        super().__init__()
        
        # 메모리 저장소 생성
        try:
            self.store = self.create_memory(create_memory, **kwargs)
        except ContextException:
            context_logger.warning("메모리 생성 실패, 빈 저장소로 초기화")
            self.store = {}
        
        # 설정 적용
        self.zero_mode = zero_mode if zero_mode is not None else DEFAULT_ZERO_MODE
        self._state: Dict[str, Any] = {}
        
        context_logger.debug(f"SlaveContext 생성 완료 (zero_mode={self.zero_mode})")

    def __str__(self) -> str:
        return f"SlaveContext(memories={len(self.store)}, zero_mode={self.zero_mode})"

    def __repr__(self) -> str:
        return f"SlaveContext(store_keys={list(self.store.keys())}, zero_mode={self.zero_mode})"

    def reset(self) -> None:
        """모든 데이터 저장소를 초기값으로 재설정합니다"""
        reset_count = 0
        for datastore in self.store.values():
            if hasattr(datastore, "reset") and callable(datastore.reset):
                try:
                    datastore.reset()
                    reset_count += 1
                except Exception as e:
                    context_logger.error(f"데이터스토어 리셋 실패: {e}")
        
        context_logger.debug(f"슬레이브 컨텍스트 리셋 완료 ({reset_count}개 저장소)")

    def _adjust_address(self, address: Union[int, str]) -> int:
        """주소를 zero_mode에 따라 조정합니다
        
        Args:
            address: 원본 주소
            
        Returns:
            조정된 주소
            
        Raises:
            ContextException: 주소가 유효하지 않은 경우
        """
        try:
            addr = int(address)
            if addr < 0:
                raise ValueError("음수 주소는 허용되지 않습니다")
        except (ValueError, TypeError) as e:
            raise ContextException(f"유효하지 않은 주소: {address}")
        
        if not self.zero_mode:
            addr += 1
        
        return addr

    def validate(self, memory: str, address: Union[int, str], count: int = 1) -> bool:
        """메모리 접근이 유효한지 검증합니다
        
        Args:
            memory: 메모리 타입
            address: 시작 주소
            count: 개수
            
        Returns:
            유효성 여부
            
        Raises:
            NoSuchMemoryException: 메모리가 존재하지 않는 경우
        """
        if memory not in self.store:
            raise NoSuchMemoryException(memory, f"사용 가능한 메모리: {list(self.store.keys())}")
        
        try:
            addr = self._adjust_address(address)
            result = self.store[memory].validate(addr, count)
            context_logger.debug(f"주소 검증: memory={memory}, address={addr}, count={count}, valid={result}")
            return result
        except Exception as e:
            context_logger.error(f"주소 검증 중 오류: {e}")
            return False

    def getValues(self, memory: str, address: Union[int, str], count: int = 1) -> List[Any]:
        """메모리에서 값들을 가져옵니다
        
        Args:
            memory: 메모리 타입
            address: 시작 주소
            count: 개수
            
        Returns:
            값들의 리스트
            
        Raises:
            NoSuchMemoryException: 메모리가 존재하지 않는 경우
        """
        if memory not in self.store:
            raise NoSuchMemoryException(memory)
        
        addr = self._adjust_address(address)
        
        try:
            values = self.store[memory].getValues(addr, count)
            context_logger.debug(f"값 조회: memory={memory}, address={addr}, count={count}")
            return values
        except Exception as e:
            context_logger.error(f"값 조회 실패: {e}")
            raise ContextException(f"Failed to get values from {memory} at {addr}")

    def setValues(self, memory: str, address: Union[int, str], values: Union[Any, List[Any]]) -> None:
        """메모리에 값들을 설정합니다
        
        Args:
            memory: 메모리 타입
            address: 시작 주소
            values: 설정할 값들
            
        Raises:
            NoSuchMemoryException: 메모리가 존재하지 않는 경우
        """
        if memory not in self.store:
            raise NoSuchMemoryException(memory)
        
        addr = self._adjust_address(address)
        
        try:
            count = len(values) if isinstance(values, (list, tuple)) else 1
            self.store[memory].setValues(addr, values)
            context_logger.debug(f"값 설정: memory={memory}, address={addr}, count={count}")
        except Exception as e:
            context_logger.error(f"값 설정 실패: {e}")
            raise ContextException(f"Failed to set values in {memory} at {addr}")

    # === 상태 관리 메서드 ===
    
    def set_state(self, key: str, value: Any) -> bool:
        """상태를 설정합니다
        
        Args:
            key: 상태 키
            value: 상태 값
            
        Returns:
            성공 여부
        """
        try:
            if not hasattr(self, '_state') or self._state is None:
                self._state = {}
            self._state[key] = value
            context_logger.debug(f"상태 설정: {key}")
            return True
        except Exception as e:
            context_logger.error(f"상태 설정 실패: {e}")
            return False

    def get_state(self, key: str, default: Any = None) -> Any:
        """상태를 조회합니다
        
        Args:
            key: 상태 키
            default: 기본값
            
        Returns:
            상태 값
        """
        try:
            return getattr(self, '_state', {}).get(key, default)
        except Exception as e:
            context_logger.error(f"상태 조회 실패: {e}")
            return default

    def get_all_state(self) -> Dict[str, Any]:
        """모든 상태를 조회합니다
        
        Returns:
            상태 딕셔너리 복사본
        """
        try:
            return dict(getattr(self, '_state', {}) or {})
        except Exception as e:
            context_logger.error(f"전체 상태 조회 실패: {e}")
            return {}

    def clear_state(self, key: Optional[str] = None) -> None:
        """상태를 삭제합니다
        
        Args:
            key: 삭제할 키 (None이면 전체 삭제)
        """
        try:
            if not hasattr(self, '_state') or self._state is None:
                return
            
            if key is None:
                self._state.clear()
                context_logger.debug("전체 상태 삭제됨")
            else:
                self._state.pop(key, None)
                context_logger.debug(f"상태 삭제: {key}")
        except Exception as e:
            context_logger.error(f"상태 삭제 실패: {e}")

    def get_memory_info(self) -> Dict[str, Dict[str, Any]]:
        """메모리 정보를 반환합니다"""
        info = {}
        for name, store in self.store.items():
            try:
                info[name] = {
                    "type": type(store).__name__,
                    "size": getattr(store, "get_size", lambda: len(getattr(store, "values", [])))(),
                    "address": getattr(store, "address", "unknown"),
                    "default_value": getattr(store, "default_value", "unknown")
                }
            except Exception as e:
                info[name] = {"error": str(e)}
        return info

# =============================================================================
# 서버 컨텍스트 클래스
# =============================================================================

class ServerContext:
    """여러 슬레이브 컨텍스트를 관리하는 서버 컨텍스트
    
    - single=True: 단일 컨텍스트 모드 (모든 요청을 같은 컨텍스트로 처리)
    - slaves: dict(slave_id -> SlaveContext) 또는 단일 컨텍스트 인스턴스
    """

    def __init__(self, slaves: Optional[Union[Dict[int, SlaveContext], SlaveContext]] = None, 
                 single: bool = True):
        """서버 컨텍스트 초기화
        
        Args:
            slaves: 슬레이브 컨텍스트들 또는 단일 컨텍스트
            single: 단일 컨텍스트 모드 여부
        """
        self.single = single
        self._slaves: Dict[int, SlaveContext] = {}
        
        if slaves is None:
            self._slaves = {}
        elif isinstance(slaves, dict):
            # 유효한 슬레이브 ID만 저장
            for slave_id, context in slaves.items():
                if ContextConfig.is_valid_slave_id(slave_id):
                    self._slaves[slave_id] = context
                else:
                    context_logger.warning(f"유효하지 않은 슬레이브 ID 무시: {slave_id}")
        else:
            # 단일 컨텍스트인 경우
            default_id = 1
            self._slaves = {default_id: slaves}
        
        context_logger.debug(f"ServerContext 생성 (single={single}, slaves={len(self._slaves)})")

    def __str__(self) -> str:
        return f"ServerContext(single={self.single}, slave_count={len(self._slaves)})"

    def __repr__(self) -> str:
        slave_ids = list(self._slaves.keys())
        return f"ServerContext(single={self.single}, slave_ids={slave_ids})"

    def __iter__(self):
        """슬레이브 ID와 컨텍스트 쌍을 순회합니다"""
        return iter(self._slaves.items())

    def __contains__(self, slave_id: int) -> bool:
        """슬레이브 ID가 존재하는지 확인합니다"""
        if self.single and self._slaves:
            return True
        return slave_id in self._slaves

    def __setitem__(self, slave_id: int, context: SlaveContext) -> None:
        """슬레이브 컨텍스트를 설정합니다"""
        if self.single:
            slave_id = 1
        
        if not ContextConfig.is_valid_slave_id(slave_id):
            raise NoSuchSlaveException(slave_id, "슬레이브 ID가 유효 범위를 벗어남")
        
        self._slaves[slave_id] = context
        context_logger.debug(f"슬레이브 {slave_id} 컨텍스트 설정됨")

    def __delitem__(self, slave_id: int) -> None:
        """슬레이브 컨텍스트를 삭제합니다"""
        if self.single:
            context_logger.warning("단일 모드에서는 슬레이브 삭제가 불가능합니다")
            return
        
        if not ContextConfig.is_valid_slave_id(slave_id):
            raise NoSuchSlaveException(slave_id, "슬레이브 ID가 유효 범위를 벗어남")
        
        if slave_id in self._slaves:
            del self._slaves[slave_id]
            context_logger.debug(f"슬레이브 {slave_id} 컨텍스트 삭제됨")
        else:
            raise NoSuchSlaveException(slave_id)

    def __getitem__(self, slave_id: int) -> SlaveContext:
        """슬레이브 컨텍스트를 가져옵니다"""
        if self.single:
            slave_id = 1
        
        if slave_id in self._slaves:
            return self._slaves[slave_id]
        
        raise NoSuchSlaveException(slave_id, f"사용 가능한 슬레이브: {list(self._slaves.keys())}")

    def slaves(self) -> List[int]:
        """등록된 슬레이브 ID 목록을 반환합니다"""
        return list(self._slaves.keys())

    def add_slave(self, slave_id: int, context: SlaveContext) -> None:
        """슬레이브를 추가합니다"""
        self[slave_id] = context

    def remove_slave(self, slave_id: int) -> None:
        """슬레이브를 제거합니다"""
        del self[slave_id]

    def get_slave_count(self) -> int:
        """슬레이브 개수를 반환합니다"""
        return len(self._slaves)

    def reset_all_slaves(self) -> None:
        """모든 슬레이브 컨텍스트를 리셋합니다"""
        reset_count = 0
        for slave_id, context in self._slaves.items():
            try:
                context.reset()
                reset_count += 1
            except Exception as e:
                context_logger.error(f"슬레이브 {slave_id} 리셋 실패: {e}")
        
        context_logger.info(f"서버 컨텍스트 리셋 완료 ({reset_count}/{len(self._slaves)})")

    def get_server_info(self) -> Dict[str, Any]:
        """서버 정보를 반환합니다"""
        return {
            "single_mode": self.single,
            "slave_count": len(self._slaves),
            "slave_ids": list(self._slaves.keys()),
            "slaves_info": {
                slave_id: context.get_memory_info() 
                for slave_id, context in self._slaves.items()
            }
        }

# =============================================================================
# 하위 호환성을 위한 별칭 (Deprecated)
# =============================================================================
RegistersBaseSlaveContext = BaseSlaveContext
RegistersSlaveContext = SlaveContext
RegistersServerContext = ServerContext
Context_Exception = ContextException
