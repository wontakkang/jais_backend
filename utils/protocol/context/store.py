from app.utils.protocol.LSIS.exceptions import NotImplementedException

# ---------------------------------------------------------------------------#
#  데이터 블록 저장소 (Datablock Storage)
# ---------------------------------------------------------------------------#
class BaseRegistersDataBlock:

    LS_XGT_TCP_Memory = ["%MB", "%RB", "%WB"]
    """LS_XGT_TCP 데이터 저장소의 기본 클래스

    파생 클래스는 다음 필드를 생성해야 합니다:
            @address 데이터 저장소의 시작 주소
            @default_value 데이터 저장소의 기본값
            @values 실제 데이터 저장소 값

    파생 클래스는 다음 메서드를 구현해야 합니다:
            validate(self, address, count=1)  # 주소 검증
            getValues(self, address, count=1)  # 값 가져오기
            setValues(self, address, values)  # 값 설정하기
    """

    def create(self, count=1000, value=0):
        """저장소를 하나의 값으로 초기화하는 함수

        :param count: 설정할 필드의 개수
        :param value: 필드에 설정할 기본값
        """
        return  [value] * count
    def reset(self):
        """데이터 저장소를 초기 기본값으로 재설정합니다."""
        return  [self.default_value] * len(self.values)

    def validate(self, address, count=1):
        """요청이 범위 내에 있는지 확인하는 함수

        :param address: 시작 주소
        :param count: 확인할 값의 개수
        :raises NotImplementedException:
        """
        raise NotImplementedException("데이터 저장소 주소 확인")

    def getValues(self, address, count=1):
        """데이터 저장소에서 요청된 값을 반환하는 함수

        :param address: 시작 주소
        :param count: 검색할 값의 개수
        :raises NotImplementedException:
        """
        raise NotImplementedException("데이터 저장소 값 검색")

    def setValues(self, address, values):
        """데이터 저장소에 요청된 값을 설정하는 함수

        :param address: 시작 주소
        :param values: 저장할 값
        :raises NotImplementedException:
        """
        raise NotImplementedException("데이터 저장소 값 저장")

    def __str__(self):
        """데이터 저장소의 문자열 표현을 반환"""
        return f"DataStore({len(self.values)}, {self.default_value})"

    def __iter__(self):
        """데이터 블록 데이터를 순회(iterate)할 수 있도록 설정"""
        if isinstance(self.values, dict):
            return iter(self.values.items())
        return enumerate(self.values, self.address)


class RegistersSequentialDataBlock(BaseRegistersDataBlock):
    """순차적 Modbus 데이터 저장소 생성 클래스"""

    def __init__(self, address, values):
        """데이터 저장소 초기화

        :param address: 데이터 저장소의 시작 주소
        :param values: 리스트 또는 딕셔너리 값
        """
        self.address = address
        if hasattr(values, "__iter__"):
            self.values = list(values)
        else:
            self.values = [values]
        self.default_value = self.values[0].__class__()

    @classmethod
    def create(cls, count=10000):
        """초기화된 데이터 저장소 생성

        주소 공간을 0x00으로 초기화함

        :returns: 초기화된 데이터 저장소
        """
        return cls(0x00, [0x00] * count)

    def validate(self, address, count=1):
        """요청이 범위 내에 있는지 확인"""
        result = self.address <= address
        result &= (self.address + len(self.values)) >= (address + count)
        return result

    def getValues(self, address, count=1):
        """데이터 저장소에서 요청된 값을 반환"""
        start = address - self.address
        return self.values[start : start + count]

    def setValues(self, address, values):
        """데이터 저장소에 요청된 값을 설정"""
        if not isinstance(values, list) and not isinstance(values, tuple):
            values = [values]
        start = address - self.address
        self.values[start : start + len(values)] = values

