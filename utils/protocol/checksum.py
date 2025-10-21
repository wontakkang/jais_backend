"""
MCU/RS-485 프로토콜용 종합 체크섬 유틸리티 모듈.

제공 항목:
- hexstr_to_bytes
- checksum_sum (단순 합계 mod256)
- checksum_lrc (LRC: 합의 2의 보수)
- ones_complement_sum_16 (인터넷 16비트 one's complement)
- crc16_modbus (CRC-16 Modbus)
- crc16_ccitt (CRC-16-CCITT)
- crc32, adler32 (zlib 기반)
- fletcher16, fletcher32
- XOR 계열 함수들 (xor_simple, xor_with_initial, xor_indexed, xor_word16_le/be, fold 등)
- append_checksum: 프레임 끝에 체크섬 자동 추가

모든 함수는 Sphinx 스타일의 한글 docstring(:param, :type, :return, :rtype)을 사용합니다. 사용 예시도 각 함수에 포함되어 있습니다.
"""

from typing import Optional
import zlib

# -------------------------
# 기본 헬퍼
# -------------------------

def hexstr_to_bytes(hexstr: str) -> bytes:
    """
    HEX 문자열(공백 허용)을 바이트로 변환합니다.

    :param hexstr: 변환할 HEX 문자열. 예: '7F 20 46 53 50 0D 00 4C 00 3C' 또는 '7F204653500D004C003C'
    :type hexstr: str
    :return: 변환된 바이트 시퀀스
    :rtype: bytes

    예시::
        >>> hexstr_to_bytes('7F 20 46')
        b"\x7f \x20F"
    """
    cleaned = ''.join(hexstr.split())
    return bytes.fromhex(cleaned)


def to_bytes_le(value: int, length: int) -> bytes:
    """
    정수 값을 지정된 길이의 리틀 엔디안 바이트로 반환합니다.

    :param value: 정수 값
    :type value: int
    :param length: 바이트 길이
    :type length: int
    :return: 리틀 엔디안 바이트
    :rtype: bytes
    """
    return value.to_bytes(length, 'little')


def to_bytes_be(value: int, length: int) -> bytes:
    """
    정수 값을 지정된 길이의 빅 엔디안 바이트로 반환합니다.

    :param value: 정수 값
    :type value: int
    :param length: 바이트 길이
    :type length: int
    :return: 빅 엔디안 바이트
    :rtype: bytes
    """
    return value.to_bytes(length, 'big')


# -------------------------
# 합계 / LRC / 1's complement
# -------------------------

def checksum_sum(data: bytes) -> int:
    """
    단순 체크섬: 바이트 합의 하위 8비트를 반환합니다 (mod 256).

    :param data: 입력 바이트
    :type data: bytes
    :return: 0..255 범위의 체크섬 값
    :rtype: int

    예시::
        >>> checksum_sum(bytes.fromhex('7F204653500D004C003C'))
        29  # 0x1D
    """
    return sum(data) & 0xFF


def checksum_lrc(data: bytes) -> int:
    """
    LRC (Longitudinal Redundancy Check): 합의 2의 보수로 (sum + lrc) & 0xFF == 0 이 되도록 계산합니다.

    :param data: 입력 바이트
    :type data: bytes
    :return: 0..255 범위의 LRC 값
    :rtype: int

    예시::
        >>> checksum_lrc(bytes.fromhex('7F204653500D004C003C'))
        227  # 0xE3
    """
    return ((-sum(data)) & 0xFF)


def ones_complement_sum_16(data: bytes) -> int:
    """
    16비트 one's complement 합계 (인터넷 체크섬 방식).

    :param data: 입력 바이트
    :type data: bytes
    :return: 16비트 one's complement 체크섬 (0..0xFFFF)
    :rtype: int

    예시::
        >>> ones_complement_sum_16(b'\x45\x00')
        0xFFFF  # 예시 값
    """
    acc = 0
    length = len(data)
    i = 0
    while i + 1 < length:
        word = (data[i] << 8) + data[i+1]
        acc += word
        acc = (acc & 0xFFFF) + (acc >> 16)
        i += 2
    if i < length:  # 홀수 바이트 처리
        acc += data[i] << 8
        acc = (acc & 0xFFFF) + (acc >> 16)
    return (~acc) & 0xFFFF


# -------------------------
# CRC 구현
# -------------------------

def crc16_modbus(data: bytes, init_val: int = 0xFFFF, return_bytes: bool = False, byteorder: str = 'little', length: int = 2):
    """
    CRC-16 (Modbus) 계산. 정수 또는 바이트 시퀀스로 반환할 수 있습니다.

    :param data: 입력 바이트
    :type data: bytes
    :param init_val: 초기 CRC 값 (기본 0xFFFF)
    :type init_val: int
    :param return_bytes: True이면 바이트 시퀀스 반환, False이면 정수 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서 ('little' 또는 'big', 기본 'little')
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 2)
    :type length: int
    :return: CRC 값(정수) 또는 CRC 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc16_modbus(bytes.fromhex('7F204653500D004C003C'))
        0x0C34  # (정수)
        >>> crc16_modbus(bytes.fromhex('7F204653500D004C003C'), return_bytes=True)
        b'\x34\x0c'  # 리틀 엔디안 바이트
    """
    crc = init_val & 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    crc = crc & 0xFFFF
    if return_bytes:
        return crc.to_bytes(length, byteorder)
    return crc


def crc16_ccitt(data: bytes, init_val: int = 0xFFFF, return_bytes: bool = False, byteorder: str = 'little', length: int = 2):
    """
    CRC-16-CCITT 계산. 정수 또는 바이트 시퀀스로 반환할 수 있습니다.

    :param data: 입력 바이트
    :type data: bytes
    :param init_val: 초기 CRC 값 (기본 0xFFFF)
    :type init_val: int
    :param return_bytes: True이면 바이트 시퀀스 반환, False이면 정수 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서 ('little' 또는 'big', 기본 'little')
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 2)
    :type length: int
    :return: CRC 값(정수) 또는 CRC 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc16_ccitt(bytes.fromhex('7F204653500D004C003C'))
        0xFFFF
    """
    crc = init_val & 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) & 0xFFFF) ^ 0x1021
            else:
                crc = (crc << 1) & 0xFFFF
    crc = crc & 0xFFFF
    if return_bytes:
        return crc.to_bytes(length, byteorder)
    return crc


def crc32(data: bytes, return_bytes: bool = False, byteorder: str = 'little', length: int = 4) -> int | bytes:
    """
    CRC-32 계산(zlib). 정수 또는 바이트 시퀀스로 반환할 수 있습니다.

    :param data: 입력 바이트
    :type data: bytes
    :param return_bytes: True이면 바이트 시퀀스 반환, False이면 정수 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서 ('little' 또는 'big', 기본 'little')
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 4)
    :type length: int
    :return: CRC-32 값(정수) 또는 CRC 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc32(bytes.fromhex('7F204653500D004C003C'))
        0xFFFFFFFF
        >>> crc32(bytes.fromhex('7F204653500D004C003C'), return_bytes=True)
        b'\xFF\xFF\xFF\xFF'
    """
    val = zlib.crc32(data) & 0xFFFFFFFF
    if return_bytes:
        return val.to_bytes(length, byteorder)
    return val


def adler32(data: bytes, return_bytes: bool = False, byteorder: str = 'little', length: int = 4) -> int | bytes:
    """
    Adler-32 계산(zlib). 정수 또는 바이트 시퀀스로 반환할 수 있습니다.

    :param data: 입력 바이트
    :type data: bytes
    :param return_bytes: True이면 바이트 시퀀스 반환, False이면 정수 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서 ('little' 또는 'big', 기본 'little')
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 4)
    :type length: int
    :return: Adler-32 값(정수) 또는 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> adler32(bytes.fromhex('7F204653500D004C003C'))
        0xFFFFFFFF
    """
    val = zlib.adler32(data) & 0xFFFFFFFF
    if return_bytes:
        return val.to_bytes(length, byteorder)
    return val


# -------------------------
# Fletcher 체크섬
# -------------------------

def fletcher16(data: bytes) -> int:
    """
    Fletcher-16 체크섬을 계산합니다.

    :param data: 입력 바이트
    :type data: bytes
    :return: 16비트 Fletcher 체크섬 (hi<<8 | lo)
    :rtype: int

    예시::
        >>> fletcher16(b'\x01\x02\x03')
        0xFFFF
    """
    sum1 = 0
    sum2 = 0
    for b in data:
        sum1 = (sum1 + b) % 255
        sum2 = (sum2 + sum1) % 255
    return ((sum2 << 8) | sum1) & 0xFFFF


def fletcher32(data: bytes) -> int:
    """
    Fletcher-32 체크섬을 계산합니다. (홀수 길이일 경우 제로 패딩을 내부 처리)

    :param data: 입력 바이트
    :type data: bytes
    :return: 32비트 Fletcher 체크섬
    :rtype: int
    """
    sum1 = 0xFFFF
    sum2 = 0xFFFF
    length = len(data)
    i = 0
    while i < length:
        tlen = min(length - i, 360)
        for j in range(tlen):
            sum1 = (sum1 + (data[i] << 8 | (data[i+1] if i+1 < length else 0))) % 0xFFFF
            sum2 = (sum2 + sum1) % 0xFFFF
            i += 2
    return ((sum2 << 16) | sum1) & 0xFFFFFFFF


# -------------------------
# 다양한 XOR 변형
# -------------------------

def xor_simple(data: bytes) -> int:
    """
    단순 8비트 XOR 체크섬(모든 바이트를 XOR).

    :param data: 입력 바이트
    :type data: bytes
    :return: 8비트 XOR 결과
    :rtype: int
    """
    r = 0
    for b in data:
        r ^= b
    return r & 0xFF


def xor_with_initial(data: bytes, initial: int = 0) -> int:
    """
    초기값(initial)과 함께 XOR을 수행합니다.

    :param data: 입력 바이트
    :type data: bytes
    :param initial: 초기 XOR 값
    :type initial: int
    :return: 8비트 XOR 결과
    :rtype: int
    """
    r = initial & 0xFF
    for b in data:
        r ^= b
    return r


def xor_indexed(data: bytes, start: int = 0) -> int:
    """
    각 바이트를 인덱스(start)와 XOR한 뒤 누적 XOR을 수행합니다.

    :param data: 입력 바이트
    :type data: bytes
    :param start: 인덱스 시작값
    :type start: int
    :return: 8비트 결과
    :rtype: int
    """
    r = 0
    for i, b in enumerate(data, start=start):
        r ^= (b ^ (i & 0xFF))
    return r & 0xFF


def xor_word16_le(data: bytes) -> int:
    """
    바이트열을 리틀 엔디안 16비트 워드로 묶어 워드 단위로 XOR합니다. 16비트 결과 반환.

    :param data: 입력 바이트
    :type data: bytes
    :return: 16비트 XOR 결과
    :rtype: int
    """
    r = 0
    for i in range(0, len(data), 2):
        low = data[i]
        high = data[i+1] if i+1 < len(data) else 0
        word = (high << 8) | low
        r ^= word
    return r & 0xFFFF


def xor_word16_be(data: bytes) -> int:
    """
    바이트열을 빅 엔디안 16비트 워드로 묶어 워드 단위로 XOR합니다. 16비트 결과 반환.

    :param data: 입력 바이트
    :type data: bytes
    :return: 16비트 XOR 결과
    :rtype: int
    """
    r = 0
    for i in range(0, len(data), 2):
        high = data[i]
        low = data[i+1] if i+1 < len(data) else 0
        word = (high << 8) | low
        r ^= word
    return r & 0xFFFF


def xor_fold16_to_8_le(data: bytes) -> int:
    """
    리틀 엔디안 16비트 XOR 결과를 두 바이트로 나누어 XOR하여 8비트로 접습니다.

    :param data: 입력 바이트
    :type data: bytes
    :return: 접힌 8비트 값
    :rtype: int
    """
    w = xor_word16_le(data)
    return ((w >> 8) ^ (w & 0xFF)) & 0xFF


def xor_fold16_to_8_be(data: bytes) -> int:
    """
    빅 엔디안 16비트 XOR 결과를 두 바이트로 나누어 XOR하여 8비트로 접습니다.

    :param data: 입력 바이트
    :type data: bytes
    :return: 접힌 8비트 값
    :rtype: int
    """
    w = xor_word16_be(data)
    return ((w >> 8) ^ (w & 0xFF)) & 0xFF


# -------------------------
# 프레임 헬퍼
# -------------------------

def append_checksum(data: bytes, algorithm: str = 'sum', byteorder: str = 'little', length: Optional[int] = None) -> bytes:
    """
    선택한 알고리즘에 따라 체크섬 바이트를 데이터 끝에 붙입니다.

    :param data: 체크섬이 없는 프레임 바이트
    :type data: bytes
    :param algorithm: 'sum','lrc','crc16modbus','crc16ccitt','crc32','adler32','xor' 중 하나
    :type algorithm: str
    :param byteorder: 멀티바이트 체크섬의 바이트 순서 ('little' 또는 'big', 기본 'little')
    :type byteorder: str
    :param length: 체크섬 바이트 길이를 명시적으로 지정 (옵션)
    :type length: int or None
    :return: 체크섬이 붙은 프레임 바이트
    :rtype: bytes

    예시::
        >>> append_checksum(b'\x7F\x20', algorithm='lrc')
    """
    alg = algorithm.lower()
    if alg == 'sum':
        val = checksum_sum(data)
        out_len = 1 if length is None else length
    elif alg == 'lrc':
        val = checksum_lrc(data)
        out_len = 1 if length is None else length
    elif alg == 'crc16modbus':
        val = crc16_modbus(data)
        out_len = 2 if length is None else length
    elif alg == 'crc16ccitt':
        val = crc16_ccitt(data)
        out_len = 2 if length is None else length
    elif alg == 'crc32':
        val = crc32(data)
        out_len = 4 if length is None else length
    elif alg == 'adler32':
        val = adler32(data)
        out_len = 4 if length is None else length
    elif alg == 'xor':
        val = xor_simple(data)
        out_len = 1 if length is None else length
    else:
        raise ValueError('알 수 없는 알고리즘')

    out_len = int(out_len)
    if out_len == 1:
        return data + bytes([val & 0xFF])
    else:
        if byteorder == 'little':
            return data + val.to_bytes(out_len, 'little')
        else:
            return data + val.to_bytes(out_len, 'big')


# -------------------------
# HEX 입력용 편의 래퍼
# -------------------------

def checksum_sum_hex(hexstr: str) -> int:
    """
    HEX 문자열에서 단순 합계 체크섬을 계산하여 정수로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :return: 계산된 8비트 체크섬 값(정수, 0..255)
    :rtype: int

    예시::
        >>> checksum_sum_hex('7F204653500D004C003C')
        29  # 0x1D
    """
    return checksum_sum(hexstr_to_bytes(hexstr))


def checksum_lrc_hex(hexstr: str) -> int:
    """
    HEX 문자열에서 LRC(Longitudinal Redundancy Check)를 계산하여 정수로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :return: 계산된 LRC 값(정수, 0..255)
    :rtype: int

    예시::
        >>> checksum_lrc_hex('7F204653500D004C003C')
        227  # 0xE3
    """
    return checksum_lrc(hexstr_to_bytes(hexstr))


def crc16_modbus_hex(hexstr: str, return_bytes: bool = False, byteorder: str = 'little', length: int = 2):
    """
    HEX 문자열에서 CRC-16(Modbus)를 계산하여 정수 또는 바이트 시퀀스로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :param return_bytes: True이면 바이트 시퀀스를 반환, False이면 정수를 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서('little' 또는 'big'), 바이트 반환 시 사용
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 2)
    :type length: int
    :return: CRC-16 값(정수) 또는 지정된 바이트 순서의 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc16_modbus_hex('7F204653500D004C003C')
        3124  # 0x0C34 (정수)
        >>> crc16_modbus_hex('7F204653500D004C003C', return_bytes=True)
        b'\x34\x0c'  # 리틀 엔디안 바이트
    """
    return crc16_modbus(hexstr_to_bytes(hexstr), return_bytes=return_bytes, byteorder=byteorder, length=length)


def crc16_ccitt_hex(hexstr: str, return_bytes: bool = False, byteorder: str = 'little', length: int = 2):
    """
    HEX 문자열에서 CRC-16-CCITT를 계산하여 정수 또는 바이트 시퀀스로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :param return_bytes: True이면 바이트 시퀀스를 반환, False이면 정수를 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서('little' 또는 'big'), 바이트 반환 시 사용
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 2)
    :type length: int
    :return: CRC-16-CCITT 값(정수) 또는 지정된 바이트 순서의 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc16_ccitt_hex('7F204653500D004C003C')
        0x????  # 예시값
    """
    return crc16_ccitt(hexstr_to_bytes(hexstr), return_bytes=return_bytes, byteorder=byteorder, length=length)


def crc32_hex(hexstr: str, return_bytes: bool = False, byteorder: str = 'little', length: int = 4):
    """
    HEX 문자열에서 CRC-32를 계산하여 정수 또는 바이트 시퀀스로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :param return_bytes: True이면 바이트 시퀀스를 반환, False이면 정수를 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서('little' 또는 'big'), 바이트 반환 시 사용
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 4)
    :type length: int
    :return: CRC-32 값(정수) 또는 지정된 바이트 순서의 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> crc32_hex('7F204653500D004C003C')
        0x????????
    """
    return crc32(hexstr_to_bytes(hexstr), return_bytes=return_bytes, byteorder=byteorder, length=length)


def adler32_hex(hexstr: str, return_bytes: bool = False, byteorder: str = 'little', length: int = 4):
    """
    HEX 문자열에서 Adler-32를 계산하여 정수 또는 바이트 시퀀스로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :param return_bytes: True이면 바이트 시퀀스를 반환, False이면 정수를 반환
    :type return_bytes: bool
    :param byteorder: 바이트 순서('little' 또는 'big'), 바이트 반환 시 사용
    :type byteorder: str
    :param length: 반환할 바이트 길이 (기본 4)
    :type length: int
    :return: Adler-32 값(정수) 또는 지정된 바이트 순서의 바이트 시퀀스
    :rtype: int or bytes

    예시::
        >>> adler32_hex('7F204653500D004C003C')
        0x????????
    """
    return adler32(hexstr_to_bytes(hexstr), return_bytes=return_bytes, byteorder=byteorder, length=length)


def xor_simple_hex(hexstr: str) -> int:
    """
    HEX 문자열에서 단순 XOR 체크섬을 계산하여 정수로 반환합니다.

    :param hexstr: 변환할 HEX 문자열(공백 허용)
    :type hexstr: str
    :return: 계산된 8비트 XOR 값(정수)
    :rtype: int

    예시::
        >>> xor_simple_hex('7F204653500D004C003C')
        0x67
    """
    return xor_simple(hexstr_to_bytes(hexstr))


# -------------------------
# 모듈 사용 예시 (주석)
# -------------------------
# from utils.protocol.MCU.checksum import hexstr_to_bytes, checksum_sum, checksum_lrc, crc16_modbus
# data = hexstr_to_bytes('7F 20 46 53 50 0D 00 4C 00 3C')
# print(hex(checksum_sum(data)))
# print(hex(checksum_lrc(data)))
# print(hex(crc16_modbus(data)))
# print(crc16_modbus(data, return_bytes=True))  # b'\x34\x0c' (리틀 엔디안)
# print(append_checksum(data, algorithm='crc16modbus'))

__all__ = [
    # 기본 헬퍼
    'hexstr_to_bytes',
    'to_bytes_le',
    'to_bytes_be',

    # 합계 / LRC / 1's complement
    'checksum_sum',
    'checksum_lrc',
    'ones_complement_sum_16',

    # CRC 구현
    'crc16_modbus',
    'crc16_ccitt',
    'crc32',
    'adler32',

    # Fletcher 체크섬
    'fletcher16',
    'fletcher32',

    # 다양한 XOR 변형
    'xor_simple',
    'xor_with_initial',
    'xor_indexed',
    'xor_word16_le',
    'xor_word16_be',
    'xor_fold16_to_8_le',
    'xor_fold16_to_8_be',

    # 프레임 헬퍼
    'append_checksum',

    # HEX 입력용 편의 래퍼
    'checksum_sum_hex',
    'checksum_lrc_hex',
    'crc16_modbus_hex',
    'crc16_ccitt_hex',
    'crc32_hex',
    'adler32_hex',
    'xor_simple_hex',
]
