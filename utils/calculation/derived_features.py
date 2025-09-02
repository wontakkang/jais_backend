
# -*- coding: utf-8 -*-
"""
스마트팜 과실 비대/품질 예측용 파생지표 함수 모음 (경량 버전)
================================================================
이 파일은 "기상+LAI만"으로 만드는 **경향 예측용 최소 세트**와,
"기상+LAI+토양(관수)"까지 포함하는 **정밀 예측 세트**에 필요한
계산식/지표를 함수화한 모듈입니다.

포함 내용
---------
[기상/환경]
- vpd_kpa: 증기압 부족
- dew_point_c: 이슬점
- absolute_humidity_g_m3, specific_humidity_g_kg: 절대/특정습도
- dli_from_ppfd: 일일광량지수(DLI)
- gdd_daily: 일일 적산온도(GDD)

[토양/관수]
- calculate_ECp: 공극수 EC
- calculate_AWC: 가용 수분량
- calculate_SWSI: 수분 스트레스 지수(장력 기반)
- calculate_stress_time_ratio: 스트레스 시간 비율
- water_stress_index_wsi: 관수/강수 vs ET0 기반 WSI
- delta_vwc: 토양함수율 변화량(ΔVWC)

[생육/품질 관련]
- load_per_lai: 수세 대비 부하(kg per LAI)
- ssc_dilution_indicator: SSC 희석 지표(관수/ΔVWC/비대 급증 반영)

[피처 빌더]
- build_minimal_features(...): 기상+LAI 최소 세트 생성
- build_precision_features(...): 기상+LAI+토양(관수) 정밀 세트 생성
- build_growth_features(...): 비대 예측용 핵심 피처 딕셔너리
- build_quality_features(...): 품질(SSC/TA) 예측용 핵심 피처 딕셔너리
"""
from __future__ import annotations
import math
from typing import Iterable, Optional, Dict, Any, Sequence
import numpy as np


# -----------------------------
# 1) 기상/공기 관련
# -----------------------------

def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

def vpd_kpa(temp_c: float, rh_percent: float) -> float:
    es = saturation_vapor_pressure_kpa(temp_c)
    return max(0.0, es * (1.0 - rh_percent / 100.0))

def dew_point_c(temp_c: float, rh_percent: float) -> float:
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(max(1e-9, rh_percent/100.0))
    return (b * gamma) / (a - gamma)

def absolute_humidity_g_m3(temp_c: float, rh_percent: float) -> float:
    es_hPa = 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c)))
    return 216.7 * (rh_percent/100.0 * es_hPa) / (temp_c + 273.15)

def specific_humidity_g_kg(temp_c: float, rh_percent: float, pressure_hpa: float = 1013.25) -> float:
    es_hpa = 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c)))
    e = rh_percent/100.0 * es_hpa
    return 1000.0 * 0.622 * e / max(1e-6, (pressure_hpa - 0.378 * e))

def dli_from_ppfd(ppfd_series_umol_m2s: Iterable[float], dt_seconds: float) -> float:
    arr = np.asarray(list(ppfd_series_umol_m2s), dtype=float)
    return float(np.nansum(arr * dt_seconds) / 1e6)

def gdd_daily(tmin_c: float, tmax_c: float, base_c: float = 10.0, upper_c: Optional[float] = None) -> float:
    if upper_c is not None:
        tmin_c = min(max(tmin_c, base_c), upper_c)
        tmax_c = min(max(tmax_c, base_c), upper_c)
    else:
        tmin_c = max(tmin_c, base_c); tmax_c = max(tmax_c, base_c)
    return max(0.0, (tmin_c + tmax_c) / 2.0 - base_c)


# -----------------------------
# 2) 토양/관수
# -----------------------------

def calculate_ECp(ec_bulk_mS_cm: float, vwc: float, x: float = 1.6) -> float:
    return ec_bulk_mS_cm / (vwc ** x) if vwc and vwc > 0 else 0.0

def calculate_AWC(vwc: float, wilting_point: float = 0.10) -> float:
    return max(0.0, vwc - wilting_point)

def calculate_SWSI(psi_kpa: float, field_capacity_kpa: float = -33.0, wilting_point_kpa: float = -1500.0) -> float:
    if psi_kpa > field_capacity_kpa:
        return 0.0
    return min(1.0, max(0.0, (psi_kpa - field_capacity_kpa) / (wilting_point_kpa - field_capacity_kpa)))

def calculate_stress_time_ratio(psi_kpa_list: Iterable[float], threshold_kpa: float = -100.0) -> float:
    arr = np.asarray(list(psi_kpa_list), dtype=float)
    if arr.size == 0:
        return 0.0
    stress = np.sum(arr <= threshold_kpa)
    return float(stress / arr.size * 100.0)

def water_stress_index_wsi(irrig_7: float, rain_7: float, et0_7: float, alpha: float = 1.0,
                           soil_vwc_mean_7: Optional[float] = None, vwc_ref: float = 0.25) -> float:
    denom = max(1e-6, alpha * et0_7)
    ratio = (irrig_7 + rain_7) / denom
    wsi = 1.0 - min(1.0, ratio)
    if soil_vwc_mean_7 is not None:
        relief = max(0.0, (soil_vwc_mean_7 - vwc_ref)) * 1.5
        wsi = max(0.0, wsi - relief)
    return float(min(1.0, max(0.0, wsi)))

def delta_vwc(vwc_now: float, vwc_prev: float) -> float:
    """토양 함수율 변화량(양수=함수 증가, 음수=감소)."""
    if vwc_now is None or vwc_prev is None:
        return float('nan')
    return float(vwc_now - vwc_prev)


# -----------------------------
# 3) 생육/품질 관련
# -----------------------------

def load_per_lai(total_weight_tree_kg: float, lai: float) -> float:
    if not lai or lai <= 0:
        return float('inf')
    return float(total_weight_tree_kg / lai)

def ssc_dilution_indicator(weight_growth_g: float,
                           irrigation_event: bool = False,
                           soil_vwc_change: float = 0.0) -> float:
    """
    SSC 희석 가능성 지표(0~1):
    - 비대 급증(무게 증가량↑)
    - 최근 관수 이벤트
    - 토양 함수 증가(ΔVWC>0)
    """
    score = 0.0
    score += max(0.0, weight_growth_g) / 50.0   # 스케일 보정(경험적)
    if irrigation_event:
        score += 0.3
    score += max(0.0, soil_vwc_change) * 2.0
    return float(min(1.0, score))


# -----------------------------
# 4) 피처 빌더
# -----------------------------

def build_minimal_features(*,
                           dli_7: float, dli_14: float,
                           vpd_7: float,
                           gdd_cum: float,
                           lai: float) -> Dict[str, Any]:
    """
    기상+LAI만으로 구성하는 '경향 예측' 최소 피처 세트
    """
    return {
        "DLI_7": dli_7,
        "DLI_14": dli_14,
        "VPD_7": vpd_7,
        "GDD_cum": gdd_cum,
        "LAI": lai,
    }

def build_precision_features(*,
                             dli_7: float, dli_14: float,
                             vpd_7: float,
                             gdd_cum: float,
                             lai: float,
                             soil_vwc_7: Optional[float] = None,
                             soil_vwc_14: Optional[float] = None,
                             delta_vwc_3: Optional[float] = None,
                             delta_vwc_7: Optional[float] = None,
                             wsi_7: Optional[float] = None,
                             wsi_14: Optional[float] = None,
                             irrigation_3: Optional[float] = None,
                             irrigation_7: Optional[float] = None,
                             high_vpd_hours_7: Optional[float] = None) -> Dict[str, Any]:
    """
    기상+LAI+토양(관수)까지 포함하는 정밀 피처 세트
    """
    features = build_minimal_features(dli_7=dli_7, dli_14=dli_14,
                                      vpd_7=vpd_7, gdd_cum=gdd_cum, lai=lai)
    features.update({
        "SoilVWC_7": soil_vwc_7,
        "SoilVWC_14": soil_vwc_14,
        "ΔVWC_3": delta_vwc_3,
        "ΔVWC_7": delta_vwc_7,
        "WSI_7": wsi_7,
        "WSI_14": wsi_14,
        "Irrigation_3": irrigation_3,
        "Irrigation_7": irrigation_7,
        "HighVPD_hours_7": high_vpd_hours_7,
    })
    return features

def build_growth_features(*,
                          dli_7: float, dli_14: float,
                          vpd_7: float, gdd_cum: float, lai: float,
                          soil_vwc_7: Optional[float] = None,
                          delta_vwc_3: Optional[float] = None,
                          irrigation_7: Optional[float] = None) -> Dict[str, Any]:
    """
    과실 비대 예측 핵심 피처
    """
    feats = build_minimal_features(dli_7=dli_7, dli_14=dli_14, vpd_7=vpd_7, gdd_cum=gdd_cum, lai=lai)
    feats.update({
        "SoilVWC_7": soil_vwc_7,
        "ΔVWC_3": delta_vwc_3,
        "Irrigation_7": irrigation_7,
    })
    return feats

def build_quality_features(*,
                           dli_14: float,
                           vpd_7: float,
                           lai: float,
                           soil_vwc_7: Optional[float] = None,
                           wsi_7: Optional[float] = None,
                           irrigation_3: Optional[float] = None,
                           ssc_dilution_score: Optional[float] = None) -> Dict[str, Any]:
    """
    품질(SSC/TA) 예측 핵심 피처
    """
    feats = {
        "DLI_14": dli_14,
        "VPD_7": vpd_7,
        "LAI": lai,
        "SoilVWC_7": soil_vwc_7,
        "WSI_7": wsi_7,
        "Irrigation_3": irrigation_3,
        "SSC_dilution_score": ssc_dilution_score,
    }
    return feats


# -----------------------------
# 5) 간단 예시
# -----------------------------
if __name__ == "__main__":
    # 예시 값
    dli_7, dli_14 = 25.0, 180.0
    vpd7 = vpd_kpa(30.0, 55.0)
    gdd = 450.0
    lai = 2.7
    soil7, soil14 = 0.22, 0.24
    dvwc3, dvwc7 = 0.03, 0.02
    wsi7, wsi14 = 0.35, 0.28
    irr3, irr7 = 8.0, 30.0

    # 최소/정밀 피처
    minimal = build_minimal_features(dli_7=dli_7, dli_14=dli_14, vpd_7=vpd7, gdd_cum=gdd, lai=lai)
    precision = build_precision_features(dli_7=dli_7, dli_14=dli_14, vpd_7=vpd7, gdd_cum=gdd, lai=lai,
                                         soil_vwc_7=soil7, soil_vwc_14=soil14,
                                         delta_vwc_3=dvwc3, delta_vwc_7=dvwc7,
                                         wsi_7=wsi7, wsi_14=wsi14,
                                         irrigation_3=irr3, irrigation_7=irr7,
                                         high_vpd_hours_7=12.0)

    # SSC 희석 지표
    dilution = ssc_dilution_indicator(weight_growth_g=35.0, irrigation_event=True, soil_vwc_change=dvwc3)

    print("Minimal:", minimal)
    print("Precision:", precision)
    print("SSC_dilution_indicator:", dilution)
