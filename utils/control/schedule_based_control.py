'''스케줄 기반 제어'''
import datetime

def schedule_based_control(schedule: dict) -> str:
    """
    지정된 시간표(schedule)에 따라 제어를 수행합니다. (RTC 기반)

    :param schedule: 시간과 해당 시간에 수행할 작업을 정의한 딕셔너리 (dict)
                     예: {"08:00": "조명 ON", "18:00": "조명 OFF"}
    :return: 현재 시간에 해당하는 작업 또는 스케줄이 없는 경우 메시지 (str)
    :rtype: str
    """
    # 여기에 스케줄 기반 제어 로직을 구현합니다.
    # 예시: schedule = {"08:00": "조명 ON", "18:00": "조명 OFF"}
    now = datetime.datetime.now().strftime("%H:%M")
    if now in schedule:
        return schedule[now]
    return "현재 스케줄 없음"
