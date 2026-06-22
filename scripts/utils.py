"""
utils.py — Shared utilities for the Group 3 FEFLOW automation pipeline.

Provides:
  - FEFLOW / IFM module bootstrapping
  - Mesh introspection helpers (boundary nodes, layer-of-element, slice-of-node)
  - Logging setup
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IFM bootstrap
# ---------------------------------------------------------------------------

# Common FEFLOW installation roots (Windows).  The first valid one is used.
# This pipeline requires FEFLOW 8.1 (ifm312.pyd).  The 7.x paths are listed
# as fallbacks only; they will NOT work correctly with this codebase.
_IFM_SEARCH_PATHS: List[Path] = [
    Path(r"C:\Program Files\DHI\2024\FEFLOW 8.1\bin64\python"),
    Path(r"C:\Program Files\DHI\FEFLOW 8.1\bin64\python"),
    Path(r"C:\Program Files\DHI\2023\FEFLOW 8.0\bin64\python"),
    Path(r"C:\Program Files\DHI\FEFLOW 8.0\bin64\python"),
    Path(r"C:\Program Files\DHI\FEFLOW 7.5\bin64\python"),  # legacy fallback
]


def bootstrap_ifm(extra_path: Optional[str] = None) -> object:
    """
    Locate and import the ``ifm`` (or ``ifm_contrib``) module.

    Tries ``ifm_contrib`` first (richer pandas API), falls back to raw ``ifm``.
    Raises ``ImportError`` with actionable message if neither is found.

    Parameters
    ----------
    extra_path:
        Additional directory to search, e.g. a custom FEFLOW install location.

    Returns
    -------
    The imported ifm module.
    """
    search = list(_IFM_SEARCH_PATHS)
    if extra_path:
        search.insert(0, Path(extra_path))

    for p in search:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            log.debug("Added IFM path: %s", p)

    # Prefer ifm_contrib (pip install ifm_contrib)
    try:
        import ifm_contrib as ifm  # type: ignore
        log.info("Using ifm_contrib %s", getattr(ifm, "__version__", "?"))
        return ifm
    except ImportError:
        pass

    try:
        import ifm  # type: ignore  # noqa: F811
        log.info("Using raw ifm (FEFLOW built-in)")
        return ifm
    except ImportError:
        raise ImportError(
            "Cannot import 'ifm' or 'ifm_contrib'.\n"
            "Ensure FEFLOW 8.1 is installed and its Python path is reachable.\n"
            "Expected path: C:\\Program Files\\DHI\\2024\\FEFLOW 8.1\\bin64\\python\\\n"
            "Or: pip install ifm_contrib  (for ifm_contrib wrapper)"
        )


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a concise format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Mesh introspection helpers
# ---------------------------------------------------------------------------

def get_nodes_per_slice(doc) -> int:
    """Return number of mesh nodes per 2-D slice."""
    return doc.getNumberOfNodesPerSlice()


def get_elements_per_layer(doc) -> int:
    """Return number of elements per 3-D layer."""
    return doc.getNumberOfElementsPerLayer()


def node_to_slice(node_id: int, nodes_per_slice: int) -> int:
    """
    Convert a global node index to its 1-based slice number.

    FEFLOW node numbering (0-based):
      Slice 1 → nodes 0 … nps-1
      Slice 2 → nodes nps … 2·nps-1
      …
    """
    return node_id // nodes_per_slice + 1


def node_to_local(node_id: int, nodes_per_slice: int) -> int:
    """Return the within-slice (local) node index."""
    return node_id % nodes_per_slice


def elem_to_layer(elem_id: int, elems_per_layer: int) -> int:
    """Convert a global element index to its 1-based layer number."""
    return elem_id // elems_per_layer + 1


def find_boundary_nodes_2d(doc, tol: float = 1.0) -> Set[int]:
    """
    Return the set of *local* (within-slice) node indices that lie on the
    rectangular domain boundary.

    Strategy: a node is on the boundary if its x or y coordinate equals 0
    or ``domain_size`` within tolerance ``tol``.  This avoids a full
    topological boundary walk, which requires the element adjacency graph.

    Parameters
    ----------
    doc:
        Loaded FEFLOW document.
    tol:
        Coordinate tolerance in metres.  Default 1 m (well within mesh accuracy).

    Returns
    -------
    Set of local (0-based, within-slice) node indices on the boundary.
    """
    nps = get_nodes_per_slice(doc)
    xs = np.array([doc.getX(n) for n in range(nps)])
    ys = np.array([doc.getY(n) for n in range(nps)])

    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()

    on_boundary = (
        (np.abs(xs - x_min) < tol) |
        (np.abs(xs - x_max) < tol) |
        (np.abs(ys - y_min) < tol) |
        (np.abs(ys - y_max) < tol)
    )
    boundary_local = set(np.where(on_boundary)[0].tolist())
    log.debug(
        "Boundary detection: domain [%.1f,%.1f]×[%.1f,%.1f], "
        "%d / %d nodes on boundary",
        x_min, x_max, y_min, y_max, len(boundary_local), nps,
    )
    return boundary_local


def local_to_global(local_node: int, slice_idx: int, nodes_per_slice: int) -> int:
    """
    Convert (local_node, 1-based slice number) to global node index.

    Parameters
    ----------
    local_node: 0-based index within one slice
    slice_idx:  1-based slice number (1 = top slice)
    """
    return (slice_idx - 1) * nodes_per_slice + local_node


def find_nodes_near_xy(
    doc,
    x_target: float,
    y_target: float,
    radius: float = 1.0,
    slice_indices: Optional[List[int]] = None,
) -> List[int]:
    """
    Return global node indices within ``radius`` metres of (x_target, y_target).

    Parameters
    ----------
    doc:
        Loaded FEFLOW document.
    x_target, y_target:
        Target coordinates in model units (metres).
    radius:
        Search radius in metres.
    slice_indices:
        If given, restrict search to these 1-based slice numbers.
        If None, search all slices.

    Returns
    -------
    List of global node indices (may be empty).
    """
    nps = get_nodes_per_slice(doc)
    n_slices = doc.getNumberOfSlices()

    # Build local coordinate arrays once
    xs = np.array([doc.getX(n) for n in range(nps)])
    ys = np.array([doc.getY(n) for n in range(nps)])
    dists = np.sqrt((xs - x_target) ** 2 + (ys - y_target) ** 2)
    local_candidates = np.where(dists <= radius)[0].tolist()

    slices = slice_indices if slice_indices else list(range(1, n_slices + 1))
    result: List[int] = []
    for s in slices:
        for loc in local_candidates:
            result.append(local_to_global(loc, s, nps))

    return result


def get_node_xy(doc, local_node: int) -> Tuple[float, float]:
    """Return (x, y) for a local (within-slice) node index."""
    return doc.getX(local_node), doc.getY(local_node)
