'''조건부 제어 (If-Else)'''
def conditional_control(conditions: dict) -> str:
    """
    다중 센서 또는 외부 조건을 고려하여 조건부 제어를 수행합니다.

    :param conditions: 현재 조건들을 담고 있는 딕셔너리 (dict)
                       예: {"temperature": 25, "humidity": 60}
    :return: 제어 동작 결과 (str)
    :rtype: str
    """
    # 여기에 조건부 제어 로직을 구현합니다.
    # 예시: conditions = {"temperature": 25, "humidity": 60}
    if conditions.get("temperature", 0) > 30:
        return "에어컨 가동"
    elif conditions.get("humidity", 0) > 70:
        return "제습기 가동"
    else:
        return "상태 유지"
