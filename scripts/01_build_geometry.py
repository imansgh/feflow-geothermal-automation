"""
01_build_geometry.py — Write the FEFLOW supermesh file (.smhx) from scratch.

The .smhx format is XML.  This script writes it programmatically from the
Group 3 workbook coordinates, eliminating all manual GUI interaction for the
geometry stage.

Output: outputs/Group3_geothermal.smhx

Tutorial reference: pp. 4–7 (§2.1)
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import numpy as np
import pandas as pd

from config import load_config, OUTPUTS_DIR, GROUP_ID

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SMHX writer
# ---------------------------------------------------------------------------

def _indent_xml(element: ET.Element) -> str:
    """Return pretty-printed XML string."""
    raw = ET.tostring(element, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def build_smhx(
    domain_size: float,
    well_nodes_xy: np.ndarray,
    output_path: Path,
) -> None:
    """
    Write a FEFLOW supermesh (.smhx) file.

    The file contains:
      - One rectangular polygon (the model domain).
      - One supermesh point per BHE node (well centres + satellite nodes).

    Parameters
    ----------
    domain_size:
        Side length of the square domain in metres (8000 m for this project).
    well_nodes_xy:
        (N, 2) array of (X, Y) coordinates for all BHE nodes.
        For Group 3: 70 rows (10 wells × 7 nodes each).
    output_path:
        Destination .smhx file path.
    """
    # Root element
    root = ET.Element("FeProblem")
    root.set("Version", "1")

    # SuperMesh section
    sm = ET.SubElement(root, "SuperMesh")

    # --- Domain polygon (counter-clockwise corner vertices) -----------------
    polygon = ET.SubElement(sm, "Polygon")
    polygon.set("Id", "0")
    polygon.set("Description", "Domain")

    vertices_elem = ET.SubElement(polygon, "Vertices")
    corners = [
        (0.0, 0.0),
        (domain_size, 0.0),
        (domain_size, domain_size),
        (0.0, domain_size),
    ]
    for x, y in corners:
        v = ET.SubElement(vertices_elem, "Vertex")
        v.set("X", f"{x:.4f}")
        v.set("Y", f"{y:.4f}")

    # Close polygon (repeat first vertex)
    vc = ET.SubElement(vertices_elem, "Vertex")
    vc.set("X", "0.0000")
    vc.set("Y", "0.0000")

    # --- Supermesh points (one per BHE node) --------------------------------
    points_elem = ET.SubElement(sm, "SupermeshPoints")
    for i, (x, y) in enumerate(well_nodes_xy):
        pt = ET.SubElement(points_elem, "Point")
        pt.set("Id", str(i))
        pt.set("X", f"{x:.6f}")
        pt.set("Y", f"{y:.6f}")

    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    xml_str = _indent_xml(root)
    output_path.write_text(xml_str, encoding="utf-8")

    log.info(
        "Supermesh written: %s  (%d polygon vertices, %d supermesh points)",
        output_path.name,
        len(corners),
        len(well_nodes_xy),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Build and save the Group 3 supermesh file."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cfg = load_config()

    # Extract (X, Y) from the wellnodecoordinates sheet
    well_nodes_xy = cfg.well_nodes[["X", "Y"]].to_numpy()

    log.info("Well node array: %d points", len(well_nodes_xy))
    log.info(
        "X range: [%.2f, %.2f]  Y range: [%.2f, %.2f]",
        well_nodes_xy[:, 0].min(), well_nodes_xy[:, 0].max(),
        well_nodes_xy[:, 1].min(), well_nodes_xy[:, 1].max(),
    )

    smhx_path = OUTPUTS_DIR / f"{GROUP_ID}_geothermal.smhx"
    build_smhx(
        domain_size=cfg.domain_size,
        well_nodes_xy=well_nodes_xy,
        output_path=smhx_path,
    )

    # Verification
    assert smhx_path.exists(), "SMHX file was not created"
    tree = ET.parse(smhx_path)
    sm = tree.getroot().find("SuperMesh")
    n_pts = len(sm.find("SupermeshPoints").findall("Point"))
    n_vtx = len(sm.find("Polygon").find("Vertices").findall("Vertex"))
    log.info("Verification: %d polygon vertices, %d supermesh points", n_vtx, n_pts)
    assert n_pts == len(well_nodes_xy), (
        f"Point count mismatch: wrote {len(well_nodes_xy)}, read back {n_pts}"
    )
    log.info("Stage 1 complete — supermesh ready at %s", smhx_path)


if __name__ == "__main__":
    main()
