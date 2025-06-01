'''센서 피드백 제어'''
def sensor_feedback_control(sensor_value: float, set_point: float, tolerance: float = 0.1) -> str:
    """
    실시간 센서 값과 설정 값, 허용 오차를 기반으로 피드백 제어를 수행합니다.

    :param sensor_value: 현재 센서 측정 값 (float)
    :param set_point: 목표 설정 값 (float)
    :param tolerance: 허용 오차 범위 (기본값: 0.1) (float)
    :return: 제어 상태 메시지 (str)
             ("증가 필요", "감소 필요", "목표 범위 내")
    :rtype: str
    """
    # 여기에 센서 피드백 제어 로직을 구현합니다.
    if sensor_value < set_point - tolerance:
        return "증가 필요"
    elif sensor_value > set_point + tolerance:
        return "감소 필요"
    else:
        return "목표 범위 내"
