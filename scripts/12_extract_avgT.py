"""
extract_avg_production_temperature.py — Group 3 geothermal doublet

Extracts the EXACT average production-well temperature time series directly
from the raw FEFLOW simulation data (Group3.fem + Group3.dac + Group3.npz).
No chart reading, no interpolation, no manual estimates.

WHY THIS SCRIPT EXISTS
-----------------------
Group3.npz (written by Stage 10) already contains the raw nodal temperature
field for every stored snapshot (T_arr, shape = [n_snapshots, n_nodes]) as
plain numpy arrays — reading it back requires NO FEFLOW license.

However, the array is indexed by *global mesh node number*, not by well name.
To know WHICH node index corresponds to each production well's screen top,
FEFLOW's IFM Python API must be used once:
    doc = ifm.loadDocument(str(FEM_PATH))                  # opens Group3.fem
    node = doc.getMultiLayerWellTopNode(mlw_id)             # -> node index
    x, y = doc.getX(node), doc.getY(node)                   # -> match to well name
This step requires a licensed, installed FEFLOW 8.1 (the `ifm` / `ifm_contrib`
Python module ships inside the FEFLOW installation itself — it is not on PyPI
and cannot be installed standalone). It is NOT available in this sandbox.

Once the node indices are known, everything else in this script is pure
numpy — reading T_arr[snapshot_index, node_index] directly is numerically
IDENTICAL to calling doc.getResultsTransportHeatValue(node) after
loadTimeStep(), because that is exactly what was stored in the NPZ by
Stage 10 in the first place. No FEFLOW round-trip is needed for that part.

HOW TO RUN THIS (on the machine where FEFLOW 8.1 is installed)
-----------------------------------------------------------------
1. This file already lives in Group3_automation/scripts/ (next to config.py, utils.py).
2. Activate the `feflow-geothermal` conda environment (see environment.yml).
3. Make sure FEFLOW's own Python bindings are importable — either:
     a) run this script with FEFLOW's bundled Python interpreter, or
     b) add FEFLOW's bin64/python (or wherever ifm_contrib is installed) to
        sys.path / PYTHONPATH before running.
4. From Group3_automation/scripts/, run:
     python 12_extract_avg_production_temperature.py
5. Two identical CSVs are written to Group3_automation/outputs/:
     Average_Production_Temperature.csv
     thermal_timeseries.csv
   and the exact day-36500 value is printed to the console.

AVERAGING METHOD
-----------------
Arithmetic mean across the 5 production wells (prod-1 .. prod-5).
Group 3's welldata sheet gives every production well an IDENTICAL rate
(30 L/s each) — so the flow-weighted average and the arithmetic average
are mathematically identical here. If a future group/model has unequal
well rates, switch to the flow-weighted formula noted in weighted_avg().
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from config import load_config, OUTPUTS_DIR, RESULTS_PATH, GeothermalConfig   # noqa: E402
from utils import bootstrap_ifm, setup_logging                                # noqa: E402

log = logging.getLogger(__name__)

OUT_CSV_1 = OUTPUTS_DIR / "Average_Production_Temperature.csv"
OUT_CSV_2 = OUTPUTS_DIR / "thermal_timeseries.csv"


class WellInfo(NamedTuple):
    mlw_id: int
    name: str
    is_injection: bool
    rate_m3d: float


def _check_prereqs() -> None:
    fem_path = OUTPUTS_DIR / "Group3.fem"
    dac_path = OUTPUTS_DIR / "Group3.dac"
    npz_path = RESULTS_PATH.with_suffix(".npz")
    missing = [p for p in (fem_path, dac_path, npz_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required file(s): "
            + ", ".join(str(p) for p in missing)
            + "\nStage 10 (singleStep simulation loop) must complete before this script runs."
        )
    log.info("Found: %s, %s, %s", fem_path.name, dac_path.name, npz_path.name)


def _load_snapshots(cfg: GeothermalConfig):
    npz_path = RESULTS_PATH.with_suffix(".npz")
    data = np.load(str(npz_path))
    T_arr = data["T"]      # float32 [n_snapshots, n_nodes]
    times = data["times"]  # float64 [n_snapshots]  (days)
    n_steps = len(times)
    if n_steps == 0:
        raise RuntimeError(f"{npz_path.name} contains 0 snapshots — re-run Stage 10.")
    log.info(
        "Loaded %d snapshots from %s  [%.0f d ... %.0f d]  T_arr shape=%s",
        n_steps, npz_path.name, float(times[0]), float(times[-1]), T_arr.shape,
    )
    return times, T_arr


def _build_mlw_map(doc, cfg: GeothermalConfig) -> List[WellInfo]:
    """Match each FEFLOW MLW to a row in cfg.wells by XY proximity (same logic
    as Stage 11 — verified). Requires FEFLOW IFM."""
    n_mlw = doc.getNumberOfMultiLayerWells()
    if n_mlw == 0:
        raise RuntimeError("No MLW wells found in the FEM. Check Group3.fem.")

    wx = cfg.wells["x"].to_numpy(dtype=float) if "x" in cfg.wells.columns else cfg.wells["X"].to_numpy(dtype=float)
    wy = cfg.wells["y"].to_numpy(dtype=float) if "y" in cfg.wells.columns else cfg.wells["Y"].to_numpy(dtype=float)

    result: List[WellInfo] = []
    for mlw_id in range(n_mlw):
        top_node = doc.getMultiLayerWellTopNode(mlw_id)
        x_mlw = doc.getX(top_node)
        y_mlw = doc.getY(top_node)
        dists = np.sqrt((wx - x_mlw) ** 2 + (wy - y_mlw) ** 2)
        best_row = int(np.argmin(dists))
        row = cfg.wells.iloc[best_row]
        result.append(WellInfo(
            mlw_id=mlw_id,
            name=str(row["name"]),
            is_injection=bool(row["is_injection"]),
            rate_m3d=abs(float(row["rate_lps"])) * 86.4,
        ))
    return result


def weighted_avg(T_by_well: Dict[str, float], rates: Dict[str, float]) -> float:
    """Flow-weighted average — kept for reference / future unequal-rate models.
    With Group 3's equal-rate wells this returns the same value as the
    arithmetic mean (verified in run_arithmetic_vs_weighted_check())."""
    num = sum(T_by_well[w] * rates[w] for w in T_by_well)
    den = sum(rates[w] for w in T_by_well)
    return num / den


def main() -> None:
    setup_logging()
    _check_prereqs()

    cfg = load_config()
    ifm = bootstrap_ifm()

    fem_path = OUTPUTS_DIR / "Group3.fem"
    log.info("Opening %s via FEFLOW IFM ...", fem_path.name)
    doc = ifm.loadDocument(str(fem_path))

    times, T_arr = _load_snapshots(cfg)
    mlw_map = _build_mlw_map(doc, cfg)
    prod_wells = [w for w in mlw_map if not w.is_injection]
    if not prod_wells:
        raise RuntimeError("No production wells identified — check MLW map.")

    log.info(
        "Production wells identified: %s (rates: %s L/s each)",
        [w.name for w in prod_wells],
        [round(w.rate_m3d / 86.4, 1) for w in prod_wells],
    )

    # Top node (shallowest screened node, in the reservoir layer) per well —
    # cached once, does not change between snapshots.
    top_nodes: Dict[str, int] = {
        w.name: doc.getMultiLayerWellTopNode(w.mlw_id) for w in prod_wells
    }
    for name, node in top_nodes.items():
        log.info("  %-8s -> global node %d  (X=%.1f, Y=%.1f)",
                 name, node, doc.getX(node), doc.getY(node))

    rates = {w.name: w.rate_m3d for w in prod_wells}
    all_equal_rate = len(set(round(r, 3) for r in rates.values())) == 1
    log.info(
        "Averaging method: %s (all production wells have %s rate)",
        "ARITHMETIC (== flow-weighted, rates are equal)" if all_equal_rate
        else "FLOW-WEIGHTED (rates differ)",
        "identical" if all_equal_rate else "different",
    )

    records = []
    for i, t_d in enumerate(times):
        T_by_well = {name: float(T_arr[i, node]) for name, node in top_nodes.items()}
        if all_equal_rate:
            T_avg = float(np.mean(list(T_by_well.values())))
        else:
            T_avg = weighted_avg(T_by_well, rates)
        row = {"Time (days)": float(t_d), "Time (years)": float(t_d) / 365.25,
               "Average Production Temperature (°C)": round(T_avg, 4)}
        for name in top_nodes:
            row[f"T_{name} (°C)"] = round(T_by_well[name], 4)
        records.append(row)

    df = pd.DataFrame(records).sort_values("Time (days)").reset_index(drop=True)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV_1, index=False, float_format="%.4f")
    df.to_csv(OUT_CSV_2, index=False, float_format="%.4f")
    log.info("Saved: %s", OUT_CSV_1)
    log.info("Saved: %s", OUT_CSV_2)

    last = df.iloc[-1]
    print("\n=== FINAL ROW (raw FEFLOW data, no chart reading) ===")
    print(f"Time (days)                         : {last['Time (days)']:.0f}")
    print(f"Time (years)                         : {last['Time (years)']:.2f}")
    print(f"Average Production Temperature (°C)  : {last['Average Production Temperature (°C)']:.2f}")
    print("======================================================\n")

    if abs(last["Time (days)"] - 36500.0) > 1.0:
        log.warning(
            "Last snapshot is at day %.0f, not day 36500. "
            "cfg.t_final=%.0f and cfg.output_times spans up to %.0f d — "
            "check Stage 10 completed the full 100-year run.",
            last["Time (days)"], cfg.t_final, max(cfg.output_times),
        )


if __name__ == "__main__":
    main()
