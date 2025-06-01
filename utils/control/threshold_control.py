'''임계값 제어'''
def set_threshold_control(current_value: float, upper_threshold: float, lower_threshold: float, hysteresis: float) -> int:
    """
    상한/하한 임계값을 기준으로 현재 값의 상태를 판단합니다.
    반환값:
        1: 현재 값이 상한 임계값을 초과한 상태 (예: 냉각 필요)
        -1: 현재 값이 하한 임계값 미만인 상태 (예: 가열 필요)
        0: 현재 값이 상한과 하한 임계값 사이인 상태 (양호)

    실제 제어 동작에서 히스테리시스 적용은 이 함수의 반환값을 사용하는 호출부에서
    `hysteresis` 매개변수를 고려하여 상태 변경 로직을 구현해야 합니다.
    예를 들어, 상태가 -1이 되어 가열을 시작했다면, 가열은 current_value가
    `lower_threshold + hysteresis`를 초과할 때까지 계속될 수 있습니다.

    :param current_value: 현재 측정 값 (float)
    :param upper_threshold: 상한 임계값 (float)
    :param lower_threshold: 하한 임계값 (float)
    :param hysteresis: 히스테리시스 값 (float). 이 함수는 직접 사용하지 않으나, 호출부의 상태 로직 구현을 위해 전달됩니다.
    :return: 현재 값의 상태 (-1, 0, 또는 1) (int)
    :rtype: int
    """
    if current_value < lower_threshold:
        return -1  # 하한 임계값 미만
    elif current_value > upper_threshold:
        return 1   # 상한 임계값 초과
    else:
        return 0   # 임계값 범위 내
