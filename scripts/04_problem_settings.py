"""
04_problem_settings.py — Configure the FEFLOW problem class for coupled TH simulation.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
The following methods were confirmed to NOT EXIST in FeflowDoc and are NOT used:
    setFlowSimulationMode()       — DNE
    setTransportSimulationMode()  — DNE
    enableHeatTransport()         — DNE
    setFluidDensityMode()         — DNE
    setFluidViscosityMode()       — DNE
    setRefTemperature()           — DNE
    setRefDensity()               — DNE

The ONLY verified API for setting the problem class in FEFLOW 8.1 is:
    doc.getProblemDefinition().setProblemClass(pcls, tcls, type)

Signature (from __doc__):
    void pd.setProblemClass(int pcls[, int tcls[, int type]])
    pcls: PCLS_FLOW | PCLS_HEAT_TRANSPORT | PCLS_MASS_TRANSPORT | PCLS_THERMOHALINE
    tcls: TCLS_STEADY | TCLS_ST_UNST | TCLS_UNSTEADY
    type: TYPE_SATURATED | TYPE_UNSATURATED

Verified enum values (ifm.Enum, FEFLOW 8.1):
    PCLS_HEAT_TRANSPORT = 2   (coupled flow + heat transport)
    TCLS_UNSTEADY       = 1   (fully transient: flow AND transport)
    TYPE_SATURATED      = 0

Settings that CANNOT be applied via IFM 8.1
--------------------------------------------
Temperature-dependent density, temperature-dependent viscosity, reference
temperature (10 °C), and reference density (999.793 kg/m³) have no verified
setter in FeflowDoc. They must be pre-configured in Group3_template.fem via
the FEFLOW GUI before the pipeline is run:
    Problem Settings > Fluid Properties > Density  → Linear T-dependent
    Problem Settings > Fluid Properties > Viscosity → T-dependent
    Problem Settings > Reference Temperature         → 10.0 °C
    Problem Settings > Reference Density             → 999.793 kg/m³

Tutorial reference: pp. 12–14 (§3.2)
"""

from __future__ import annotations

import logging

from config import load_config, OUTPUTS_DIR, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verified enum values — read from live ifm.Enum namespace, FEFLOW 8.1
# ---------------------------------------------------------------------------
# ifm.Enum.PCLS_HEAT_TRANSPORT = 2  (flow + heat transport, no mass transport)
# ifm.Enum.TCLS_UNSTEADY       = 1  (both flow and transport fully transient)
# ifm.Enum.TYPE_SATURATED      = 0  (saturated zone, no unsaturated zone)


# ---------------------------------------------------------------------------
# Settings that require manual GUI configuration
# ---------------------------------------------------------------------------

_MANUAL_SETTINGS = (
    "The following settings CANNOT be applied via FEFLOW 8.1 IFM (no verified setter).\n"
    "They MUST be present in Group3_template.fem before running this pipeline:\n"
    "\n"
    "  1. Fluid density model  : Temperature-dependent, linear\n"
    "     FEFLOW GUI path: Problem Settings > Fluid Properties > Density\n"
    "\n"
    "  2. Fluid viscosity model: Temperature-dependent\n"
    "     FEFLOW GUI path: Problem Settings > Fluid Properties > Viscosity\n"
    "\n"
    "  3. Reference temperature: 10.0 degC\n"
    "     FEFLOW GUI path: Problem Settings > Fluid Properties > Reference Temperature\n"
    "\n"
    "  4. Reference density    : 999.793 kg/m3\n"
    "     FEFLOW GUI path: Problem Settings > Fluid Properties > Reference Density\n"
)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_problem_class(doc, ifm) -> None:
    """
    Set problem class to coupled TH, fully transient, saturated.

    Uses doc.getProblemDefinition().setProblemClass() — the only verified
    FEFLOW 8.1 API for this purpose.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    ifm : module
        Imported IFM module (ifm312).

    Raises
    ------
    RuntimeError
        If setProblemClass raises an exception.
    """
    pd = doc.getProblemDefinition()
    try:
        pd.setProblemClass(
            ifm.Enum.PCLS_HEAT_TRANSPORT,   # 2: flow + heat transport
            ifm.Enum.TCLS_UNSTEADY,          # 1: fully transient
            ifm.Enum.TYPE_SATURATED,         # 0: saturated zone
        )
    except Exception as exc:
        raise RuntimeError(
            f"setProblemClass failed: {exc}\n"
            "Ensure Group3_template.fem was created with a TH problem class in FEFLOW GUI."
        ) from exc

    log.info(
        "Problem class applied: PCLS_HEAT_TRANSPORT=%d, TCLS_UNSTEADY=%d, TYPE_SATURATED=%d",
        ifm.Enum.PCLS_HEAT_TRANSPORT,
        ifm.Enum.TCLS_UNSTEADY,
        ifm.Enum.TYPE_SATURATED,
    )


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify_problem_class(doc, ifm) -> bool:
    """
    Read back problem class and time class from the document and compare
    against expected values.

    Uses:
        doc.getProblemDefinition().getProblemClass()  — verified in FeflowDoc
        doc.getProblemDefinition().getTimeClass()     — verified in FeflowDoc

    Returns
    -------
    bool
        True if both values match expectations, False otherwise.
    """
    pd   = doc.getProblemDefinition()
    pcls = pd.getProblemClass()
    tcls = pd.getTimeClass()

    ok = True

    if pcls != ifm.Enum.PCLS_HEAT_TRANSPORT:
        log.error(
            "Problem class mismatch: expected PCLS_HEAT_TRANSPORT (%d), got %d",
            ifm.Enum.PCLS_HEAT_TRANSPORT, pcls,
        )
        ok = False
    else:
        log.info("  Problem class: PCLS_HEAT_TRANSPORT (%d) [OK]", pcls)

    if tcls != ifm.Enum.TCLS_UNSTEADY:
        log.error(
            "Time class mismatch: expected TCLS_UNSTEADY (%d), got %d",
            ifm.Enum.TCLS_UNSTEADY, tcls,
        )
        ok = False
    else:
        log.info("  Time class   : TCLS_UNSTEADY (%d) [OK]", tcls)

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    cfg = load_config()  # noqa: F841 — kept for pipeline API consistency
    ifm = bootstrap_ifm()

    fem_path = OUTPUTS_DIR / "Group3.fem"
    if not fem_path.exists():
        raise FileNotFoundError(
            f"FEM not found: {fem_path}\n"
            "Stage 02/03 must complete before Stage 04."
        )

    # Remind the operator about settings that cannot be scripted.
    log.warning(_MANUAL_SETTINGS)

    doc = ifm.loadDocument(str(fem_path))

    apply_problem_class(doc, ifm)

    log.info("Verifying problem class readback:")
    if not verify_problem_class(doc, ifm):
        raise RuntimeError(
            "Problem class verification failed. "
            "Check that Group3_template.fem was configured as a TH problem."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 4 complete — problem class saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
