import time
from typing import Optional

def set_on_off_timer_control(
    on_time_minutes: int,
    off_time_minutes: int,
    repeat: bool,
    current_timestamp: Optional[float] = None,
    sequence_start_timestamp: Optional[float] = None # Only used if repeat is False
) -> bool: # True for ON, False for OFF
    """
    지정된 ON 시간, OFF 시간에 따라 현재 ON/OFF 상태를 반환합니다.
    반복 모드 또는 단일 시퀀스 모드를 지원합니다.

    :param on_time_minutes: 켜짐 시간 (분), 0 이상.
    :param off_time_minutes: 꺼짐 시간 (분), 0 이상.
    :param repeat: 반복 여부 (bool)
    :param current_timestamp: 현재 Unix 타임스탬프 (테스트용, 기본값: 현재 시간).
    :param sequence_start_timestamp: 단일 시퀀스 모드 (repeat=False)일 때의 시퀀스 시작 타임스탬프.
                                     이 값이 없으면 단일 시퀀스 모드는 항상 OFF를 반환합니다.
    :return: 현재 ON 상태이면 True, OFF 상태이면 False.
    :rtype: bool
    """
    if not isinstance(on_time_minutes, int) or not isinstance(off_time_minutes, int):
        raise TypeError("ON/OFF 시간 매개변수는 정수여야 합니다.")
    if on_time_minutes < 0 or off_time_minutes < 0:
        raise ValueError("ON/OFF 시간은 음수일 수 없습니다.")

    _current_ts = current_timestamp if current_timestamp is not None else time.time()
    on_duration_s = on_time_minutes * 60
    off_duration_s = off_time_minutes * 60

    if repeat:
        if on_time_minutes == 0:
            return False # ON 시간이 0이면 반복 주기 내내 OFF
        
        # ON 시간이 양수이고 OFF 시간이 0이면 반복 주기 내내 ON
        if off_time_minutes == 0:
            return True 

        # 둘 다 양수일 때 일반적인 사이클 로직
        total_cycle_s = on_duration_s + off_duration_s
        # total_cycle_s는 여기서 항상 0보다 큽니다 (on_time_minutes > 0, off_time_minutes > 0 가정).
        # 만약 on_time_minutes > 0 이고 off_time_minutes = 0 이면 위에서 True 반환됨.
        # 만약 on_time_minutes = 0 이면 위에서 False 반환됨.
        # 따라서 이 시점에서 total_cycle_s는 on_duration_s + off_duration_s > 0 입니다.

        time_within_cycle_s = _current_ts % total_cycle_s
        if time_within_cycle_s < on_duration_s:
            return True  # ON 상태
        else:
            return False # OFF 상태
    else: # 단일 시퀀스 (repeat=False)
        if sequence_start_timestamp is None:
            return False # 시작 시간이 없으면 단일 시퀀스는 상태를 알 수 없거나 완료된 것으로 간주

        elapsed_s = _current_ts - sequence_start_timestamp

        if 0 <= elapsed_s < on_duration_s:
            return True  # 시퀀스의 ON 구간
        elif on_duration_s <= elapsed_s < on_duration_s + off_duration_s:
            return False # 시퀀스의 OFF 구간
        else:
            return False # 시퀀스 완료, 계속 OFF
