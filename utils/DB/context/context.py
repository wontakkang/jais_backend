from .store import RegistersSequentialDataBlock, BaseRegistersDataBlock
from app.utils import setup_logger

# SQL 로거 초기화
context_logger = setup_logger(name="context_logger", log_file="./log/context_logger.log")


class Context_Exception(Exception):
    """Base Context_ exception."""

    def __init__(self, string):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        self.string = string
        super().__init__()

    def __str__(self):
        """Return string representation."""
        return f"Context_ Error: {self.string}"

    def isError(self):
        """Error"""
        return True


class NoSuchSlaveException(Context_Exception):
    """Error resulting from making a request to a slave that does not exist."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[No Such Slave] {string}"
        Context_Exception.__init__(self, message)
        

class RegistersBaseSlaveContext:
    """
    기본 슬레이브 컨텍스트 클래스

    이 클래스는 Modbus 및 LS XGT TCP 프로토콜을 위한 기본 데이터 저장소를 제공합니다.
    """
    def __init__(self, *_args, **kwargs):
        super().__init__()

    def MODBUS(self, *_args, **kwargs):
        """
        MODBUS 프로토콜을 사용할 경우 호출되는 함수
        """
        if "count" in kwargs:
            store = RegistersSequentialDataBlock().create(count=kwargs.get("count"))
        else:
            store = RegistersSequentialDataBlock().create()
        return store

    def LS_XGT_TCP(self, *_args, **kwargs):
        """
        LS XGT TCP 메모리를 초기화하고 데이터 저장소를 생성하는 함수

        :param kwargs: 메모리 크기 등 설정 값
        :returns: 생성된 데이터 저장소
        """
        store = {}
        # LSIS에서 허용하는 메모리 형식을 불러와서 각 메모리 형식별 바이트 데이터 생성
        memory = BaseRegistersDataBlock().LS_XGT_TCP_Memory
        for m in memory:
            if "count" in kwargs:
                store[m] = kwargs.get(
                    m, BaseRegistersDataBlock().create(count=kwargs.get("count"))
                )
            else:
                store[m] = kwargs.get(m, BaseRegistersDataBlock().create())
        return store

# ---------------------------------------------------------------------------#
#  Slave Contexts (슬레이브 컨텍스트)
# ---------------------------------------------------------------------------#
class RegistersSlaveContext(RegistersBaseSlaveContext):
    def __init__(self, createMemory=None, *_args, **kwargs):
        """ 
        RegistersSlaveContext 클래스의 생성자

        :param createMemory: 메모리를 생성하는 함수 (선택 사항)
        :param _args: 추가적인 인자
        :param kwargs: 키워드 인자

        클래스의 초기화 과정에서 `createMemory`가 존재하면 해당 함수를 호출하여 `store`를 생성하고,
        존재하지 않으면 빈 사전(`{}`)을 생성합니다.
        또한 `zero_mode` 플래그를 설정합니다.
        """
        super().__init__(self, createMemory=None, *_args, **kwargs)
        if hasattr(self, createMemory):
            self.store = getattr(self, createMemory)(*_args, **kwargs)
            self.zero_mode = kwargs.get("zero_mode", True)
        else:
            self.store = {}
            self.zero_mode = kwargs.get("zero_mode", False)

    def __str__(self):
        """
        문자열 표현을 반환합니다.

        :return: "Registers Slave Context" 문자열을 반환
        """
        return "Registers Slave Context"

    def reset(self):
        """
        모든 데이터 저장소를 기본값으로 재설정합니다.
        """
        for datastore in iter(self.store.values()):
            datastore.reset()

    def validate(self, memory, address, count=1):
        """
        요청이 유효한지 확인합니다.

        :param memory: 조회할 메모리 영역
        :param address: 시작 주소
        :param count: 조회할 값의 개수 (기본값: 1)
        :return: 요청이 유효한 범위 내에 있으면 True, 그렇지 않으면 False
        """
        if not self.zero_mode:
            address = address + 1
        context_logger.debug("validate: fc-[{}] address-{}: count-{}", memory, address, count)
        return self.store[memory].validate(address, count)

    def getValues(self, memory, address, count=1):
        """
        데이터 저장소에서 `count` 개수만큼 값을 가져옵니다.

        :param memory: 조회할 메모리 영역
        :param address: 시작 주소
        :param count: 조회할 값의 개수 (기본값: 1)
        :return: 지정된 주소 범위의 값 리스트를 반환
        """
        if not self.zero_mode:
            address = address + 1
        context_logger.debug("getValues: fc-[{}] address-{}: count-{}", memory, address, count)
        return self.store[memory].getValues(address, count)

    def setValues(self, memory, address, values):
        """
        데이터 저장소에 값을 설정합니다.

        :param memory: 설정할 메모리 영역
        :param address: 시작 주소
        :param values: 설정할 값의 리스트
        """
        if not self.zero_mode:
            address = address + 1
        context_logger.debug("setValues[{}] address-{}: count-{}", memory, address, len(values))
        self.store[memory].setValues(address, values)
"""
# ---------------------------------------------------------------------------#
#  클래스 사용 방법 예제
# ---------------------------------------------------------------------------#
# 1. 인스턴스 생성
context = RegistersSlaveContext(createMemory="some_memory_function", zero_mode=True)

# 2. 값 설정하기
context.setValues("holding_registers", address=10, values=[100, 200, 300])

# 3. 값 가져오기
values = context.getValues("holding_registers", address=10, count=3)
print(values)  # 예상 출력: [100, 200, 300]

# 4. 값 검증
is_valid = context.validate("holding_registers", address=10, count=3)
print(is_valid)  # 예상 출력: True (유효한 주소일 경우)

# 5. 데이터 초기화
context.reset()
"""


class RegistersServerContext:
    """이 클래스는 슬레이브 컨텍스트들의 마스터 컬렉션을 나타냅니다.

    `single` 값이 `True`이면 모든 단위 ID가 동일한 컨텍스트를 반환하는 단일 컨텍스트로 취급됩니다.
    `single` 값이 `False`이면 여러 슬레이브 컨텍스트를 포함하는 컬렉션으로 해석됩니다.
    """

    def __init__(self, slaves=None, single=True):
        """새로운 Modbus 서버 컨텍스트 인스턴스를 초기화합니다.

        :param slaves: 클라이언트 컨텍스트의 딕셔너리
        :param single: `True`로 설정하면 단일 컨텍스트로 처리됩니다.
        """
        self.single = single
        self._slaves = slaves or {}
        if self.single:
            self._slaves = {0x00: self._slaves}

    def __iter__(self):
        """현재 슬레이브 컨텍스트 컬렉션을 순회합니다.

        :returns: 슬레이브 컨텍스트에 대한 반복자
        """
        return iter(self._slaves.items())

    def __contains__(self, slave):
        """주어진 슬레이브가 목록에 포함되어 있는지 확인합니다.

        :param slave: 확인할 슬레이브
        :returns: 슬레이브가 존재하면 `True`, 그렇지 않으면 `False`
        """
        if self.single and self._slaves:
            return True
        return slave in self._slaves

    def __setitem__(self, slave, context):
        """새로운 슬레이브 컨텍스트를 설정합니다.

        :param slave: 설정할 슬레이브 컨텍스트
        :param context: 해당 슬레이브에 대한 새로운 컨텍스트
        :raises NoSuchSlaveException: 유효하지 않은 슬레이브 인덱스인 경우 예외 발생
        """
        if self.single:
            slave = 1
        if 0xF7 >= slave >= 0x00:
            self._slaves[slave] = context
        else:
            raise NoSuchSlaveException(f"슬레이브 인덱스: {slave} 범위를 벗어남")

    def __delitem__(self, slave):
        """슬레이브 컨텍스트를 제거합니다.

        :param slave: 제거할 슬레이브 컨텍스트
        :raises NoSuchSlaveException: 유효하지 않은 슬레이브 인덱스인 경우 예외 발생
        """
        if not self.single and (0xF7 >= slave >= 0x00):
            del self._slaves[slave]
        else:
            raise NoSuchSlaveException(f"슬레이브 인덱스: {slave} 범위를 벗어남")

    def __getitem__(self, slave):
        """슬레이브 컨텍스트를 가져옵니다.

        :param slave: 가져올 슬레이브 컨텍스트
        :returns: 요청된 슬레이브 컨텍스트
        :raises NoSuchSlaveException: 존재하지 않거나 범위를 벗어난 경우 예외 발생
        """
        if self.single:
            slave = 1
        if slave in self._slaves:
            return self._slaves.get(slave)
        raise NoSuchSlaveException(
            f"슬레이브 - {slave}가 존재하지 않거나 범위를 벗어났습니다."
        )

    def slaves(self):
        """슬레이브 목록을 반환합니다."""
        # Python3에서는 keys()가 반복자로 반환됩니다.
        return list(self._slaves.keys())
"""
# ---------------------------------------------------------------------------#
#  사용 예제
# ---------------------------------------------------------------------------#
# 1. 단일 컨텍스트 인스턴스 생성
single_context = RegistersServerContext(single=True)

# 2. 여러 슬레이브를 포함하는 컨텍스트 인스턴스 생성
multi_context = RegistersServerContext(slaves={1: "Slave1 Context", 2: "Slave2 Context"}, single=False)

# 3. 특정 슬레이브 컨텍스트 가져오기
context = multi_context[1]
print(context)  # 예상 출력: "Slave1 Context"

# 4. 새로운 슬레이브 컨텍스트 설정
multi_context[3] = "Slave3 Context"
print(multi_context[3])  # 예상 출력: "Slave3 Context"

# 5. 슬레이브 목록 가져오기
print(multi_context.slaves())  # 예상 출력: [1, 2, 3]

# 6. 슬레이브 삭제
del multi_context[2]
print(multi_context.slaves())  # 예상 출력: [1, 3]
"""
