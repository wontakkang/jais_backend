"""LSIS_ Utilities.

A collection of utilities for packing data, unpacking
data computing checksums, and decode checksums.
"""
# pylint: disable=missing-type-doc
import struct
import sys


class LSIS_TransactionState:  # pylint: disable=too-few-public-methods
    """LSIS_ Client States."""

    IDLE = 0
    SENDING = 1
    WAITING_FOR_REPLY = 2
    WAITING_TURNAROUND_DELAY = 3
    PROCESSING_REPLY = 4
    PROCESSING_ERROR = 5
    TRANSACTION_COMPLETE = 6
    RETRYING = 7
    NO_RESPONSE_STATE = 8

    @classmethod
    def to_string(cls, state):
        """Convert to string."""
        states = {
            LSIS_TransactionState.IDLE: "IDLE",
            LSIS_TransactionState.SENDING: "SENDING",
            LSIS_TransactionState.WAITING_FOR_REPLY: "WAITING_FOR_REPLY",
            LSIS_TransactionState.WAITING_TURNAROUND_DELAY: "WAITING_TURNAROUND_DELAY",
            LSIS_TransactionState.PROCESSING_REPLY: "PROCESSING_REPLY",
            LSIS_TransactionState.PROCESSING_ERROR: "PROCESSING_ERROR",
            LSIS_TransactionState.TRANSACTION_COMPLETE: "TRANSACTION_COMPLETE",
            LSIS_TransactionState.RETRYING: "RETRYING TRANSACTION",
        }
        return states.get(state, None)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def default(value):
    """Return the default value of object.

    :param value: The value to get the default of
    :returns: The default value
    """
    return type(value)()


def dict_property(store, index):
    """Create class properties from a dictionary.

    Basically this allows you to remove a lot of possible
    boilerplate code.

    :param store: The store store to pull from
    :param index: The index into the store to close over
    :returns: An initialized property set
    """
    if hasattr(store, "__call__"):
        getter = lambda self: store(  # pylint: disable=unnecessary-lambda-assignment
            self
        )[index]
        setter = lambda self, value: store(  # pylint: disable=unnecessary-dunder-call,unnecessary-lambda-assignment
            self
        ).__setitem__(
            index, value
        )
    elif isinstance(store, str):
        getter = lambda self: self.__getattribute__(  # pylint: disable=unnecessary-dunder-call,unnecessary-lambda-assignment
            store
        )[
            index
        ]
        setter = lambda self, value: self.__getattribute__(  # pylint: disable=unnecessary-dunder-call,unnecessary-lambda-assignment
            store
        ).__setitem__(
            index, value
        )
    else:
        getter = lambda self: store[  # pylint: disable=unnecessary-lambda-assignment
            index
        ]
        setter = lambda self, value: store.__setitem__(  # pylint: disable=unnecessary-dunder-call,unnecessary-lambda-assignment
            index, value
        )

    return property(getter, setter)


# --------------------------------------------------------------------------- #
# Bit packing functions
# --------------------------------------------------------------------------- #
def pack_bitstring(bits):
    """Create a string out of an array of bits.

    :param bits: A bit array

    example::

        bits   = [False, True, False, True]
        result = pack_bitstring(bits)
    """
    ret = b""
    i = packed = 0
    for bit in bits:
        if bit:
            packed += 128
        i += 1
        if i == 8:
            ret += struct.pack(">B", packed)
            i = packed = 0
        else:
            packed >>= 1
    if 0 < i < 8:
        packed >>= 7 - i
        ret += struct.pack(">B", packed)
    return ret


class LSIS_MappingTool:
    DATA_FORMAT = {
        'bit': '?',
        'uint8': 'B',
        'int8': 'b',
        'uint16': 'H',
        'int16': 'h',
        'uint32': 'I',
        'int32': 'i',
        'float': 'f',
    }
    ADDRESS_FORMAT = {
        '%MB': 1,
        '%MW': 2,
        '%MD': 4,
    }
    WRITE_SIZE = {
        'bit': 'B',
        'uint8': 'B',
        'int8': 'B',
        'uint16': 'H',
        'int16': 'H',
        'uint32': 'I',
        'int32': 'I',
        'float': 'I',
    }
    UNIT_SIZE = {
        'bit': '',
        'byte': '8',
        'word': '16',
        'dword': '32',
        'lword': '64',
    }
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.type = kwargs.get('data_type')
        self.unit = kwargs.get('unit')
        self.size = self.UNIT_SIZE[self.unit]
        self.format = self.DATA_FORMAT[f'{self.type}{self.size}']
        self.position = self.determine_base(args[1][3:])
        self.address = kwargs.get('device', 'M') + 'B'
        self.scale = kwargs.get('scalse', 1)
        if self.type is "float":
            self.min = kwargs.get('min', sys.float_info.min)
            self.max = kwargs.get('max', sys.float_info.max)
        if self.type is "int":
            self.min = kwargs.get('min', sys.int_info.min_int)
            self.max = kwargs.get('max', sys.int_info.max_int)
        if self.type is "bool":
            self.min = kwargs.get('min', 0)
            self.max = kwargs.get('max', 1)
            
            

    def read_scale(self, value):
        if 'int' in self.type:
            return float(value)*float(self.scale)
        elif 'float' in self.type:
            return value*float(self.scale)

    def write_scale(self, value):
        if 'int' in self.type:
            return int(float(value)/float(self.scale))
        elif 'float' in self.type:
            return value/float(self.scale)

    def minmax(self, value):
        if type(value).__name__ == 'int' or type(value).__name__ == 'float':
            if self.max == self.min == 0:
                return value
            elif self.max < self.min:
                return value
            elif value > self.max:
                if 'int' in self.type:
                    return self.max
                elif 'float' in self.type:
                    return float(self.max)
            elif value < self.min:
                if 'int' in self.type:
                    return self.min
                elif 'float' in self.type:
                    return float(self.min)
            else:
                return value

    {"address": "%MB80000", "count": 1, "format": "B", "values": 1}
    def repack_write(self, value):
        if len(self.position) > 1:
            writeFormat = {
                "address" : f"{self.address[:-1]}X{self.position[0]*8+self.position[1]}",
                "count" : 1,
                "format" : self.WRITE_SIZE[self.type],
                "values" : int(value),
            }
            return writeFormat
        elif len(self.position) == 1:
            writeFormat = {
                "address": self.args[1],
                "count": 1,
                "format": self.WRITE_SIZE[self.type],
                "values": self.write_scale(value),
            }
            return writeFormat
        else:
            return f"유효한 값이 아닙니다."

    def repack(self, data):
        if len(self.position) > 1:
            #bit 변환
            repack_data = data[self.position[0]:self.position[0]+2]
            result = self.unpack_bitslist(repack_data)[self.position[1]]
            return bool(result)
        elif len(self.position) == 1:
            #byte 이상 사이즈 변환
            repack_data = data[self.position[0]: self.position[0] + self.address_size]
            result = self.repack_byte(format=self.format, data=repack_data)
            result = self.read_scale(result)
            result = self.minmax(result)
            return result
        else:
            return f"유효한 주소가 아닙니다."

    def unpack_bitslist(self, data=list):
        """Create bit array out of a string.

        :param string: The modbus data packet to decode

        example::

            bytes  = "bytes to decode"
            result = unpack_bitstring(bytes)
        """
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> i) & 1)
        return bits

    def repack_byte(self, format=None, data=list):
        before_size = len(data)
        after_size = struct.calcsize(format)
        return struct.unpack(format, struct.pack(''.join('B' * before_size), *data))[0]

    def parse_number(self, value):
        # 문자열에서 소수점 위치 찾기
        if '.' in value:
            integer_part, fractional_part = value.split('.')
            # 정수부(byte 자리수로 변경)와 소수부 출력
            try:
                int(fractional_part)
                return [int(integer_part)*self.address_size, int(fractional_part)]
            except:
                return [int(integer_part)*self.address_size, int(fractional_part, 16)]
        else:
            # 소수점이 없으면 정수부(byte 자리수로 변경)만 출력
            return [int(value)*self.address_size]
    def determine_base(self, value):
        # 16진수 표현의 문자 집합 정의
        hex_chars = set('0123456789ABCDEFabcdef.')

        # 숫자인지 확인하고, 실수인지 판별
        try:
            # 값이 16진수 문자로만 구성되어 있는지 확인
            if all(c in hex_chars for c in value):
                return self.parse_number(value)
            else:
                # 10진수 변환 시도 (소수점 포함 가능)
                float(value)
                # 실수로 간주하여 분리
                return self.parse_number(value)
        except ValueError:
            print(f"{value}는 유효한 숫자가 아닙니다.")


    def __str__(self):
        return f"format : {self.format} address : {self.position}"

def interpretation(header, instruction):
    message = {}
    text_PLC_info = bin(header["PLC_Info"])[2:].zfill(16)
    CPU_TYPE = int(text_PLC_info[-5:], 16)
    COMPOSITION = int(text_PLC_info[-6])
    CPU_STATUS = int(text_PLC_info[-7])
    SYSTEM_STATUS = int(text_PLC_info[-12:-8], 16)
    if CPU_TYPE == 0x01:
        message["CPU TYPE"] = "XGK/I/R-CPUH"
    elif CPU_TYPE == 0x02:
        message["CPU TYPE"] = "XGK/I-CPUS"
    elif CPU_TYPE == 0x03:
        message["CPU TYPE"] = "XGK-CPUA"
    elif CPU_TYPE == 0x04:
        message["CPU TYPE"] = "XGK/I-CPUE"
    elif CPU_TYPE == 0x05:
        message["CPU TYPE"] = "XGK/I-CPUU"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGK-CPUHN"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGK-CPUSN"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGI-CPUUN"
    if COMPOSITION == 1:
        message["COMPOSITION"] = "이중화"
    else:
        message["COMPOSITION"] = "단중화"
    if CPU_STATUS == 1:
        message["CPU STATUS"] = "CPU 동작 에러"
    else:
        message["CPU STATUS"] = "CPU 동작 정상"
    if SYSTEM_STATUS == 0x01:
        message["SYSTEM STATUS"] = "RUN"
    elif SYSTEM_STATUS == 0x02:
        message["SYSTEM STATUS"] = "STOP"
    elif SYSTEM_STATUS == 0x04:
        message["SYSTEM STATUS"] = "ERROR"
    elif SYSTEM_STATUS == 0x08:
        message["SYSTEM STATUS"] = "DEBUG"
    else:
        message["SYSTEM STATUS"] = "Exception"

    text_CPU_info = hex(header["CPU_Info"])
    if text_CPU_info == '0xa0':
        message["CPU Info"] = "XGK"
    elif text_CPU_info == '0xb0':
        message["CPU Info"] = "XGB(MK)"
    elif text_CPU_info == '0xa4':
        message["CPU Info"] = "XGI"
    elif text_CPU_info == '0xb4':
        message["CPU Info"] = "XGB(IEC)"
    elif text_CPU_info == '0xa8':
        message["CPU Info"] = "XGR"
    else:
        message["CPU Info"] = "Exception"
    message["ERROR CODE"] = instruction["error_Status"]
    return message

def unpack_bitstring(string):
    """Create bit array out of a string.

    :param string: The modbus data packet to decode

    example::

        bytes  = "bytes to decode"
        result = unpack_bitstring(bytes)
    """
    byte_count = len(string)
    bits = []
    for byte in range(byte_count):
        value = int(int(string[byte]))
        for _ in range(8):
            bits.append((value & 1) == 1)
            value >>= 1
    return bits


def make_byte_string(byte_string):
    """Return byte string from a given string, python3 specific fix.

    :param byte_string:
    :return:
    """
    if isinstance(byte_string, str):
        byte_string = byte_string.encode()
    return byte_string

class LSIS_MappingTool2:
    """
    LSIS Mapping Tool.
    This class is used to map LSIS data types to Python data types.
    It also provides methods to read and write data to and from the PLC.
    It is used to convert data types and handle scaling.
    The class is initialized with the following parameters:
    
    version 무버전시와 버전시의 데이터 타입을 구분하기 위해 version을 인자로 받습니다.
    type : 데이터 타입 (bit, uint8, int8, uint16, int16, uint32, int32, float)
    address : PLC 주소 (예: %MB80000)
    scale : 스케일링 값 (예: 0.1)
    min : 최소값 (예: 0)
    max : 최대값 (예: 100)
    version : 버전 (예: 1.0.0)
    
    version >= 1.0.0일 경우, 데이터 타입을 int, uint, dint, udint, float, bool을 type로 변경합니다.
    
    """
    version = "1.0.0"
    DATA_FORMAT = {
        'bit': '?',
        'uint8': 'B',
        'int8': 'b',
        'uint16': 'H',
        'int16': 'h',
        'uint32': 'I',
        'int32': 'i',
        'float': 'f',
    }
    ADDRESS_FORMAT = {
        '%MB': 1,
        '%MW': 2,
        '%MD': 4,
    }
    WRITE_SIZE = {
        'bit': 'B',
        'uint8': 'B',
        'int8': 'B',
        'uint16': 'H',
        'int16': 'H',
        'uint32': 'I',
        'int32': 'I',
        'float': 'I',
    }
    def __init__(self, *args, version=None):
        if version is None:
            self.type = args[0]
            self.args = args
            self.format = self.DATA_FORMAT[args[0]]
            self.address = args[1][:2] + 'B'
            self.address_size = self.ADDRESS_FORMAT[args[1][:3]]
            self.position = self.determine_base(args[1][3:])
            self.scale = args[2]
            self.min = int(args[3])
            self.max = int(args[4])
        elif version >= self.version:
            self.type = args[0]
            self.args = args
            self.format = self.DATA_FORMAT[args[0]]
            self.address = args[1][:2] + 'B'
            self.address_size = self.ADDRESS_FORMAT[args[1][:3]]
            self.position = self.determine_base(args[1][3:])
            self.scale = args[2]
            self.min = int(args[3])
            self.max = int(args[4])
            
            

    def read_scale(self, value):
        if 'int' in self.type:
            return float(value)*float(self.scale)
        elif 'float' in self.type:
            return value*float(self.scale)

    def write_scale(self, value):
        if 'int' in self.type:
            return int(float(value)/float(self.scale))
        elif 'float' in self.type:
            return value/float(self.scale)

    def minmax(self, value):
        if type(value).__name__ == 'int' or type(value).__name__ == 'float':
            if self.max == self.min == 0:
                return value
            elif self.max < self.min:
                return value
            elif value > self.max:
                if 'int' in self.type:
                    return self.max
                elif 'float' in self.type:
                    return float(self.max)
            elif value < self.min:
                if 'int' in self.type:
                    return self.min
                elif 'float' in self.type:
                    return float(self.min)
            else:
                return value

    {"address": "%MB80000", "count": 1, "format": "B", "values": 1}
    def repack_write(self, value):
        if len(self.position) > 1:
            writeFormat = {
                "address" : f"{self.address[:-1]}X{self.position[0]*8+self.position[1]}",
                "count" : 1,
                "format" : self.WRITE_SIZE[self.type],
                "values" : int(value),
            }
            return writeFormat
        elif len(self.position) == 1:
            writeFormat = {
                "address": self.args[1],
                "count": 1,
                "format": self.WRITE_SIZE[self.type],
                "values": self.write_scale(value),
            }
            return writeFormat
        else:
            return f"유효한 값이 아닙니다."

    def repack(self, data):
        if len(self.position) > 1:
            #bit 변환
            repack_data = data[self.position[0]:self.position[0]+2]
            result = self.unpack_bitslist(repack_data)[self.position[1]]
            return bool(result)
        elif len(self.position) == 1:
            #byte 이상 사이즈 변환
            repack_data = data[self.position[0]: self.position[0] + self.address_size]
            result = self.repack_byte(format=self.format, data=repack_data)
            result = self.read_scale(result)
            result = self.minmax(result)
            return result
        else:
            return f"유효한 주소가 아닙니다."

    def unpack_bitslist(self, data=list):
        """Create bit array out of a string.

        :param string: The modbus data packet to decode

        example::

            bytes  = "bytes to decode"
            result = unpack_bitstring(bytes)
        """
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> i) & 1)
        return bits

    def repack_byte(self, format=None, data=list):
        before_size = len(data)
        after_size = struct.calcsize(format)
        return struct.unpack(format, struct.pack(''.join('B' * before_size), *data))[0]

    def parse_number(self, value):
        # 문자열에서 소수점 위치 찾기
        if '.' in value:
            integer_part, fractional_part = value.split('.')
            # 정수부(byte 자리수로 변경)와 소수부 출력
            try:
                int(fractional_part)
                return [int(integer_part)*self.address_size, int(fractional_part)]
            except:
                return [int(integer_part)*self.address_size, int(fractional_part, 16)]
        else:
            # 소수점이 없으면 정수부(byte 자리수로 변경)만 출력
            return [int(value)*self.address_size]
    def determine_base(self, value):
        # 16진수 표현의 문자 집합 정의
        hex_chars = set('0123456789ABCDEFabcdef.')

        # 숫자인지 확인하고, 실수인지 판별
        try:
            # 값이 16진수 문자로만 구성되어 있는지 확인
            if all(c in hex_chars for c in value):
                return self.parse_number(value)
            else:
                # 10진수 변환 시도 (소수점 포함 가능)
                float(value)
                # 실수로 간주하여 분리
                return self.parse_number(value)
        except ValueError:
            print(f"{value}는 유효한 숫자가 아닙니다.")


    def __str__(self):
        return f"format : {self.format} address : {self.position}"

def interpretation(header, instruction):
    message = {}
    text_PLC_info = bin(header["PLC_Info"])[2:].zfill(16)
    CPU_TYPE = int(text_PLC_info[-5:], 16)
    COMPOSITION = int(text_PLC_info[-6])
    CPU_STATUS = int(text_PLC_info[-7])
    SYSTEM_STATUS = int(text_PLC_info[-12:-8], 16)
    if CPU_TYPE == 0x01:
        message["CPU TYPE"] = "XGK/I/R-CPUH"
    elif CPU_TYPE == 0x02:
        message["CPU TYPE"] = "XGK/I-CPUS"
    elif CPU_TYPE == 0x03:
        message["CPU TYPE"] = "XGK-CPUA"
    elif CPU_TYPE == 0x04:
        message["CPU TYPE"] = "XGK/I-CPUE"
    elif CPU_TYPE == 0x05:
        message["CPU TYPE"] = "XGK/I-CPUU"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGK-CPUHN"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGK-CPUSN"
    elif CPU_TYPE == 0x11:
        message["CPU TYPE"] = "XGI-CPUUN"
    if COMPOSITION == 1:
        message["COMPOSITION"] = "이중화"
    else:
        message["COMPOSITION"] = "단중화"
    if CPU_STATUS == 1:
        message["CPU STATUS"] = "CPU 동작 에러"
    else:
        message["CPU STATUS"] = "CPU 동작 정상"
    if SYSTEM_STATUS == 0x01:
        message["SYSTEM STATUS"] = "RUN"
    elif SYSTEM_STATUS == 0x02:
        message["SYSTEM STATUS"] = "STOP"
    elif SYSTEM_STATUS == 0x04:
        message["SYSTEM STATUS"] = "ERROR"
    elif SYSTEM_STATUS == 0x08:
        message["SYSTEM STATUS"] = "DEBUG"
    else:
        message["SYSTEM STATUS"] = "Exception"

    text_CPU_info = hex(header["CPU_Info"])
    if text_CPU_info == '0xa0':
        message["CPU Info"] = "XGK"
    elif text_CPU_info == '0xb0':
        message["CPU Info"] = "XGB(MK)"
    elif text_CPU_info == '0xa4':
        message["CPU Info"] = "XGI"
    elif text_CPU_info == '0xb4':
        message["CPU Info"] = "XGB(IEC)"
    elif text_CPU_info == '0xa8':
        message["CPU Info"] = "XGR"
    else:
        message["CPU Info"] = "Exception"
    message["ERROR CODE"] = instruction["error_Status"]
    return message

def unpack_bitstring(string):
    """Create bit array out of a string.

    :param string: The modbus data packet to decode

    example::

        bytes  = "bytes to decode"
        result = unpack_bitstring(bytes)
    """
    byte_count = len(string)
    bits = []
    for byte in range(byte_count):
        value = int(int(string[byte]))
        for _ in range(8):
            bits.append((value & 1) == 1)
            value >>= 1
    return bits


def make_byte_string(byte_string):
    """Return byte string from a given string, python3 specific fix.

    :param byte_string:
    :return:
    """
    if isinstance(byte_string, str):
        byte_string = byte_string.encode()
    return byte_string


# --------------------------------------------------------------------------- #
# Error Detection Functions
# --------------------------------------------------------------------------- #


def __generate_crc16_table():
    """Generate a crc16 lookup table.

    .. note:: This will only be generated once
    """
    result = []
    for byte in range(256):
        crc = 0x0000
        for _ in range(8):
            if (byte ^ crc) & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            byte >>= 1
        result.append(crc)
    return result


__crc16_table = __generate_crc16_table()


def computeCRC(data):  # pylint: disable=invalid-name
    """Compute a crc16 on the passed in string.

    For modbus, this is only used on the binary serial protocols (in this
    case RTU).

    The difference between modbus's crc16 and a normal crc16
    is that modbus starts the crc value out at 0xffff.

    :param data: The data to create a crc16 of
    :returns: The calculated CRC
    """
    crc = 0xFFFF
    for data_byte in data:
        idx = __crc16_table[(crc ^ int(data_byte)) & 0xFF]
        crc = ((crc >> 8) & 0xFF) ^ idx
    swapped = ((crc << 8) & 0xFF00) | ((crc >> 8) & 0x00FF)
    return swapped


def checkCRC(data, check):  # pylint: disable=invalid-name
    """Check if the data matches the passed in CRC.

    :param data: The data to create a crc16 of
    :param check: The CRC to validate
    :returns: True if matched, False otherwise
    """
    return computeCRC(data) == check


def computeLRC(data):  # pylint: disable=invalid-name
    """Use to compute the longitudinal redundancy check against a string.

    This is only used on the serial ASCII
    modbus protocol. A full description of this implementation
    can be found in appendix B of the serial line modbus description.

    :param data: The data to apply a lrc to
    :returns: The calculated LRC

    """
    lrc = sum(int(a) for a in data) & 0xFF
    lrc = (lrc ^ 0xFF) + 1
    return lrc & 0xFF


def checkLRC(data, check):  # pylint: disable=invalid-name
    """Check if the passed in data matches the LRC.

    :param data: The data to calculate
    :param check: The LRC to validate
    :returns: True if matched, False otherwise
    """
    return computeLRC(data) == check


def rtuFrameSize(data, byte_count_pos):  # pylint: disable=invalid-name
    """Calculate the size of the frame based on the byte count.

    :param data: The buffer containing the frame.
    :param byte_count_pos: The index of the byte count in the buffer.
    :returns: The size of the frame.

    The structure of frames with a byte count field is always the
    same:

    - first, there are some header fields
    - then the byte count field
    - then as many data bytes as indicated by the byte count,
    - finally the CRC (two bytes).

    To calculate the frame size, it is therefore sufficient to extract
    the contents of the byte count field, add the position of this
    field, and finally increment the sum by three (one byte for the
    byte count field, two for the CRC).
    """
    return int(data[byte_count_pos]) + byte_count_pos + 3


def hexlify_packets(packet):
    """Return hex representation of bytestring received.

    :param packet:
    :return:
    """
    if not packet:
        return ""
    return " ".join([hex(int(x)) for x in packet])


def addressFrameSize(i):
    byteLength = 0
    if type(i) == int:
        for x in range(0, 5):
            byteLength = 2 ** x
            if (len(hex(i)) - 2) / byteLength <= 2:
                break
            print(len(hex(i)) - 2, byteLength, hex(i))
        if byteLength == 1:
            addressInfo = ["B", byteLength]
        elif byteLength == 2:
            addressInfo = ["H", byteLength]
        elif byteLength == 4:
            addressInfo = ["I", byteLength]
        elif byteLength == 8:
            addressInfo = ["Q", byteLength]
        else:
            addressInfo = ["", 0]
    elif type(i) == float:
        addressInfo = ["f", len(str(i))]
    else:
        addressInfo = ["", 0]
    return addressInfo


# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #
__all__ = [
    "pack_bitstring",
    "unpack_bitstring",
    "default",
    "computeCRC",
    "checkCRC",
    "computeLRC",
    "checkLRC",
    "rtuFrameSize",
]
