"""
05_material_properties.py — Assign hydraulic and thermal material properties
to every element, layer by layer.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
Fabricated method removed:
    setParamSize(param, val, item)  — DNE in FeflowDoc

Verified replacements used here:
    setParamValues(parameter, values)           — bulk setter; verified signature:
        setParamValues(parameter, values, first_item=0, item_count=len(values))
    setParamValue(parameter, item, value)       — single-item setter; verified signature:
        setParamValue(parameter, item, value)
    getParamValue(parameter, item)              — single-item getter; verified signature:
        getParamValue(parameter, item)

NOTE: getParamSize(param_id) is a VERIFIED method but returns the COUNT of items
(i.e., total number of nodes or elements for that parameter), NOT a value at a
specific index. It was misused in the original script and is NOT called here.

Fabricated enum names removed and replaced:
    P_POROSITY  (DNE) → P_POROH   = 301   kinematic porosity for heat-transport [-]
                                          (P_PORO=201 is mass-transport only; invalid here)
    P_ST        (DNE) → P_CONDUCS = 303   solid thermal conductivity
    P_CS        (DNE) → P_CAPACS  = 302   solid volumetric heat capacity

Verified enum values (ifm.Enum, FEFLOW 8.1):
    P_CONDX   = 101   hydraulic conductivity, x-direction [m/d]
    P_CONDY   = 103   hydraulic conductivity, y-direction [m/d]
    P_CONDZ   = 105   hydraulic conductivity, z-direction [m/d]
    P_POROH   = 301   kinematic porosity for heat-transport [-]
    P_CONDUCS = 303   solid thermal conductivity [J/(m·d·K)]
    P_CAPACS  = 302   solid volumetric heat capacity [J/(m³·K)]

Unit conversions
----------------
P_CONDX/Y/Z  [m/d]       : config K_mday already in m/d.   No conversion.
P_POROH      [-]          : config phi is dimensionless.      No conversion.
P_CAPACS     [J/(m³·K)]  : config Cv in J/(m³·K).           No conversion.
P_CONDUCS    [J/(m·d·K)] : config lambda_s in W/(m·K)
                            = J/(s·m·K).
                            Multiply by 86400 s/d to convert to J/(m·d·K).
                            Authority: setMatHeatSolidConductivity.__doc__:
                            "Physical unit is [J/m/d/K]"

Property table (Group 3)
------------------------
  Layer 1 (caprock,   Slices 1-2):  K=9.37e-4 m/d  phi=0.27   Cv=2.228e6 J/(m3K)  lam=1.76 W/(mK)
  Layer 2 (reservoir, Slices 2-3):  K=6.89e-2 m/d  phi=0.025  Cv=2.247e6 J/(m3K)  lam=2.30 W/(mK)
  Layer 3 (reservoir, Slices 3-4):  (same as layer 2)
  Layer 4 (reservoir, Slices 4-5):  (same as layer 2)
  Layer 5 (basement,  Slices 5-6):  K=5.45e-4 m/d  phi=0.01   Cv=2.611e6 J/(m3K)  lam=4.87 W/(mK)

Element numbering (FEFLOW 8.1, 0-based):
  Elements are ordered by layer: all Layer-1 elements first, then Layer-2, etc.
  Layer L occupies element indices [(L-1)*epl, L*epl - 1].

Implementation choice: setParamValues vs. setParamValue
--------------------------------------------------------
setParamValues(param, list_of_values) sets all items in a single call and is
verified in FEFLOW 8.1. It is used here instead of per-element setParamValue
calls to avoid an inner loop with O(n_elements) Python-to-C boundary crossings.
setParamValue(param, item, val) is reserved for the spot-check verification.

Tutorial reference: pp. 15–20 (§4)
"""

from __future__ import annotations

import logging
from typing import Dict, List

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)

# Seconds per day — used for thermal conductivity unit conversion only.
_S_PER_DAY: float = 86_400.0


# ---------------------------------------------------------------------------
# Enum resolution
# ---------------------------------------------------------------------------

def _resolve_enums(ifm) -> Dict[str, int]:
    """
    Resolve all required parameter IDs from ifm.Enum.

    All names and integer values were verified against the live ifm312.pyd
    (FEFLOW 8.1) during the engineering audit. No fallback to arbitrary
    hardcoded integers is provided — a missing enum name here is a sign of
    a wrong FEFLOW installation, not a version difference.

    Returns
    -------
    dict mapping human label to integer parameter ID.
    """
    return {
        "P_CONDX":   ifm.Enum.P_CONDX,    # 101  [m/d]
        "P_CONDY":   ifm.Enum.P_CONDY,    # 103  [m/d]
        "P_CONDZ":   ifm.Enum.P_CONDZ,    # 105  [m/d]
        "P_POROH":   ifm.Enum.P_POROH,    # 301  [-]  heat-transport porosity (P_PORO=201 is mass-transport only)
        "P_CONDUCS": ifm.Enum.P_CONDUCS,  # 303  [J/(m·d·K)]
        "P_CAPACS":  ifm.Enum.P_CAPACS,   # 302  [J/(m³·K)]
    }


# ---------------------------------------------------------------------------
# Value array construction
# ---------------------------------------------------------------------------

def _build_value_arrays(
    cfg: GeothermalConfig,
    n_layers: int,
    epl: int,
) -> Dict[str, List[float]]:
    """
    Build one value list per parameter, ordered by element index.

    Elements are ordered in FEFLOW as: all Layer-1 elements, then Layer-2, etc.
    Each layer block has exactly epl (elements per layer) entries.

    Parameters
    ----------
    cfg : GeothermalConfig
        Material properties keyed by 1-based layer number.
    n_layers : int
        Number of geological layers (5 for Group 3).
    epl : int
        Number of FEM elements per layer.

    Returns
    -------
    dict with keys 'K', 'phi', 'lam_Jmdk', 'Cv' and list-of-float values.
    """
    K_vals:      List[float] = []
    phi_vals:    List[float] = []
    lam_vals:    List[float] = []   # [J/(m·d·K)] — converted from W/(m·K)
    Cv_vals:     List[float] = []

    for layer in range(1, n_layers + 1):
        K         = cfg.K_mday[layer]
        phi       = cfg.phi[layer]
        lam_Jmdk  = cfg.lambda_s[layer] * _S_PER_DAY   # W/(m·K) → J/(m·d·K)
        Cv        = cfg.Cv[layer]

        K_vals.extend([K] * epl)
        phi_vals.extend([phi] * epl)
        lam_vals.extend([lam_Jmdk] * epl)
        Cv_vals.extend([Cv] * epl)

    return {
        "K":       K_vals,
        "phi":     phi_vals,
        "lam":     lam_vals,
        "Cv":      Cv_vals,
    }


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def assign_material_properties(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Set K, porosity, solid thermal conductivity, and solid heat capacity for
    every element, using bulk setParamValues calls.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        Material properties (K_mday, phi, Cv, lambda_s) keyed by layer number.
    ifm : module
        Imported IFM module (ifm312).
    """
    n_total  = doc.getNumberOfElements()
    epl      = doc.getNumberOfElementsPerLayer()
    n_layers = doc.getNumberOfLayers()

    log.info(
        "Assigning material properties: %d elements total, %d per layer, %d layers",
        n_total, epl, n_layers,
    )

    params = _resolve_enums(ifm)
    arrays = _build_value_arrays(cfg, n_layers, epl)

    if len(arrays["K"]) != n_total:
        raise RuntimeError(
            f"Value array length ({len(arrays['K'])}) does not match "
            f"number of elements ({n_total}). "
            f"Check n_layers={n_layers}, epl={epl}."
        )

    # Isotropic K: x = y = z (tutorial assumption, p. 15)
    # setParamValues(parameter, values) — verified signature, sets all items at once.
    doc.setParamValues(params["P_CONDX"],   arrays["K"])
    doc.setParamValues(params["P_CONDY"],   arrays["K"])
    doc.setParamValues(params["P_CONDZ"],   arrays["K"])
    doc.setParamValues(params["P_POROH"],   arrays["phi"])
    doc.setParamValues(params["P_CONDUCS"], arrays["lam"])   # [J/(m·d·K)]
    doc.setParamValues(params["P_CAPACS"],  arrays["Cv"])    # [J/(m³·K)]

    log.info("Bulk setParamValues complete. Summary per layer:")
    for ly in range(1, n_layers + 1):
        log.info(
            "  Layer %d | K=%.4e m/d | phi=%.4f | "
            "lam=%.4e J/(m·d·K) [%.2f W/(mK)] | Cv=%.4e J/(m3K)",
            ly,
            cfg.K_mday[ly],
            cfg.phi[ly],
            cfg.lambda_s[ly] * _S_PER_DAY,
            cfg.lambda_s[ly],
            cfg.Cv[ly],
        )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_material_properties(doc, cfg: GeothermalConfig, ifm) -> bool:
    """
    Spot-check the first element of each layer for three properties:
    K_x, porosity, and solid thermal conductivity.

    Uses getParamValue(parameter, item) — verified FEFLOW 8.1 API.
    getParamValue returns the float value at a specific element/node index.

    NOTE: getParamSize(param_id) is NOT used here. That function returns
    the COUNT of items for a parameter, not a value — it was misused in
    the original script.

    Returns
    -------
    bool
        True if all spot-checks pass within tolerance.
    """
    epl      = doc.getNumberOfElementsPerLayer()
    n_layers = doc.getNumberOfLayers()
    params   = _resolve_enums(ifm)
    ok       = True
    tol      = 1e-6   # relative tolerance

    for ly in range(1, n_layers + 1):
        e0 = (ly - 1) * epl   # first element of this layer (0-based)

        # -- K_x --
        K_read = doc.getParamValue(params["P_CONDX"], e0)
        K_exp  = cfg.K_mday[ly]
        rel    = abs(K_read - K_exp) / K_exp
        if rel > tol:
            log.error(
                "Layer %d P_CONDX: expected %.6e, got %.6e (rel=%.2e)",
                ly, K_exp, K_read, rel,
            )
            ok = False
        else:
            log.info("  Layer %d P_CONDX : %.6e m/d [OK]", ly, K_read)

        # -- porosity --
        phi_read = doc.getParamValue(params["P_POROH"], e0)
        phi_exp  = cfg.phi[ly]
        rel      = abs(phi_read - phi_exp) / max(phi_exp, 1e-12)
        if rel > tol:
            log.error(
                "Layer %d P_POROH: expected %.6f, got %.6f (rel=%.2e)",
                ly, phi_exp, phi_read, rel,
            )
            ok = False
        else:
            log.info("  Layer %d P_POROH  : %.6f [-] [OK]", ly, phi_read)

        # -- solid thermal conductivity (stored in J/(m·d·K), reported as W/(m·K)) --
        lam_exp_Jmdk = cfg.lambda_s[ly] * _S_PER_DAY
        lam_read     = doc.getParamValue(params["P_CONDUCS"], e0)
        rel          = abs(lam_read - lam_exp_Jmdk) / lam_exp_Jmdk
        if rel > tol:
            log.error(
                "Layer %d P_CONDUCS: expected %.4e J/(m·d·K), got %.4e (rel=%.2e)",
                ly, lam_exp_Jmdk, lam_read, rel,
            )
            ok = False
        else:
            log.info(
                "  Layer %d P_CONDUCS: %.4e J/(m·d·K) [%.2f W/(mK)] [OK]",
                ly, lam_read, lam_read / _S_PER_DAY,
            )

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
            "Stage 03/04 must complete before Stage 05."
        )

    doc = ifm.loadDocument(str(fem_path))

    assign_material_properties(doc, cfg, ifm)

    log.info("Verifying material properties (spot-check, first element per layer):")
    if not verify_material_properties(doc, cfg, ifm):
        raise RuntimeError(
            "Material property verification failed. See log for details."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 5 complete — material properties saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
