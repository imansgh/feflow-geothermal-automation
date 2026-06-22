"""
11_postprocess.py — Extract simulation results from the DAC file and produce
all figures and tables for the scientific report.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
The following methods were confirmed to NOT EXIST in FeflowDoc and are NOT
used anywhere in this module:

    readResultsFile()           — DNE  (was original primary DAC-open call)
    openResultsFile()           — DNE
    closeResultsFile()          — DNE
    getResultsFileName()        — DNE
    getResultsNumberOfTimes()   — DNE  (was used to count snapshots)
    getResultsTimeValue(i)      — DNE  (was used to get simulation time per step)
    setResultsTime(i)           — DNE  (was used to activate a snapshot)
    getParamSize(P_TEMP, node)  — WRONG semantics: returns COUNT of items,
                                  not value at node; replaced throughout
    ifm.Enum.P_TRANS_INT        — DNE  (used in original for temperature enum)
    budgetFlowCreate()          — EXISTS but requires running simulator +
                                  PostTimeStep callback; CANNOT be used to
                                  read heat flux from a loaded DAC file

Snapshot access (FEFLOW 8.1 architecture)
------------------------------------------
FEFLOW 8.1 IFM's getTimeSteps() / loadTimeStep() only expose ONE entry from
the DAC regardless of how many output times were written (confirmed by binary
analysis -- the DAC binary contains all snapshots but the Python API cannot
enumerate them; this is a regression from FEFLOW 7.x).

Stage 10 therefore captures T and h arrays via getParamValues() at each
custom time during the singleStep() loop and saves them to Group3.npz.
Stage 11 reads Group3.npz with numpy and restores each snapshot to the
FEFLOW document via setParamValues(P_TEMP, ...) + setParamValues(P_HEAD, ...)
-- see activate_snapshot() and load_snapshots() below.

Single-node results getters (after activate_snapshot):
    getResultsTransportHeatValue(node)  → float [deg C]
    getResultsFlowHeadValue(node)       → float [m]

Bulk parameter getters (after activate_snapshot):
    getParamValues(P_TEMP)              → list[float] [deg C], length = n_nodes
    getParamValues(P_HEAD)              → list[float] [m],     length = n_nodes

Spatial interpolation (after activate_snapshot, slice is 0-based):
    getResultsTransportHeatValueAtXYSlice(x, y, slice_0based) → float [deg C]
    getResultsFlowHeadValueAtXYSlice(x, y, slice_0based)      → float [m]

Node coordinates:
    getX(node), getY(node), getZ(node)  → float [m]
    getNumberOfNodes()                  → int
    getNumberOfNodesPerSlice()          → int
    getNumberOfSlices()                 → int

MLW:
    getNumberOfMultiLayerWells()                → int
    getMultiLayerWellTopNode(mlw_id)            → int (0-based global node)
    getMultiLayerWellBottomNode(mlw_id)         → int
    getMultiLayerWellAttrValue(mlw_id, MLW_RATE)→ float [m3/d]

Verified enums (ifm.Enum, FEFLOW 8.1):
    P_TEMP = 402    temperature [deg C]
    P_HEAD = 400    hydraulic head [m]
    MLW_RATE = 0    volumetric flow rate [m3/d]

Budget API note
----------------
budgetFlowCreate() / budgetHeatCreate() require a running simulator with
PostTimeStep callbacks; they CANNOT be called on a loaded DAC. Thermal power
is therefore computed analytically from well rates and temperature difference:
    P_W = rho_Cp * (Q_prod_m3d / _S_PER_DAY) * |dT|
where rho_Cp = 4.1868e6 J/(m3·K), dT = T_prod_avg - T_inj.

getTimeSteps() indexing note
------------------------------
loadTimeStep(i) uses i as the 0-based position in the getTimeSteps() list.
The simulation step number stored in steps[i][0] is the INTERNAL step counter
(may differ from i on sparse DACs); it is not passed to loadTimeStep.

Output files
-------------
    figures/F1_temperature_maps.png     plan-view T, Slice 2, five times
    figures/F2_cross_section.png        vertical T cross-section, 100 yr
    figures/F3_breakthrough_curve.png   T_prod(t) for each production well
    figures/F4_thermal_power.png        P_th [MW_th] vs time
    figures/F5_head_map.png             hydraulic head, Slice 2, final time
    figures/F6_head_evolution.png       h(t) at representative prod/inj wells
    figures/F7_timestep_evolution.png   adaptive dt vs time (log-y axis)
    outputs/thermal_power_table.csv     P_th at every output snapshot

Tutorial reference: pp. 31–32 (§6)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import matplotlib
matplotlib.use("Agg")   # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    load_config, OUTPUTS_DIR, FIGURES_DIR, RESULTS_PATH, GeothermalConfig,
)
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

# Volumetric heat capacity of water [J/(m3·K)] at ~60 °C
# Equivalent to 1.16 kWh/(m3·K) × 3600 s/h = 4176000 J/(m3·K)
_RHO_CP_WATER: float = 4.1868e6    # J/(m3·K)
_S_PER_DAY:    float = 86_400.0    # s/d
_LS_TO_M3D:    float = 86.4        # (L/s) → (m3/d)

# Cross-section sampling resolution
_XSECT_N_POINTS: int = 200          # points along horizontal transect

# Plan-view scatter marker size — kept for F5 (head map)
_SCATTER_SIZE: float = 1.0


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------

class WellInfo(NamedTuple):
    mlw_id:       int
    name:         str
    is_injection: bool
    rate_m3d:     float   # always positive; sign from is_injection


# ---------------------------------------------------------------------------
# DAC validation
# ---------------------------------------------------------------------------

def load_snapshots(cfg: GeothermalConfig) -> Tuple[List, int, np.ndarray, np.ndarray]:
    """
    Load the simulation snapshot file written by Stage 10's singleStep loop.

    Background
    ----------
    FEFLOW 8.1 IFM's getTimeSteps() / loadTimeStep() expose only ONE entry
    from the DAC regardless of how many output times were written (confirmed
    by binary analysis -- the DAC binary contains all snapshots but the Python
    API cannot enumerate them).  Stage 10 therefore captures snapshots via
    getParamValues() at each custom time and saves them to Group3.npz.

    Parameters
    ----------
    cfg:
        GeothermalConfig -- used to cross-check expected snapshot count.

    Returns
    -------
    (steps, n_steps, T_arr, h_arr)
        steps   : list of (i, time_d) tuples -- same format as getTimeSteps()
        n_steps : number of stored snapshots
        T_arr   : float32 ndarray, shape (n_steps, n_nodes), temperature [degC]
        h_arr   : float32 ndarray, shape (n_steps, n_nodes), head [m]
    """
    npz_path = RESULTS_PATH.with_suffix('.npz')
    if not npz_path.exists():
        raise FileNotFoundError(
            f"Snapshot file not found: {npz_path}\n"
            "Stage 10 must complete successfully before Stage 11.\n"
            "The singleStep simulation loop writes this file."
        )

    data    = np.load(str(npz_path))
    T_arr   = data['T']      # float32[n_steps, n_nodes]
    h_arr   = data['h']      # float32[n_steps, n_nodes]
    times   = data['times']  # float64[n_steps]
    n_steps = len(times)

    if n_steps == 0:
        raise RuntimeError(
            f"Snapshot file {npz_path.name} contains 0 snapshots.\n"
            "Re-run Stage 10 to regenerate the results."
        )

    # Build steps list in the same format as getTimeSteps() -- (index, time_d)
    steps = [(i, float(times[i])) for i in range(n_steps)]

    n_exp = len(cfg.output_times)
    if n_steps < n_exp:
        log.warning(
            "Snapshot file has %d snapshots; expected %d. "
            "Stage 10 may have been interrupted.",
            n_steps, n_exp,
        )
    else:
        log.info(
            "Snapshots: %d  [%.0f d ... %.0f d]  T_arr %s  h_arr %s",
            n_steps, float(times[0]), float(times[-1]),
            T_arr.shape, h_arr.shape,
        )

    return steps, n_steps, T_arr, h_arr


def activate_snapshot(doc, ifm, T_row: np.ndarray, h_row: np.ndarray) -> None:
    """
    Populate the FEFLOW document's in-memory field registers from a snapshot.

    setParamValues(P_TEMP, T_list) updates the same register read by
    getResultsTransportHeatValue(), getResultsTransportHeatValueAtXYSlice(),
    and getParamValues(P_TEMP) -- confirmed by live API testing in FEFLOW 8.1.
    One bulk call per field replaces loadTimeStep(i).
    """
    doc.setParamValues(ifm.Enum.P_TEMP, T_row.tolist())
    doc.setParamValues(ifm.Enum.P_HEAD, h_row.tolist())


# ---------------------------------------------------------------------------
# MLW → well mapping
# ---------------------------------------------------------------------------

def _build_mlw_map(doc, cfg: GeothermalConfig) -> List[WellInfo]:
    """
    Match each MLW in the FEM to a row in cfg.wells by XY proximity.

    Strategy
    --------
    1. For each MLW, get its top node via getMultiLayerWellTopNode(mlw_id).
    2. Read that node's XY via getX/getY.
    3. Find the cfg.well_nodes row with the smallest Euclidean distance.
    4. Map to the corresponding cfg.wells row (same index, row-aligned).

    cfg.wells and cfg.well_nodes are row-aligned (both from the workbook,
    same row count and order).

    Returns
    -------
    List of WellInfo — one per MLW, sorted by mlw_id.
    """
    n_mlw = doc.getNumberOfMultiLayerWells()
    if n_mlw == 0:
        raise RuntimeError(
            "No MLW wells found in the FEM. Run Stage 08 first."
        )

    # Use cfg.wells["x"/"y"] (centre coordinates, 1 row per well).
    # cfg.well_nodes has 7 rows per well (1 centre + 6 cluster nodes) so
    # using it here would give argmin indices up to 69, which is out of
    # bounds for cfg.wells.iloc (10 rows).  The centre XY is the correct
    # reference for matching MLW → well.
    wx = cfg.wells["x"].to_numpy(dtype=float)
    wy = cfg.wells["y"].to_numpy(dtype=float)

    result: List[WellInfo] = []
    for mlw_id in range(n_mlw):
        top_node = doc.getMultiLayerWellTopNode(mlw_id)
        x_mlw    = doc.getX(top_node)
        y_mlw    = doc.getY(top_node)

        dists    = np.sqrt((wx - x_mlw) ** 2 + (wy - y_mlw) ** 2)
        best_row = int(np.argmin(dists))

        row           = cfg.wells.iloc[best_row]
        name          = str(row["name"])
        is_injection  = bool(row["is_injection"])
        rate_m3d      = abs(float(row["rate_lps"])) * _LS_TO_M3D

        result.append(WellInfo(mlw_id, name, is_injection, rate_m3d))
        log.debug(
            "MLW %d → %s  (%s)  dist=%.1f m  rate=%.1f m3/d",
            mlw_id, name,
            "injection" if is_injection else "production",
            dists[best_row], rate_m3d,
        )

    prod = [w for w in result if not w.is_injection]
    inj  = [w for w in result if w.is_injection]
    log.info(
        "MLW map: %d total  (%d production, %d injection)",
        len(result), len(prod), len(inj),
    )
    return result


# ---------------------------------------------------------------------------
# Production temperature extraction (thermal breakthrough)
# ---------------------------------------------------------------------------

def extract_production_temperatures(
    doc,
    cfg:     GeothermalConfig,
    ifm,
    steps:   List,
    T_arr:   np.ndarray,
    h_arr:   np.ndarray,
    mlw_map: List[WellInfo],
) -> pd.DataFrame:
    """
    Read production-well temperature at every stored time step.

    Method
    ------
    For each time step i:
        1. activate_snapshot(doc, ifm, T_arr[i], h_arr[i]) — restores the
           in-memory field registers from the NPZ snapshot (replaces loadTimeStep)
        2. For each production MLW:
               top_node = getMultiLayerWellTopNode(mlw_id)
               T = getResultsTransportHeatValue(top_node)
    The top node is the shallowest screened node, in the reservoir layer —
    the appropriate location for production-temperature monitoring.

    Parameters
    ----------
    doc:
        Loaded FEFLOW document.
    cfg:
        GeothermalConfig (T_inj for reference).
    steps:
        List of (index, time_d) tuples from load_snapshots().
    mlw_map:
        List of WellInfo from _build_mlw_map().

    Returns
    -------
    DataFrame with columns: time_d, time_yr, well_name, T_prod_C.
    """
    prod_wells = [w for w in mlw_map if not w.is_injection]
    if not prod_wells:
        raise RuntimeError(
            "No production wells found in MLW map. "
            "Check cfg.wells and Stage 08."
        )

    # Cache top nodes — they do not change between time steps
    top_nodes: Dict[int, int] = {
        w.mlw_id: doc.getMultiLayerWellTopNode(w.mlw_id)
        for w in prod_wells
    }

    records: List[Dict] = []
    n_steps = len(steps)

    for i, (step_no, time_d) in enumerate(steps):
        activate_snapshot(doc, ifm, T_arr[i], h_arr[i])

        if i % 5 == 0 or i == n_steps - 1:
            log.info("  Reading T at t = %.0f d (step %d of %d)", time_d, i + 1, n_steps)

        for w in prod_wells:
            node = top_nodes[w.mlw_id]
            T    = doc.getResultsTransportHeatValue(node)
            records.append({
                "time_d":    time_d,
                "time_yr":   time_d / 365.25,
                "well_name": w.name,
                "T_prod_C":  T,
            })

    df = pd.DataFrame(records)
    if df.empty:
        log.warning("extract_production_temperatures: empty DataFrame.")
    else:
        log.info(
            "Extracted T_prod for %d wells × %d steps  "
            "(T range: %.2f … %.2f °C)",
            len(prod_wells), n_steps,
            df["T_prod_C"].min(), df["T_prod_C"].max(),
        )
    return df


# ---------------------------------------------------------------------------
# Thermal power
# ---------------------------------------------------------------------------

def compute_thermal_power(
    df_prod:  pd.DataFrame,
    cfg:      GeothermalConfig,
    mlw_map:  List[WellInfo],
) -> pd.DataFrame:
    """
    Compute thermal power P_th [MW] at each output time.

    Formula (SI)
    ------------
    P_W = rho_Cp [J/(m3·K)] * Q_prod [m3/s] * |dT| [K]
    P_MW = P_W / 1e6

    where:
        rho_Cp   = _RHO_CP_WATER = 4.1868e6 J/(m3·K)  (water at ~60 °C)
        Q_prod   = total production flow rate [m3/d] / 86400 [s/d]
        dT       = T_prod_avg - cfg.T_inj  [K = °C]

    The total production rate Q_prod is the sum of all production-well rates
    from cfg.wells (column rate_lps, converted to m3/d).  This uses real
    workbook rates rather than a hardcoded value.

    Budget API note
    ---------------
    budgetHeatCreate() cannot be called on a loaded DAC; it requires a running
    simulator with a PostTimeStep callback.  The analytical formula above is
    the only correct post-hoc approach.

    Parameters
    ----------
    df_prod:
        DataFrame from extract_production_temperatures().
    cfg:
        GeothermalConfig; cfg.T_inj is the reinjection temperature [°C].
    mlw_map:
        List of WellInfo — used to sum production rates.

    Returns
    -------
    DataFrame with columns: time_d, time_yr, T_prod_avg, dT, P_MW.
    """
    prod_wells = [w for w in mlw_map if not w.is_injection]
    Q_prod_m3d = sum(w.rate_m3d for w in prod_wells)
    Q_prod_m3s = Q_prod_m3d / _S_PER_DAY

    log.info(
        "Thermal power: Q_prod = %.1f m3/d = %.4f m3/s  (sum of %d wells)",
        Q_prod_m3d, Q_prod_m3s, len(prod_wells),
    )

    df_avg = (
        df_prod
        .groupby(["time_d", "time_yr"], sort=True)["T_prod_C"]
        .mean()
        .reset_index()
        .rename(columns={"T_prod_C": "T_prod_avg"})
    )
    df_avg["dT"]   = df_avg["T_prod_avg"] - cfg.T_inj
    df_avg["P_W"]  = _RHO_CP_WATER * Q_prod_m3s * df_avg["dT"]
    df_avg["P_MW"] = df_avg["P_W"] / 1e6
    df_avg = df_avg.drop(columns=["P_W"])

    P0 = _RHO_CP_WATER * Q_prod_m3s * (cfg.slice_T[1] - cfg.T_inj) / 1e6
    log.info(
        "Initial thermal power (T_res=%.2f °C, T_inj=%.1f °C): P0 = %.2f MW_th",
        cfg.slice_T[1], cfg.T_inj, P0,
    )
    return df_avg


# ---------------------------------------------------------------------------
# Figure F1: Temperature plan-view maps
# ---------------------------------------------------------------------------

def plot_temperature_maps(
    doc,
    cfg:   GeothermalConfig,
    ifm,
    steps: List,
    T_arr: np.ndarray,
    h_arr: np.ndarray,
) -> None:
    """
    Figure F1: Temperature plan-view at Slice 2 (top of reservoir) for five
    selected simulation times: 0, 10, 30, 50, and 100 years.

    Uses matplotlib.tri.Triangulation + tricontourf() for a continuous field
    representation (replaces scatter, which produced visually poor results on
    the irregular FEFLOW mesh).

    Well overlays
    -------------
    Production wells: red upward triangles (▲).
    Injection wells : blue downward triangles (▼).
    Labels are drawn next to each marker.

    Colorbar
    --------
    One shared colorbar, identical vmin/vmax across all panels.
    vmin = cfg.T_inj  (reinjection temperature)
    vmax = cfg.slice_T[1]  (undisturbed reservoir temperature at Slice 2)
    """
    import matplotlib.tri as mtri
    import matplotlib.lines as mlines

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    nps = doc.getNumberOfNodesPerSlice()

    xs_m = np.array([doc.getX(n) for n in range(nps)])
    ys_m = np.array([doc.getY(n) for n in range(nps)])
    xs_km = xs_m / 1000.0
    ys_km = ys_m / 1000.0

    # Build Delaunay triangulation once — shared across all panels
    triang = mtri.Triangulation(xs_km, ys_km)

    target_years = [0, 10, 30, 50, 100]
    times_d = [s[1] for s in steps]
    step_indices: List[Optional[int]] = []
    for yr in target_years:
        if yr == 0:
            step_indices.append(None)   # initial condition, not in NPZ
        else:
            t_target = yr * 365.25
            diffs = [abs(t - t_target) for t in times_d]
            step_indices.append(int(np.argmin(diffs)))

    vmin   = cfg.T_inj        # injection temperature (cold end)
    vmax   = cfg.slice_T[1]   # undisturbed reservoir temperature (warm end)
    levels = np.linspace(vmin, vmax, 21)

    # Well positions in km (from cfg.wells, which has "x"/"y" columns)
    prod_df = cfg.wells[~cfg.wells["is_injection"]]
    inj_df  = cfg.wells[cfg.wells["is_injection"]]
    wx_prod = prod_df["x"].to_numpy(dtype=float) / 1000.0
    wy_prod = prod_df["y"].to_numpy(dtype=float) / 1000.0
    wn_prod = prod_df["name"].tolist()
    wx_inj  = inj_df["x"].to_numpy(dtype=float) / 1000.0
    wy_inj  = inj_df["y"].to_numpy(dtype=float) / 1000.0
    wn_inj  = inj_df["name"].tolist()

    fig, axes = plt.subplots(
        1, len(target_years),
        figsize=(22, 5),
        constrained_layout=True,
    )

    domain_km = cfg.domain_size / 1000.0
    tcf_handle = None

    for ax, yr, s_idx in zip(axes, target_years, step_indices):
        if s_idx is None:
            T_slice2 = np.full(nps, cfg.slice_T[1])
        else:
            activate_snapshot(doc, ifm, T_arr[s_idx], h_arr[s_idx])
            all_T    = doc.getParamValues(ifm.Enum.P_TEMP)
            T_slice2 = np.array(all_T[nps : 2 * nps])

        tcf = ax.tricontourf(
            triang, T_slice2,
            levels=levels,
            cmap="RdYlBu_r",
            vmin=vmin, vmax=vmax,
            extend="both",
        )
        tcf_handle = tcf

        # Production wells — red upward triangle
        ax.scatter(
            wx_prod, wy_prod,
            c="red", s=120, marker="^",
            zorder=6, edgecolors="k", linewidths=0.7,
        )
        for x, y, name in zip(wx_prod, wy_prod, wn_prod):
            ax.annotate(
                name, (x, y),
                xytext=(0, 6), textcoords="offset points",
                fontsize=6, color="darkred",
                ha="center", va="bottom", fontweight="bold",
            )

        # Injection wells — blue downward triangle
        ax.scatter(
            wx_inj, wy_inj,
            c="deepskyblue", s=120, marker="v",
            zorder=6, edgecolors="k", linewidths=0.7,
        )
        for x, y, name in zip(wx_inj, wy_inj, wn_inj):
            ax.annotate(
                name, (x, y),
                xytext=(0, -6), textcoords="offset points",
                fontsize=6, color="navy",
                ha="center", va="top", fontweight="bold",
            )

        ax.set_title(f"t = {yr} yr", fontsize=11, fontweight="bold", pad=6)
        ax.set_xlabel("X [km]", fontsize=9)
        ax.set_aspect("equal")
        ax.set_xlim(0, domain_km)
        ax.set_ylim(0, domain_km)
        ax.tick_params(labelsize=8)

    axes[0].set_ylabel("Y [km]", fontsize=9)

    # Shared colorbar
    cbar = fig.colorbar(
        tcf_handle, ax=axes.tolist(),
        label="Temperature [°C]",
        shrink=0.85, pad=0.01, aspect=30,
    )
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("Temperature [°C]", fontsize=9)

    # Legend for well types (shown on first panel only)
    prod_handle = mlines.Line2D(
        [], [], color="red", marker="^", linestyle="None",
        markersize=7, markeredgecolor="k", markeredgewidth=0.5,
        label="Production well",
    )
    inj_handle = mlines.Line2D(
        [], [], color="deepskyblue", marker="v", linestyle="None",
        markersize=7, markeredgecolor="k", markeredgewidth=0.5,
        label="Injection well",
    )
    axes[0].legend(
        handles=[prod_handle, inj_handle],
        fontsize=7, loc="upper left",
        framealpha=0.85, edgecolor="gray",
    )

    fig.suptitle(
        "Slice 2 temperature — Group 3 geothermal doublet",
        fontsize=13, fontweight="bold",
    )

    path = FIGURES_DIR / "F1_temperature_maps.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# Figure F2: Vertical cross-section
# ---------------------------------------------------------------------------

def plot_cross_section(
    doc,
    cfg:     GeothermalConfig,
    ifm,
    steps:   List,
    T_arr:   np.ndarray,
    h_arr:   np.ndarray,
    mlw_map: List[WellInfo],
) -> None:
    """
    Figure F2: Temperature cross-section along the doublet axis at t = 100 yr.

    Method
    ------
    1. Identify the injection well and the nearest production well from mlw_map.
    2. Sample N_POINTS along the line connecting them.
    3. At each sample point, read T for all 6 slices using:
           getResultsTransportHeatValueAtXYSlice(x, y, slice_0based)
       after loadTimeStep(last_step_index).
    4. Plot T as a 2D image: horizontal axis = distance along transect [m],
       vertical axis = elevation [m a.s.l.] from cfg.slice_elevations.

    getResultsTransportHeatValueAtXYSlice
    --------------------------------------
    Verified signature: getResultsTransportHeatValueAtXYSlice(x, y, slice)
        x, y   : coordinates in model space [m]
        slice  : 0-based slice index (0 = top slice = Slice 1)
    Returns float [deg C] at the current simulation time (set by loadTimeStep).
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Identify injection and production wells
    inj_wells  = [w for w in mlw_map if w.is_injection]
    prod_wells = [w for w in mlw_map if not w.is_injection]
    if not inj_wells or not prod_wells:
        log.warning("Cross-section skipped: need at least 1 injection + 1 production well.")
        return

    inj_node  = doc.getMultiLayerWellTopNode(inj_wells[0].mlw_id)
    prod_node = doc.getMultiLayerWellTopNode(prod_wells[0].mlw_id)
    x0, y0    = doc.getX(inj_node),  doc.getY(inj_node)
    x1, y1    = doc.getX(prod_node), doc.getY(prod_node)

    dist_total = float(np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2))
    log.info(
        "Cross-section: %s → %s  (distance = %.0f m)",
        inj_wells[0].name, prod_wells[0].name, dist_total,
    )

    # Sample coordinates
    t_vals = np.linspace(0.0, 1.0, _XSECT_N_POINTS)
    xs     = x0 + t_vals * (x1 - x0)
    ys     = y0 + t_vals * (y1 - y0)
    dists  = t_vals * dist_total

    n_slices = doc.getNumberOfSlices()

    # Activate last time step (t = 100 yr)
    last_idx = len(steps) - 1
    activate_snapshot(doc, ifm, T_arr[last_idx], h_arr[last_idx])
    t_final_d = steps[last_idx][1]

    # Build T grid: shape (n_slices, N_POINTS)
    T_grid = np.full((n_slices, _XSECT_N_POINTS), np.nan)
    for slc in range(n_slices):      # 0-based
        for j, (x, y) in enumerate(zip(xs, ys)):
            try:
                T_grid[slc, j] = doc.getResultsTransportHeatValueAtXYSlice(x, y, slc)
            except Exception:
                pass   # outside mesh: leave NaN

    # Z axis: use cfg.slice_elevations (design values)
    z_vals = np.array(cfg.slice_elevations)   # length = n_slices

    fig, ax = plt.subplots(figsize=(12, 6))

    im = ax.contourf(
        dists / 1000.0,               # km
        z_vals,
        T_grid,
        levels=20,
        cmap="RdYlBu_r",
        vmin=cfg.T_inj,
        vmax=cfg.slice_T[-1],
    )
    fig.colorbar(im, ax=ax, label="Temperature [°C]")

    # Mark well positions
    ax.axvline(0.0, color="blue", linestyle="--", lw=1.0,
               label=f"Injection: {inj_wells[0].name}")
    ax.axvline(dist_total / 1000.0, color="red", linestyle="--", lw=1.0,
               label=f"Production: {prod_wells[0].name}")

    ax.set_xlabel("Distance along doublet axis [km]")
    ax.set_ylabel("Elevation [m a.s.l.]")
    ax.set_title(
        f"Temperature cross-section at t = {t_final_d:.0f} d "
        f"({t_final_d / 365.25:.0f} yr) — Group 3"
    )
    ax.legend(fontsize=9)
    fig.tight_layout()

    path = FIGURES_DIR / "F2_cross_section.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# Figure F3: Thermal breakthrough curve
# ---------------------------------------------------------------------------

def plot_breakthrough_curve(
    df_prod: pd.DataFrame,
    cfg:     GeothermalConfig,
) -> None:
    """
    Figure F3: Production temperature vs. time for each well + average.

    Thermal breakthrough is defined as the arrival of the injected cold
    plume at the production wells.  The average production temperature
    is the primary metric for thermal power computation.

    No IFM calls — data are already extracted into df_prod.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))

    well_names = sorted(df_prod["well_name"].unique())
    for name in well_names:
        sub = df_prod[df_prod["well_name"] == name].sort_values("time_yr")
        ax.plot(sub["time_yr"], sub["T_prod_C"], "--", alpha=0.7,
                linewidth=1.2, label=name)

    df_avg = (
        df_prod
        .groupby("time_yr")["T_prod_C"]
        .mean()
        .reset_index()
        .sort_values("time_yr")
    )
    ax.plot(df_avg["time_yr"], df_avg["T_prod_C"],
            "k-", lw=2.0, label="Average production T")

    ax.axhline(cfg.T_inj, color="steelblue", linestyle=":",
               label=f"T_inj = {cfg.T_inj:.0f} °C")
    ax.axhline(cfg.slice_T[1], color="firebrick", linestyle=":",
               label=f"T_reservoir = {cfg.slice_T[1]:.1f} °C")

    ax.set_xlabel("Time [yr]")
    ax.set_ylabel("Production temperature [°C]")
    ax.set_title("Thermal breakthrough curve — Group 3 geothermal doublet")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, cfg.t_final / 365.25)

    fig.tight_layout()
    path = FIGURES_DIR / "F3_breakthrough_curve.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# Figure F4: Thermal power
# ---------------------------------------------------------------------------

def plot_thermal_power(
    df_power: pd.DataFrame,
    cfg:      GeothermalConfig,
    mlw_map:  List[WellInfo],
) -> None:
    """
    Figure F4: Thermal power P_th [MW_th] vs. time.

    P0 (theoretical maximum at undisturbed reservoir temperature) is shown
    as a reference line.

    No IFM calls — data already computed in compute_thermal_power().
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    prod_wells = [w for w in mlw_map if not w.is_injection]
    Q_prod_m3s = sum(w.rate_m3d for w in prod_wells) / _S_PER_DAY
    P0_MW      = _RHO_CP_WATER * Q_prod_m3s * (cfg.slice_T[1] - cfg.T_inj) / 1e6

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df_power["time_yr"], df_power["P_MW"],
            "b-o", markersize=4, lw=1.5, label="P_th [MW_th]")
    ax.axhline(P0_MW, color="gray", linestyle="--",
               label=f"P0 = {P0_MW:.2f} MW_th (undisturbed reservoir)")

    ax.set_xlabel("Time [yr]")
    ax.set_ylabel("Thermal power [MW_th]")
    ax.set_title("Thermal power over 100 years — Group 3 geothermal doublet")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, cfg.t_final / 365.25)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    path = FIGURES_DIR / "F4_thermal_power.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# Figure F5: Hydraulic head map
# ---------------------------------------------------------------------------

def plot_head_map(
    doc,
    cfg:   GeothermalConfig,
    ifm,
    steps: List,
    T_arr: np.ndarray,
    h_arr: np.ndarray,
) -> None:
    """
    Figure F5: Hydraulic head at Slice 2 at the final simulation time.

    The head field at t = 100 yr reflects the quasi-steady pumping pattern
    imposed by the MLW wells.

    Implementation
    --------------
    activate_snapshot(doc, ifm, T_arr[last_idx], h_arr[last_idx])
    all_h = getParamValues(P_HEAD)   → list[float], length = n_nodes
    h_slice2 = all_h[nps : 2*nps]   → Slice 2 values

    Note: Slice 2 (1-based) = nodes with global 0-based index in [nps, 2*nps-1].
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    nps = doc.getNumberOfNodesPerSlice()

    xs = np.array([doc.getX(n) for n in range(nps)])
    ys = np.array([doc.getY(n) for n in range(nps)])

    last_idx  = len(steps) - 1
    t_final_d = steps[last_idx][1]
    activate_snapshot(doc, ifm, T_arr[last_idx], h_arr[last_idx])

    all_h    = doc.getParamValues(ifm.Enum.P_HEAD)    # list[float]
    h_slice2 = np.array(all_h[nps : 2 * nps])         # Slice 2

    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(
        xs / 1000.0, ys / 1000.0,
        c=h_slice2,
        cmap="viridis",
        s=_SCATTER_SIZE, linewidths=0,
    )
    fig.colorbar(sc, ax=ax, label="Hydraulic head [m]")
    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_title(
        f"Hydraulic head — Slice 2 at t = {t_final_d:.0f} d "
        f"({t_final_d / 365.25:.0f} yr)"
    )
    ax.set_aspect("equal")
    ax.set_xlim(0, cfg.domain_size / 1000.0)
    ax.set_ylim(0, cfg.domain_size / 1000.0)
    fig.tight_layout()

    path = FIGURES_DIR / "F5_head_map.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)



# ---------------------------------------------------------------------------
# Figure F6: Hydraulic head evolution
# ---------------------------------------------------------------------------

def plot_head_evolution(
    doc,
    cfg:     GeothermalConfig,
    steps:   List,
    h_arr:   np.ndarray,
    mlw_map: List[WellInfo],
) -> None:
    """
    Figure F6: Hydraulic head at a representative production well and a
    representative injection well over the 100-year simulation.

    Replicates the "Hydraulic Head" diagnostic chart from the DHI FEFLOW
    geothermal tutorial, which shows the head drawdown/build-up caused by
    pumping as a function of time.

    Data source
    -----------
    ``h_arr`` (shape: n_snapshots × n_nodes) already contains all hydraulic
    head values at every stored time.  No ``activate_snapshot()`` or IFM
    call is needed here — the data is read directly from the NumPy array:

        h_at_node = h_arr[snapshot_index, global_node_index]

    The global node index of each well's top node is obtained once via
    ``doc.getMultiLayerWellTopNode(mlw_id)`` (verified FEFLOW 8.1 API).

    Time points
    -----------
    t = 0 is not stored in the NPZ (simulation starts stepping forward from 0).
    For t = 0 we use ``cfg.h_initial = 200 m`` (undisturbed hydraulic head
    everywhere in the domain — see Stage 06).

    Well selection
    --------------
    Uses the first production well and the first injection well in ``mlw_map``
    (sorted by mlw_id).  These are representative because all production wells
    have the same pumping rate and all injection wells have the same injection
    rate; head perturbations from different wells of the same type differ only
    slightly due to their spatial arrangement.

    Parameters
    ----------
    doc:
        Loaded FEFLOW document — used only for ``getMultiLayerWellTopNode``.
    cfg:
        GeothermalConfig — provides ``h_initial`` and ``t_final``.
    steps:
        List of (index, time_d) tuples from ``load_snapshots()``.
    h_arr:
        float32 array (n_snapshots, n_nodes) from the NPZ snapshot file.
    mlw_map:
        List of WellInfo from ``_build_mlw_map()``.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    prod_wells = [w for w in mlw_map if not w.is_injection]
    inj_wells  = [w for w in mlw_map if w.is_injection]

    if not prod_wells or not inj_wells:
        log.warning(
            "F6 skipped: need at least one production and one injection well "
            "in mlw_map (found %d prod, %d inj).",
            len(prod_wells), len(inj_wells),
        )
        return

    # Use first well of each type as representative
    rep_prod = prod_wells[0]
    rep_inj  = inj_wells[0]

    # Get global node indices (top of screen = shallowest reservoir slice)
    prod_node = doc.getMultiLayerWellTopNode(rep_prod.mlw_id)
    inj_node  = doc.getMultiLayerWellTopNode(rep_inj.mlw_id)

    log.info(
        "F6: production representative = '%s' (node %d), "
        "injection representative = '%s' (node %d)",
        rep_prod.name, prod_node, rep_inj.name, inj_node,
    )

    # Build time series, prepending t = 0 with undisturbed head
    times_yr: List[float] = [0.0]
    h_prod:   List[float] = [cfg.h_initial]
    h_inj:    List[float] = [cfg.h_initial]

    for i, (_, time_d) in enumerate(steps):
        times_yr.append(time_d / 365.25)
        # Direct array indexing — no IFM call, no activate_snapshot required
        h_prod.append(float(h_arr[i, prod_node]))
        h_inj.append(float(h_arr[i, inj_node]))

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(times_yr, h_prod, "r-o", markersize=5, lw=1.8,
            label=f"Production well: {rep_prod.name}")
    ax.plot(times_yr, h_inj,  "b-s", markersize=5, lw=1.8,
            label=f"Injection well: {rep_inj.name}")
    ax.axhline(
        cfg.h_initial, color="gray", linestyle=":",
        lw=1.2, label=f"Initial head = {cfg.h_initial:.0f} m",
    )

    ax.set_xlabel("Time [yr]", fontsize=10)
    ax.set_ylabel("Hydraulic head [m]", fontsize=10)
    ax.set_title(
        "Hydraulic head evolution — Group 3 geothermal doublet",
        fontsize=12,
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, cfg.t_final / 365.25)
    fig.tight_layout()

    path = FIGURES_DIR / "F6_head_evolution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# Figure F7: Adaptive timestep evolution
# ---------------------------------------------------------------------------

def plot_timestep_evolution(
    cfg:      GeothermalConfig,
    npz_path: Optional[Path] = None,
) -> None:
    """
    Figure F7: Adaptive time-step size vs. absolute simulation time.

    Replicates the "Time Steps" diagnostic panel from the DHI FEFLOW
    geothermal tutorial.  Uses a logarithmic y-axis to span the full
    dynamic range from the initial 1 × 10⁻¹⁰ d first step to the
    100 d maximum allowed step size.

    Data source
    -----------
    The NPZ snapshot file produced by Stage 10 must contain two arrays
    written by the singleStep() loop:

        ``time_abs_d``  float64 (n_accepted_steps,)  — absolute time [d]
        ``dt_d``        float64 (n_accepted_steps,)  — step size [d]

    These arrays are absent in NPZ files generated by Stage 10 builds
    prior to this feature being added.  In that case the function logs a
    warning and returns without producing a figure — no exception is raised,
    so the rest of Stage 11 continues normally.  Re-run Stage 10 to populate
    the arrays.

    Parameters
    ----------
    cfg:
        GeothermalConfig — provides ``t_final``, ``dt_max``, ``dt_initial``
        for axis limits and reference lines.
    npz_path:
        Path to the NPZ file.  Defaults to ``RESULTS_PATH.with_suffix('.npz')``.
        Override in tests by passing a temporary path.

    FEFLOW API
    ----------
    No IFM calls — all data is read from the NumPy archive.
    The diagnostic values (absolute time, step size) were captured in Stage 10
    using the verified ``getAbsoluteSimulationTime()`` getter.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    if npz_path is None:
        npz_path = RESULTS_PATH.with_suffix('.npz')

    if not Path(npz_path).exists():
        log.warning(
            "F7 skipped: NPZ not found at %s. "
            "Stage 10 must complete before F7 can be generated.",
            npz_path,
        )
        return

    data = np.load(str(npz_path))

    if 'time_abs_d' not in data or 'dt_d' not in data:
        log.warning(
            "F7 skipped: 'time_abs_d' / 'dt_d' arrays not present in %s. "
            "Re-run Stage 10 (which writes these arrays) to generate F7. "
            "Existing F1–F6 figures are unaffected.",
            Path(npz_path).name,
        )
        return

    time_abs_d = data['time_abs_d']   # float64 (n_steps,)
    dt_d       = data['dt_d']         # float64 (n_steps,)

    # Guard against zero or negative dt (should not occur, but safeguard
    # for the first step if t_prev initialisation ever drifts).
    mask       = dt_d > 0
    t_plot     = time_abs_d[mask]
    dt_plot    = dt_d[mask]

    if len(t_plot) == 0:
        log.warning("F7 skipped: all dt_d values are zero or negative.")
        return

    log.info(
        "F7: %d accepted steps  dt range [%.2e, %.2f] d  "
        "t range [%.2e, %.0f] d",
        len(t_plot), float(dt_plot.min()), float(dt_plot.max()),
        float(t_plot.min()), float(t_plot.max()),
    )

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(t_plot, dt_plot, "b-", lw=0.8, alpha=0.75,
            label="Accepted time-step size")
    ax.set_yscale("log")   # log y-axis required by tutorial

    # Reference lines for configured bounds
    ax.axhline(
        cfg.dt_max, color="red", linestyle="--", lw=1.2,
        label=f"dt_max = {cfg.dt_max:.0f} d",
    )
    ax.axhline(
        cfg.dt_initial, color="green", linestyle=":", lw=1.2,
        label=f"dt_initial = {cfg.dt_initial:.1e} d",
    )

    ax.set_xlabel("Simulation time [d]", fontsize=10)
    ax.set_ylabel("Time-step length [d]", fontsize=10)
    ax.set_title(
        "Adaptive time-step evolution — Group 3 simulation",
        fontsize=12,
    )
    ax.legend(fontsize=9)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xlim(0, cfg.t_final)

    fig.tight_layout()
    path = FIGURES_DIR / "F7_timestep_evolution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved: %s", path.name)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_thermal_power_table(df_power: pd.DataFrame) -> None:
    """
    Write the thermal power table to outputs/thermal_power_table.csv.

    Columns in output: time_d, time_yr, T_prod_avg, dT, P_MW.
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / "thermal_power_table.csv"
    df_power.to_csv(out, index=False, float_format="%.4f")
    log.info("Thermal power table saved: %s", out.name)

    display_cols = ["time_yr", "T_prod_avg", "dT", "P_MW"]
    log.info("\n%s", df_power[display_cols].to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    cfg = load_config()
    ifm = bootstrap_ifm()

    # --- Guard: check files exist ---
    fem_path = OUTPUTS_DIR / "Group3.fem"
    if not fem_path.exists():
        raise FileNotFoundError(
            f"FEM not found: {fem_path}\n"
            "Stage 10 must complete before Stage 11."
        )
    npz_path = RESULTS_PATH.with_suffix('.npz')
    if not npz_path.exists():
        raise FileNotFoundError(
            f"Snapshot file not found: {npz_path}\n"
            "Stage 10 must complete (singleStep loop) before Stage 11.\n"
            "Re-run Stage 10 to generate the NPZ snapshot file."
        )

    # --- Load document (DAC auto-attached from FEM reference) ---
    log.info("Loading model: %s", fem_path.name)
    doc = ifm.loadDocument(str(fem_path))

    # --- Load NPZ snapshots (replaces DAC enumeration) ---
    log.info("Loading simulation snapshots from NPZ:")
    steps, n_steps, T_arr, h_arr = load_snapshots(cfg)

    # --- MLW → well mapping ---
    log.info("Building MLW-to-well map:")
    mlw_map = _build_mlw_map(doc, cfg)

    # --- Production temperatures (activate_snapshot replaces loadTimeStep) ---
    log.info("Extracting production temperatures (%d steps):", n_steps)
    df_prod = extract_production_temperatures(doc, cfg, ifm, steps, T_arr, h_arr, mlw_map)

    if df_prod.empty:
        log.error(
            "No production temperature data extracted. "
            "Check MLW well assignment (Stage 08) and NPZ content."
        )
        return

    # --- Thermal power ---
    df_power = compute_thermal_power(df_prod, cfg, mlw_map)

    # --- Figures ---
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Generating F1 (temperature maps):")
    plot_temperature_maps(doc, cfg, ifm, steps, T_arr, h_arr)

    log.info("Generating F2 (cross-section):")
    plot_cross_section(doc, cfg, ifm, steps, T_arr, h_arr, mlw_map)

    log.info("Generating F3 (breakthrough curve):")
    plot_breakthrough_curve(df_prod, cfg)

    log.info("Generating F4 (thermal power):")
    plot_thermal_power(df_power, cfg, mlw_map)

    log.info("Generating F5 (head map):")
    plot_head_map(doc, cfg, ifm, steps, T_arr, h_arr)

    log.info("Generating F6 (head evolution):")
    plot_head_evolution(doc, cfg, steps, h_arr, mlw_map)

    log.info("Generating F7 (timestep evolution):")
    plot_timestep_evolution(cfg)

    # --- CSV ---
    export_thermal_power_table(df_power)

    log.info(
        "Stage 11 complete — %d figures + 1 CSV saved.",
        7,
    )
    log.info("Figures : %s", FIGURES_DIR)
    log.info("Outputs : %s", OUTPUTS_DIR)


if __name__ == "__main__":
    main()
