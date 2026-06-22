"""
02_generate_mesh.py — Bootstrap module: validate, load, inspect, and register
the Group 3 FEFLOW template mesh as the working FEM file.

Design rationale
----------------
Programmatic mesh creation through IFM is not viable for FEFLOW 8.1:

    createNewDocument2D()   — DNE in ifm312.pyd
    setNumberOfNodes()      — DNE
    setNumberOfElements()   — DNE
    setNumberOfLayers()     — DNE
    setNode()               — DNE

The PYSMH (SuperMesh Python API) that CAN create meshes is
license-gated; doc.getSuperMesh() raises RuntimeError on all
standard educational licenses.

Strategy
--------
The mesh is created once manually in the FEFLOW GUI and saved as
Group3_template.fem.  This module:

    1. Confirms Group3_template.fem exists (fails loudly if not).
    2. Loads it with ifm.loadDocument() — the only verified load path.
    3. Reports mesh statistics (nodes, elements, slices, layers, extents).
    4. Runs hard-fail structural checks.
    5. Cross-checks domain size and well-node proximity against config.
    6. Saves the loaded document as Group3.fem in the same directory
       (via doc.saveDocument — cleaner than shutil.copy, goes through
       FEFLOW's writer so internal file references stay consistent).
    7. Stops.

Group3_template.fem must be built in the FEFLOW GUI before running the
pipeline.  See _TEMPLATE_INSTRUCTIONS below.

Expected mesh structure (Group 3 geothermal doublet)
------------------------------------------------------
    Slices  : 6  (Slice 1 = surface, Slice 6 = basement base)
    Layers  : 5  (Layer 1 = caprock, Layers 2–4 = reservoir, Layer 5 = basement)
    Mesh    : triangular, structured extrusion (epl > 0)
    Domain  : 8 000 × 8 000 m square
    Projection: PROJ_CONFINED_3D (=4) for 3-D saturated confined problem

Subsequent stages depend on this structure:
    04  setProblemClass(PCLS_HEAT_TRANSPORT, TCLS_UNSTEADY, TYPE_SATURATED)
    05  setParamValues(P_CONDX, …) — layer-indexed element array
    06  setParamValues(P_HEAD/P_TEMP, …) — slice-indexed node array
    07  setBcFlowTypeAndValueAtCurrentTime — border nodes of each slice
    08  createWellManager() → well screening
    09  setFinalSimulationTime, setCustomTimes, …
    10  startSimulator(Group3.dac, F_BINARY, output_times)
    11  getTimeSteps(), loadTimeStep(), getResultsTransportHeatValue()

Verified IFM API used here (all confirmed in ifm312.pyd, FEFLOW 8.1)
----------------------------------------------------------------------
Module-level:
    ifm.loadDocument(str(path))         → FeflowDoc
    ifm.getKernelVersion()              → int  e.g. 8100 for FEFLOW 8.1
    ifm.getKernelRevision()             → int  build number

Document-level geometry:
    doc.getNumberOfNodes()              → int  total nodes (all slices)
    doc.getNumberOfNodesPerSlice()      → int  nodes per horizontal slice
    doc.getNumberOfElements()           → int  total elements (all layers)
    doc.getNumberOfElementsPerLayer()   → int  elements per layer (0 = unstructured)
    doc.getNumberOfSlices()             → int  horizontal slices
    doc.getNumberOfLayers()             → int  element layers
    doc.getNumberOfEdges()              → int  edges (informational)
    doc.getX(node), getY(node), getZ(node) → float [m]

Extents:
    doc.getExtents()    → tuple(xmin, xmax, ymin, ymax, zmin, zmax) [m]
    doc.getExtentX()    → float  X span [m]
    doc.getExtentY()    → float  Y span [m]
    doc.getExtentZ()    → float  Z span [m]

Problem definition:
    doc.getProblemClass()               → int  (PCLS_NO_CLASS=-1 for unconfigured)
    doc.getTimeClass()                  → int
    doc.getProblemDefinition().getProjection() → int  (PROJ_CONFINED_3D=4)
    doc.getLoadVersion()                → int  FEM-file IFM version

Persistence:
    doc.saveDocument(str(path))         → None  writes Group3.fem
    doc.closeDocument()                 → None

Tutorial reference: pp. 8–10 (§2.2)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from config import load_config, OUTPUTS_DIR, DATA_DIR, GROUP_ID, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template FEM instructions (printed when the file is missing)
# ---------------------------------------------------------------------------

_TEMPLATE_INSTRUCTIONS = """
Group3_template.fem not found.  Create it once in the FEFLOW GUI:

  1. Open FEFLOW 8.1.
  2. File > New > New Problem
     - Problem class : Flow and Heat Transport (coupled TH)
     - Time class    : Transient
     - Projection    : 3D (confined, fully saturated)
  3. Supermesh > import your boundary polygon (8 000 × 8 000 m square)
     and the well-node point file (BHE locations from wellnodecoordinates sheet).
  4. Mesh > Meshing > Triangle  (PTS = 5 m, PG = 4, refine at points = True)
     → Click "Generate mesh"
  5. Slices > Add slices (total 6 slices at elevations from the tutorial):
       Slice 1:  +600 m    Slice 4: -470 m
       Slice 2:  -270 m    Slice 5: -520 m
       Slice 3:  -370 m    Slice 6: -2500 m
  6. Also set temperature-dependent density, temperature-dependent viscosity,
     reference temperature = 10 °C, reference density = 999.793 kg/m³
     (Problem Settings > Fluid Properties — these cannot be set via IFM API).
  7. File > Save As > <project>/outputs/Group3_template.fem

Then re-run: python 02_generate_mesh.py
"""


# ---------------------------------------------------------------------------
# Template search
# ---------------------------------------------------------------------------

_TEMPLATE_SEARCH_PATHS: List[Path] = [
    OUTPUTS_DIR / f"{GROUP_ID}_template.fem",        # primary: same dir as working FEM
    DATA_DIR    / f"{GROUP_ID}_template.fem",        # secondary: data directory
    OUTPUTS_DIR.parent / f"{GROUP_ID}_template.fem", # project root (common GUI save location)
]


def _find_template() -> Optional[Path]:
    """Return the first existing template path, or None."""
    for p in _TEMPLATE_SEARCH_PATHS:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Mesh statistics (read-only, no modification)
# ---------------------------------------------------------------------------

def report_mesh_statistics(doc, ifm) -> dict:
    """
    Read and log all structural mesh statistics.

    All getters are confirmed in ifm312.pyd (FEFLOW 8.1).  No computation,
    no modification — read-only pass.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document.
    ifm : module
        Imported IFM module (ifm312).

    Returns
    -------
    dict with keys: n_nodes, nps, n_elements, epl, n_slices, n_layers,
                    n_edges, extents, pcls, tcls, projection, load_version.
    """
    n_nodes   = doc.getNumberOfNodes()
    nps       = doc.getNumberOfNodesPerSlice()
    n_elems   = doc.getNumberOfElements()
    epl       = doc.getNumberOfElementsPerLayer()
    n_slices  = doc.getNumberOfSlices()
    n_layers  = doc.getNumberOfLayers()
    n_edges   = doc.getNumberOfEdges()
    extents   = doc.getExtents()          # (xmin, xmax, ymin, ymax, zmin, zmax)
    pcls      = doc.getProblemClass()
    tcls      = doc.getTimeClass()
    proj      = doc.getProblemDefinition().getProjection()
    load_ver  = doc.getLoadVersion()
    kern_ver  = ifm.getKernelVersion()
    kern_rev  = ifm.getKernelRevision()

    xmin, xmax, ymin, ymax, zmin, zmax = extents

    # ---- Human-readable problem class / projection labels ----
    pcls_name = {
        -1: "PCLS_NO_CLASS (not configured)",
         0: "PCLS_FLOW",
         2: "PCLS_HEAT_TRANSPORT",
         1: "PCLS_MASS_TRANSPORT",
         3: "PCLS_THERMOHALINE",
    }.get(pcls, f"unknown ({pcls})")

    tcls_name = {
        0: "TCLS_STEADY",
        1: "TCLS_UNSTEADY",
        2: "TCLS_ST_UNST",
    }.get(tcls, f"unknown ({tcls})")

    proj_name = {
        -1: "PROJ_UNDEF (not set)",
         0: "PROJ_CONFINED_2D",
         1: "PROJ_PHREATIC_2D",
         2: "PROJ_VERTICAL_2D",
         3: "PROJ_AXISYM_2D",
         4: "PROJ_CONFINED_3D",
         5: "PROJ_PHREATIC_3D",
         6: "PROJ_MOVE_FS_3D",
    }.get(proj, f"unknown ({proj})")

    log.info("=== Mesh statistics ===")
    log.info("  FEFLOW kernel   : %d  (rev %d)", kern_ver, kern_rev)
    log.info("  FEM load version: %d",  load_ver)
    log.info("  Projection      : %s",  proj_name)
    log.info("  Problem class   : %s",  pcls_name)
    log.info("  Time class      : %s",  tcls_name)
    log.info("  Slices          : %d",  n_slices)
    log.info("  Layers          : %d",  n_layers)
    log.info("  Nodes per slice : %d",  nps)
    log.info("  Total nodes     : %d  (= %d slices × %d nps)", n_nodes, n_slices, nps)
    log.info("  Elements/layer  : %d",  epl)
    log.info("  Total elements  : %d  (= %d layers × %d epl)", n_elems, n_layers, epl)
    log.info("  Edges           : %d",  n_edges)
    log.info(
        "  X extent        : [%.1f, %.1f] m  (span = %.1f m)",
        xmin, xmax, xmax - xmin,
    )
    log.info(
        "  Y extent        : [%.1f, %.1f] m  (span = %.1f m)",
        ymin, ymax, ymax - ymin,
    )
    log.info(
        "  Z extent        : [%.1f, %.1f] m  (span = %.1f m)",
        zmin, zmax, zmax - zmin,
    )

    return {
        "n_nodes":      n_nodes,
        "nps":          nps,
        "n_elements":   n_elems,
        "epl":          epl,
        "n_slices":     n_slices,
        "n_layers":     n_layers,
        "n_edges":      n_edges,
        "extents":      extents,
        "pcls":         pcls,
        "tcls":         tcls,
        "projection":   proj,
        "load_version": load_ver,
    }


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

def verify_mesh_structure(stats: dict, cfg: GeothermalConfig, ifm) -> None:
    """
    Hard-fail structural validation.  Raises RuntimeError on any failure.

    Hard-fail conditions (pipeline cannot continue)
    ------------------------------------------------
    1.  n_slices != 6
        Stages 05–08 are coded for 6 slices. Wrong slice count → wrong
        array sizes in setParamValues, wrong BC nodes, wrong well screening.

    2.  n_layers != 5
        Property assignment (Stage 05) indexes layers 1–5. Wrong count →
        wrong material property arrays.

    3.  n_nodes <= 0 or n_elements <= 0
        Empty mesh — nothing to configure.

    4.  epl == 0
        Zero elements per layer means an unstructured 3-D mesh.  All
        downstream stages rely on layer-indexed element arrays and
        slice-indexed node arrays, which only work on structured meshes.

    5.  n_nodes != n_slices * nps
        Internal inconsistency in the FEM file (corrupted or truncated).

    6.  n_elements != n_layers * epl
        Same — structural inconsistency.

    7.  projection not in {PROJ_CONFINED_3D, PROJ_PHREATIC_3D, PROJ_MOVE_FS_3D}
        The mesh must be 3-D.  A 2-D or unset projection means Stage 08
        (well screening with depth intervals) will produce incorrect results.

    Warnings (non-fatal, logged but do not stop the pipeline)
    ----------------------------------------------------------
    W1. Domain extents differ from cfg.domain_size by > 10 %
        Suggests wrong template or coordinate system issue.

    W2. Problem class is not PCLS_NO_CLASS and not PCLS_HEAT_TRANSPORT
        A correctly-built template should have either no class set yet
        (PCLS_NO_CLASS = -1, Stage 04 will configure it) or already be
        set to PCLS_HEAT_TRANSPORT by the GUI.  Any other class suggests
        a template built for a different problem type.

    Parameters
    ----------
    stats : dict
        Output of report_mesh_statistics().
    cfg : GeothermalConfig
        Used for domain-size cross-check.
    ifm : module
        Imported IFM module; provides enum values.
    """
    errors: List[str] = []

    # --- Hard-fail checks ---
    n_slices  = stats["n_slices"]
    n_layers  = stats["n_layers"]
    n_nodes   = stats["n_nodes"]
    n_elems   = stats["n_elements"]
    nps       = stats["nps"]
    epl       = stats["epl"]
    proj      = stats["projection"]
    pcls      = stats["pcls"]
    extents   = stats["extents"]

    EXPECTED_SLICES = 6
    EXPECTED_LAYERS = 5
    PROJ_3D = {
        ifm.Enum.PROJ_CONFINED_3D,
        ifm.Enum.PROJ_PHREATIC_3D,
        ifm.Enum.PROJ_MOVE_FS_3D,
    }

    if n_slices != EXPECTED_SLICES:
        errors.append(
            f"Slice count: expected {EXPECTED_SLICES}, got {n_slices}. "
            "Rebuild the template with 6 slices (5 layers)."
        )

    if n_layers != EXPECTED_LAYERS:
        errors.append(
            f"Layer count: expected {EXPECTED_LAYERS}, got {n_layers}. "
            "Rebuild the template with 5 layers (6 slices)."
        )

    if n_nodes <= 0:
        errors.append("Mesh has 0 nodes — FEM file may be corrupt or empty.")

    if n_elems <= 0:
        errors.append("Mesh has 0 elements — FEM file may be corrupt or empty.")

    if epl == 0:
        errors.append(
            "Elements-per-layer is 0 (unstructured 3-D mesh). "
            "Downstream stages require a structured extrusion (epl > 0). "
            "Rebuild template with the 2-D triangular base mesh extruded to layers."
        )

    if n_nodes > 0 and nps > 0 and n_nodes != n_slices * nps:
        errors.append(
            f"Node count inconsistency: {n_nodes} nodes "
            f"!= {n_slices} slices × {nps} nps = {n_slices * nps}. "
            "The FEM file may be corrupt."
        )

    if n_elems > 0 and epl > 0 and n_elems != n_layers * epl:
        errors.append(
            f"Element count inconsistency: {n_elems} elements "
            f"!= {n_layers} layers × {epl} epl = {n_layers * epl}. "
            "The FEM file may be corrupt."
        )

    if proj not in PROJ_3D:
        # -1 = PROJ_UNDEF means the template has no projection set at all
        hint = ("2-D projection detected." if proj >= 0
                else "Projection not set (PROJ_UNDEF).")
        errors.append(
            f"{hint} Stage 08 (well screening) requires a 3-D mesh. "
            "Set projection to 'Confined (saturated)' (3D) in the FEFLOW GUI."
        )

    if errors:
        msg = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        raise RuntimeError(
            f"{len(errors)} structural check(s) failed:\n{msg}\n\n"
            "Fix Group3_template.fem and re-run Stage 02."
        )

    log.info("Structural checks: ALL PASSED")

    # --- Non-fatal warnings ---
    xmin, xmax, ymin, ymax, zmin, zmax = extents
    x_span = xmax - xmin
    y_span = ymax - ymin

    for axis, span, label in [("X", x_span, "width"), ("Y", y_span, "height")]:
        rel = abs(span - cfg.domain_size) / cfg.domain_size
        if rel > 0.10:
            log.warning(
                "Domain %s mismatch: mesh %s = %.0f m, "
                "cfg.domain_size = %.0f m (rel diff = %.1f %%). "
                "Check template coordinates.",
                axis, label, span, cfg.domain_size, 100.0 * rel,
            )

    if pcls not in (-1, ifm.Enum.PCLS_HEAT_TRANSPORT):
        log.warning(
            "Problem class is %d — expected PCLS_NO_CLASS (-1, not yet configured) "
            "or PCLS_HEAT_TRANSPORT (%d, already configured). "
            "Verify this template was built for a TH problem.",
            pcls, ifm.Enum.PCLS_HEAT_TRANSPORT,
        )


# ---------------------------------------------------------------------------
# Well-node proximity check
# ---------------------------------------------------------------------------

def verify_well_nodes(doc, cfg: GeothermalConfig, tol_m: float = 200.0) -> None:
    """
    Confirm that each well XY from cfg.well_nodes has a nearby mesh node.

    Strategy
    --------
    Load all XY coordinates of Slice 1 (local nodes 0 … nps-1).
    For each row in cfg.well_nodes, find the minimum XY distance to any
    Slice 1 node.  If the distance exceeds ``tol_m``, log a warning.

    This check is non-fatal: a large distance (> tol_m) may mean the well
    was not inserted as a constrained vertex in the supermesh, which causes
    Stage 08's WellManager to snap to an approximate node rather than the
    exact BHE location.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document.
    cfg : GeothermalConfig
        Well node coordinates from cfg.well_nodes (columns X, Y).
    tol_m : float
        Warning threshold in metres.  Default 200 m (half a far-field element).
    """
    nps = doc.getNumberOfNodesPerSlice()

    # Load all Slice 1 XY once (vectorised)
    xs = np.array([doc.getX(n) for n in range(nps)])
    ys = np.array([doc.getY(n) for n in range(nps)])

    n_wells  = len(cfg.well_nodes)
    n_warns  = 0

    for _, row in cfg.well_nodes.iterrows():
        wx    = float(row["X"])
        wy    = float(row["Y"])
        dists = np.sqrt((xs - wx) ** 2 + (ys - wy) ** 2)
        d_min = float(dists.min())
        near  = int(np.argmin(dists))

        if d_min > tol_m:
            log.warning(
                "Well node (%.1f, %.1f): nearest mesh node %d is %.1f m away "
                "(threshold %.0f m). "
                "Well may not be a constrained vertex — Stage 08 will snap to "
                "nearest available node.",
                wx, wy, near, d_min, tol_m,
            )
            n_warns += 1

    if n_warns == 0:
        log.info(
            "Well-node proximity check: all %d well nodes within %.0f m of a mesh node.",
            n_wells, tol_m,
        )
    else:
        log.warning(
            "Well-node proximity: %d / %d well nodes exceed %.0f m threshold.",
            n_warns, n_wells, tol_m,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    cfg = load_config()
    ifm = bootstrap_ifm()

    # ---- 1. Locate template ------------------------------------------------
    template_path = _find_template()
    if template_path is None:
        searched = "\n  ".join(str(p) for p in _TEMPLATE_SEARCH_PATHS)
        raise FileNotFoundError(
            f"Group3_template.fem not found.\n"
            f"Searched:\n  {searched}\n"
            f"{_TEMPLATE_INSTRUCTIONS}"
        )
    log.info("Template found: %s", template_path)

    # ---- 2. Load -----------------------------------------------------------
    log.info("Loading template with ifm.loadDocument()…")
    doc = ifm.loadDocument(str(template_path))
    log.info("Document loaded.")

    # ---- 3. Mesh statistics (read-only) ------------------------------------
    stats = report_mesh_statistics(doc, ifm)

    # ---- 4. Structural checks (hard-fail on error) -------------------------
    log.info("Running structural checks:")
    verify_mesh_structure(stats, cfg, ifm)

    # ---- 5. Well-node proximity check (non-fatal) --------------------------
    log.info("Checking well-node proximity:")
    verify_well_nodes(doc, cfg)

    # ---- 6. Save as Group3.fem (working copy for stages 03–11) ------------
    fem_path = OUTPUTS_DIR / "Group3.fem"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    doc.saveDocument(str(fem_path))
    log.info("Working FEM saved: %s", fem_path)

    # ---- 7. Close template document ----------------------------------------
    doc.closeDocument()

    # ---- Summary -----------------------------------------------------------
    nps = stats["nps"]
    epl = stats["epl"]
    log.info(
        "Stage 2 complete — mesh bootstrap OK.\n"
        "  Working FEM  : %s\n"
        "  Slices/layers: %d / %d\n"
        "  Nodes        : %d total  (%d per slice)\n"
        "  Elements     : %d total  (%d per layer)\n"
        "  Domain       : %.0f × %.0f m",
        fem_path,
        stats["n_slices"], stats["n_layers"],
        stats["n_nodes"],   nps,
        stats["n_elements"], epl,
        stats["extents"][1] - stats["extents"][0],
        stats["extents"][3] - stats["extents"][2],
    )
    log.info("Ready for Stage 03 (slice elevations) → Stage 04 (problem class) → …")


if __name__ == "__main__":
    main()
