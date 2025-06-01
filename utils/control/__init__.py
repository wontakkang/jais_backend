all_list = [
    "hysteresis_control",
    "pid_control",
    "proportional_control",
    "conditional_control",
    "schedule_based_control",
    "sensor_feedback_control",
    "ai_ml_based_control",
    "set_deviation_control",
    "set_threshold_control",
    "set_simple_conditional_control",
    "set_time_based_control",
    "set_cycle_control",
    "set_on_off_timer_control",
]
all_dict = {}
__all__ = all_list

# all_dict: {함수명: 함수객체} 형태로 제공

from .hysteresis_control import hysteresis_control
from .pid_control import pid_control
from .proportional_control import proportional_control
from .conditional_control import conditional_control
from .schedule_based_control import schedule_based_control
from .sensor_feedback_control import sensor_feedback_control
from .ai_ml_based_control import ai_ml_based_control
from .deviation_control import set_deviation_control  # 추가
from .threshold_control import set_threshold_control  # 추가
from .simple_conditional_control import set_simple_conditional_control  # 추가
from .time_based_control import set_time_based_control  # 추가
from .cycle_control import set_cycle_control # 추가
from .on_off_timer_control import set_on_off_timer_control # 추가

all_dict = {
    "hysteresis_control": hysteresis_control,
    "pid_control": pid_control,
    "proportional_control": proportional_control,
    "conditional_control": conditional_control,
    "schedule_based_control": schedule_based_control,
    "sensor_feedback_control": sensor_feedback_control,
    "ai_ml_based_control": ai_ml_based_control,
    "set_deviation_control": set_deviation_control,  # 추가
    "set_threshold_control": set_threshold_control,  # 추가
    "set_simple_conditional_control": set_simple_conditional_control,  # 추가
    "set_time_based_control": set_time_based_control,  # 추가
    "set_cycle_control": set_cycle_control, # 추가
    "set_on_off_timer_control": set_on_off_timer_control, # 추가
}

__all__ = all_list
