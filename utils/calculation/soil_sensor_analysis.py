"""
📌 스마트팜 토양 분석 지표 계산 코드
---------------------------------------------------
이 코드는 METER Group의 TEROS 12 / 21 / 32 센서를 포함하여,
아래 조건을 만족하는 모든 토양 센서 시스템에 적용 가능합니다.

✅ 적용 가능한 센서 조건:
- 함수율(VWC, % 또는 m³/m³) 제공
- 전기전도도(EC_bulk, mS/cm) 제공
- 수분장력(Soil Water Potential, kPa) 제공

✅ 주요 분석 항목:
1. 공극수 전기전도도 (ECp)
2. 가용 수분량 (AWC)
3. 수분 스트레스 지수 (SWSI)
4. 누적 수분 스트레스 시간 비율

⚠️ 주의:
- 함수율은 반드시 부피 기준이어야 함 (중량 함수율이면 환산 필요)
- 센서에 따라 ECp 계산식의 x 보정 계수(1.3~2.0)를 조정해야 함
- 수분장력 미제공 시 SWSI 및 스트레스 비율 계산은 제외
"""

# -------------------------
# ▶ 계산 함수 정의
# -------------------------

def calculate_ECp(EC_bulk: float, vwc: float, x: float = 1.6) -> float:
    """
    공극수 전기전도도 ECp 계산 (mS/cm)
    :param EC_bulk: 벌크 전기전도도 (mS/cm, float 또는 int)
    :param vwc: 함수율 (m³/m³, float 또는 int)
    :param x: 보정 계수[Option] (1.3~2.0, float, 센서에 따라 조정)
    :return: 공극수 전기전도도 (mS/cm, float)
    :rtype: float
    """
    return EC_bulk / (vwc ** x) if vwc > 0 else 0

def calculate_AWC(vwc: float, wilting_point: float = 0.10) -> float:
    """
    가용 수분량 계산 (m³/m³ 기준). 일반적으로 wilting_point는 10%
    :param vwc: 함수율 (m³/m³, float 또는 int)
    :param wilting_point: 시들기 시작하는 함수율[Option] (m³/m³, float 또는 int)
    :return: 가용 수분량 (m³/m³, float)
    :rtype: float
    """
    return max(0, vwc - wilting_point)

def calculate_SWSI(psi_kpa: float, field_capacity: float = -33, wilting_point: float = -1500) -> float:
    """
    수분 스트레스 지수 (0=양호 ~ 1=시듦)
    :param psi_kpa: 수분장력 (kPa, float 또는 int)
    :param field_capacity: 필드 용적 (kPa) [Option] (기본값: -33 kPa, float 또는 int)
    :param wilting_point: 시들기 시작하는 수분장력 (kPa) [Option] (기본값: -1500 kPa, float 또는 int)
    :return: 수분 스트레스 지수 (0~1, float)
    :rtype: float
    """
    if psi_kpa > field_capacity:
        return (psi_kpa - field_capacity) / (wilting_point - field_capacity)
    return 0

def calculate_stress_time_ratio(psi_kpa_list: list, threshold_kpa: float = 100) -> float:
    """
    누적 수분 스트레스 시간 비율 계산 (%)
    :param psi_kpa_list: 수분장력(kPa) 리스트 (list of float or int)
    :param threshold_kpa: 스트레스 기준 kPa (기본값: 100 kPa, float 또는 int)
    :return: 스트레스 비율 (%), float
    :rtype: float
    """
    
    if not psi_kpa_list:
        return 0
    stress_count = sum(1 for psi in psi_kpa_list if psi > threshold_kpa)
    return (stress_count / len(psi_kpa_list)) * 100

# -------------------------
# ▶ 위험 수준 판정 및 조치 메시지
# -------------------------

def ecp_risk_action(ecp):
    if ecp < 1.5:
        return "⚪ 안전: 염류 문제 없음"
    elif ecp < 3.0:
        return "🟡 주의: 염류 민감 작물은 관찰 필요"
    elif ecp < 4.5:
        return "🔶 경고: EC 낮추기 위해 세척 관수 고려"
    else:
        return "🔴 위험: 고염 스트레스 → 즉시 관주 또는 배수 조치 필요"

def awc_risk_action(awc):
    if awc > 0.15:
        return "⚪ 충분: 현재 상태 양호, 관수 불필요"
    elif awc > 0.10:
        return "🟡 적당: 모니터링 필요, 당장은 무관수 가능"
    elif awc > 0.05:
        return "🔶 부족: 조만간 관수 필요"
    else:
        return "🔴 매우 부족: 즉시 관수 필요"

def swsi_risk_action(swsi):
    if swsi < 0.2:
        return "⚪ 양호: 스트레스 없음"
    elif swsi < 0.5:
        return "🟡 약 스트레스: 관수 계획 검토"
    elif swsi < 0.8:
        return "🔶 중간 스트레스: 생육 저하 우려, 관수 고려"
    else:
        return "🔴 고 스트레스: 즉시 관수 필요, 생리적 피해 위험"

def stress_time_risk_action(ratio):
    if ratio < 20:
        return "⚪ 정상: 스트레스 누적 없음"
    elif ratio < 40:
        return "🟡 주의: 누적 스트레스 경향"
    elif ratio < 60:
        return "🔶 경고: 생육 저하 가능성, 관수 주기 재조정 필요"
    else:
        return "🔴 고위험: 지속 스트레스 상태, 전략적 관수 필요"


calculation_methods = {
    "calculate_ECp": calculate_ECp,
    "calculate_AWC": calculate_AWC,
    "calculate_SWSI": calculate_SWSI,
    "calculate_stress_time_ratio": calculate_stress_time_ratio,
}

# -------------------------
# ▶ 예시 입력 데이터
# -------------------------

# data = {
#     "vwc": 0.25,            # 함수율 (m³/m³)
#     "ec_bulk": 0.8,         # 벌크 전기전도도 (mS/cm)
#     "psi_kpa": -120,        # 수분장력 (kPa)
#     "psi_kpa_history": [-80, -110, -140, -130, -70, -160, -200]  # 과거 7회 측정
# }

# -------------------------
# ▶ 계산 및 결과 출력
# -------------------------

# 계산
# ecp = calculate_ECp(data["ec_bulk"], data["vwc"])
# awc = calculate_AWC(data["vwc"])
# swsi = calculate_SWSI(data["psi_kpa"])
# stress_ratio = calculate_stress_time_ratio(data["psi_kpa_history"])

# # 결과 출력
# print("📈 분석 결과 및 작물 관리 조치")
# print(f"🌱 공극수 EC (ECp): {ecp:.2f} mS/cm → {ecp_risk_action(ecp)}")
# print(f"💧 가용 수분량 (AWC): {awc:.2f} m³/m³ → {awc_risk_action(awc)}")
# print(f"📉 수분 스트레스 지수 (SWSI): {swsi:.2f} → {swsi_risk_action(swsi)}")
# print(f"⏱️ 스트레스 지속 비율: {stress_ratio:.1f}% → {stress_time_risk_action(stress_ratio)}")
