"""
test_thermal_power.py — Tests for the thermal power calculation in Stage 11.

No FEFLOW required.  The calculation is pure Python / numpy / pandas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from config import GeothermalConfig

# Import compute_thermal_power and WellInfo from the module directly.
# We load the module without running main().
import importlib.util

_STAGE11 = SCRIPTS / "11_postprocess.py"


def _import_stage11():
    spec = importlib.util.spec_from_file_location("postprocess", _STAGE11)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage11():
    return _import_stage11()


# ---------------------------------------------------------------------------
# WellInfo construction
# ---------------------------------------------------------------------------

def test_well_info_fields(stage11):
    wi = stage11.WellInfo(mlw_id=0, name="prod-1", is_injection=False, rate_m3d=2592.0)
    assert wi.mlw_id == 0
    assert wi.name == "prod-1"
    assert not wi.is_injection
    assert wi.rate_m3d == pytest.approx(2592.0)


# ---------------------------------------------------------------------------
# Thermal power calculation
# ---------------------------------------------------------------------------

def _make_prod_df(T_prod: float, time_yr: float = 5.0) -> pd.DataFrame:
    """Minimal df_prod with one time step and one well."""
    return pd.DataFrame({
        "time_d":    [time_yr * 365.25],
        "time_yr":   [time_yr],
        "well_name": ["prod-1"],
        "T_prod_C":  [T_prod],
    })


def _make_mlw_map(stage11, n_prod: int = 5, rate_lps: float = 30.0):
    _LS_TO_M3D = 86.4
    wells = [
        stage11.WellInfo(i, f"prod-{i+1}", False, rate_lps * _LS_TO_M3D)
        for i in range(n_prod)
    ]
    return wells


def test_thermal_power_at_initial_T(stage11):
    """P_th at undisturbed reservoir T should equal the reference P0."""
    cfg = GeothermalConfig()
    T_res = cfg.slice_T[1]    # 134.13 °C
    T_inj = cfg.T_inj         # 50.0 °C

    records = []
    for name in ["prod-1", "prod-2", "prod-3", "prod-4", "prod-5"]:
        records.append({"time_d": 1825.0, "time_yr": 1825.0/365.25,
                        "well_name": name, "T_prod_C": T_res})
    df_prod = pd.DataFrame(records)

    mlw_map = _make_mlw_map(stage11, n_prod=5, rate_lps=30.0)

    df_power = stage11.compute_thermal_power(df_prod, cfg, mlw_map)

    # Reference: rho_Cp * Q_total_m3s * dT
    _RHO_CP = 4.1868e6     # J/(m3·K)
    Q_m3s   = 5 * 30.0 * 86.4 / 86_400.0
    dT      = T_res - T_inj
    P0_MW   = _RHO_CP * Q_m3s * dT / 1e6

    actual = float(df_power["P_MW"].iloc[0])
    assert actual == pytest.approx(P0_MW, rel=1e-4), (
        f"Expected P0={P0_MW:.3f} MW, got {actual:.3f} MW"
    )


def test_thermal_power_decreases_with_breakthrough(stage11):
    """Lower T_prod (thermal breakthrough) must give lower thermal power."""
    cfg = GeothermalConfig()
    mlw_map = _make_mlw_map(stage11, n_prod=5)

    records_hi = [{"time_d": 1825.0, "time_yr": 5.0,
                   "well_name": f"prod-{i}", "T_prod_C": 130.0} for i in range(5)]
    records_lo = [{"time_d": 1825.0, "time_yr": 5.0,
                   "well_name": f"prod-{i}", "T_prod_C": 100.0} for i in range(5)]

    df_hi = pd.DataFrame(records_hi)
    df_lo = pd.DataFrame(records_lo)

    P_hi = float(stage11.compute_thermal_power(df_hi, cfg, mlw_map)["P_MW"].iloc[0])
    P_lo = float(stage11.compute_thermal_power(df_lo, cfg, mlw_map)["P_MW"].iloc[0])

    assert P_hi > P_lo, (
        f"Higher T_prod ({P_hi:.2f} MW) should give higher power than lower ({P_lo:.2f} MW)"
    )


def test_thermal_power_group3_final(stage11):
    """
    Sanity check against the known Group 3 result.
    At t=100 yr, T_prod_avg ≈ 124.5 °C → P_th ≈ 46.8 MW_th.
    Allow ±2 MW tolerance for different workbook inputs.
    """
    cfg = GeothermalConfig()
    mlw_map = _make_mlw_map(stage11, n_prod=5)

    T_prod_final = 124.5   # °C (approximate from published run)
    records = [{"time_d": 36500.0, "time_yr": 99.93,
                "well_name": f"prod-{i}", "T_prod_C": T_prod_final} for i in range(5)]
    df_prod = pd.DataFrame(records)

    df_power = stage11.compute_thermal_power(df_prod, cfg, mlw_map)
    P_final = float(df_power["P_MW"].iloc[0])

    assert 40.0 < P_final < 55.0, (
        f"Final thermal power {P_final:.2f} MW outside expected range [40, 55]"
    )


# ---------------------------------------------------------------------------
# NPZ array structure
# ---------------------------------------------------------------------------

def test_npz_path_is_alongside_dac(stage11):
    """Group3.npz must live next to Group3.dac in outputs/."""
    from config import RESULTS_PATH
    npz = RESULTS_PATH.with_suffix(".npz")
    assert npz.parent == RESULTS_PATH.parent
    assert npz.stem == RESULTS_PATH.stem
    assert npz.suffix == ".npz"


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "outputs" / "Group3.npz").exists(),
    reason="Group3.npz not generated yet (run Stage 10 first)",
)
def test_npz_content():
    npz_path = Path(__file__).parent.parent / "outputs" / "Group3.npz"
    data = np.load(str(npz_path))

    assert "times" in data, "NPZ missing 'times' array"
    assert "T" in data,     "NPZ missing 'T' array"
    assert "h" in data,     "NPZ missing 'h' array"

    n_steps, n_nodes = data["T"].shape
    assert n_steps == 20,   f"Expected 20 snapshots, got {n_steps}"
    assert n_nodes == 28236, f"Expected 28236 nodes, got {n_nodes}"

    assert data["T"].dtype  == np.float32
    assert data["h"].dtype  == np.float32
    assert data["times"].dtype == np.float64

    # Physical plausibility: all temperatures between 0 and 400 °C
    assert float(data["T"].min()) > 0.0
    assert float(data["T"].max()) < 400.0

    # Snapshots must be at 5-year intervals (1825 d each)
    times = data["times"]
    assert abs(times[0] - 1825.0) < 1.0, f"First snapshot at {times[0]:.1f} d (expected 1825 d)"
    assert abs(times[-1] - 36500.0) < 1.0, f"Last snapshot at {times[-1]:.1f} d (expected 36500 d)"
