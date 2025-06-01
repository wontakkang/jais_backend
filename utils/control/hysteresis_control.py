'''히스테리시스 제어'''
def hysteresis_control(current_value: float, set_point: float, dead_band: float) -> bool:
    """
    현재 값, 설정 값, 불감대(dead band)를 이용하여 히스테리시스 제어를 수행합니다.
    설정 값 주변의 불감대 내에서는 현재 상태를 유지하고, 벗어나면 상태를 변경합니다.

    :param current_value: 현재 측정 값 (float)
    :param set_point: 목표 설정 값 (float)
    :param dead_band: 불감대의 폭 (float)
    :return: 제어 결과 (True: ON, False: OFF) (bool)
    :rtype: bool
    """
    # 여기에 히스테리시스 제어 로직을 구현합니다.
    if current_value < set_point - dead_band:
        return True  # ON
    elif current_value > set_point + dead_band:
        return False  # OFF
    # 현재 상태 유지 (혹은 이전 상태 반환 로직 추가 필요)
    # 이 예제에서는 False를 반환하지만, 실제 구현에서는 이전 상태를 유지하도록 수정해야 할 수 있습니다.
    return False # 기본적으로 OFF 또는 이전 상태 유지
