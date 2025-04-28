from collections import namedtuple
import hashlib
from datetime import datetime, timezone
import time
import tzlocal  # 로컬 타임존 자동 감지

# 로컬 타임존 가져오기
local_tz = tzlocal.get_localzone()

def _set_password(passwd):
    return hashlib.sha256(passwd.encode("utf-8")).hexdigest()

def dict_to_object(data_dict):
    """
    딕셔너리를 객체로 변환합니다.
    """
    if data_dict is None:
        return None
    ObjectClass = namedtuple("ObjectClass", data_dict.keys())
    return ObjectClass(*data_dict.values())

def get_info_value(info_list, key):
    """
    TS.INFO 반환값(list)에서 특정 key의 값을 가져옴.
    :param info_list: TS.INFO에서 반환된 리스트
    :param key: 찾고자 하는 키 값 (예: 'rules', 'labels', 'sourceKey' 등)
    :return: 해당 키의 값, 없으면 None 반환
    """
    try:
        index = info_list.index(key) + 1  # key 다음에 위치한 값이 해당 키의 데이터
        return info_list[index]
    except ValueError:
        return None  # 키가 존재하지 않으면 None 반환


def format_timestamp_local(timestamp_ms):
    """밀리초(ms) 단위의 timestamp를 YYYY-MM-DD HH:MM:SS (로컬 타임존) 형식으로 변환"""
    dt = datetime.utcfromtimestamp(timestamp_ms / 1000)  # UTC 기준 변환
    local_dt = dt.astimezone(local_tz)  # 로컬 타임존 변환
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')