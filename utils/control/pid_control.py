'''PID 제어'''
# PID 상태 저장을 위한 간단한 클래스 또는 딕셔너리 사용이 권장됩니다.
pid_state = {
    "previous_error": 0,
    "integral": 0
}

def pid_control(current_value: float, set_point: float, kp: float, ki: float, kd: float, dt: float = 1.0) -> float:
    """
    PID(Proportional-Integral-Derivative) 제어를 수행합니다.
    오차(error)를 기반으로 비례(P), 적분(I), 미분(D) 항을 계산하여 제어 출력을 결정합니다.

    :param current_value: 현재 측정 값 (float)
    :param set_point: 목표 설정 값 (float)
    :param kp: 비례 이득 (Proportional gain) (float)
    :param ki: 적분 이득 (Integral gain) (float)
    :param kd: 미분 이득 (Derivative gain) (float)
    :param dt: 시간 변화량 (델타 타임, 기본값: 1.0) (float)
    :return: PID 제어 출력 값 (float)
    :rtype: float
    """
    error = set_point - current_value
    
    # 비례항 (Proportional)
    p_term = kp * error
    
    # 적분항 (Integral)
    pid_state["integral"] += error * dt
    i_term = ki * pid_state["integral"]
    
    # 미분항 (Derivative)
    # 이전 오류가 0이고 dt가 매우 작을 경우 ZeroDivisionError를 방지하기 위해 작은 값(epsilon)을 분모에 더할 수 있습니다.
    # 또는 dt가 0인 경우를 명시적으로 처리할 수 있습니다.
    if dt == 0:
        derivative = 0.0
    else:
        derivative = (error - pid_state["previous_error"]) / dt
    d_term = kd * derivative
    
    # PID 출력
    output = p_term + i_term + d_term
    
    pid_state["previous_error"] = error
    
    print(f"PID 제어: 현재값={current_value}, 설정값={set_point}, P={p_term}, I={i_term}, D={d_term}, 출력={output}")
    return output
