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
- calculate_ECp: 공극수 E
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

[추가 기능]
- generate_diffusivity_series_from_theta: van Genuchten 기반 수분확산도 시리즈 생성
- pedotransfer_estimate_vg_params_from_bulk_and_d50: 벌크밀도·입경 기반 VG 파라미터 추정
- estimate_evaporation_from_radiation: 일사량 기반 간단한 건조 모델
"""
from __future__ import annotations
import math
from typing import Iterable, Optional, Dict, Any, Sequence, Tuple
import numpy as np
from .material_properties import (
    soil_moisture_diffusivity_vg,
    porosity_from_bulk_and_particle_density,
    water_dynamic_viscosity_pa_s,
)
from scipy.optimize import least_squares


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
        "Irration_7": irrigation_7,
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
# 6) 토양 수분확산도 시리즈 생성 / Pedotransfer
# -----------------------------

def generate_diffusivity_series_from_theta(theta_values: Iterable[float], *,
                                           theta_s: float, theta_r: float,
                                           alpha: float, n: float, Ks: float,
                                           l: float = 0.5) -> Dict[float, float]:
    """주어진 theta(체적함수율) 값 목록에 대해 수분확산도 D(theta)를 계산해서 딕셔너리로 반환.

    파라미터:
    - theta_values: 반복 가능한 theta 값들 (m3/m3)
    - theta_s, theta_r, alpha, n, Ks: van Genuchten / Mualem 파라미터
    - l: pore-connectivity 파라미터 (기본 0.5)

    반환: {theta: D} (D 단위: m2/s)

    예시:
    >>> thetas = [0.05, 0.10, 0.15, 0.20, 0.25]
    >>> params = dict(theta_s=0.45, theta_r=0.05, alpha=30.0, n=2.0, Ks=1e-5)
    >>> generate_diffusivity_series_from_theta(thetas, **params)
    {0.05: 1.2e-08, ...}
    """
    result = {}
    for th in theta_values:
        try:
            d = soil_moisture_diffusivity_vg(float(th), Ks=float(Ks), theta_s=float(theta_s),
                                             theta_r=float(theta_r), alpha=float(alpha), n=float(n), l=float(l))
        except Exception:
            d = float('nan')
        result[float(th)] = float(d)
    return result


def generate_diffusivity_grid(theta_min: float = 0.01, theta_max: float = 0.45, n_points: int = 20, **vg_params) -> Dict[float, float]:
    """theta_min..theta_max 범위에서 균등 그리드를 만들어 D(theta) 시리즈를 반환.

    vg_params: theta_s, theta_r, alpha, n, Ks, l(optional)

    예시:
    >>> generate_diffusivity_grid(0.05, 0.4, 10, theta_s=0.45, theta_r=0.05, alpha=25.0, n=1.7, Ks=1e-5)
    {0.05: ..., ...}
    """
    thetas = np.linspace(theta_min, theta_max, int(max(2, n_points))).tolist()
    return generate_diffusivity_series_from_theta(thetas, **vg_params)


def pedotransfer_estimate_vg_params_from_bulk_and_d50(bulk_density_kg_m3: float, d50_mm: float,
                                                      particle_density: float = 2650.0,
                                                      temp_c: float = 20.0) -> Dict[str, float]:
    """간단한 Pedotransfer(벌크밀도 + 입경) 기반 van Genuchten 파라미터 추정.

    입력:
    - bulk_density_kg_m3: 벌크밀도(kg/m3)
    - d50_mm: 중간입경 D50 (mm)
    - particle_density: 입자밀도(기본 2650 kg/m3)
    - temp_c: 점성 계산을 위한 온도(°C)

    반환: dict(theta_s, theta_r, alpha, n, Ks)

    주의/설명:
    - 매우 단순화된 경험식입니다. 문헌값/현장측정으로 보정 필요합니다.
    - theta_s는 공극률로 근사(porosity = 1 - bulk/particle)
    - theta_r는 공극률에 따라 경험적으로 설정
    - alpha, n은 입경(d50)에 의존하도록 휴리스틱으로 추정(단위 alpha: 1/m)
    - Ks는 Kozeny-Carman 방식으로 투수계수(단위 m/s) 근사

    예시:
    >>> pedotransfer_estimate_vg_params_from_bulk_and_d50(1400, 0.5)
    {'theta_s': 0.47, 'theta_r': 0.06, 'alpha': 40.0, 'n': 1.8, 'Ks': 0.0023}
    """
    # porosity, theta_s
    por = porosity_from_bulk_and_particle_density(float(bulk_density_kg_m3), float(particle_density))
    theta_s = float(max(0.01, min(0.60, por)))

    # theta_r: 경험식 (건토양 잔류함수율). 공극률이 클수록 theta_r 상대적으로 작게 잡음
    theta_r = float(max(0.01, min(0.20, 0.02 + 0.1 * (1.0 - por))))

    # alpha: 입경에 따라 역비례적 휴리스틱 (단위 1/m), 범위 제한
    d50 = float(max(0.01, d50_mm))
    alpha = max(0.1, min(200.0, 20.0 / d50))

    # n: 입경이 클수록 더 큰 n (모래형), 범위 1.1~4.0
    n = max(1.1, min(4.0, 1.1 + 2.0 * (d50 / (d50 + 0.5))))

    # Ks: Kozeny-Carman을 이용한 근사
    d_m = d50 / 1000.0
    if d_m <= 0:
        k_perm = 0.0
    else:
        k_perm = (d_m ** 2) / 180.0 * (por ** 3) / max(1e-9, (1.0 - por) ** 2)
    mu = water_dynamic_viscosity_pa_s(float(temp_c))
    rho_w = 1000.0
    g = 9.81
    Ks = float(k_perm * (rho_w * g) / max(1e-12, mu))

    return {
        "theta_s": theta_s,
        "theta_r": theta_r,
        "alpha": float(alpha),
        "n": float(n),
        "Ks": float(Ks),
    }


def fit_vg_parameters_from_data(psi_m: Iterable[float], theta_m: Iterable[float], *,
                                initial_params: Optional[Dict[str, float]] = None,
                                bounds: Optional[Dict[str, Tuple[float, float]]] = None,
                                fit_Ks: bool = False,
                                max_nfev: int = 1000) -> Dict[str, Any]:
    """현장 측정된 ψ(매트릭 포텐셜, m)와 θ(체적함수율, m3/m3)를 사용해
    van Genuchten 파라미터를 비선형 최적화로 피팅합니다 (θ = f(ψ)).

    하이브리드 워크플로우:
    1) initial_params가 없으면 pedotransfer_estimate_vg_params_from_bulk_and_d50로 초기값 설정
    2) scipy.optimize.least_squares를 사용해 θ_obs와 모델 θ 간의 잔차를 최소화

    파라미터:
    - psi_m: 배열(또는 반복자), 매트릭 포텐셜(단위 m). 흡수장력이면 양/음 상관없이 처리(절대값 사용).
    - theta_m: 관측된 θ 값(동일 길이 배열)
    - initial_params: {'theta_s', 'theta_r', 'alpha', 'n', 'Ks'(선택적)} 초기값
    - bounds: 각 파라미터의 (min,max) 딕셔너리 (생략 시 안전 기본값 사용)
    - fit_Ks: Ks까지 함께 피팅할지 여부
    - max_nfev: 최대 반복수

    반환: dict(파라미터..., 'success':bool, 'cost':float)

    예제:
    >>> # 합성 데이터 생성
    >>> true = dict(theta_s=0.45, theta_r=0.05, alpha=25.0, n=1.6)
    >>> psi = np.linspace(-0.001, -150.0, 30)  # m
    >>> theta = [van_genuchten_theta(p, **true) for p in psi]
    >>> out = fit_vg_parameters_from_data(psi, theta)
    >>> print(out['theta_s'], out['n'])
    """
    try:
        from scipy.optimize import least_squares
    except Exception as e:
        raise RuntimeError("scipy required for parameter fitting. Please install scipy: pip install scipy")

    psi_arr = np.asarray(list(psi_m), dtype=float)
    theta_arr = np.asarray(list(theta_m), dtype=float)
    if psi_arr.size != theta_arr.size:
        raise ValueError("psi and theta must have same length")

    # ensure psi is negative (suction). van_genuchten_theta uses abs(psi) internally
    psi_arr = -np.abs(psi_arr)

    # defaults
    if initial_params is None:
        # very basic default if no bulk/d50 provided
        initial_params = {
            'theta_s': 0.45,
            'theta_r': 0.05,
            'alpha': 25.0,
            'n': 1.4,
            'Ks': 1e-5,
        }
    init = dict(initial_params)

    # bounds defaults
    default_bounds = {
        'theta_s': (0.01, 0.60),
        'theta_r': (0.0, 0.4),
        'alpha': (0.001, 1000.0),
        'n': (1.01, 10.0),
        'Ks': (1e-12, 1e-1),
    }
    if bounds is None:
        bounds = default_bounds
    else:
        # merge provided bounds with defaults
        for k, v in default_bounds.items():
            if k not in bounds:
                bounds[k] = v

    # build parameter vector and bounds
    keys = ['theta_s', 'theta_r', 'alpha', 'n']
    if fit_Ks:
        keys.append('Ks')

    x0 = []
    lb = []
    ub = []
    for k in keys:
        x0.append(float(init.get(k, default_bounds[k][0] if k != 'Ks' else 1e-5)))
        b = bounds.get(k, default_bounds[k])
        lb.append(b[0]); ub.append(b[1])

    x0 = np.asarray(x0, dtype=float)
    lb = np.asarray(lb, dtype=float)
    ub = np.asarray(ub, dtype=float)

    def residuals(x):
        params = {k: float(x[i]) for i, k in enumerate(keys)}
        theta_pred = np.array([van_genuchten_theta(p, params.get('theta_s'), params.get('theta_r'), params.get('alpha'), params.get('n')) for p in psi_arr])
        return (theta_pred - theta_arr)

    res = least_squares(residuals, x0, bounds=(lb, ub), max_nfev=max_nfev)

    out = {k: float(res.x[i]) for i, k in enumerate(keys)}
    out['success'] = bool(res.success)
    out['cost'] = float(res.cost)
    return out


def hybrid_calibrate_vg(bulk_density_kg_m3: float, d50_mm: float, psi_m: Iterable[float], theta_m: Iterable[float], *,
                        particle_density: float = 2650.0, temp_c: float = 20.0,
                        fit_Ks: bool = False, max_nfev: int = 1000) -> Dict[str, Any]:
    """하이브리드 워크플로우: pedotransfer로 초기값을 만들고 현장데이터로 소폭 보정(fit).

    반환: 피팅된 파라미터 딕셔너리 (theta_s, theta_r, alpha, n, Ks 가능)

    예시:
    >>> # bulk, d50로 초기값 생성
    >>> init = pedotransfer_estimate_vg_params_from_bulk_and_d50(1400, 0.5)
    >>> out = hybrid_calibrate_vg(1400, 0.5, psi_obs, theta_obs)
    """
    init = pedotransfer_estimate_vg_params_from_bulk_and_d50(bulk_density_kg_m3, d50_mm, particle_density, temp_c)
    fitted = fit_vg_parameters_from_data(psi_m, theta_m, initial_params=init, fit_Ks=fit_Ks, max_nfev=max_nfev)
    # merge init and fitted to produce final
    result = dict(init)
    for k, v in fitted.items():
        if k in result or k in ('theta_s', 'theta_r', 'alpha', 'n', 'Ks'):
            result[k] = v
    result['fit_success'] = fitted.get('success', False)
    result['fit_cost'] = fitted.get('cost', None)
    return result


# -----------------------------
# 7) 일사량 기반 간단한 토양 건조(물마름) 추정 함수
# -----------------------------

def estimate_evaporation_from_radiation(radiation_w_m2: float, duration_s: float,
                                         root_zone_depth_m: float = 0.3,
                                         crop_coefficient: float = 1.0,
                                         latent_heat_j_per_kg: float = 2.45e6) -> Dict[str, float]:
    """단순한 에너지 기반 증발량 추정 및 토양 함수율 변화 계산.

    모형 (아주 간단한 근사):
      - 입력 복사에너지(순복사 근사) radiation_w_m2 (W/m2)
      - 기간 duration_s (초)
      - 잠열(latent heat)로 나누어 질량(kg/m2)으로 환산
      - 루트존 깊이(root_zone_depth_m)를 이용해 체적함수율 변화로 변환

    반환 딕셔너리:
      - water_depth_m: 증발로 손실된 물의 깊이 (m)
      - delta_vwc: 토양 함수율 체적 변화 (m3/m3)
      - evap_mm: 증발량(mm)

    주의: 실제 ET는 기상요소(VPD, 풍속, 온도 등)와 작물계수에 크게 의존합니다.
    이 함수는 ‘일사량이 주어질 때의 최대 가능한 증발(간단 근사)’을 제공하기 위한 것임.

    예시:
    >>> estimate_evaporation_from_radiation(300.0, 3600*6, root_zone_depth_m=0.3)
    {'water_depth_m': 0.0026, 'delta_vwc': 0.0087, 'evap_mm': 2.6}
    """
    # 에너지량 (J/m2)
    energy_j_m2 = float(radiation_w_m2) * float(duration_s) * float(max(0.0, crop_coefficient))
    # 질량(kg/m2) = 에너지 / 잠열
    mass_kg_m2 = energy_j_m2 / float(latent_heat_j_per_kg)
    # 물의 깊이(m) = mass(kg/m2) / rho_w(kg/m3)
    rho_w = 1000.0
    water_depth_m = mass_kg_m2 / rho_w
    evap_mm = water_depth_m * 1000.0

    # delta vwc = water_depth / root_zone_depth
    rz = max(1e-6, float(root_zone_depth_m))
    delta_vwc = water_depth_m / rz
    return {
        "water_depth_m": float(water_depth_m),
        "delta_vwc": float(delta_vwc),
        "evap_mm": float(evap_mm),
    }


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

    print("최소 피처:", minimal)
    print("정밀 피처:", precision)
    print("SSC 희석 지표:", dilution)
