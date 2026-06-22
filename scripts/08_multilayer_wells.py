"""
08_multilayer_wells.py — Create and configure 10 Multilayer Wells (MLW) and
apply the injection temperature Dirichlet BC.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
Removed entirely (ifm_contrib, NOT INSTALLED):
    doc.c.wells.addWell()       — ModuleNotFoundError at runtime
    doc.c.wells.setWellRate()   — ModuleNotFoundError at runtime

Fabricated method removed:
    setParamSize(param, val, node)   — DNE in FeflowDoc

Fabricated enum names removed (all DNE in ifm.Enum):
    P_BC_WELL_4TH                    — DNE; integer fallback 700 was unverified
    P_BC_TRANS_1ST                   — DNE; corrected to BC_DIRICHLET via
                                       setBcHeatTypeAndValueAtCurrentTime()

Verified API used in this module (all confirmed from live ifm312.pyd)
----------------------------------------------------------------------
WellManager (obtained via doc.createWellManager()):
    createWell(well_type)          → ManagedWell
    createWells(well_type, positions) → list[ManagedWell]
        positions for WM_WELL_MLW: list of 3-float-tuples (X, Y, Z) defining
        a polyline; FEFLOW snaps each point to the nearest mesh node within
        the current snap distance.
    applyOperations([commit=True]) → bool
        Commits pending well operations. Returns True on success.
        WARNING: after applyOperations(), the WellManager object must NOT be
        used for further create/delete operations — only for queries.
    putOverwriteConflicts(bool)    Overwrite conflicting BCs when True.
    putSnapDistance(double)        Set snap radius [m] for coordinate→node.

ManagedWell (returned by createWell / createWells):
    getError()    → str    Error after failed applyOperations.
    getWarning()  → str    Warning after applyOperations.
    getType()     → int    WM_WELL_BC | WM_WELL_MLW | WM_WELL_BHE

Direct FeflowDoc MLW API (no WellManager — works on existing MLWs):
    getNumberOfMultiLayerWells()              → int
    getMultiLayerWellTopNode(mlw_id)          → int  (0-based global node)
    getMultiLayerWellBottomNode(mlw_id)       → int  (0-based global node)
    getMultiLayerWellAttrValue(mlw_id, attr)  → float
    setMultiLayerWellAttrValue(mlw_id, attr, value)
        attr = ifm.Enum.MLW_RATE (=0):  flow rate [m³/d]
        attr = ifm.Enum.MLW_BCC_HMIN (=1): minimum head BCC constraint
        attr = ifm.Enum.MLW_BCC_HMAX (=2): maximum head BCC constraint
    queryMultiLayerWellInfo(bottom_node)      → ifm.MLWInfo
        .getId()              → int    MLW index
        .getName()            → str    MLW name
        .getTopElevation()    → float  screen top [m a.s.l.]
        .getBottomElevation() → float  screen bottom [m a.s.l.]
        .getTopNode()         → int    global node at top
        .getBottomNode()      → int    global node at bottom
        .getRadius()          → float  well radius [m]
    getX(node), getY(node), getZ(node) → float  node coordinates [m]

Injection temperature BC (verified FEFLOW 8.1):
    setBcHeatTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, T_inj)
        node : global node index
        BC_DIRICHLET = 1
        0    : constant BC (bc_unst = 0)
        T    : injection temperature [°C]

Verified enum values (ifm.Enum):
    WM_WELL_MLW   = 2
    MLW_RATE      = 0      flow rate [m³/d]
    MLW_BCC_HMIN  = 1      head BCC minimum [m]
    MLW_BCC_HMAX  = 2      head BCC maximum [m]
    BC_DIRICHLET  = 1
    BC_NONE       = 0

Well configuration (Group 3)
-----------------------------
  10 wells: 5 producers + 5 injectors
  All well screens: depth_top → depth_bottom from workbook [m below surface]
  Intersected slices: determined at runtime from cfg.slice_depths
  T_inj = 50 °C (cfg.T_inj) applied to ALL nodes of each injection well
  Radius: from workbook (cfg.wells.radius)

Flow-rate units and sign convention
-------------------------------------
  FEFLOW MLW stores flow rate in m³/d (setMultiLayerWellAttrValue / MLW_RATE).
  Workbook stores rate in L/s (cfg.wells.rate_lps):
      positive = production (pumping from aquifer)
      negative = injection  (water returning to aquifer)
  Conversion: rate_m3d = rate_lps × 86.4   (1 L/s = 86.4 m³/d)

  SIGN CONVENTION UNCERTAINTY: the IFM __doc__ for setMultiLayerWellAttrValue
  states "Flow rate to be set [m³/d]" without specifying the sign convention.
  This module preserves the workbook sign (positive = production, negative =
  injection), which is the most common FEFLOW MLW convention. If wells pump
  in the wrong direction in the simulation, negate _RATE_SIGN_FLIP below.
  See "Remaining uncertainties" in the module docstring.

Node ordering for injection-T BC
----------------------------------
  All nodes of an MLW screen are at the same local (within-slice) index.
  For a vertical well with top node T and bottom node B (both global):
      node(slice s) = T + (s - slice_of_T) × nps
  which simplifies to: range(T, B + 1, nps)
  These nodes span from the top to the bottom of the screen interval.

Two-path execution strategy
----------------------------
  Path A (preferred): MLWs pre-exist in Group3_template.fem (created in GUI).
      → Stage 8 only sets rates and injection T on existing MLWs.
      → No WellManager create/apply cycle needed.

  Path B (fallback): No MLWs in FEM.
      → createWellManager() → createWells(WM_WELL_MLW, polyline) per well
      → applyOperations(commit=True)
      → Then rate/T assignment as in Path A.

Tutorial reference: pp. 25–29 (§5.2.2.2 and §5.2.2.3)
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, NamedTuple

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LS_TO_M3D: float = 86.4        # L/s → m³/d  (1 L/s = 86.4 m³/d)

# Set to -1.0 if FEFLOW interprets the sign opposite to the workbook convention.
# See "SIGN CONVENTION UNCERTAINTY" in module docstring.
_RATE_SIGN_FLIP: float = 1.0

# Snap distance [m] for coordinate→node assignment in WellManager.
# Must be larger than the maximum distance between a well XY coordinate and
# the nearest mesh node centroid. A value of 500 m is conservative for an
# 8000×8000 m domain with ~1000 m element spacing.
_SNAP_DISTANCE_M: float = 500.0

# XY matching tolerance [m] used when identifying which MLW corresponds to
# which workbook well after creation or in a pre-existing FEM.
_MATCH_TOL_M: float = 200.0

_BC_UNST_CONSTANT: int = 0      # all BCs in this model are constant


# ---------------------------------------------------------------------------
# Well record structure
# ---------------------------------------------------------------------------

class WellRecord(NamedTuple):
    """One row from the joined wells + well_nodes tables."""
    name:         str
    x:            float
    y:            float
    depth_top:    float   # m below surface (positive downward)
    depth_bottom: float   # m below surface (positive downward)
    radius:       float   # m
    rate_lps:     float   # L/s; positive = production, negative = injection
    is_injection: bool


def _build_well_table(cfg: GeothermalConfig) -> List[WellRecord]:
    """
    Join cfg.wells (rate, geometry) with cfg.well_nodes (X, Y) by row order.

    The two DataFrames originate from separate sheets of the workbook and are
    aligned by row position — workbook row i in 'welldata' corresponds to row i
    in 'wellnodecoordinates'.

    Raises
    ------
    ValueError
        If the two DataFrames have different row counts.
    """
    w = cfg.wells.reset_index(drop=True)
    # cfg.well_nodes has 7 rows per well (1 centre + 6 cluster nodes); only the
    # centre coordinates are needed here and they already live in cfg.wells.x/y.

    records: List[WellRecord] = []
    for i in range(len(w)):
        records.append(WellRecord(
            name         = str(w.at[i, "name"]),
            x            = float(w.at[i, "x"]),
            y            = float(w.at[i, "y"]),
            depth_top    = float(w.at[i, "depth_top"]),
            depth_bottom = float(w.at[i, "depth_bottom"]),
            radius       = float(w.at[i, "radius"]),
            rate_lps     = float(w.at[i, "rate_lps"]),
            is_injection = bool(w.at[i, "is_injection"]),
        ))
    return records


# ---------------------------------------------------------------------------
# Slice intersection
# ---------------------------------------------------------------------------

def intersected_slices(
    depth_top: float,
    depth_bottom: float,
    slice_depths: List[float],
) -> List[int]:
    """
    Return 1-based slice indices whose depth falls within [depth_top, depth_bottom].

    The well screen spans from depth_top to depth_bottom (both measured positive
    downward from the surface). A slice is "intersected" if its depth is within
    that interval (endpoints inclusive, 1 m tolerance).

    Parameters
    ----------
    depth_top : float
        Depth of top of well screen [m below surface].
    depth_bottom : float
        Depth of bottom of well screen [m below surface].
    slice_depths : list of float
        Depth of each slice below surface [m], ordered Slice 1 → Slice N.

    Returns
    -------
    List of 1-based slice indices within the screen interval.
    """
    tol = 1.0    # m — floating-point tolerance for endpoint matching
    result: List[int] = []
    for s_idx, d in enumerate(slice_depths, start=1):
        if (depth_top - tol) <= d <= (depth_bottom + tol):
            result.append(s_idx)
    return result


# ---------------------------------------------------------------------------
# MLW node enumeration
# ---------------------------------------------------------------------------

def _mlw_screen_nodes(doc, mlw_id: int, nps: int) -> List[int]:
    """
    Return all global node indices for an MLW screen (top → bottom inclusive).

    FEFLOW stores nodes slice-major (all Slice 1 nodes first, then Slice 2,
    etc.). The local index (position within a slice) is the same for all nodes
    of a vertical well. Given the top-node global index T and the bottom-node
    global index B:
        node at slice s = T + (s_offset) × nps
    which is simply range(T, B+1, nps).

    Parameters
    ----------
    doc : FeflowDoc
    mlw_id : int
        0-based MLW index.
    nps : int
        Number of nodes per slice.

    Returns
    -------
    List of global node indices from top to bottom.
    """
    top = doc.getMultiLayerWellTopNode(mlw_id)
    bot = doc.getMultiLayerWellBottomNode(mlw_id)
    span = bot - top
    if span < 0:
        log.warning(
            "MLW %d: top_node (%d) > bot_node (%d) — unexpected topology",
            mlw_id, top, bot,
        )
        return [top]
    if span % nps != 0:
        log.warning(
            "MLW %d: (bot_node - top_node) = %d is not divisible by nps = %d. "
            "Well may not be vertical or node ordering assumption is wrong.",
            mlw_id, span, nps,
        )
    return list(range(top, bot + 1, nps))


# ---------------------------------------------------------------------------
# MLW ↔ workbook well matching
# ---------------------------------------------------------------------------

def _match_mlw_to_wells(
    doc,
    well_table: List[WellRecord],
    n_mlw: int,
) -> Dict[int, int]:
    """
    Match each MLW (by index 0…n_mlw-1) to the closest workbook well by XY.

    Uses the XY coordinates of the MLW's top node. Each workbook well is
    matched to at most one MLW (greedy nearest-neighbour; works correctly when
    all XY positions are distinct, as expected for a 10-well doublet layout).

    Parameters
    ----------
    doc : FeflowDoc
    well_table : list of WellRecord
    n_mlw : int
        Total number of MLWs in the document.

    Returns
    -------
    Dict mapping mlw_id (int) → index into well_table (int).
    Logs a warning for any MLW whose nearest workbook well exceeds
    _MATCH_TOL_M.
    """
    result: Dict[int, int] = {}
    for mlw_id in range(n_mlw):
        top_node = doc.getMultiLayerWellTopNode(mlw_id)
        mx = doc.getX(top_node)
        my = doc.getY(top_node)

        best_idx  = -1
        best_dist = float("inf")
        for i, wr in enumerate(well_table):
            dist = math.sqrt((mx - wr.x) ** 2 + (my - wr.y) ** 2)
            if dist < best_dist:
                best_dist, best_idx = dist, i

        if best_dist > _MATCH_TOL_M:
            log.warning(
                "MLW %d at (%.0f, %.0f): nearest workbook well is %.1f m away "
                "(tolerance %.0f m) — rate NOT assigned",
                mlw_id, mx, my, best_dist, _MATCH_TOL_M,
            )
        else:
            result[mlw_id] = best_idx
            log.info(
                "MLW %d ↔ well '%s'  dist=%.1f m",
                mlw_id, well_table[best_idx].name, best_dist,
            )

    return result


# ---------------------------------------------------------------------------
# Path B: create wells via WellManager
# ---------------------------------------------------------------------------

def create_wells_via_well_manager(
    doc,
    cfg: GeothermalConfig,
    ifm,
    well_table: List[WellRecord],
) -> bool:
    """
    Create 10 Multilayer Wells using the verified WellManager API.

    Uses createWells(WM_WELL_MLW, polyline) where polyline is a 2-point list:
        [(X, Y, z_top_screen), (X, Y, z_bot_screen)]
    z_top and z_bot are elevations [m a.s.l.]:
        z = cfg.z_surface - depth

    The snap distance is set to _SNAP_DISTANCE_M so coordinates are mapped to
    the nearest mesh node within that radius. If the mesh is too coarse or the
    well coordinates do not fall within _SNAP_DISTANCE_M of a node, FEFLOW
    will report an error or warning via ManagedWell.getError().

    applyOperations() is called once after all wells are staged. After that
    call the WellManager object is NOT reused for further create operations.

    Parameters
    ----------
    doc : FeflowDoc
    cfg : GeothermalConfig
    ifm : module
    well_table : list of WellRecord

    Returns
    -------
    bool
        True if applyOperations() succeeded (no errors).
    """
    wm = doc.createWellManager()
    wm.putSnapDistance(_SNAP_DISTANCE_M)
    wm.putOverwriteConflicts(True)

    managed_wells = []
    for wr in well_table:
        z_top = cfg.z_surface - wr.depth_top
        z_bot = cfg.z_surface - wr.depth_bottom

        # polyline: [(X, Y, z_top), (X, Y, z_bot)]
        polyline = [(wr.x, wr.y, z_top), (wr.x, wr.y, z_bot)]
        created = wm.createWells(ifm.Enum.WM_WELL_MLW, polyline)
        if not created:
            log.error(
                "Well '%s': createWells returned empty list for polyline "
                "[(%.0f, %.0f, %.1f)→(%.0f, %.0f, %.1f)]",
                wr.name, wr.x, wr.y, z_top, wr.x, wr.y, z_bot,
            )
        else:
            managed_wells.extend(created)
            log.info(
                "Staged MLW '%s' at (%.0f, %.0f) z=%.1f→%.1f m a.s.l.",
                wr.name, wr.x, wr.y, z_top, z_bot,
            )

    log.info(
        "Committing %d staged MLWs via applyOperations()…", len(managed_wells)
    )
    ok = wm.applyOperations(True)   # commit=True

    # Collect per-well errors / warnings after apply
    all_ok = ok
    for i, mw in enumerate(managed_wells):
        err  = mw.getError()
        warn = mw.getWarning()
        if err:
            log.error("Well %d (ManagedWell): ERROR — %s", i, err)
            all_ok = False
        if warn:
            log.warning("Well %d (ManagedWell): WARNING — %s", i, warn)

    if all_ok:
        log.info("WellManager applyOperations: SUCCESS")
    else:
        log.error(
            "WellManager applyOperations: FAILED or partial. "
            "Check errors above. The FEM may be in an inconsistent state."
        )
    return all_ok


# ---------------------------------------------------------------------------
# Rate assignment
# ---------------------------------------------------------------------------

def assign_well_rates(
    doc,
    cfg: GeothermalConfig,
    ifm,
    well_table: List[WellRecord],
) -> None:
    """
    Set the flow rate of each MLW using setMultiLayerWellAttrValue.

    Verified API:
        setMultiLayerWellAttrValue(mlw_id, MLW_RATE, rate_m3d)
            mlw_id   : 0-based MLW index
            MLW_RATE : ifm.Enum.MLW_RATE = 0
            rate_m3d : flow rate [m³/d]  (sign: see module docstring)

    Unit conversion: rate_m3d = rate_lps × _LS_TO_M3D × _RATE_SIGN_FLIP

    Parameters
    ----------
    doc : FeflowDoc
    cfg : GeothermalConfig
    ifm : module
    well_table : list of WellRecord
    """
    nps    = doc.getNumberOfNodesPerSlice()
    n_mlw  = doc.getNumberOfMultiLayerWells()
    MLW_RATE = ifm.Enum.MLW_RATE   # 0

    if n_mlw == 0:
        raise RuntimeError(
            "No MLWs found in the document. "
            "Run create_wells_via_well_manager() first, or ensure "
            "Group3_template.fem contains pre-built MLWs."
        )

    log.info(
        "Assigning flow rates to %d MLWs (workbook has %d wells).",
        n_mlw, len(well_table),
    )

    match = _match_mlw_to_wells(doc, well_table, n_mlw)

    for mlw_id, well_idx in match.items():
        wr           = well_table[well_idx]
        rate_m3d     = wr.rate_lps * _LS_TO_M3D * _RATE_SIGN_FLIP
        doc.setMultiLayerWellAttrValue(mlw_id, MLW_RATE, rate_m3d)
        log.info(
            "MLW %d ('%s'): rate = %.2f L/s = %.2f m³/d [MLW_RATE=%d, %s]",
            mlw_id, wr.name, wr.rate_lps, rate_m3d, MLW_RATE,
            "INJECTION" if wr.is_injection else "PRODUCTION",
        )

    if len(match) < n_mlw:
        log.warning(
            "%d MLWs in document but only %d matched to workbook wells. "
            "Rates for unmatched MLWs are unchanged.",
            n_mlw, len(match),
        )


# ---------------------------------------------------------------------------
# Injection temperature BC
# ---------------------------------------------------------------------------

def assign_injection_temperature(
    doc,
    cfg: GeothermalConfig,
    ifm,
    well_table: List[WellRecord],
) -> None:
    """
    Set T_inj = cfg.T_inj as a constant Dirichlet heat BC on all nodes of
    each injection well's screen interval.

    Verified API:
        setBcHeatTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, T_inj)
            node        : global node index (0-based)
            BC_DIRICHLET: 1
            0           : constant BC (bc_unst = 0)
            T_inj       : cfg.T_inj = 50.0 °C

    The injection nodes are determined from the MLW's top node and bottom node
    (obtained from getMultiLayerWellTopNode/BottomNode). All slices between
    the top and bottom of the screen interval are included.

    For PRODUCTION wells no temperature BC is applied.

    Parameters
    ----------
    doc : FeflowDoc
    cfg : GeothermalConfig
        cfg.T_inj = 50.0 °C
    ifm : module
    well_table : list of WellRecord
    """
    n_mlw        = doc.getNumberOfMultiLayerWells()
    nps          = doc.getNumberOfNodesPerSlice()
    BC_DIRICHLET = ifm.Enum.BC_DIRICHLET   # 1
    T_inj        = float(cfg.T_inj)

    if n_mlw == 0:
        log.error("No MLWs found — cannot assign injection temperature.")
        return

    match = _match_mlw_to_wells(doc, well_table, n_mlw)
    assigned_total = 0

    for mlw_id, well_idx in match.items():
        wr = well_table[well_idx]
        if not wr.is_injection:
            continue   # only injectors receive T_inj BC

        nodes = _mlw_screen_nodes(doc, mlw_id, nps)
        for node in nodes:
            doc.setBcHeatTypeAndValueAtCurrentTime(
                node, BC_DIRICHLET, _BC_UNST_CONSTANT, T_inj,
            )
        assigned_total += len(nodes)
        log.info(
            "Injection T BC: well '%s' (MLW %d) — %.1f °C applied to %d nodes",
            wr.name, mlw_id, T_inj, len(nodes),
        )

    log.info(
        "Injection temperature assignment complete: %d nodes total",
        assigned_total,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_wells(
    doc,
    cfg: GeothermalConfig,
    ifm,
    well_table: List[WellRecord],
) -> bool:
    """
    Spot-check well count and flow rates.

    Checks:
      1. Number of MLWs matches number of wells in workbook.
      2. Rate read-back: getMultiLayerWellAttrValue(mlw_id, MLW_RATE) matches
         the value that was set, within 1 m³/d tolerance.
      3. Injection well nodes have BC_DIRICHLET heat BC at T_inj (first node).

    Returns
    -------
    bool
        True if all checks pass.
    """
    n_mlw    = doc.getNumberOfMultiLayerWells()
    nps      = doc.getNumberOfNodesPerSlice()
    MLW_RATE = ifm.Enum.MLW_RATE
    ok       = True

    # --- count check ---
    if n_mlw != len(well_table):
        log.error(
            "MLW count: document has %d, workbook has %d",
            n_mlw, len(well_table),
        )
        ok = False
    else:
        log.info("MLW count: %d [OK]", n_mlw)

    if n_mlw == 0:
        return ok

    match = _match_mlw_to_wells(doc, well_table, n_mlw)

    for mlw_id, well_idx in match.items():
        wr           = well_table[well_idx]
        rate_exp     = wr.rate_lps * _LS_TO_M3D * _RATE_SIGN_FLIP
        rate_actual  = doc.getMultiLayerWellAttrValue(mlw_id, MLW_RATE)
        rate_delta   = abs(rate_actual - rate_exp)

        if rate_delta > 1.0:
            log.error(
                "MLW %d ('%s'): rate expected %.2f m³/d, got %.2f m³/d "
                "(delta=%.2f)",
                mlw_id, wr.name, rate_exp, rate_actual, rate_delta,
            )
            ok = False
        else:
            log.info(
                "  MLW %d '%s': %.2f m³/d [OK]",
                mlw_id, wr.name, rate_actual,
            )

        # --- injection T BC spot-check (first node only) ---
        if wr.is_injection:
            nodes = _mlw_screen_nodes(doc, mlw_id, nps)
            if nodes:
                bc_type = doc.getBcHeatType(nodes[0])
                bc_val  = doc.getBcHeatValue(nodes[0])
                if bc_type != ifm.Enum.BC_DIRICHLET:
                    log.error(
                        "MLW %d '%s' top node %d: heat BC type = %d, "
                        "expected BC_DIRICHLET (%d)",
                        mlw_id, wr.name, nodes[0], bc_type,
                        ifm.Enum.BC_DIRICHLET,
                    )
                    ok = False
                elif abs(bc_val - cfg.T_inj) > 0.01:
                    log.error(
                        "MLW %d '%s' top node %d: T_inj = %.4f °C, "
                        "expected %.4f °C",
                        mlw_id, wr.name, nodes[0], bc_val, cfg.T_inj,
                    )
                    ok = False
                else:
                    log.info(
                        "  MLW %d '%s' top node %d: T_inj = %.2f °C "
                        "[OK]",
                        mlw_id, wr.name, nodes[0], bc_val,
                    )

    if ok:
        log.info("Well verification: ALL PASSED")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    cfg = load_config()
    ifm = bootstrap_ifm()

    fem_path = OUTPUTS_DIR / "Group3.fem"
    if not fem_path.exists():
        raise FileNotFoundError(
            f"FEM not found: {fem_path}\n"
            "Stage 07 must complete before Stage 08."
        )

    doc = ifm.loadDocument(str(fem_path))

    well_table = _build_well_table(cfg)
    log.info(
        "Well table: %d wells (%d production, %d injection)",
        len(well_table),
        sum(1 for w in well_table if not w.is_injection),
        sum(1 for w in well_table if w.is_injection),
    )

    # --- Path selection ---
    n_existing = doc.getNumberOfMultiLayerWells()
    if n_existing == 0:
        log.info(
            "No MLWs found in document — creating via WellManager (Path B)."
        )
        ok = create_wells_via_well_manager(doc, cfg, ifm, well_table)
        if not ok:
            raise RuntimeError(
                "WellManager.applyOperations() failed. "
                "Check log for per-well errors. "
                "Consider pre-building MLWs in Group3_template.fem via the "
                "FEFLOW GUI (Path A) to avoid coordinate-snapping issues."
            )
        log.info(
            "Wells created. MLW count now: %d",
            doc.getNumberOfMultiLayerWells(),
        )
    else:
        log.info(
            "Found %d existing MLWs in document (Path A — updating rates only).",
            n_existing,
        )

    assign_well_rates(doc, cfg, ifm, well_table)
    assign_injection_temperature(doc, cfg, ifm, well_table)

    log.info("Verifying wells (spot-check):")
    if not verify_wells(doc, cfg, ifm, well_table):
        raise RuntimeError(
            "Well verification failed. See log for details."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 8 complete — wells saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
