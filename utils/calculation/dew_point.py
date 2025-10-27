import math

def dew_point(temp_c: float, rh_percent: float) -> float:
    """
    이슬점 온도를 Magnus 공식을 이용하여 섭씨로 계산합니다.
    :param temp_c: 섭씨 온도 (float 또는 int)
    :param rh_percent: 상대 습도 (퍼센트, float 또는 int)
    :return: 섭씨로 된 이슬점 온도 (float)
    :rtype: float
    """
    if rh_percent <= 0 or rh_percent > 100:
        rh_percent = 0.1  # 상대 습도가 0 이하이거나 100을 초과하면 0.1로 설정
    a = 17.62
    b = 243.12
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh_percent / 100.0)
    td = (b * gamma) / (a - gamma)
    _value= float("{:.1f}".format(round(td, 1)))
    return _value

def condensation_risk(surface_temp_c: float, air_temp_c: float, rh_percent: float) -> dict:
    """
    표면 온도, 공기 온도, 상대 습도를 기반으로 결로 위험도를 계산합니다.
    :param surface_temp_c: 표면 온도 (°C, float 또는 int)
    :param air_temp_c: 공기 온도 (°C, float 또는 int)
    :param rh_percent: 상대 습도 (%, float 또는 int)
    :return: 이슬점 온도, 온도 차 (ΔT), 위험 등급, 위험 레벨을 포함하는 딕셔너리
    :rtype: dict
    """
    td = dew_point(air_temp_c, rh_percent)
    delta_t = surface_temp_c - td

    # 등급 산정
    if delta_t >= 3:
        risk = "좋음"
        level = 1
    elif 1 <= delta_t < 3:
        risk = "보통"
        level = 2
    elif 0 <= delta_t < 1:
        risk = "나쁨"
        level = 3
    else:  # delta_t < 0
        risk = "매우나쁨"
        level = 4

    return {
        "이슬점(°C)": round(td, 2),
        "ΔT(°C)": round(delta_t, 2),
        "결로위험등급": risk,
        "위험레벨": level
    }
"""
# 결로 위험도 예측 함수
result = condensation_risk(표면온도, 실내온도, 실내습도)
print(result)
# {'이슬점(°C)': 15.78, 'ΔT(°C)': 6.22, '결로위험등급': '좋음', '위험레벨': 1}
# 예시
실외온도 = 10.0      # °C
실외습도 = 80.0      # %
표면온도 = 8.0       # °C

result_환기 = condensation_risk(표면온도, 실외온도, 실외습도)
print(result_환기)
# 출력: {'이슬점(°C)': 6.72, 'ΔT(°C)': 1.28, '결로위험등급': '보통', '위험레벨': 2}

기준:

표면온도 - 이슬점온도 = ΔT (온도 차)

ΔT가 작을수록 결로 위험도가 커짐

ΔT(°C) = 표면온도 - 이슬점온도	등급	설명
ΔT ≥ 3	좋음	결로 위험 매우 낮음
1 ≤ ΔT < 3	보통	결로 위험이 낮지만 주의 필요
0 ≤ ΔT < 1	나쁨	결로 발생 위험 높음
ΔT < 0	매우나쁨	이미 결로 발생 중(표면이 이슬점 이하)
1. 실내 결로 예측
필요 센서:

실내 온도 센서

실내 습도 센서

표면 온도 센서 (벽, 유리 등)

예측 방식:

실내 온도, 습도로 이슬점 온도 계산

표면 온도 ≤ 이슬점 온도 → 결로 위험 판단

2. 환기 시 결로 위험도 예측
필요 센서:

실외 온도 센서

실외 습도 센서

(+ 기존의 실내 표면 온도 센서)

예측 방식:

환기 시 실내 공기가 실외 공기 조건을 따라간다고 가정

실외 온도, 습도로 새로운 이슬점 온도 계산

표면 온도 ≤ (환기 후 이슬점 온도) → 환기 후 결로 위험 예측

"""

calculation_methods = {
    "dew_point": dew_point,
    "condensation_risk": condensation_risk,
}