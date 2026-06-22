"""
test_config.py — Tests for config.py (no FEFLOW required).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from config import GeothermalConfig, load_config, WORKBOOK_PATH


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def test_workbook_exists():
    assert WORKBOOK_PATH.exists(), (
        f"Workbook not found: {WORKBOOK_PATH}\n"
        "Tests that depend on the workbook will be skipped if it is absent."
    )


# ---------------------------------------------------------------------------
# Default config (no workbook)
# ---------------------------------------------------------------------------

def test_default_config_initialises():
    cfg = GeothermalConfig()
    assert len(cfg.slice_elevations) == 6
    assert len(cfg.slice_depths) == 6
    assert len(cfg.slice_T) == 6
    assert len(cfg.K_mday) == 5
    assert len(cfg.phi) == 5
    assert len(cfg.Cv) == 5
    assert len(cfg.lambda_s) == 5
    assert len(cfg.output_times) == 20


def test_slice_elevations_ordering():
    cfg = GeothermalConfig()
    # Slice elevations must be monotonically decreasing (surface → basement)
    for i in range(len(cfg.slice_elevations) - 1):
        assert cfg.slice_elevations[i] > cfg.slice_elevations[i + 1], (
            f"Slice {i+1} elevation {cfg.slice_elevations[i]} is not greater "
            f"than Slice {i+2} elevation {cfg.slice_elevations[i+1]}"
        )


def test_slice_temperatures_increasing():
    cfg = GeothermalConfig()
    # Temperature increases with depth (positive geothermal gradient)
    for i in range(len(cfg.slice_T) - 1):
        assert cfg.slice_T[i] < cfg.slice_T[i + 1], (
            f"Slice {i+1} T={cfg.slice_T[i]:.2f} >= Slice {i+2} T={cfg.slice_T[i+1]:.2f}"
        )


def test_slice_T_surface():
    cfg = GeothermalConfig()
    assert abs(cfg.slice_T[0] - 15.0) < 0.01, (
        f"Surface temperature should be 15.0 °C, got {cfg.slice_T[0]}"
    )


def test_heat_flux_bc_negative():
    cfg = GeothermalConfig()
    # Heat flux BC is negative (flux into domain = upward geothermal heat)
    assert cfg.heat_flux_bc < 0, (
        f"heat_flux_bc should be negative (into domain), got {cfg.heat_flux_bc}"
    )


def test_heat_flux_bc_magnitude():
    cfg = GeothermalConfig()
    # 241 mW/m² = 0.241 W/m² × 86400 s/d = 20822.4 J/(m²·d)
    expected = -0.241 * 86_400.0
    assert abs(cfg.heat_flux_bc - expected) < 0.5, (
        f"heat_flux_bc: expected {expected:.1f}, got {cfg.heat_flux_bc:.1f}"
    )


def test_output_times_20_snapshots():
    cfg = GeothermalConfig()
    assert len(cfg.output_times) == 20
    assert cfg.output_times[0] == pytest.approx(1825.0)
    assert cfg.output_times[-1] == pytest.approx(36500.0)


def test_output_times_uniform_spacing():
    cfg = GeothermalConfig()
    diffs = [cfg.output_times[i+1] - cfg.output_times[i]
             for i in range(len(cfg.output_times) - 1)]
    assert all(abs(d - 1825.0) < 0.01 for d in diffs), (
        f"Output times not uniformly spaced at 1825 d: {diffs}"
    )


def test_K_caprock_lt_reservoir():
    cfg = GeothermalConfig()
    assert cfg.K_mday[1] < cfg.K_mday[2], (
        "Caprock K should be less than reservoir K"
    )


def test_phi_reservoir_lt_caprock():
    cfg = GeothermalConfig()
    # Reservoir has low porosity (tight sandstone); caprock is more porous
    # Group 3: caprock phi=0.27, reservoir phi=0.025
    assert cfg.phi[1] > cfg.phi[2], (
        "Group 3: caprock porosity (0.27) should exceed reservoir (0.025)"
    )


# ---------------------------------------------------------------------------
# Loaded config (requires workbook)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_load_config_returns_config(cfg):
    from config import GeothermalConfig
    assert isinstance(cfg, GeothermalConfig)


@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_wells_loaded(cfg):
    assert len(cfg.wells) == 10, f"Expected 10 wells, got {len(cfg.wells)}"


@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_wells_balanced(cfg):
    n_prod = (~cfg.wells["is_injection"]).sum()
    n_inj  = cfg.wells["is_injection"].sum()
    assert n_prod == 5, f"Expected 5 production wells, got {n_prod}"
    assert n_inj  == 5, f"Expected 5 injection wells, got {n_inj}"


@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_T_inj_loaded(cfg):
    assert abs(cfg.T_inj - 50.0) < 0.1, f"T_inj should be ~50 °C, got {cfg.T_inj}"


@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_well_nodes_count(cfg):
    # 10 wells × 7 nodes each = 70 rows
    assert len(cfg.well_nodes) == 70, (
        f"Expected 70 well-node rows (10 × 7), got {len(cfg.well_nodes)}"
    )


@pytest.mark.skipif(not WORKBOOK_PATH.exists(), reason="Workbook not found")
def test_slice_T_matches_workbook_approx(cfg):
    # The workbook sliceT sheet is cross-checked in load_config().
    # Verify the computed values are physically reasonable.
    assert 10.0 < cfg.slice_T[1] < 200.0, (
        f"Slice 2 temperature {cfg.slice_T[1]:.2f} °C out of range"
    )
    assert cfg.slice_T[5] > cfg.slice_T[1], (
        "Basement temperature should exceed reservoir temperature"
    )
