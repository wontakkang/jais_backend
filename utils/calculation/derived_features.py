
# -*- coding: utf-8 -*-
"""
파생 데이터 및 지표값 도출 함수 모음
=================================================
- 기상·환경: VPD, 이슬점, 절대/특정습도, DLI, GDD 등
- 토양: ECp, AWC, SWSI, 스트레스 시간비율
- 수분스트레스 지수(WSI): 관수/강수 vs ET0, 토양수분 보정
- 수액흐름: 일유량/피크/히스테리시스/상승·하강 기울기
- 생육/품질 관련: Load_per_LAI, Conductance proxy 등
- 롤링 파생: 3/7/14일 창 평균/합/표준편차
"""
from __future__ import annotations
import math
from typing import Iterable, Optional, Tuple
import numpy as np
import pandas as pd


# -----------------------------
# 1) 기상/공기 관련 파생지표
# -----------------------------

def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """포화수증기압 (kPa), Tetens 공식."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

def vpd_kpa(temp_c: float, rh_percent: float) -> float:
    """증기압 부족 VPD (kPa) = es(T)*(1 - RH)."""
    es = saturation_vapor_pressure_kpa(temp_c)
    return max(0.0, es * (1.0 - rh_percent / 100.0))

def dew_point_c(temp_c: float, rh_percent: float) -> float:
    """이슬점(°C), Magnus-Tetens 근사."""
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(max(1e-9, rh_percent/100.0))
    return (b * gamma) / (a - gamma)

def absolute_humidity_g_m3(temp_c: float, rh_percent: float) -> float:
    """절대습도(g/m^3)."""
    es_hPa = 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c)))
    ah = 216.7 * (rh_percent/100.0 * es_hPa) / (temp_c + 273.15)
    return ah

def specific_humidity_g_kg(temp_c: float, rh_percent: float, pressure_hpa: float = 1013.25) -> float:
    """특정습도(g/kg 건공기)."""
    es_hpa = 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c)))
    e = rh_percent/100.0 * es_hpa
    q = 1000.0 * 0.622 * e / max(1e-6, (pressure_hpa - 0.378 * e))
    return q

def dli_from_ppfd(ppfd_series_umol_m2s: Iterable[float], dt_seconds: float) -> float:
    """
    일일광량지수(DLI, mol m-2 d-1).
    Σ(PPFD * Δt) / 1e6
    """
    arr = np.asarray(list(ppfd_series_umol_m2s), dtype=float)
    return float(np.nansum(arr * dt_seconds) / 1e6)

def ppfd_from_irradiance(irr_w_m2: Iterable[float], factor: float = 2.04) -> np.ndarray:
    """
    전천일사(W/m²) → PPFD(μmol m-2 s-1) 근사.
    factor는 태양광 스펙트럼 가정(대략 2.0~2.2)으로 조정 가능.
    """
    return np.asarray(list(irr_w_m2), dtype=float) * factor

def ppfd_from_lux(lux: Iterable[float], k: float = 60.0) -> np.ndarray:
    """
    조도(lux) → PPFD(μmol m-2 s-1) 근사.
    K는 54~73 범위(스펙트럼 의존). 기본 60.
    """
    return np.asarray(list(lux), dtype=float) / k

def gdd_daily(tmin_c: float, tmax_c: float, base_c: float = 10.0, upper_c: Optional[float] = None) -> float:
    """
    일일 적산온도(GDD). 상·하한 절단 포함(선택).
    """
    if upper_c is not None:
        tmin_c = min(max(tmin_c, base_c), upper_c)
        tmax_c = min(max(tmax_c, base_c), upper_c)
    else:
        tmin_c = max(tmin_c, base_c)
        tmax_c = max(tmax_c, base_c)
    return max(0.0, (tmin_c + tmax_c) / 2.0 - base_c)


# -----------------------------
# 2) 토양 관련 파생지표
# -----------------------------

def calculate_ECp(ec_bulk_mS_cm: float, vwc: float, x: float = 1.6) -> float:
    """공극수 EC (mS/cm). vwc는 체적함수율(m³/m³)."""
    return ec_bulk_mS_cm / (vwc ** x) if vwc and vwc > 0 else 0.0

def calculate_AWC(vwc: float, wilting_point: float = 0.10) -> float:
    """가용 수분량(m³/m³)."""
    return max(0.0, vwc - wilting_point)

def calculate_SWSI(psi_kpa: float, field_capacity_kpa: float = -33.0, wilting_point_kpa: float = -1500.0) -> float:
    """
    수분 스트레스 지수(0~1). psi, FC, WP는 음수(kPa). 값이 클수록(덜 음수) 양호.
    """
    if psi_kpa > field_capacity_kpa:
        return 0.0
    return min(1.0, max(0.0, (psi_kpa - field_capacity_kpa) / (wilting_point_kpa - field_capacity_kpa)))

def calculate_stress_time_ratio(psi_kpa_list: Iterable[float], threshold_kpa: float = -100.0) -> float:
    """
    누적 스트레스 시간비율(%). 임계치보다 더 음수(건조)인 시간 비율.
    기본 threshold -100 kPa.
    """
    arr = np.asarray(list(psi_kpa_list), dtype=float)
    if arr.size == 0:
        return 0.0
    stress = np.sum(arr <= threshold_kpa)  # 더 건조(더 음수)면 카운트
    return float(stress / arr.size * 100.0)

def water_stress_index_wsi(irrig_7: float, rain_7: float, et0_7: float, alpha: float = 1.0,
                           soil_vwc_mean_7: Optional[float] = None, vwc_ref: float = 0.25) -> float:
    """
    수분 스트레스 지수(0~1, 1이 건조). 관수/강수 vs ET0 기반, 토양수분으로 보정.
    """
    denom = max(1e-6, alpha * et0_7)
    ratio = (irrig_7 + rain_7) / denom
    wsi = 1.0 - min(1.0, ratio)
    if soil_vwc_mean_7 is not None:
        relief = max(0.0, (soil_vwc_mean_7 - vwc_ref)) * 1.5  # 경험계수
        wsi = max(0.0, wsi - relief)
    return float(min(1.0, max(0.0, wsi)))


# -----------------------------
# 3) 수액흐름 지표 (시계열)
# -----------------------------

def sapflow_daily_metrics(flow_l_per_h: Iterable[float], vpd_kpa_series: Optional[Iterable[float]] = None,
                          dt_hours: float = 1.0) -> dict:
    """
    수액흐름 일일 지표 계산.
    - 총유량(L/day), 피크(L/h), 피크시, 오전 상승/오후 하강 기울기, (옵션)VPD-유량 히스테리시스 면적
    """
    q = np.asarray(list(flow_l_per_h), dtype=float)
    total = float(np.nansum(q * dt_hours))
    peak = float(np.nanmax(q)) if q.size else float('nan')
    t_peak = int(np.nanargmax(q)) if q.size else -1

    n = q.size
    hours = np.arange(n) * dt_hours
    def slope(x, y):
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() < 2: return float('nan')
        xm, ym = x[mask].mean(), y[mask].mean()
        return float(np.sum((x[mask]-xm)*(y[mask]-ym)) / np.sum((x[mask]-xm)**2))

    morning_idx = (hours >= 6) & (hours <= 12)
    afternoon_idx = (hours >= 12) & (hours <= 18)
    rise_rate = slope(hours[morning_idx], q[morning_idx])
    decline_rate = slope(hours[afternoon_idx], q[afternoon_idx])

    hysteresis_area = float('nan')
    if vpd_kpa_series is not None:
        v = np.asarray(list(vpd_kpa_series), dtype=float)
        mask = np.isfinite(q) & np.isfinite(v)
        if mask.sum() >= 3:
            x, y = v[mask], q[mask]
            s = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
            hysteresis_area = float(s)

    return {
        "sap_flow_total_l_day": total,
        "sap_flow_peak_l_h": peak,
        "time_of_peak_index": t_peak,
        "rise_rate_morning_L_h2": rise_rate,
        "decline_rate_afternoon_L_h2": decline_rate,
        "hysteresis_area_vpd_flow": hysteresis_area,
    }

def conductance_proxy_mm_s(sapflow_l_per_h: float, leaf_area_m2: float, vpd_kpa_value: float) -> float:
    """
    간이 전도도 지표 ≈ (E_leaf / VPD). 상대지표 용도.
    """
    if leaf_area_m2 <= 0 or vpd_kpa_value <= 0:
        return float('nan')
    e_kg_s = (sapflow_l_per_h / 3600.0)
    e_per_m2 = e_kg_s / leaf_area_m2
    return float(e_per_m2 / vpd_kpa_value)


# -----------------------------
# 4) 생육/품질 관련 파생
# -----------------------------

def load_per_lai(total_weight_tree_kg: float, lai: float) -> float:
    """수세 대비 부하(kg per LAI)."""
    if not lai or lai <= 0:
        return float('inf')
    return float(total_weight_tree_kg / lai)

def ssc_dilution_indicator(weight_growth_g: float, irrigation_event: bool = False, soil_vwc_change: float = 0.0) -> float:
    """
    SSC 희석 가능성 지표 (0~1). 비대 급증(+관수/토양 함수 증가) 시 높아짐.
    """
    score = 0.0
    score += max(0.0, weight_growth_g) / 50.0  # 50g/day 기준 스케일
    if irrigation_event:
        score += 0.3
    score += max(0.0, soil_vwc_change) * 2.0
    return float(min(1.0, score))


# -----------------------------
# 5) 롤링/창 파생 유틸
# -----------------------------

def rolling_features(df: pd.DataFrame, value_cols: list, windows: Iterable[int] = (3,7,14),
                     how: Tuple[str,...] = ("mean","sum","std"), on_col: str = "date",
                     group_cols: Optional[list] = None) -> pd.DataFrame:
    """
    날짜 인덱스 또는 date 컬럼 기반 롤링 파생. 그룹별 적용 가능.
    """
    x = df.copy()
    if on_col in x.columns:
        x = x.sort_values(on_col).set_index(on_col)
    if group_cols:
        x = x.groupby(group_cols + [x.index.name])
    out = df.copy()
    for w in windows:
        for c in value_cols:
            if isinstance(x, pd.core.groupby.generic.DataFrameGroupBy):
                roll = x[c].rolling(f"{w}D")
                mean_vals = roll.mean().reset_index(level=group_cols, drop=True)
                sum_vals  = roll.sum().reset_index(level=group_cols, drop=True)
                std_vals  = roll.std().reset_index(level=group_cols, drop=True)
            else:
                roll = x[c].rolling(window=w, min_periods=1)
                mean_vals, sum_vals, std_vals = roll.mean(), roll.sum(), roll.std()
            if "mean" in how:
                out[f"{c}_{w}d_mean"] = mean_vals.values if hasattr(mean_vals, "values") else mean_vals
            if "sum" in how:
                out[f"{c}_{w}d_sum"]  = sum_vals.values if hasattr(sum_vals, "values") else sum_vals
            if "std" in how:
                out[f"{c}_{w}d_std"]  = std_vals.values if hasattr(std_vals, "values") else std_vals
    return out


# -----------------------------
# 6) 간단 사용 예시
# -----------------------------
if __name__ == "__main__":
    # 예시: 기상에서 VPD/DLI 계산
    ppfd = [0, 100, 500, 1200, 800, 200, 0]  # μmol m-2 s-1
    vpd = vpd_kpa(30.0, 60.0)
    dli = dli_from_ppfd(ppfd, dt_seconds=3600)
    print(f"VPD: {vpd:.2f} kPa, DLI: {dli:.2f} mol m-2 d-1")

    # 예시: 토양
    ecp = calculate_ECp(0.8, 0.25)
    awc = calculate_AWC(0.25)
    swsi = calculate_SWSI(-120)
    stress = calculate_stress_time_ratio([-80, -110, -140, -130, -70, -160, -200], threshold_kpa=-100)
    print(f"ECp={ecp:.2f} mS/cm, AWC={awc:.2f} m3/m3, SWSI={swsi:.2f}, Stress%={stress:.1f}")

    # 예시: 수액흐름
    flow = [0,0.2,0.8,1.2,1.6,1.1,0.5,0.1,0]  # L/h
    vpd_seq = [0.2,0.4,0.8,1.5,2.2,2.0,1.2,0.6,0.3]
    metrics = sapflow_daily_metrics(flow, vpd_seq, dt_hours=1.0)
    print(metrics)
