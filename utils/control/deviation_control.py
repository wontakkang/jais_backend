'''편차 제어'''

def set_deviation_control(current_value: float, target_value: float, allowed_deviation: float) -> bool:
    """
    목표값과 현재값의 편차에 따라 제어 동작 필요 여부를 판단합니다.
    현재값이 (목표값 ± 허용편차) 범위를 벗어날 경우 True를 반환합니다.

    :param current_value: 현재 측정 값 (float)
    :param target_value: 목표 설정 값 (float)
    :param allowed_deviation: 허용 편차 범위 (float)
    :return: 제어 동작이 필요한 경우 True, 그렇지 않으면 False (bool)
    :rtype: bool
    """
    lower_bound = target_value - allowed_deviation
    upper_bound = target_value + allowed_deviation

    if current_value < lower_bound or current_value > upper_bound:
        return True  # 편차 범위를 벗어남 -> 제어 동작 필요
    else:
        return False # 편차 범위 내 -> 제어 동작 불필요
