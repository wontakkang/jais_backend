import time
from typing import Optional

def duty_control(
    cycle_time_minutes: int,
    on_ratio: float,
    current_timestamp: Optional[float] = None
) -> bool:
    """
    전체 주기 시간 중 설정된 비율(on_ratio)만큼 ON 상태를 반환하는 Duty 제어 상태를 결정합니다.

    :param cycle_time_minutes: 전체 주기 시간 (분), 0보다 커야 함.
    :param on_ratio: ON 상태 비율 (0.0 ~ 1.0), 0.0 이상 1.0 이하.
    :param current_timestamp: 현재 Unix 타임스탬프 (테스트용, 기본값: 현재 시간)
    :return: 현재 ON 상태이면 True, OFF 상태이면 False
    :rtype: bool
    """
    if not isinstance(cycle_time_minutes, int):
        raise TypeError("cycle_time_minutes는 정수여야 합니다.")
    if not isinstance(on_ratio, (float, int)):
        raise TypeError("on_ratio는 실수 또는 정수여야 합니다.")
    
    _on_ratio = float(on_ratio)

    if cycle_time_minutes <= 0:
        raise ValueError("cycle_time_minutes는 0보다 커야 합니다.")
    if not (0.0 <= _on_ratio <= 1.0):
        raise ValueError(f"on_ratio({_on_ratio})는 0.0과 1.0 사이여야 합니다.")

    if _on_ratio == 0.0:  # 항상 OFF
        return False
    if _on_ratio == 1.0:  # 항상 ON (주어진 주기 내에서)
        return True

    _current_ts = current_timestamp if current_timestamp is not None else time.time()

    cycle_time_s = cycle_time_minutes * 60
    on_duration_s = cycle_time_s * _on_ratio
    
    time_within_cycle_s = _current_ts % cycle_time_s
    
    return time_within_cycle_s < on_duration_s
