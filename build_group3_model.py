"""
build_group3_model.py — Master script for the Group 3 FEFLOW automation pipeline.

Executes all 11 stages in sequence:
  01  Build geometry      → outputs/Group3_geothermal.smhx
  02  Generate mesh       → outputs/Group3.fem  (skeleton)
  03  Create slices       → slice Z-elevations
  04  Problem settings    → TH transient, T-dep fluid
  05  Material properties → K, φ, Cv, λ per layer
  06  Initial conditions  → h = 200 m, T per slice
  07  Boundary conditions → T-BC, heat-flux BC, h-BC
  08  Multilayer wells    → well BCs + T_inj BC
  09  Simulation settings → 36500 d, FE/BE, output schedule
  10  Run model           → Group3.dac
  11  Post-process        → figures + CSV table

Usage
-----
  python build_group3_model.py [--skip-run] [--group N]

Options
-------
  --skip-run    Build and configure the model but do not run the simulation.
                Useful for checking the setup before committing to a long run.
  --group N     Not yet implemented (placeholder for Groups 1–6 extension).

Extensibility
-------------
To generate the model for a different group:
  1. Copy geoth_tutorial_data_GroupN.xlsx into data/.
  2. Edit WORKBOOK_PATH in scripts/config.py (or pass --group N when implemented).
  3. Update the geological constants in _GEOLOGICAL (config.py) for that group.
  4. Run this master script.
  All physics, mesh logic, and output routines remain unchanged.

Requirements
------------
  See requirements.txt.
  FEFLOW 8.1 must be installed (provides the ``ifm`` / ``ifm312`` Python module).
  This pipeline will NOT work with FEFLOW 7.x (verified API names differ).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add scripts/ directory to import path
_SCRIPTS = Path(__file__).parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# ---------------------------------------------------------------------------
# Individual stage imports
# ---------------------------------------------------------------------------
from config import load_config, OUTPUTS_DIR, FIGURES_DIR, GROUP_ID
from utils  import bootstrap_ifm, setup_logging

import importlib

def _import_stage(module_name: str):
    """Dynamically import a numbered stage module."""
    return importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

STAGES = [
    ("01_build_geometry",    "Stage 1: Geometry (supermesh)"),
    ("02_generate_mesh",     "Stage 2: Mesh generation"),
    ("03_create_slices",     "Stage 3: Slice elevations"),
    ("04_problem_settings",  "Stage 4: Problem class & fluid settings"),
    ("05_material_properties","Stage 5: Material properties"),
    ("06_initial_conditions","Stage 6: Initial conditions"),
    ("07_boundary_conditions","Stage 7: Boundary conditions"),
    ("08_multilayer_wells",  "Stage 8: Multilayer wells"),
    ("09_simulation_settings","Stage 9: Simulation settings"),
    ("10_run_model",         "Stage 10: Run simulation"),
    ("11_postprocess",       "Stage 11: Post-processing"),
]


def run_pipeline(skip_run: bool = False) -> None:
    """Execute the complete pipeline."""
    setup_logging(logging.INFO)
    log = logging.getLogger(__name__)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    log.info("=" * 60)
    log.info("%s Geothermal FEFLOW Automation Pipeline", GROUP_ID)
    log.info("=" * 60)
    log.info("Group     : %s", GROUP_ID)
    log.info("Domain    : %.0f × %.0f m", cfg.domain_size, cfg.domain_size)
    log.info("Wells     : %d production + %d injection",
             (~cfg.wells["is_injection"]).sum(),
             cfg.wells["is_injection"].sum())
    log.info("Q/well    : ±30 L/s")
    log.info("t_final   : %.0f d (100 yr)", cfg.t_final)
    log.info("=" * 60)

    pipeline_start = time.time()
    failed: list[str] = []

    for module_name, description in STAGES:
        # Skip the simulation run if requested
        if skip_run and module_name == "10_run_model":
            log.info("[SKIPPED] %s", description)
            continue

        log.info("")
        log.info("─── %s ───", description)
        stage_start = time.time()

        try:
            mod = _import_stage(module_name)
            mod.main()
            elapsed = time.time() - stage_start
            log.info("[OK] %s  (%.1f s)", description, elapsed)
        except Exception as exc:
            elapsed = time.time() - stage_start
            log.error("[FAILED] %s  (%.1f s): %s", description, elapsed, exc)
            failed.append(description)
            # Continue to the next stage regardless of failure.

    total = time.time() - pipeline_start
    log.info("")
    log.info("=" * 60)
    if not failed:
        log.info("Pipeline completed successfully in %.1f s", total)
    else:
        log.warning(
            "Pipeline finished with %d failure(s): %s",
            len(failed), ", ".join(failed)
        )
    log.info("=" * 60)
    log.info("Outputs : %s", OUTPUTS_DIR)
    log.info("Figures : %s", FIGURES_DIR)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and run the Group 3 FEFLOW geothermal model."
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Build and configure the model but skip the simulation (Stage 10).",
    )
    parser.add_argument(
        "--group",
        type=int,
        default=3,
        help="Group number (1–6).  Currently only Group 3 is implemented.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.group != 3:
        print(f"Group {args.group} not yet implemented. Only Group 3 is supported.")
        sys.exit(1)
    run_pipeline(skip_run=args.skip_run)
