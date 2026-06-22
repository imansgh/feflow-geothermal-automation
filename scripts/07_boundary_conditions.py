"""
07_boundary_conditions.py — Apply the three boundary conditions required by
the Group 3 geothermal model.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
Fabricated method removed:
    setParamSize(param, val, node)  — DNE in FeflowDoc

Fabricated enum names removed (all DNE in ifm.Enum):
    P_BC_HEAD_1ST    — DNE
    P_BC_TRANS_1ST   — DNE
    P_BC_HEAT_2ND    — DNE
    (Fallback integer codes 256, 512, 600 were unverified and are removed.)

Verified API used (signatures from live ifm312.pyd __doc__):
    setBcFlowTypeAndValueAtCurrentTime(node, bc_type, bc_unst, value)
        bc_type : BC_NONE(0) | BC_DIRICHLET(1) | BC_NEUMANN(2) | ...
        bc_unst : 0 = constant (steady-state), 1 = unsteady (value = power ID)
        value   : constant BC value when bc_unst=0
    setBcHeatTypeAndValueAtCurrentTime(node, bctype, bcUnst, value)
        (same argument structure as flow)
    getBcFlowType(node)   → int   BC type for flow at node
    getBcFlowValue(node)  → float BC value for flow at node
    getBcHeatType(node)   → int   BC type for heat at node
    getBcHeatValue(node)  → float BC value for heat at node

Verified enum values (ifm.Enum, FEFLOW 8.1):
    BC_NONE      = 0
    BC_DIRICHLET = 1    (1st-kind / Dirichlet)
    BC_NEUMANN   = 2    (2nd-kind / Neumann)

All BCs in this model are constant (bc_unst = 0).

BC summary
----------
  BC-1  Temperature 1st-kind (Dirichlet heat)
        setBcHeatTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, T_slice)
        Applied to: border nodes of ALL slices
        Value: cfg.slice_T[slice_index] °C

  BC-2  Geothermal heat flux 2nd-kind (Neumann heat)
        setBcHeatTypeAndValueAtCurrentTime(node, BC_NEUMANN, 0, cfg.heat_flux_bc)
        Applied to: ALL nodes of Slice 6 (bottom face)
        Value: cfg.heat_flux_bc = -20822.4 J/(m²·d)
        Sign: negative = flux into domain (upward geothermal heat)

  BC-3  Hydraulic head 1st-kind (Dirichlet flow)
        setBcFlowTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, h)
        Applied to: border nodes of ALL slices
        Value: cfg.h_initial = 200.0 m

Application order and corner-node behaviour:
  BC-1 is applied first (T Dirichlet on all border nodes including Slice 6).
  BC-2 is applied second (heat flux on ALL Slice-6 nodes).
  For border nodes of Slice 6, BC-2 OVERWRITES BC-1's heat assignment.
  Those corners therefore carry the geothermal heat flux BC, not the T BC.
  BC-3 (flow BC) is applied last and does not conflict with heat BCs, since
  FEFLOW maintains separate flow-BC and heat-BC slots per node.

"Border nodes" are nodes whose (X, Y) coordinate lies on the perimeter of
the rectangular domain, detected within a 1 m tolerance by
find_boundary_nodes_2d() in utils.py.

Tutorial reference: pp. 22–25 (§5.2)
"""

from __future__ import annotations

import logging
from typing import Set

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import (
    bootstrap_ifm, setup_logging,
    find_boundary_nodes_2d, local_to_global,
)

log = logging.getLogger(__name__)

# bc_unst = 0 throughout: all BCs in this model are constant (steady-state).
_BC_UNST_CONSTANT: int = 0


# ---------------------------------------------------------------------------
# Enum resolution
# ---------------------------------------------------------------------------

def _resolve_enums(ifm) -> dict:
    """
    Resolve BC type enums from the live ifm.Enum namespace.

    Verified values (FEFLOW 8.1, ifm312.pyd):
        BC_DIRICHLET = 1
        BC_NEUMANN   = 2
        BC_NONE      = 0

    Raises AttributeError immediately if any name is absent — indicates wrong
    FEFLOW installation or version. No integer fallback is provided.
    """
    return {
        "BC_DIRICHLET": ifm.Enum.BC_DIRICHLET,   # 1
        "BC_NEUMANN":   ifm.Enum.BC_NEUMANN,      # 2
        "BC_NONE":      ifm.Enum.BC_NONE,         # 0
    }


# ---------------------------------------------------------------------------
# BC-1: Temperature (1st-kind / Dirichlet heat)
# ---------------------------------------------------------------------------

def apply_temperature_bc(
    doc,
    cfg: GeothermalConfig,
    boundary_local: Set[int],
    ifm,
) -> None:
    """
    Apply constant Dirichlet temperature BC to border nodes of every slice.

    Holds the lateral domain boundary at the undisturbed geothermal temperature
    for the depth of each slice. Prevents boundary effects from distorting the
    thermal plume over the 100-year simulation.

    API used (verified FEFLOW 8.1):
        setBcHeatTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, T)
        node        : global node index
        BC_DIRICHLET: 1
        0           : constant BC (bc_unst = 0)
        T           : temperature [°C]

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        cfg.slice_T = [T_s1, T_s2, ..., T_s6]  (°C)
    boundary_local : Set[int]
        Within-slice local indices of perimeter nodes.
    ifm : module
        Imported IFM module (ifm312).
    """
    enums    = _resolve_enums(ifm)
    nps      = doc.getNumberOfNodesPerSlice()
    n_slices = doc.getNumberOfSlices()
    total    = 0

    for s_idx, T in enumerate(cfg.slice_T):
        T_val = float(T)
        for local in boundary_local:
            g = local_to_global(local, s_idx + 1, nps)
            doc.setBcHeatTypeAndValueAtCurrentTime(
                g, enums["BC_DIRICHLET"], _BC_UNST_CONSTANT, T_val,
            )
        n = len(boundary_local)
        total += n
        log.info(
            "T BC  Slice %d: %.4f degC → %d border nodes (BC_DIRICHLET)",
            s_idx + 1, T_val, n,
        )

    log.info(
        "Temperature BC complete: %d nodes across %d slices",
        total, n_slices,
    )


# ---------------------------------------------------------------------------
# BC-2: Geothermal heat flux (2nd-kind / Neumann heat)
# ---------------------------------------------------------------------------

def apply_heat_flux_bc(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Apply constant Neumann heat-flux BC to ALL nodes of Slice 6 (model bottom).

    Represents the upward geothermal heat flux (241 mW/m²) entering the domain
    from below. Sign convention: negative value = flux into the domain.

    For border nodes of Slice 6, this call overwrites the Dirichlet temperature
    BC set by apply_temperature_bc (called first). Corner-bottom nodes therefore
    carry a Neumann heat flux, not a temperature constraint.

    API used (verified FEFLOW 8.1):
        setBcHeatTypeAndValueAtCurrentTime(node, BC_NEUMANN, 0, flux)
        node      : global node index
        BC_NEUMANN: 2
        0         : constant BC (bc_unst = 0)
        flux      : heat flux [J/(m²·d)], negative = into domain

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        cfg.heat_flux_bc = -20822.4 J/(m²·d)   (= -241 mW/m²)
    ifm : module
        Imported IFM module (ifm312).
    """
    enums      = _resolve_enums(ifm)
    nps        = doc.getNumberOfNodesPerSlice()
    n_slices   = doc.getNumberOfSlices()
    last_slice = n_slices          # Slice 6 (1-based)
    q_bc       = float(cfg.heat_flux_bc)   # already negative

    log.info(
        "Heat-flux BC on Slice %d: %.2f J/(m2·d) (%.1f mW/m2 upward) → %d nodes (BC_NEUMANN)",
        last_slice, q_bc, -cfg.heat_flux * 1000.0, nps,
    )

    for local in range(nps):
        g = local_to_global(local, last_slice, nps)
        doc.setBcHeatTypeAndValueAtCurrentTime(
            g, enums["BC_NEUMANN"], _BC_UNST_CONSTANT, q_bc,
        )

    log.info("Heat-flux BC complete: %d nodes on Slice %d", nps, last_slice)


# ---------------------------------------------------------------------------
# BC-3: Hydraulic head (1st-kind / Dirichlet flow)
# ---------------------------------------------------------------------------

def apply_head_bc(
    doc,
    cfg: GeothermalConfig,
    boundary_local: Set[int],
    ifm,
) -> None:
    """
    Apply constant Dirichlet head BC (h = 200 m) to border nodes of all slices.

    Holds the far-field piezometric level fixed during pumping, representing
    the undisturbed regional aquifer pressure at 200 m a.s.l.

    Flow BCs and heat BCs occupy independent slots per node in FEFLOW:
    setting a flow BC does not affect the heat BC on the same node.

    API used (verified FEFLOW 8.1):
        setBcFlowTypeAndValueAtCurrentTime(node, BC_DIRICHLET, 0, h)
        node        : global node index
        BC_DIRICHLET: 1
        0           : constant BC (bc_unst = 0)
        h           : hydraulic head [m]

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        cfg.h_initial = 200.0 m
    boundary_local : Set[int]
        Within-slice local indices of perimeter nodes.
    ifm : module
        Imported IFM module (ifm312).
    """
    enums    = _resolve_enums(ifm)
    nps      = doc.getNumberOfNodesPerSlice()
    n_slices = doc.getNumberOfSlices()
    h        = float(cfg.h_initial)
    total    = 0

    for s_idx in range(n_slices):
        for local in boundary_local:
            g = local_to_global(local, s_idx + 1, nps)
            doc.setBcFlowTypeAndValueAtCurrentTime(
                g, enums["BC_DIRICHLET"], _BC_UNST_CONSTANT, h,
            )
        total += len(boundary_local)

    log.info(
        "Head BC: h = %.1f m → %d border nodes × %d slices = %d total (BC_DIRICHLET)",
        h, len(boundary_local), n_slices, total,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_boundary_conditions(
    doc,
    cfg: GeothermalConfig,
    boundary_local: Set[int],
    ifm,
) -> bool:
    """
    Spot-check boundary conditions using the verified getter API.

    Getters used (all verified present in FeflowDoc, FEFLOW 8.1):
        getBcHeatType(node)  → int    BC type for heat at node
        getBcHeatValue(node) → float  BC value for heat at node
        getBcFlowType(node)  → int    BC type for flow at node
        getBcFlowValue(node) → float  BC value for flow at node

    Checks performed:
      1. First boundary node of Slice 1:
         - Heat BC type  == BC_DIRICHLET (T boundary)
         - Heat BC value ≈ cfg.slice_T[0]
         - Flow BC type  == BC_DIRICHLET (head boundary)
         - Flow BC value ≈ cfg.h_initial
      2. First non-corner node of Slice 6 (local index 0):
         - Heat BC type  == BC_NEUMANN   (heat flux)
         - Heat BC value ≈ cfg.heat_flux_bc

    Parameters
    ----------
    doc : FeflowDoc
    cfg : GeothermalConfig
    boundary_local : Set[int]
    ifm : module

    Returns
    -------
    bool
        True if all spot-checks pass.
    """
    enums  = _resolve_enums(ifm)
    nps    = doc.getNumberOfNodesPerSlice()
    n_slices = doc.getNumberOfSlices()
    ok     = True

    # ---- Check 1: first boundary node on Slice 1 --------------------------
    if not boundary_local:
        log.warning("No boundary nodes found; skipping border-node verification.")
    else:
        first_border = sorted(boundary_local)[0]
        node_s1 = local_to_global(first_border, 1, nps)

        # Heat BC type
        heat_type = doc.getBcHeatType(node_s1)
        if heat_type != enums["BC_DIRICHLET"]:
            log.error(
                "Slice 1 border node %d: heat BC type = %d, expected BC_DIRICHLET (%d)",
                node_s1, heat_type, enums["BC_DIRICHLET"],
            )
            ok = False
        else:
            log.info(
                "  Slice 1 border node %d: heat BC = BC_DIRICHLET (%d) [OK]",
                node_s1, heat_type,
            )

        # Heat BC value
        heat_val = doc.getBcHeatValue(node_s1)
        T_exp    = cfg.slice_T[0]
        if abs(heat_val - T_exp) > 0.01:
            log.error(
                "Slice 1 border node %d: heat BC value = %.4f degC, expected %.4f degC",
                node_s1, heat_val, T_exp,
            )
            ok = False
        else:
            log.info(
                "  Slice 1 border node %d: heat BC value = %.4f degC [OK]",
                node_s1, heat_val,
            )

        # Flow BC type
        flow_type = doc.getBcFlowType(node_s1)
        if flow_type != enums["BC_DIRICHLET"]:
            log.error(
                "Slice 1 border node %d: flow BC type = %d, expected BC_DIRICHLET (%d)",
                node_s1, flow_type, enums["BC_DIRICHLET"],
            )
            ok = False
        else:
            log.info(
                "  Slice 1 border node %d: flow BC = BC_DIRICHLET (%d) [OK]",
                node_s1, flow_type,
            )

        # Flow BC value
        flow_val = doc.getBcFlowValue(node_s1)
        if abs(flow_val - cfg.h_initial) > 0.001:
            log.error(
                "Slice 1 border node %d: flow BC value = %.4f m, expected %.4f m",
                node_s1, flow_val, cfg.h_initial,
            )
            ok = False
        else:
            log.info(
                "  Slice 1 border node %d: flow BC value = %.4f m [OK]",
                node_s1, flow_val,
            )

    # ---- Check 2: first local node of Slice 6 (heat flux BC) --------------
    node_s6 = local_to_global(0, n_slices, nps)

    heat_type_s6 = doc.getBcHeatType(node_s6)
    if heat_type_s6 != enums["BC_NEUMANN"]:
        log.error(
            "Slice 6 node %d: heat BC type = %d, expected BC_NEUMANN (%d)",
            node_s6, heat_type_s6, enums["BC_NEUMANN"],
        )
        ok = False
    else:
        log.info(
            "  Slice 6 node %d: heat BC = BC_NEUMANN (%d) [OK]",
            node_s6, heat_type_s6,
        )

    heat_val_s6 = doc.getBcHeatValue(node_s6)
    if abs(heat_val_s6 - cfg.heat_flux_bc) > 1.0:   # tolerance 1 J/(m²·d)
        log.error(
            "Slice 6 node %d: heat BC value = %.2f J/(m2·d), expected %.2f",
            node_s6, heat_val_s6, cfg.heat_flux_bc,
        )
        ok = False
    else:
        log.info(
            "  Slice 6 node %d: heat BC value = %.2f J/(m2·d) [OK]",
            node_s6, heat_val_s6,
        )

    if ok:
        log.info("Boundary condition verification: ALL PASSED")
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
            "Stage 06 must complete before Stage 07."
        )

    doc = ifm.loadDocument(str(fem_path))

    boundary_local = find_boundary_nodes_2d(doc)
    if not boundary_local:
        raise RuntimeError(
            "find_boundary_nodes_2d() returned no nodes. "
            "Check that the domain has a rectangular perimeter and that "
            "the tolerance in utils.find_boundary_nodes_2d is appropriate."
        )
    log.info("Boundary nodes detected (within-slice): %d", len(boundary_local))

    # Application order matters: T BC (BC-1) applied first, heat flux (BC-2)
    # second. For Slice 6 border nodes, BC-2 overwrites BC-1's heat assignment.
    apply_temperature_bc(doc, cfg, boundary_local, ifm)
    apply_heat_flux_bc(doc, cfg, ifm)
    apply_head_bc(doc, cfg, boundary_local, ifm)

    log.info("Verifying boundary conditions (spot-check):")
    if not verify_boundary_conditions(doc, cfg, boundary_local, ifm):
        raise RuntimeError(
            "Boundary condition verification failed. See log for details."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 7 complete — boundary conditions saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
