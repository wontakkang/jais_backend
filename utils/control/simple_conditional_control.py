from typing import Callable, Any

def set_simple_conditional_control(condition: bool, true_action: Callable[[], Any], false_action: Callable[[], Any]) -> Any:
    """
    주어진 조건식의 결과에 따라 지정된 참 또는 거짓 동작을 수행합니다.

    :param condition: 평가될 조건식의 결과 (bool)
    :param true_action: 조건이 참일 때 실행될 함수 (Callable)
    :param false_action: 조건이 거짓일 때 실행될 함수 (Callable)
    :return: 실행된 함수의 반환 값
    :rtype: Any
    """
    if condition:
        return true_action()
    else:
        return false_action()
