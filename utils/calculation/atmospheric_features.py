# -*- coding: utf-8 -*-
"""
증기압/습도 관련 계산 유틸리티

포함 함수(주요):
- saturation_vapor_pressure_hpa(temp_c)
- saturation_vapor_pressure_kpa(temp_c)
- actual_vapor_pressure_from_rh(temp_c, rh_percent)
- actual_vapor_pressure_from_dew_point(dewpoint_c)
- vpd_hpa(temp_c, rh_percent)
- vpd_kpa(temp_c, rh_percent)
- slope_saturation_vapor_pressure_kpa_per_c(temp_c)
- absolute_humidity_g_m3_from_e_hpa(temp_c, e_hpa)
- specific_humidity_g_kg_from_e_hpa(e_hpa, pressure_hpa=1013.25)

이 모듈은 다른 계산 모듈에서 증기압 관련 값을 얻을 때 재사용하도록 설계되었습니다.
"""
from __future__ import annotations
import math
from typing import Optional


def saturation_vapor_pressure_hpa(temp_c: float) -> float:
    """포화 증기압(단위: hPa) -- Magnus 식 기반 (T in °C)."""
    return 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c)))


def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """포화 증기압(단위: kPa)."""
    return saturation_vapor_pressure_hpa(temp_c) / 10.0


def actual_vapor_pressure_from_rh(temp_c: float, rh_percent: float) -> float:
    """상대습도(rh%)와 기온으로 실제 증기압(e, 단위: hPa) 계산."""
    es = saturation_vapor_pressure_hpa(temp_c)
    return max(0.0, es * max(0.0, min(rh_percent / 100.0, 1.0)))


def actual_vapor_pressure_from_dew_point(dewpoint_c: float) -> float:
    """이슬점(°C)으로부터 실제 증기압(e, 단위: hPa) 계산."""
    return saturation_vapor_pressure_hpa(dewpoint_c)


def vpd_hpa(temp_c: float, rh_percent: float) -> float:
    """VPD(단위: hPa). 포화증기압 - 실제증기압."""
    es = saturation_vapor_pressure_hpa(temp_c)
    e = actual_vapor_pressure_from_rh(temp_c, rh_percent)
    return max(0.0, es - e)


def vpd_kpa(temp_c: float, rh_percent: float) -> float:
    """VPD(단위: kPa)."""
    return vpd_hpa(temp_c, rh_percent) / 10.0


def slope_saturation_vapor_pressure_kpa_per_c(temp_c: float) -> float:
    """포화증기압 곡선의 기울기 (dkPa/dT) -- Penman-Monteith 등에서 사용.
    식: de/dT = 4098 * (0.6108 * exp(17.27*T/(T+237.3))) / (T+237.3)^2
    반환 단위: kPa / °C
    """
    es_kpa = saturation_vapor_pressure_kpa(temp_c)
    denom = (temp_c + 237.3)
    return (4098.0 * es_kpa) / (denom * denom)


def absolute_humidity_g_m3_from_e_hpa(temp_c: float, e_hpa: float) -> float:
    """절대습도 (g/m3) -- 실제 증기압(e, hPa)을 사용.
    공식: AH = 216.7 * e(hPa) / (T(K))
    """
    t_k = temp_c + 273.15
    return 216.7 * (e_hpa / t_k)


def specific_humidity_g_kg_from_e_hpa(e_hpa: float, pressure_hpa: float = 1013.25) -> float:
    """특정습도 (g/kg) -- 실제 증기압(e, hPa)과 기압( hPa )로 계산.
    q = 1000 * 0.622 * e / (P - 0.378 * e)
    """
    denom = max(1e-6, pressure_hpa - 0.378 * e_hpa)
    return 1000.0 * 0.622 * e_hpa / denom


__all__ = [
    "saturation_vapor_pressure_hpa",
    "saturation_vapor_pressure_kpa",
    "actual_vapor_pressure_from_rh",
    "actual_vapor_pressure_from_dew_point",
    "vpd_hpa",
    "vpd_kpa",
    "slope_saturation_vapor_pressure_kpa_per_c",
    "absolute_humidity_g_m3_from_e_hpa",
    "specific_humidity_g_kg_from_e_hpa",
]
