"""
데이터 블록 저장소 모듈

MCU 노드 통신을 위한 다양한 데이터 저장소 클래스를 제공합니다.
네임 패턴을 표준화하고 가독성과 재사용성을 높였습니다.
"""

from typing import List, Dict, Any, Union, Optional
try:
    from utils.protocol.LSIS.exceptions import NotImplementedException
except ImportError:
    # 외부 모듈이 없을 경우 파이썬 내장 NotImplementedError를 사용
    NotImplementedException = NotImplementedError

from .config import (
    LS_XGT_TCP_MEMORY_TYPES, 
    DEFAULT_REGISTER_COUNT, 
    DEFAULT_REGISTER_VALUE, 
    DEFAULT_START_ADDRESS,
    JSON_SERIALIZATION_SETTINGS
)

# =============================================================================
# 추상 기본 클래스
# =============================================================================

class BaseRegistersDataBlock:
    """레지스터 데이터 저장소의 추상 기본 클래스
    
    모든 구체적인 데이터 저장소 클래스는 이 클래스를 상속받아야 합니다.
    
    Attributes:
        address: 데이터 저장소의 시작 주소
        default_value: 데이터 저장소의 기본값
        values: 실제 데이터 저장소 값
        
    파생 클래스는 다음 메서드를 구현해야 합니다:
        - validate(self, address, count=1): 주소 검증
        - getValues(self, address, count=1): 값 가져오기
        - setValues(self, address, values): 값 설정하기
    """
    
    # 클래스 레벨 상수
    SUPPORTED_MEMORY_TYPES = LS_XGT_TCP_MEMORY_TYPES
    
    def __init__(self):
        """기본 초기화"""
        self.address: int = DEFAULT_START_ADDRESS
        self.default_value: Any = DEFAULT_REGISTER_VALUE
        self.values: Union[List, Dict] = []
    
    @classmethod
    def create(cls, count: int = DEFAULT_REGISTER_COUNT, value: Any = DEFAULT_REGISTER_VALUE) -> List:
        """저장소를 하나의 값으로 초기화하는 팩토리 메서드
        
        Args:
            count: 설정할 필드의 개수
            value: 필드에 설정할 기본값
            
        Returns:
            초기화된 값들의 리스트
        """
        return [value] * count
    
    def reset(self) -> None:
        """데이터 저장소를 초기 기본값으로 재설정합니다."""
        if isinstance(self.values, list):
            self.values = [self.default_value] * len(self.values)
        elif isinstance(self.values, dict):
            for key in self.values:
                self.values[key] = self.default_value
    
    def validate(self, address: int, count: int = 1) -> bool:
        """요청이 범위 내에 있는지 확인하는 추상 메서드
        
        Args:
            address: 시작 주소
            count: 확인할 값의 개수
            
        Raises:
            NotImplementedException: 구현되지 않은 경우
        """
        raise NotImplementedException("데이터 저장소 주소 확인 메서드가 구현되지 않았습니다.")
    
    def getValues(self, address: int, count: int = 1) -> List[Any]:
        """데이터 저장소에서 요청된 값을 반환하는 추상 메서드
        
        Args:
            address: 시작 주소
            count: 검색할 값의 개수
            
        Raises:
            NotImplementedException: 구현되지 않은 경우
        """
        raise NotImplementedException("데이터 저장소 값 검색 메서드가 구현되지 않았습니다.")
    
    def setValues(self, address: int, values: Union[Any, List[Any]]) -> None:
        """데이터 저장소에 요청된 값을 설정하는 추상 메서드
        
        Args:
            address: 시작 주소
            values: 저장할 값
            
        Raises:
            NotImplementedException: 구현되지 않은 경우
        """
        raise NotImplementedException("데이터 저장소 값 저장 메서드가 구현되지 않았습니다.")
    
    def get_size(self) -> int:
        """저장소의 크기를 반환합니다."""
        if isinstance(self.values, (list, tuple)):
            return len(self.values)
        elif isinstance(self.values, dict):
            return len(self.values)
        return 0
    
    def is_empty(self) -> bool:
        """저장소가 비어있는지 확인합니다."""
        return self.get_size() == 0
    
    def __str__(self) -> str:
        """데이터 저장소의 문자열 표현을 반환"""
        return f"{self.__class__.__name__}(size={self.get_size()}, default={self.default_value})"
    
    def __repr__(self) -> str:
        """디버깅용 상세 문자열 표현"""
        return f"{self.__class__.__name__}(address={self.address}, size={self.get_size()})"
    
    def __iter__(self):
        """데이터 블록 데이터를 순회할 수 있도록 설정"""
        if isinstance(self.values, dict):
            return iter(self.values.items())
        return enumerate(self.values, self.address)

# =============================================================================
# 순차적 데이터 저장소
# =============================================================================

class SequentialRegistersDataBlock(BaseRegistersDataBlock):
    """순차적 레지스터 데이터 저장소 클래스
    
    연속된 메모리 주소에 값을 저장하는 데이터 저장소입니다.
    주로 Modbus와 같은 순차적 접근이 필요한 프로토콜에 사용됩니다.
    """
    
    def __init__(self, address: int, values: Union[List, Any]):
        """데이터 저장소 초기화
        
        Args:
            address: 데이터 저장소의 시작 주소
            values: 리스트 또는 단일 값
        """
        super().__init__()
        self.address = address
        
        if hasattr(values, "__iter__") and not isinstance(values, (str, bytes)):
            self.values = list(values)
        else:
            self.values = [values]
        
        # 기본값을 첫 번째 요소의 타입으로 설정
        if self.values:
            self.default_value = type(self.values[0])()
        else:
            self.default_value = DEFAULT_REGISTER_VALUE
    
    @classmethod
    def create(cls, count: int = DEFAULT_REGISTER_COUNT, value: Any = DEFAULT_REGISTER_VALUE, 
               address: int = DEFAULT_START_ADDRESS) -> 'SequentialRegistersDataBlock':
        """초기화된 순차적 데이터 저장소 생성
        
        Args:
            count: 레지스터 개수
            value: 초기값
            address: 시작 주소
            
        Returns:
            초기화된 SequentialRegistersDataBlock 인스턴스
        """
        return cls(address, [value] * count)
    
    def validate(self, address: int, count: int = 1) -> bool:
        """요청 주소와 개수가 유효한 범위인지 확인"""
        if not isinstance(address, int) or address < 0:
            return False
        if not isinstance(count, int) or count <= 0:
            return False
        
        start_valid = self.address <= address
        end_valid = (self.address + len(self.values)) >= (address + count)
        return start_valid and end_valid
    
    def getValues(self, address: int, count: int = 1) -> List[Any]:
        """지정된 주소에서 값들을 가져옵니다"""
        if not self.validate(address, count):
            raise IndexError(f"주소 {address}부터 {count}개 값은 유효 범위를 벗어났습니다.")
        
        start_index = address - self.address
        return self.values[start_index:start_index + count]
    
    def setValues(self, address: int, values: Union[Any, List[Any]]) -> None:
        """지정된 주소에 값들을 설정합니다"""
        if not isinstance(values, (list, tuple)):
            values = [values]
        
        if not self.validate(address, len(values)):
            raise IndexError(f"주소 {address}부터 {len(values)}개 값은 유효 범위를 벗어났습니다.")
        
        start_index = address - self.address
        self.values[start_index:start_index + len(values)] = values
    
    def extend_capacity(self, new_size: int, fill_value: Optional[Any] = None) -> None:
        """저장소 용량을 확장합니다"""
        if fill_value is None:
            fill_value = self.default_value
        
        current_size = len(self.values)
        if new_size > current_size:
            self.values.extend([fill_value] * (new_size - current_size))

# =============================================================================
# JSON 기반 키-값 데이터 저장소
# =============================================================================

class JSONRegistersDataBlock(BaseRegistersDataBlock):
    """JSON 직렬화가 가능한 키-값형 데이터 저장소
    
    문자열 키를 사용하여 값을 저장하므로 JSON 직렬화/역직렬화가 용이합니다.
    MCU 노드와 같이 유연한 데이터 구조가 필요한 경우에 사용됩니다.
    """
    
    def __init__(self, start_address: int = DEFAULT_START_ADDRESS, 
                 count: int = DEFAULT_REGISTER_COUNT, 
                 default_value: Any = DEFAULT_REGISTER_VALUE):
        """JSON 데이터 저장소 초기화
        
        Args:
            start_address: 시작 주소
            count: 초기 레지스터 개수
            default_value: 기본값
        """
        super().__init__()
        self.address = start_address
        self.default_value = default_value
        
        # 문자열 키로 저장하여 JSON 직렬화 호환성 보장
        self.values = {
            str(addr): default_value 
            for addr in range(start_address, start_address + count)
        }
    
    @classmethod
    def create(cls, count: int = DEFAULT_REGISTER_COUNT, 
               value: Any = DEFAULT_REGISTER_VALUE,
               address: int = DEFAULT_START_ADDRESS) -> 'JSONRegistersDataBlock':
        """JSON 데이터 저장소 팩토리 메서드
        
        Args:
            count: 레지스터 개수
            value: 초기값
            address: 시작 주소
            
        Returns:
            초기화된 JSONRegistersDataBlock 인스턴스
        """
        return cls(start_address=address, count=count, default_value=value)
    
    def validate(self, address: int, count: int = 1) -> bool:
        """연속된 주소 범위가 모두 존재하는지 확인"""
        try:
            start_addr = int(address)
        except (ValueError, TypeError):
            return False
        
        if count <= 0:
            return False
        
        # 연속된 범위 확인
        for addr in range(start_addr, start_addr + count):
            if str(addr) not in self.values:
                return False
        return True
    
    def getValues(self, address: int, count: int = 1) -> List[Any]:
        """지정된 주소에서 값들을 가져옵니다"""
        start_addr = int(address)
        result = []
        
        for addr in range(start_addr, start_addr + count):
            addr_str = str(addr)
            if addr_str in self.values:
                result.append(self.values[addr_str])
            else:
                result.append(self.default_value)
        
        return result
    
    def setValues(self, address: int, values: Union[Any, List[Any]]) -> None:
        """지정된 주소에 값들을 설정합니다"""
        if not isinstance(values, (list, tuple)):
            values = [values]
        
        start_addr = int(address)
        for i, value in enumerate(values):
            self.values[str(start_addr + i)] = value
    
    def add_key(self, key: Union[str, int], value: Any = None) -> None:
        """새로운 키-값 쌍을 추가합니다"""
        if value is None:
            value = self.default_value
        self.values[str(key)] = value
    
    def remove_key(self, key: Union[str, int]) -> bool:
        """키를 제거합니다"""
        key_str = str(key)
        if key_str in self.values:
            del self.values[key_str]
            return True
        return False
    
    def get_all_keys(self) -> List[str]:
        """모든 키를 반환합니다"""
        return list(self.values.keys())
    
    def to_json(self) -> Dict[str, Any]:
        """JSON 직렬화를 위한 딕셔너리 반환"""
        return {
            "address": self.address,
            "default_value": self.default_value,
            "values": self.values,
            "type": self.__class__.__name__
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'JSONRegistersDataBlock':
        """JSON 데이터로부터 인스턴스 생성"""
        start_addr = data.get("address", DEFAULT_START_ADDRESS)
        default_val = data.get("default_value", DEFAULT_REGISTER_VALUE)
        
        instance = cls(start_address=start_addr, count=0, default_value=default_val)
        
        # 값들을 문자열 키로 변환하여 저장
        values_data = data.get("values", {})
        instance.values = {str(k): v for k, v in values_data.items()}
        
        return instance
    
    def reset(self) -> None:
        """모든 값을 기본값으로 재설정"""
        for key in self.values:
            self.values[key] = self.default_value

# =============================================================================
# 하위 호환성을 위한 별칭 (Deprecated)
# =============================================================================
# 기존 코드와의 호환성을 위해 유지
RegistersSequentialDataBlock = SequentialRegistersDataBlock

# =============================================================================
# 유틸리티 함수
# =============================================================================

def create_datablock_from_config(config: Dict[str, Any]) -> BaseRegistersDataBlock:
    """설정 딕셔너리로부터 적절한 데이터 블록을 생성합니다
    
    Args:
        config: 데이터 블록 설정
            - type: "sequential" 또는 "json"
            - count: 레지스터 개수
            - value: 초기값
            - address: 시작 주소
    
    Returns:
        생성된 데이터 블록 인스턴스
    """
    block_type = config.get("type", "sequential").lower()
    count = config.get("count", DEFAULT_REGISTER_COUNT)
    value = config.get("value", DEFAULT_REGISTER_VALUE)
    address = config.get("address", DEFAULT_START_ADDRESS)
    
    if block_type == "json":
        return JSONRegistersDataBlock.create(count=count, value=value, address=address)
    else:
        return SequentialRegistersDataBlock.create(count=count, value=value, address=address)

def serialize_datablock(datablock: BaseRegistersDataBlock) -> Dict[str, Any]:
    """데이터 블록을 직렬화합니다"""
    if isinstance(datablock, JSONRegistersDataBlock):
        return datablock.to_json()
    
    # 순차적 데이터 블록의 경우
    return {
        "type": datablock.__class__.__name__,
        "address": datablock.address,
        "default_value": datablock.default_value,
        "values": datablock.values if isinstance(datablock.values, list) else []
    }

