"""
test_postprocess_new.py — Tests for Stage 11 additions: F6 (hydraulic head
evolution) and F7 (adaptive timestep evolution).

No FEFLOW / IFM execution is required.  All tests are pure-Python and work
without a FEFLOW installation.

Coverage
--------
1. Function existence — plot_head_evolution and plot_timestep_evolution must
   be importable from Stage 11.
2. NPZ backward compatibility — plot_timestep_evolution must return silently
   (no exception) when the NPZ does not contain the new arrays.
3. Missing NPZ — plot_timestep_evolution must return silently when the NPZ
   file itself does not exist.
4. Valid synthetic data — plot_timestep_evolution produces a figure file when
   time_abs_d / dt_d arrays are present.
5. Extended NPZ format — adding time_abs_d / dt_d to the NPZ does not break
   the three "times / T / h" checks in the existing test_npz_content test.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

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
# Helper: build a minimal synthetic NPZ in a temp directory
# ---------------------------------------------------------------------------

def _write_npz(path: Path, **arrays) -> None:
    """Write a NumPy .npz file with the given keyword arrays."""
    np.savez(str(path), **arrays)


def _synthetic_timestep_arrays(n: int = 80):
    """
    Generate realistic synthetic time_abs_d / dt_d arrays.

    Simulates rapid dt growth from 1e-10 d toward 100 d, as the FEFLOW
    predictor-corrector scheme would produce for a well-converged run.
    """
    # Exponential ramp from 1e-10 to 100 d, then constant at 100 d
    dt_arr = np.concatenate([
        np.geomspace(1e-10, 100.0, n // 2),
        np.full(n - n // 2, 100.0),
    ])
    # Cumulative time
    time_arr = np.cumsum(dt_arr)
    return time_arr.astype(np.float64), dt_arr.astype(np.float64)


# ---------------------------------------------------------------------------
# 1. Function existence
# ---------------------------------------------------------------------------

def test_plot_head_evolution_exists(stage11):
    """plot_head_evolution must be defined in Stage 11."""
    assert hasattr(stage11, "plot_head_evolution"), (
        "plot_head_evolution not found in 11_postprocess.py"
    )
    assert callable(stage11.plot_head_evolution)


def test_plot_timestep_evolution_exists(stage11):
    """plot_timestep_evolution must be defined in Stage 11."""
    assert hasattr(stage11, "plot_timestep_evolution"), (
        "plot_timestep_evolution not found in 11_postprocess.py"
    )
    assert callable(stage11.plot_timestep_evolution)


# ---------------------------------------------------------------------------
# 2. Missing NPZ file — graceful fallback
# ---------------------------------------------------------------------------

def test_f7_skips_when_npz_missing(tmp_path, stage11):
    """
    plot_timestep_evolution must return without raising when the NPZ path
    does not exist.  It should only log a warning and return None.
    """
    from config import GeothermalConfig
    cfg       = GeothermalConfig()
    fake_path = tmp_path / "nonexistent.npz"
    assert not fake_path.exists()

    result = stage11.plot_timestep_evolution(cfg, npz_path=fake_path)
    assert result is None   # function returns None (no return statement = None)


# ---------------------------------------------------------------------------
# 3. NPZ without the new arrays — backward compatibility
# ---------------------------------------------------------------------------

def test_f7_skips_when_arrays_missing(tmp_path, stage11):
    """
    plot_timestep_evolution must return without raising when the NPZ exists
    but does not contain 'time_abs_d' or 'dt_d' (old-format NPZ from Stage 10
    before this feature was added).
    """
    from config import GeothermalConfig
    cfg      = GeothermalConfig()
    npz_path = tmp_path / "old_format.npz"

    # Simulate an old-format NPZ: only contains the snapshot arrays
    n_snap  = 20
    n_nodes = 100
    _write_npz(
        npz_path,
        times = np.linspace(1825.0, 36500.0, n_snap),
        T     = np.ones((n_snap, n_nodes), dtype=np.float32) * 100.0,
        h     = np.ones((n_snap, n_nodes), dtype=np.float32) * 200.0,
        # 'time_abs_d' and 'dt_d' intentionally omitted
    )

    result = stage11.plot_timestep_evolution(cfg, npz_path=npz_path)
    assert result is None


# ---------------------------------------------------------------------------
# 4. Valid synthetic data — function runs without exception
# ---------------------------------------------------------------------------

def test_f7_runs_with_valid_data(tmp_path, stage11):
    """
    plot_timestep_evolution must complete without raising when time_abs_d and
    dt_d are present and contain physically plausible values.

    The figure is saved to FIGURES_DIR (which exists because Stage 11 creates
    it via mkdir).  We redirect FIGURES_DIR to tmp_path to avoid touching the
    repository's figures/ directory during testing.
    """
    import matplotlib
    matplotlib.use("Agg")   # headless — no display required

    from config import GeothermalConfig
    cfg = GeothermalConfig()

    time_arr, dt_arr = _synthetic_timestep_arrays(n=80)
    npz_path = tmp_path / "synthetic.npz"
    _write_npz(npz_path, time_abs_d=time_arr, dt_d=dt_arr)

    # Redirect FIGURES_DIR to tmp_path so the figure is written there
    original_figures_dir = stage11.FIGURES_DIR
    stage11.FIGURES_DIR = tmp_path
    try:
        stage11.plot_timestep_evolution(cfg, npz_path=npz_path)
    finally:
        stage11.FIGURES_DIR = original_figures_dir

    saved = tmp_path / "F7_timestep_evolution.png"
    assert saved.exists(), (
        f"F7 figure not found at {saved}. "
        "plot_timestep_evolution may have raised or returned early."
    )
    assert saved.stat().st_size > 10_000, (
        f"F7 figure file is suspiciously small ({saved.stat().st_size} bytes)."
    )


# ---------------------------------------------------------------------------
# 5. Extended NPZ format — existing key checks still pass
# ---------------------------------------------------------------------------

def test_extended_npz_passes_existing_key_checks(tmp_path):
    """
    An NPZ containing the new 'time_abs_d' / 'dt_d' arrays must still satisfy
    the three checks from test_thermal_power.test_npz_content:
        'times' in data
        'T'     in data
        'h'     in data
    Adding new keys must not invalidate the existing format contract.
    """
    n_snap  = 20
    n_nodes = 28_236

    time_arr, dt_arr = _synthetic_timestep_arrays(n=100)
    npz_path = tmp_path / "extended.npz"
    np.savez_compressed(
        str(npz_path),
        times      = np.linspace(1825.0, 36500.0, n_snap),
        T          = np.ones((n_snap, n_nodes), dtype=np.float32) * 100.0,
        h          = np.ones((n_snap, n_nodes), dtype=np.float32) * 200.0,
        time_abs_d = time_arr,
        dt_d       = dt_arr,
    )

    data = np.load(str(npz_path))

    # Original format requirements still satisfied
    assert "times" in data, "NPZ missing 'times' array"
    assert "T"     in data, "NPZ missing 'T' array"
    assert "h"     in data, "NPZ missing 'h' array"

    # New arrays present
    assert "time_abs_d" in data, "NPZ missing 'time_abs_d' array"
    assert "dt_d"       in data, "NPZ missing 'dt_d' array"

    # Shape and dtype checks for new arrays
    assert data["time_abs_d"].dtype == np.float64
    assert data["dt_d"].dtype       == np.float64
    assert data["time_abs_d"].ndim  == 1
    assert data["dt_d"].ndim        == 1
    assert len(data["time_abs_d"]) == len(data["dt_d"])


# ---------------------------------------------------------------------------
# 6. Synthetic dt array physics checks
# ---------------------------------------------------------------------------

def test_synthetic_dt_arrays_are_positive():
    """dt_d values must all be positive (step size is always > 0)."""
    _, dt_arr = _synthetic_timestep_arrays(n=80)
    assert np.all(dt_arr > 0), (
        "All dt values must be positive (each accepted step advances time)."
    )


def test_synthetic_time_array_is_monotone():
    """time_abs_d must be strictly monotone increasing."""
    time_arr, _ = _synthetic_timestep_arrays(n=80)
    diffs = np.diff(time_arr)
    assert np.all(diffs > 0), (
        "time_abs_d must be strictly increasing (simulation only advances forward)."
    )


def test_synthetic_cumsum_consistency():
    """time_abs_d must equal cumsum(dt_d) within floating-point precision."""
    time_arr, dt_arr = _synthetic_timestep_arrays(n=80)
    cumsum = np.cumsum(dt_arr)
    assert np.allclose(time_arr, cumsum, rtol=1e-10), (
        "time_abs_d does not match cumsum(dt_d). "
        "The relationship time[i] = sum(dt[0..i]) must hold."
    )
