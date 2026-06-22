"""
06_initial_conditions.py — Assign hydraulic head and temperature initial
conditions to every node.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
Fabricated method removed:
    setParamSize(param, val, item)   — DNE in FeflowDoc

Fabricated enum names removed:
    P_HEAD_INT  (DNE)  — replaced with P_HEAD  = 400
    P_TRANS_INT (DNE)  — replaced with P_TEMP  = 402

NOTE — getParamSize misuse corrected:
    getParamSize(param_id) is VERIFIED but returns the COUNT of items for a
    parameter, not a value at a specific node. It was misused in the original
    script for value read-back and is NOT called anywhere in this rewrite.

Verified API used here:
    setParamValues(parameter, values)       — bulk setter (verified signature:
        setParamValues(param, values [,first_item=0 [,item_count=len(values)]])
        'values' may be a list (per-item) or a single float (applied to all))
    getParamValue(parameter, item)          — single-value getter (verified:
        getParamValue(parameter, item) → float)
    getNumberOfNodes()                      — verified
    getNumberOfNodesPerSlice()              — verified
    getNumberOfSlices()                     — verified

Verified enum values (ifm.Enum, FEFLOW 8.1):
    P_HEAD = 400    hydraulic head [m]       — initial + current value
    P_TEMP = 402    temperature [°C]         — initial + current value

Setting P_HEAD / P_TEMP before the simulation starts writes the initial
condition. During the run, the same parameter holds the current computed value.
This is the standard FEFLOW IFM pattern for initial conditions.

Argument order corrected:
    OLD (fabricated): setParamSize(param, VALUE, index)   ← value before index
    NEW (verified):   setParamValue(param, index, value)  ← index before value
    The mismatch was silent in the old code; it would have written values to
    the wrong nodes without raising an error.

Initial condition table (Group 3)
----------------------------------
    Hydraulic head : h = 200.0 m   (all nodes, all slices — tutorial p. 21)
    Temperature    : from geothermal gradient (config.slice_T)
        Slice 1 →  15.0000 °C   (ground surface)
        Slice 2 → 134.1307 °C
        Slice 3 → 144.6089 °C
        Slice 4 → 155.0872 °C
        Slice 5 → 160.3263 °C
        Slice 6 → 258.3099 °C

Node ordering in FEFLOW (0-based global index):
    Nodes are ordered by slice: all nodes of Slice 1 first (0 … nps-1),
    then Slice 2 (nps … 2·nps-1), etc.
    Formula: global_node = slice_index * nps + local_node_index

Tutorial reference: pp. 21–22 (§5.1)
"""

from __future__ import annotations

import logging
from typing import List

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enum resolution
# ---------------------------------------------------------------------------

def _resolve_enums(ifm) -> dict:
    """
    Resolve P_HEAD and P_TEMP from ifm.Enum.

    Both names and integer values were verified against the live ifm312.pyd
    (FEFLOW 8.1) during the engineering audit:
        P_HEAD = 400
        P_TEMP = 402

    Raises AttributeError immediately if either name is missing — a missing
    name here indicates a wrong FEFLOW installation, not a version difference.
    No silent integer fallback is provided.
    """
    return {
        "P_HEAD": ifm.Enum.P_HEAD,   # 400
        "P_TEMP": ifm.Enum.P_TEMP,   # 402
    }


# ---------------------------------------------------------------------------
# Initial head
# ---------------------------------------------------------------------------

def assign_initial_head(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Set h = cfg.h_initial (200.0 m) for every node in the model.

    Uses setParamValues(P_HEAD, scalar) — when a single float is passed,
    FEFLOW applies it to all items, so one call covers the entire mesh.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        Configuration; cfg.h_initial = 200.0 m.
    ifm : module
        Imported IFM module (ifm312).
    """
    params  = _resolve_enums(ifm)
    n_nodes = doc.getNumberOfNodes()
    h       = float(cfg.h_initial)

    # setParamValues with a scalar applies the value to ALL items.
    # Verified signature: setParamValues(parameter, values [,first_item, item_count])
    doc.setParamValues(params["P_HEAD"], h)

    log.info(
        "Initial head: h = %.2f m applied to all %d nodes (P_HEAD=%d)",
        h, n_nodes, params["P_HEAD"],
    )


# ---------------------------------------------------------------------------
# Initial temperature
# ---------------------------------------------------------------------------

def _build_temperature_array(cfg: GeothermalConfig, nps: int) -> List[float]:
    """
    Build a flat list of initial temperatures ordered by global node index.

    Global node index in FEFLOW:
        global_node = slice_index * nps + local_node_index
    All nodes on the same slice receive the same temperature.

    Parameters
    ----------
    cfg : GeothermalConfig
        cfg.slice_T = [T_slice1, T_slice2, ..., T_slice6]  (°C)
    nps : int
        Number of nodes per slice.

    Returns
    -------
    List[float]
        Flat list of length (n_slices × nps), ordered by global node index.
    """
    T_list: List[float] = []
    for T in cfg.slice_T:
        T_list.extend([float(T)] * nps)
    return T_list


def assign_initial_temperature(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Set temperature IC slice by slice from the geothermal gradient.

    Uses setParamValues(P_TEMP, T_list) — one bulk call for the entire mesh.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        cfg.slice_T = list of 6 temperatures [°C], one per slice.
    ifm : module
        Imported IFM module (ifm312).

    Raises
    ------
    ValueError
        If the number of slices in the FEM does not match len(cfg.slice_T).
    RuntimeError
        If the constructed array length does not match getNumberOfNodes().
    """
    params   = _resolve_enums(ifm)
    nps      = doc.getNumberOfNodesPerSlice()
    n_slices = doc.getNumberOfSlices()
    n_nodes  = doc.getNumberOfNodes()

    if n_slices != len(cfg.slice_T):
        raise ValueError(
            f"FEM has {n_slices} slices but config has {len(cfg.slice_T)} "
            f"temperature values. Check config.slice_T."
        )

    T_list = _build_temperature_array(cfg, nps)

    if len(T_list) != n_nodes:
        raise RuntimeError(
            f"Temperature array length ({len(T_list)}) does not match "
            f"number of nodes ({n_nodes}). "
            f"nps={nps}, n_slices={n_slices}."
        )

    doc.setParamValues(params["P_TEMP"], T_list)

    log.info(
        "Initial temperature: %d nodes assigned (P_TEMP=%d)",
        n_nodes, params["P_TEMP"],
    )
    for s_idx, T in enumerate(cfg.slice_T):
        log.info("  Slice %d: T = %.4f degC  (%d nodes)", s_idx + 1, T, nps)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_initial_conditions(doc, cfg: GeothermalConfig, ifm) -> bool:
    """
    Spot-check initial conditions at the first local node of each slice.

    Uses getParamValue(parameter, item) — verified FEFLOW 8.1 single-value
    getter. Returns the float value stored at a specific node index.

    Both head and temperature are checked at node (slice_index * nps).

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (after IC assignment).
    cfg : GeothermalConfig
        Expected values: cfg.h_initial (m) and cfg.slice_T (°C per slice).
    ifm : module
        Imported IFM module (ifm312).

    Returns
    -------
    bool
        True if all spot-checks pass within tolerance.
    """
    params = _resolve_enums(ifm)
    nps    = doc.getNumberOfNodesPerSlice()
    ok     = True

    h_tol = 1e-3   # m   — tolerance for head check
    T_tol = 1e-2   # °C  — tolerance for temperature check

    for s_idx, T_exp in enumerate(cfg.slice_T):
        node = s_idx * nps   # first local node of this slice (global index)

        # --- hydraulic head ---
        h_actual = doc.getParamValue(params["P_HEAD"], node)
        h_delta  = abs(h_actual - cfg.h_initial)
        if h_delta > h_tol:
            log.error(
                "Slice %d head IC: expected %.4f m, got %.4f m (delta=%.2e)",
                s_idx + 1, cfg.h_initial, h_actual, h_delta,
            )
            ok = False
        else:
            log.info(
                "  Slice %d h  : %.4f m [OK]", s_idx + 1, h_actual,
            )

        # --- temperature ---
        T_actual = doc.getParamValue(params["P_TEMP"], node)
        T_delta  = abs(T_actual - T_exp)
        if T_delta > T_tol:
            log.error(
                "Slice %d temp IC: expected %.4f degC, got %.4f degC (delta=%.2e)",
                s_idx + 1, T_exp, T_actual, T_delta,
            )
            ok = False
        else:
            log.info(
                "  Slice %d T  : %.4f degC [OK]", s_idx + 1, T_actual,
            )

    if ok:
        log.info("Initial condition verification: ALL PASSED")
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
            "Stage 05 must complete before Stage 06."
        )

    doc = ifm.loadDocument(str(fem_path))

    assign_initial_head(doc, cfg, ifm)
    assign_initial_temperature(doc, cfg, ifm)

    log.info("Verifying initial conditions (spot-check, node 0 per slice):")
    if not verify_initial_conditions(doc, cfg, ifm):
        raise RuntimeError(
            "Initial condition verification failed. See log for details."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 6 complete — initial conditions saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
