'''비례제어 (Proportional Control)'''
def proportional_control(input_value: float, gain: float) -> float:
    """
    입력 값에 비례 이득(gain)을 곱하여 선형 비례 제어 출력을 계산합니다.

    :param input_value: 제어 입력 값 (float)
    :param gain: 비례 이득 (float)
    :return: 비례 제어 출력 값 (float)
    :rtype: float
    """
    # 여기에 비례제어 로직을 구현합니다.
    output = input_value * gain
    print(f"비례 제어: 입력값={input_value}, 게인={gain}, 출력={output}")
    return output
