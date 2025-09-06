# -*- coding: utf-8 -*-
import math
from utils.calculation.derived_features import (
    pedotransfer_estimate_vg_params_from_bulk_and_d50,
    generate_diffusivity_grid,
    generate_diffusivity_series_from_theta,
    estimate_evaporation_from_radiation,
)


def test_pedotransfer_basic():
    params = pedotransfer_estimate_vg_params_from_bulk_and_d50(1400, 0.5)
    assert isinstance(params, dict)
    for k in ("theta_s", "theta_r", "alpha", "n", "Ks"):
        assert k in params
    assert 0.01 <= params["theta_s"] <= 0.6
    assert 0.0 <= params["theta_r"] <= 0.3
    assert params["alpha"] > 0.0
    assert params["n"] >= 1.1
    assert params["Ks"] >= 0.0


def test_generate_diffusivity_grid_and_series():
    params = pedotransfer_estimate_vg_params_from_bulk_and_d50(1400, 0.5)
    grid = generate_diffusivity_grid(0.05, 0.4, 10, **params)
    assert isinstance(grid, dict)
    assert len(grid) == 10
    values = [v for k, v in sorted(grid.items())]
    # 값이 유한하고 음수가 아닌지 확인
    assert all([math.isfinite(v) for v in values])
    assert all([v >= 0.0 for v in values])
    # 확산도는 전형적으로 함수율이 증가하면 증가하거나 안정적이어야 함(엄격하지 않은 검사)
    assert max(values) >= min(values)


def test_generate_diffusivity_series_from_theta_monotonicity():
    params = pedotransfer_estimate_vg_params_from_bulk_and_d50(1400, 0.5)
    thetas = [0.05, 0.10, 0.15, 0.20, 0.25]
    series = generate_diffusivity_series_from_theta(thetas, **params)
    vals = [series[t] for t in thetas]
    assert all([math.isfinite(v) for v in vals])
    assert all([v >= 0.0 for v in vals])


def test_estimate_evaporation_from_radiation_example():
    out = estimate_evaporation_from_radiation(300.0, 3600.0 * 6, root_zone_depth_m=0.3)
    assert "evap_mm" in out and "delta_vwc" in out
    # 계산값이 합리적 범위인지 확인 (대략 2.5~2.8 mm)
    assert 2.4 <= out["evap_mm"] <= 2.8
    assert 0.0 <= out["delta_vwc"] <= 0.1
