import datetime
from typing import Any, Union

def set_time_based_control(
    start_time_str: str,
    end_time_str: str,
    control_value: Any,
    current_time_obj: Union[datetime.time, None] = None  # 테스트 용이성을 위해 현재 시간 주입 가능
) -> Any:
    """
    지정된 시간대에 따라 제어 값을 반환합니다.
    현재 시간이 시작 시간(포함)과 종료 시간(미포함) 사이면 control_value를 반환하고,
    그렇지 않으면 None을 반환합니다.

    :param start_time_str: 시작 시간 (HH:MM 형식의 문자열)
    :param end_time_str: 종료 시간 (HH:MM 형식의 문자열)
    :param control_value: 지정된 시간대에 적용될 제어 값
    :param current_time_obj: 현재 시간 (datetime.time 객체, 테스트용, 기본값: 현재 시간)
    :return: 현재 시간이 지정된 범위 내에 있으면 control_value, 그렇지 않으면 None
    :rtype: Any
    """
    try:
        start_t = datetime.datetime.strptime(start_time_str, "%H:%M").time()
        end_t = datetime.datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        print(f"오류: 잘못된 시간 형식입니다. 시작시간='{start_time_str}', 종료시간='{end_time_str}'. HH:MM 형식을 사용하세요.")
        return None

    if current_time_obj is None:
        now_t = datetime.datetime.now().time()
    else:
        now_t = current_time_obj

    # 시간대 처리
    if start_t <= end_t:
        # 일반적인 경우 (예: 08:00 ~ 17:00)
        if start_t <= now_t < end_t:
            return control_value
    else:
        # 자정을 넘어가는 경우 (예: 22:00 ~ 02:00)
        # 현재 시간이 시작 시간 이후이거나, 또는 현재 시간이 종료 시간 이전인 경우
        if now_t >= start_t or now_t < end_t:
            return control_value
            
    return None
