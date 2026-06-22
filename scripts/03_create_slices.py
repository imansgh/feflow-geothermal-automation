"""
03_create_slices.py — Set the correct Z-elevation for every node in every
slice of the 3-D FEFLOW model.

After script 02 creates the mesh skeleton with uniformly-spaced placeholder
Z-values, this script replaces those values with the exact Group 3 slice
elevations derived from the geothermal gradient.

Slice structure (6 slices → 5 layers):
  Slice 1  +600 m a.s.l.  (ground surface, top of caprock)
  Slice 2  -270 m a.s.l.  (top of reservoir)
  Slice 3  -370 m a.s.l.  (reservoir sub-layer boundary)
  Slice 4  -470 m a.s.l.  (reservoir sub-layer boundary)
  Slice 5  -520 m a.s.l.  (base of reservoir / top of basement)
  Slice 6 -2500 m a.s.l.  (base of basement)

IFM API:
  doc.setZ(global_node, z)  — set node elevation [m a.s.l.]
  FEFLOW stores Z in metres above sea level (positive upward).

Tutorial reference: pp. 10–12 (§3.1)
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def set_slice_elevations(doc, cfg: GeothermalConfig) -> None:
    """
    Assign the Group 3 elevation to every node in every slice.

    Nodes are numbered sequentially in FEFLOW:
      global_node = (slice_index - 1) * nodes_per_slice + local_node

    Parameters
    ----------
    doc:
        Loaded FEFLOW document (writable).
    cfg:
        Loaded configuration with ``slice_elevations`` list.
    """
    nps     = doc.getNumberOfNodesPerSlice()
    n_slices = doc.getNumberOfSlices()

    if n_slices != len(cfg.slice_elevations):
        raise ValueError(
            f"FEM has {n_slices} slices but config defines "
            f"{len(cfg.slice_elevations)} elevations."
        )

    log.info("Setting Z for %d slices × %d nodes/slice = %d total nodes",
             n_slices, nps, n_slices * nps)

    for s_idx, z_elev in enumerate(cfg.slice_elevations):
        for local in range(nps):
            global_node = s_idx * nps + local
            doc.setZ(global_node, float(z_elev))

        log.debug(
            "Slice %d: elevation = %+.1f m a.s.l.  (%d nodes assigned)",
            s_idx + 1, z_elev, nps
        )

    log.info("Slice elevations set: %s m a.s.l.", cfg.slice_elevations)


def verify_slice_elevations(doc, cfg: GeothermalConfig) -> bool:
    """
    Read back a sample of Z-values and verify they match the config.

    Checks the first node of each slice (local index 0).

    Returns True if all values match within 0.001 m, False otherwise.
    """
    nps = doc.getNumberOfNodesPerSlice()
    ok = True
    for s_idx, z_expected in enumerate(cfg.slice_elevations):
        global_node = s_idx * nps    # local node 0, slice s_idx+1
        z_actual = doc.getZ(global_node)
        delta = abs(z_actual - z_expected)
        if delta > 0.001:
            log.error(
                "Slice %d Z mismatch: expected %+.4f, got %+.4f (Δ = %.4f m)",
                s_idx + 1, z_expected, z_actual, delta
            )
            ok = False
        else:
            log.debug("Slice %d Z OK: %+.4f m", s_idx + 1, z_actual)
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
            f"FEM not found: {fem_path}\nRun 02_generate_mesh.py first."
        )

    doc = ifm.loadDocument(str(fem_path))

    # Check that the FEM has 5 layers (6 slices) before proceeding
    n_layers = doc.getNumberOfLayers()
    n_slices = doc.getNumberOfSlices()
    log.info("FEM layers: %d  slices: %d", n_layers, n_slices)

    if n_layers != 5:
        raise ValueError(
            f"Expected 5 layers but FEM has {n_layers}.\n"
            "Ensure script 02 (setNumberOfLayers(5)) ran correctly."
        )

    set_slice_elevations(doc, cfg)

    if not verify_slice_elevations(doc, cfg):
        raise RuntimeError("Slice elevation verification failed — see log for details.")

    doc.saveDocument(str(fem_path))
    log.info("Stage 3 complete — slice elevations saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
