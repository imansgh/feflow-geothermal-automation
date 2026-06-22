"""
config.py — Central configuration for the Group 3 geothermal FEFLOW model.

All physical parameters, file paths and derived quantities are assembled here
from the Group 3 workbook and the reservoir-properties PDF.  Every downstream
script imports ``load_config()`` rather than reading the workbook itself.

To adapt this pipeline for Groups 1–6, change WORKBOOK_PATH and the geological
constants in ``_GEOLOGICAL`` to match the target group's values.

Tutorial reference: FEFLOW Geothermal Energy Tutorial, Alessandro Casasso,
rev00 (03/06/2024), pp. 2–14.
"""

from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent          # Group3_automation/
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = ROOT / "figures"

# Group identifier — change this (and _GEOLOGICAL below) to adapt the pipeline
# for a different group (1–6).  All file names and log messages derive from it.
GROUP_ID: str = "Group3"

WORKBOOK_PATH = DATA_DIR / f"geoth_tutorial_data_{GROUP_ID}.xlsx"
FEM_PATH      = OUTPUTS_DIR / f"{GROUP_ID}.fem"
RESULTS_PATH  = OUTPUTS_DIR / f"{GROUP_ID}.dac"

# ---------------------------------------------------------------------------
# Geological constants — source: reservoir properties PDF (Group 3 column)
# These do NOT appear in the workbook; they must be changed per group.
# ---------------------------------------------------------------------------

_GEOLOGICAL: Dict[str, Dict] = {
    "caprock": {
        "lambda_s": 1.76,        # W/(m·K)  thermal conductivity solid
        "Cv":       2.228e6,     # J/(m³·K) volumetric heat capacity
        "phi":      0.27,        # —         porosity
        "k":        1.243e-15,   # m²        intrinsic permeability
    },
    "reservoir": {
        "lambda_s": 2.30,
        "Cv":       2.247e6,
        "phi":      0.025,
        "k":        9.133e-14,
    },
    "basement": {
        "lambda_s": 4.87,
        "Cv":       2.611e6,
        "phi":      0.01,
        "k":        7.226e-16,
    },
}

# ---------------------------------------------------------------------------
# Reference fluid properties at 10 °C (tutorial p. 14, FEFLOW default)
# ---------------------------------------------------------------------------

_RHO_REF = 999.793     # kg/m³
_MU_REF  = 1.124e-3    # Pa·s  (= 97.1136 kg/(m·d))
_G       = 9.81        # m/s²

def _k_to_K(k_m2: float) -> float:
    """Convert intrinsic permeability [m²] to hydraulic conductivity [m/d]."""
    return k_m2 * _RHO_REF * _G / _MU_REF * 86_400   # m/d


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class GeothermalConfig:
    """All parameters required to build the FEFLOW model."""

    # ---- Geometry ----------------------------------------------------------
    z_surface:        float = 600.0    # m a.s.l.  ground surface
    z_top_reservoir:  float = -270.0   # m a.s.l.
    z_bot_reservoir:  float = -520.0   # m a.s.l.
    z_bot_basement:   float = -2500.0  # m a.s.l.

    # Derived slice elevations (set in __post_init__)
    slice_elevations: List[float] = field(default_factory=list)

    # Slice depths below surface [m] (positive downward)
    slice_depths: List[float] = field(default_factory=list)

    # ---- Thermal -----------------------------------------------------------
    T_surface:   float = 15.0    # °C
    heat_flux:   float = 0.241   # W/m²  → 241 mW/m²
    T_inj:       float = 50.0    # °C  reinjection temperature
    slice_T:     List[float] = field(default_factory=list)  # °C per slice

    # ---- Hydraulic ---------------------------------------------------------
    h_initial:   float = 200.0   # m  hydraulic head everywhere

    # ---- Domain ------------------------------------------------------------
    domain_size: float = 8000.0  # m  (square side)

    # ---- Material properties per layer (1 = caprock, 2-4 = reservoir, 5 = basement)
    K_mday:      Dict[int, float] = field(default_factory=dict)   # m/d
    phi:         Dict[int, float] = field(default_factory=dict)
    Cv:          Dict[int, float] = field(default_factory=dict)   # J/(m³·K)
    lambda_s:    Dict[int, float] = field(default_factory=dict)   # W/(m·K)

    # ---- Reference fluid ---------------------------------------------------
    rho_ref:     float = _RHO_REF    # kg/m³
    mu_ref:      float = _MU_REF     # Pa·s
    T_ref:       float = 10.0        # °C

    # ---- Wells (from workbook) ---------------------------------------------
    wells:       pd.DataFrame = field(default_factory=pd.DataFrame)
    well_nodes:  pd.DataFrame = field(default_factory=pd.DataFrame)
    # columns: mesh_node_id, X, Y

    # ---- Simulation --------------------------------------------------------
    t_final:     float = 36_500.0    # d (100 years)
    dt_initial:  float = 1e-10       # d
    dt_max:      float = 100.0       # d
    output_times: List[float] = field(default_factory=list)   # d

    # ---- Heat-flux BC (J/m²/d, negative = into domain) --------------------
    heat_flux_bc: float = 0.0

    def __post_init__(self) -> None:
        # Slice elevations
        self.slice_elevations = [
            self.z_surface,          # Slice 1  +600 m
            self.z_top_reservoir,    # Slice 2  -270 m
            self.z_top_reservoir - 100.0,   # Slice 3  -370 m
            self.z_top_reservoir - 200.0,   # Slice 4  -470 m
            self.z_bot_reservoir,    # Slice 5  -520 m
            self.z_bot_basement,     # Slice 6 -2500 m
        ]
        # Depths (positive downward)
        self.slice_depths = [
            self.z_surface - z for z in self.slice_elevations
        ]

        # Geothermal temperature per slice (Fourier: T = T_surface + q/λ · Δz)
        q = self.heat_flux
        lam = _GEOLOGICAL
        T1 = self.T_surface
        T2 = T1 + (q / lam["caprock"]["lambda_s"])   * (self.slice_depths[1] - self.slice_depths[0])
        T3 = T2 + (q / lam["reservoir"]["lambda_s"]) * (self.slice_depths[2] - self.slice_depths[1])
        T4 = T2 + (q / lam["reservoir"]["lambda_s"]) * (self.slice_depths[3] - self.slice_depths[1])
        T5 = T2 + (q / lam["reservoir"]["lambda_s"]) * (self.slice_depths[4] - self.slice_depths[1])
        T6 = T5 + (q / lam["basement"]["lambda_s"])  * (self.slice_depths[5] - self.slice_depths[4])
        self.slice_T = [round(t, 4) for t in [T1, T2, T3, T4, T5, T6]]

        # Material properties per layer
        # Layer 1 = caprock, layers 2-4 = reservoir, layer 5 = basement
        for layer_idx, geo_key in [(1, "caprock"),
                                   (2, "reservoir"), (3, "reservoir"), (4, "reservoir"),
                                   (5, "basement")]:
            geo = lam[geo_key]
            self.K_mday[layer_idx]   = _k_to_K(geo["k"])
            self.phi[layer_idx]      = geo["phi"]
            self.Cv[layer_idx]       = geo["Cv"]
            self.lambda_s[layer_idx] = geo["lambda_s"]

        # Heat-flux BC: convert W/m² → J/(m²·d), sign: negative = into domain
        self.heat_flux_bc = -self.heat_flux * 86_400.0

        # Output times: every 5 years (1825 d) over 100 years
        self.output_times = [1825.0 * i for i in range(1, 21)]   # 20 snapshots


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(workbook: Path = WORKBOOK_PATH) -> GeothermalConfig:
    """
    Read Group 3 workbook and return a fully populated GeothermalConfig.

    Parameters
    ----------
    workbook:
        Path to ``geoth_tutorial_data_Group3.xlsx``.

    Returns
    -------
    GeothermalConfig
    """
    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")

    cfg = GeothermalConfig()

    # ---- welldata sheet ----------------------------------------------------
    df_wells = pd.read_excel(workbook, sheet_name="welldata")
    df_wells.columns = [c.strip().lower().replace(" ", "_") for c in df_wells.columns]
    # Rename to canonical names
    df_wells = df_wells.rename(columns={
        "well_id":      "name",
        "depth_top":    "depth_top",
        "depth_bottom": "depth_bottom",
        "radius":       "radius",
        "rate":         "rate_lps",   # L/s; positive = production, negative = injection
    })
    df_wells["is_injection"] = df_wells["rate_lps"] < 0
    cfg.wells = df_wells.reset_index(drop=True)

    # ---- wellnodecoordinates sheet -----------------------------------------
    df_wnc = pd.read_excel(workbook, sheet_name="wellnodecoordinates")
    # Keep only mesh_node_id, X, Y columns
    df_wnc = df_wnc.iloc[:, :3].copy()
    df_wnc.columns = ["mesh_node_id", "X", "Y"]
    df_wnc = df_wnc.dropna(subset=["X", "Y"]).reset_index(drop=True)
    cfg.well_nodes = df_wnc

    # ---- Tinj sheet --------------------------------------------------------
    df_tinj = pd.read_excel(workbook, sheet_name="Tinj")
    df_tinj.columns = [c.strip() for c in df_tinj.columns]
    t_inj_vals = df_tinj["Tinj"].dropna().unique()
    if len(t_inj_vals) == 1:
        cfg.T_inj = float(t_inj_vals[0])
    else:
        log.warning("Multiple Tinj values found; using %s °C", t_inj_vals[0])
        cfg.T_inj = float(t_inj_vals[0])

    # ---- Validate temperatures (cross-check with workbook sliceT) ----------
    df_sliceT = pd.read_excel(workbook, sheet_name="sliceT")
    df_sliceT.columns = ["slice", "Tinit", "depth"]
    wb_T = list(df_sliceT["Tinit"].dropna())
    for i, (computed, expected) in enumerate(zip(cfg.slice_T, wb_T), start=1):
        delta = abs(computed - expected)
        if delta > 0.05:
            log.warning(
                "Slice %d temperature mismatch: computed %.4f °C vs workbook %.4f °C "
                "(Δ = %.4f °C)",
                i, computed, expected, delta
            )

    log.info("Configuration loaded from %s", workbook.name)
    log.info("Slice temperatures: %s", cfg.slice_T)
    log.info("Heat-flux BC: %.2f J/(m²·d)", cfg.heat_flux_bc)
    log.info(
        "K (m/d): caprock=%.4e reservoir=%.4e basement=%.4e",
        cfg.K_mday[1], cfg.K_mday[2], cfg.K_mday[5],
    )
    log.info("Wells: %d total (%d production, %d injection)",
             len(df_wells),
             (~df_wells["is_injection"]).sum(),
             df_wells["is_injection"].sum())

    return cfg


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    cfg = load_config()

    print("\n=== GeothermalConfig (Group 3) ===")
    print(f"Domain: {cfg.domain_size} × {cfg.domain_size} m")
    print(f"Slices: {len(cfg.slice_elevations)}  elevations = {cfg.slice_elevations}")
    print(f"T per slice (°C): {cfg.slice_T}")
    print(f"Heat-flux BC: {cfg.heat_flux_bc:.2f} J/(m²·d)")
    print(f"t_final: {cfg.t_final} d  dt_init: {cfg.dt_initial}  dt_max: {cfg.dt_max}")
    print()
    print("Material properties per layer:")
    for ly in range(1, 6):
        print(f"  Layer {ly}: K={cfg.K_mday[ly]:.4e} m/d  phi={cfg.phi[ly]}  "
              f"Cv={cfg.Cv[ly]:.4e} J/(m3K)  lam={cfg.lambda_s[ly]} W/(mK)")
    print()
    print(cfg.wells.to_string(index=False))
