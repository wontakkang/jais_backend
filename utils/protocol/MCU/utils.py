# Utility helpers for DE-MCU protocol
# 위치: utils/protocol/MCU/utils.py
# - to_bytes: 다양한 형식(str/list/int/bytes)을 바이트로 정규화 (엔디언 지정 가능)
# - bytes_to_hex: 바이트열을 사람이 읽기 좋은 HEX 문자열로 변환

import struct
from typing import Union


def to_bytes(
    value: Union[None, bytes, bytearray, str, list, int], endian: str = ""
) -> bytes:
    """Normalize various serial-number-like inputs to bytes with optional endian specification.

    Args:
        value: Input value to convert to bytes
        endian: Endian specification (optional):
            '<' : little-endian (LSB first)
            '>' : big-endian (MSB first)
            '!' : network (same as big-endian)
            '=' : native endian (플랫폼 기본)
            '@' : native alignment 포함
            ''  : no endian conversion (default)

    Accepts:
      - None -> b''
      - bytes/bytearray -> bytes(value)
      - str: hex string with or without spaces, optionally prefixed with 0x
      - list: iterable of integers (0-255)
      - int: single byte value

    Raises TypeError/ValueError on invalid input.
    """
    # Validate endian parameter
    valid_endians = {"", "<", ">", "!", "=", "@"}
    if endian not in valid_endians:
        raise ValueError(f"잘못된 엔디언 지정: '{endian}'. 유효한 값: {valid_endians}")

    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray)):
        result = bytes(value)
    elif isinstance(value, str):
        s = value.replace(" ", "")
        if s.startswith(("0x", "0X")):
            s = s[2:]
        try:
            result = bytes.fromhex(s)
        except ValueError as e:
            raise ValueError("serial_number hex 문자열 형식이 유효하지 않습니다") from e
    elif isinstance(value, list):
        try:
            result = bytes(int(x) & 0xFF for x in value)
        except Exception as e:
            raise ValueError("serial_number 리스트의 값이 정수가 아닙니다") from e
    elif isinstance(value, int):
        result = bytes([value & 0xFF])
    else:
        raise TypeError("지원되지 않는 serial_number 형식")

    # Apply endian conversion if specified
    if endian and len(result) > 1:
        # Convert to list of integers, reverse if needed, then back to bytes
        if endian == "<":  # little-endian: reverse bytes
            result = result[::-1]
        elif endian in [">", "!"]:  # big-endian: keep as is
            pass
        elif endian in ["=", "@"]:  # native: use struct to handle properly
            # For multi-byte values, we need to know the intended data type
            # For now, treat as sequence of bytes (no conversion needed)
            pass

    return result


def bytes_to_hex(b: Union[bytes, bytearray, None]) -> str:
    """Convert bytes to spaced upper-case hex string. None or empty -> ''."""
    if not b:
        return ""
    return " ".join(f"{x:02X}" for x in bytes(b))
