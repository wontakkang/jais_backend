import time
from typing import Optional

def set_cycle_control(
    cycle_time_minutes: int,
    on_time_minutes: int,
    off_time_minutes: int,
    current_timestamp: Optional[float] = None
) -> bool: # True for ON, False for OFF
    """
    설정된 사이클 주기, ON 시간, 명시적 OFF 시간에 따라 현재 ON/OFF 상태를 반환합니다.
    한 사이클은 cycle_time_minutes로 구성됩니다.
    사이클 시작 후 on_time_minutes 동안 ON 상태입니다.
    그 후 off_time_minutes 동안 OFF 상태입니다.

    :param cycle_time_minutes: 전체 사이클 주기 (분), 0보다 커야 함.
    :param on_time_minutes: 사이클 내 켜짐 시간 (분), 0 이상.
    :param off_time_minutes: 켜짐 시간 이후의 명시적 꺼짐 시간 (분), 0 이상.
    :param current_timestamp: 현재 Unix 타임스탬프 (테스트용, 기본값: 현재 시간)
    :return: 현재 ON 상태이면 True, OFF 상태이면 False
    :rtype: bool
    """
    if not all(isinstance(arg, int) for arg in [cycle_time_minutes, on_time_minutes, off_time_minutes]):
        raise TypeError("모든 시간 매개변수는 정수여야 합니다.")

    if cycle_time_minutes <= 0:
        raise ValueError("사이클 주기는 0보다 커야 합니다.")
    if on_time_minutes < 0 or off_time_minutes < 0:
        raise ValueError("ON 시간과 OFF 시간은 음수일 수 없습니다.")
    if on_time_minutes > cycle_time_minutes:
        raise ValueError(f"ON 시간({on_time_minutes}분)은 사이클 주기({cycle_time_minutes}분)보다 클 수 없습니다.")

    # on_time_minutes + off_time_minutes 가 cycle_time_minutes 를 초과하는 경우,
    # off_time_minutes 는 cycle_time_minutes - on_time_minutes 로 제한될 수 있습니다.
    # 여기서는 off_time_minutes를 on_time_minutes 이후의 명시적 OFF 구간으로 해석합니다.
    # 이 명시적 OFF 구간이 사이클 주기를 넘어서면, 사이클 주기까지만 적용됩니다.

    _current_timestamp = current_timestamp if current_timestamp is not None else time.time()

    cycle_duration_s = cycle_time_minutes * 60
    on_duration_s = on_time_minutes * 60
    
    # on_time 이후의 명시적 off 구간. 이 구간은 cycle_time 내로 제한됨.
    # on_time이 cycle_time과 같거나 크면, explicit_off_duration_s는 0 또는 음수가 될 수 있음.
    # on_time_minutes > cycle_time_minutes는 위에서 이미 오류 처리됨.
    # 따라서 on_duration_s <= cycle_duration_s 는 보장됨.
    
    # on_time 이후, 사이클 종료까지 남은 시간
    remaining_time_after_on_s = cycle_duration_s - on_duration_s
    
    # 명시적 off 시간은 남은 시간과 off_time_minutes 중 작은 값으로 결정
    explicit_off_duration_s = min(off_time_minutes * 60, remaining_time_after_on_s)
    if explicit_off_duration_s < 0: # 혹시 모를 경우 방지 (예: 부동소수점 연산 오류 등)
        explicit_off_duration_s = 0

    time_within_cycle_s = _current_timestamp % cycle_duration_s

    if time_within_cycle_s < on_duration_s:
        return True  # ON 상태
    # on_duration_s 이후, on_duration_s + explicit_off_duration_s 이전
    elif on_duration_s <= time_within_cycle_s < on_duration_s + explicit_off_duration_s:
        return False # 명시적 OFF 상태
    else:
        # (on_duration_s + explicit_off_duration_s) 이후, cycle_duration_s 이전
        return False # 나머지 시간도 OFF 상태
