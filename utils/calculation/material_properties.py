# -*- coding: utf-8 -*-
"""
물성치(material properties) 계산 유틸리티

포함 함수:
- water_density_kg_m3(temp_c)
- water_dynamic_viscosity_pa_s(temp_c)
- water_kinematic_viscosity_m2_s(temp_c)
- water_specific_heat_j_kgk(temp_c)
- water_thermal_conductivity_w_mk(temp_c)
- bulk_density_from_porosity(porosity, particle_density=2650.0)
- porosity_from_bulk_and_particle_density(bulk_density, particle_density=2650.0)
- volumetric_heat_capacity_j_m3k(bulk_density, specific_heat_j_kgk)
- gravimetric_to_volumetric_moisture(theta_g, bulk_density, water_density=1000.0)
- volumetric_to_gravimetric_moisture(theta_v, bulk_density, water_density=1000.0)

간단한 경험식/근사식을 사용합니다. 단위에 유의하세요.
"""
from __future__ import annotations
import math


def water_density_kg_m3(temp_c: float) -> float:
    """물의 밀도(kg/m3), 온도 의존 근사식 (0-40°C)
    근사식: Kell (1975) 근사를 단순화한 형태.
    """
    t = temp_c
    # 근사 다항식 (0-40°C 범위에서 오차 작음)
    return 1000.0 * (1 - ((t + 288.9414) / (508929.2 * (t + 68.12963))) * (t - 3.9863) ** 2)


def water_dynamic_viscosity_pa_s(temp_c: float) -> float:
    """물의 동점성계수(파스칼·초), 온도 의존 근사식 (°C).
    Vogel 식 근사: mu = A * 10^(B/(T-C)) 사용 (T in °C) 대신 간단한 경험식 사용.
    반환값 예: 1.002e-3 Pa·s (20°C)
    """
    t = temp_c
    # Sutherland-like 근사 (허용 오차 있음)
    # 경험적으로 0°C~40°C에서 대략적 추정
    mu20 = 1.002e-3
    return mu20 * math.exp(-0.033*(t-20.0))


def water_kinematic_viscosity_m2_s(temp_c: float) -> float:
    """동점성계수(nu = mu / rho)."""
    rho = water_density_kg_m3(temp_c)
    mu = water_dynamic_viscosity_pa_s(temp_c)
    return mu / max(1e-6, rho)


def water_specific_heat_j_kgk(temp_c: float) -> float:
    """물의 비열(J/kg/K) 근사 (온도 약한 의존성). 평균값 사용."""
    # 0~40°C 범위에서 비열은 약 4180 J/kg/K 부근
    return 4181.3 - 0.1 * (temp_c - 20.0)


def water_thermal_conductivity_w_mk(temp_c: float) -> float:
    """물의 열전도도(W/m/K) 근사."""
    # 20°C에서 약 0.598 W/mK, 온도가 높아지면 약간 증가
    return 0.598 + 0.001*(temp_c - 20.0)


def bulk_density_from_porosity(porosity: float, particle_density: float = 2650.0) -> float:
    """공극률(0-1)과 입자밀도(kg/m3)로부터 벌크밀도(kg/m3) 계산.
    bulk = particle_density * (1 - porosity)
    """
    por = max(0.0, min(1.0, porosity))
    return particle_density * (1.0 - por)


def porosity_from_bulk_and_particle_density(bulk_density: float, particle_density: float = 2650.0) -> float:
    """벌크밀도와 입자밀도(kg/m3)로부터 공극률 계산."""
    pd = max(1e-6, particle_density)
    return max(0.0, min(1.0, 1.0 - bulk_density / pd))


def volumetric_heat_capacity_j_m3k(bulk_density: float, specific_heat_j_kgk: float) -> float:
    """체적 열용량 (J/m3/K) = bulk_density * specific_heat (J/kg/K)"""
    return bulk_density * specific_heat_j_kgk


def gravimetric_to_volumetric_moisture(theta_g: float, bulk_density: float, water_density: float = 1000.0) -> float:
    """중량수분(kg/kg)을 체적수분(m3/m3)으로 변환.
    theta_v = theta_g * bulk_density / water_density
    """
    return theta_g * (bulk_density / max(1e-6, water_density))


def volumetric_to_gravimetric_moisture(theta_v: float, bulk_density: float, water_density: float = 1000.0) -> float:
    """체적수분(m3/m3)을 중량수분(kg/kg)으로 변환."""
    return theta_v * (water_density / max(1e-6, bulk_density))


def van_genuchten_theta(psi: float, theta_s: float, theta_r: float, alpha: float, n: float) -> float:
    """van Genuchten 토양수분 보유곡선: psi(매트릭 포텐셜, 음수, 단위 m) -> theta (m3/m3)

    psi는 음수(흡수장력)로 입력. alpha의 단위는 1/m, n>1.
    """
    m = 1.0 - 1.0 / float(n)
    psi_abs = abs(psi)
    se = (1.0 + (alpha * psi_abs) ** float(n)) ** (-m)
    return float(theta_r + (theta_s - theta_r) * se)


def van_genuchten_psi_from_theta(theta: float, theta_s: float, theta_r: float, alpha: float, n: float) -> float:
    """theta -> psi(음수)로 역변환. theta 범위를 검증 후 음수 매트릭 포텐셜 반환(단위 m)."""
    th = float(theta)
    th = max(min(th, theta_s - 1e-12), theta_r + 1e-12)
    se = (th - theta_r) / (theta_s - theta_r)
    m = 1.0 - 1.0 / float(n)
    # invert Se = (1 + (alpha*|psi|)^n)^(-m)
    inner = max(0.0, se ** (-1.0 / m) - 1.0)
    psi_abs = inner ** (1.0 / float(n)) / alpha
    return -float(psi_abs)


def hydraulic_conductivity_vg(theta: float, Ks: float, theta_s: float, theta_r: float,
                              alpha: float, n: float, l: float = 0.5) -> float:
    """van Genuchten-Mualem 수리전도도 모델.

    입력:
    - theta: 체적함수율 (m3/m3)
    - Ks: 포화수리전도도 (m/s)
    - theta_s, theta_r, alpha (1/m), n
    - l: pore-connectivity parameter (보통 ~0.5)

    반환: K(theta) (m/s)
    """
    th = float(theta)
    se = (th - theta_r) / max(1e-12, (theta_s - theta_r))
    se = min(max(se, 1e-12), 1.0 - 1e-12)
    m = 1.0 - 1.0 / float(n)
    term = 1.0 - (1.0 - se ** (1.0 / m)) ** m
    kr = se ** l * (term ** 2)
    return float(Ks * kr)


def soil_moisture_diffusivity_vg(theta: float, Ks: float, theta_s: float, theta_r: float,
                                 alpha: float, n: float, l: float = 0.5,
                                 eps_psi: float = 1e-6) -> float:
    """토양 수분확산도 (hydraulic diffusivity) D(theta) = K(theta) / C(theta)

    - theta: 체적수분 (m3/m3)
    - Ks: 포화수리전도도 (m/s)
    - 나머지 van Genuchten 파라미터
    - eps_psi: 매트릭 포텐셜 수치 미분을 위한 작은 변화(단위 m)

    반환: D (m2/s)

    구현: C(theta)=dtheta/dpsi를 수치미분으로 계산하여 안정적으로 처리.
    """
    # 역으로 psi 구함
    try:
        psi = van_genuchten_psi_from_theta(theta, theta_s, theta_r, alpha, n)
    except Exception:
        return float('nan')

    # 중앙 차분으로 dtheta/dpsi 계산
    h = max(eps_psi, abs(psi) * 1e-4, 1e-8)
    theta_plus = van_genuchten_theta(psi + h, theta_s, theta_r, alpha, n)
    theta_minus = van_genuchten_theta(psi - h, theta_s, theta_r, alpha, n)
    c = (theta_plus - theta_minus) / (2.0 * h)
    c = max(c, 1e-18)

    k = hydraulic_conductivity_vg(theta, Ks, theta_s, theta_r, alpha, n, l)
    return float(k / c)


__all__ = [
    "water_density_kg_m3",
    "water_dynamic_viscosity_pa_s",
    "water_kinematic_viscosity_m2_s",
    "water_specific_heat_j_kgk",
    "water_thermal_conductivity_w_mk",
    "bulk_density_from_porosity",
    "porosity_from_bulk_and_particle_density",
    "volumetric_heat_capacity_j_m3k",
    "gravimetric_to_volumetric_moisture",
    "volumetric_to_gravimetric_moisture",
    "van_genuchten_theta",
    "van_genuchten_psi_from_theta",
    "hydraulic_conductivity_vg",
    "soil_moisture_diffusivity_vg",
]
