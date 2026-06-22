"""
09_simulation_settings.py — Configure time-stepping, predictor-corrector
scheme, and output schedule for the Group 3 geothermal doublet model.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
The following methods were confirmed to NOT EXIST in FeflowDoc:
    setTimeLength()           — DNE  (the original script's primary time setter)
    setMaxTimeIncrement()     — DNE  (maximum time step)
    setTimeSteppingScheme()   — DNE  (predictor-corrector variant)
    setTimeStepControlMode()  — DNE  (automatic vs manual control)
    addObservationTime()      — DNE  (individual output-time adder)
    setResultsFileName()      — DNE  (DAC file path)
    getTimeLength()           — DNE  (verify read-back)
    getMaxTimeIncrement()     — DNE  (verify read-back)

Every one of these was silently swallowed by try/except in the original file.
The FEM was saved with no simulation settings applied.

Verified replacements (confirmed present in ifm312.pyd with full __doc__):
---------------------------------------------------------------------------
  setFinalSimulationTime(tend)                          [d]
  getFinalSimulationTime()                    → float   [d]
  setInitialSimulationTime(tini)                        [d]
  getInitialSimulationTime()                  → float   [d]
  setInitialTimeIncrement(init_dt)                      [d]
  getInitialTimeIncrement()                   → float   [d]
  setTimeSteppingKind(KTSFlag)
      KTS_PCS (=0) = predictor-corrector
      KTS_CTS (=1) = constant time stepping
  getTimeSteppingKind()                       → int
  setPredictorCorrectorMethod(PCSFlag)
      PCS_FEBE (=0) = Forward Euler / Backward Euler  ← tutorial setting
      PCS_ABTR (=1) = Adams-Bashforth / Trapezoid Rule
  getPredictorCorrectorMethod()               → int
  setPredictorCorrectorTimeStepMaximumSize(Mtsize)      [d]
  getPredictorCorrectorTimeStepMaximumSize()  → float   [d]
  setCustomTimes(arTimes [, nFlags])
      arTimes : list[float] of times [d] for adaptive control to navigate to
      nFlags  : target flags (IfmCUSTOMSTEPS_* — NOT in ifm.Enum; see below)
  queryCustomTimes()                          → tuple([float], int)

Verified enums (ifm.Enum, FEFLOW 8.1):
    KTS_PCS  = 0    predictor-corrector time stepping
    KTS_CTS  = 1    constant time stepping
    PCS_FEBE = 0    FE/BE predictor-corrector
    PCS_ABTR = 1    AB/TR predictor-corrector
    F_BINARY = 1    binary DAC file (used in Stage 10 startSimulator)

Additionally observed (purpose uncertain — not used here):
    TS_CONSTANT_STEPS    = 0
    TS_VARYING_STEPS     = 1
    TS_PREDICTOR_CORRECTOR = 2
    These appear to be a separate enum set whose relationship to
    setTimeSteppingKind() is not documented in __doc__.

Results file (DAC) — Stage 10 responsibility
---------------------------------------------
setResultsFileName() does NOT EXIST in FeflowDoc. The DAC output file path
is passed directly to startSimulator() in Stage 10:
    doc.startSimulator(str(RESULTS_PATH), ifm.Enum.F_BINARY, output_times)
It is NOT configured here.

Output schedule (setCustomTimes)
---------------------------------
setCustomTimes(arTimes [, nFlags]) instructs FEFLOW's adaptive time-stepping
to navigate to each time in arTimes — FEFLOW will ensure that it evaluates
and records a result at exactly each of those times.

The optional nFlags argument is documented as:
    "IfmCUSTOMSTEPS_ALL | IfmCUSTOMSTEPS_OUTPUT | IfmCUSTOMSTEPS_SIMUL"
but these constant names are NOT present in ifm.Enum in FEFLOW 8.1.
setCustomTimes is called without nFlags, relying on the default behaviour.
See "Remaining uncertainties" #2.

Settings (Group 3, tutorial p. 13)
------------------------------------
  t_start      =      0 d       (cfg.output_times starts at 1825 d)
  t_final      = 36 500 d       (100 years)
  dt_initial   =  1e-10 d       (extremely small first step for stability)
  dt_max       =    100 d       (maximum allowed time step size)
  Scheme       =  KTS_PCS + PCS_FEBE
                 (predictor-corrector, FE/BE variant — unconditionally stable)
  Output times =  1825, 3650, …, 36 500 d  (every 5 years, 20 snapshots)
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
    Resolve time-stepping enums from the live ifm.Enum namespace.

    Verified values (FEFLOW 8.1, ifm312.pyd):
        KTS_PCS  = 0    predictor-corrector kind
        PCS_FEBE = 0    FE/BE method

    Raises AttributeError immediately on any missing name — fail fast, no
    integer fallbacks.
    """
    return {
        "KTS_PCS":  ifm.Enum.KTS_PCS,    # 0
        "PCS_FEBE": ifm.Enum.PCS_FEBE,   # 0
    }


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def apply_simulation_settings(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Apply all time-stepping and output-schedule settings to the document.

    Uses only the six setters verified against ifm312.pyd. No try/except
    wrappers — any AttributeError here indicates a wrong FEFLOW installation
    and should surface immediately rather than being silently ignored.

    Parameters
    ----------
    doc : FeflowDoc
        Loaded FEFLOW document (writable).
    cfg : GeothermalConfig
        t_final, dt_initial, dt_max, output_times.
    ifm : module
        Imported IFM module (ifm312).
    """
    enums = _resolve_enums(ifm)

    # 1. Final simulation time [d]
    #    Replaces DNE setTimeLength().
    doc.setFinalSimulationTime(float(cfg.t_final))
    log.info(
        "Final simulation time  : %.0f d  (= %.0f years)",
        cfg.t_final, cfg.t_final / 365.25,
    )

    # 2. Initial simulation time [d]
    #    Absent from the original script; included for completeness.
    doc.setInitialSimulationTime(0.0)
    log.info("Initial simulation time: 0 d")

    # 3. Initial time step [d]
    #    setInitialTimeIncrement() EXISTS in FEFLOW 8.1 — no change to the call.
    doc.setInitialTimeIncrement(float(cfg.dt_initial))
    log.info("Initial time step      : %.2e d", cfg.dt_initial)

    # 4. Time-stepping kind: predictor-corrector
    #    Replaces DNE setTimeStepControlMode(0).
    #    KTS_PCS (=0) activates the predictor-corrector adaptive scheme.
    doc.setTimeSteppingKind(enums["KTS_PCS"])
    log.info(
        "Time-stepping kind     : KTS_PCS (%d) — predictor-corrector",
        enums["KTS_PCS"],
    )

    # 5. Predictor-corrector method: FE/BE
    #    Replaces DNE setTimeSteppingScheme(1).
    #    PCS_FEBE (=0) = Forward Euler predictor + Backward Euler corrector.
    #    This is unconditionally stable for TH coupling (tutorial §3.2).
    doc.setPredictorCorrectorMethod(enums["PCS_FEBE"])
    log.info(
        "PC method              : PCS_FEBE (%d) — FE/BE (unconditionally stable)",
        enums["PCS_FEBE"],
    )

    # 6. Maximum time step [d]
    #    Replaces DNE setMaxTimeIncrement().
    #    A negative value switches off bounding (per __doc__); we use 100 d.
    doc.setPredictorCorrectorTimeStepMaximumSize(float(cfg.dt_max))
    log.info("Maximum time step      : %.0f d", cfg.dt_max)

    # 7. Custom output / navigation times [d]
    #    Replaces DNE addObservationTime() loop.
    #    setCustomTimes() instructs FEFLOW's adaptive stepper to navigate to
    #    each time exactly, ensuring results are recorded at those instants.
    #    nFlags is omitted — IfmCUSTOMSTEPS_* constants are NOT in ifm.Enum
    #    (see "Remaining uncertainties" #2 in module docstring).
    output_times: List[float] = [float(t) for t in cfg.output_times]
    doc.setCustomTimes(output_times)
    n = len(output_times)
    interval = output_times[1] - output_times[0] if n > 1 else output_times[0]
    log.info(
        "Custom times           : %d snapshots every %.0f d  "
        "(t = %.0f … %.0f d)",
        n, interval, output_times[0], output_times[-1],
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_simulation_settings(doc, cfg: GeothermalConfig, ifm) -> bool:
    """
    Read back all six settings and compare against expected values.

    Getters used (all verified present in FeflowDoc, FEFLOW 8.1):
        getFinalSimulationTime()                    → float [d]
        getInitialSimulationTime()                  → float [d]
        getInitialTimeIncrement()                   → float [d]
        getTimeSteppingKind()                       → int
        getPredictorCorrectorMethod()               → int
        getPredictorCorrectorTimeStepMaximumSize()  → float [d]
        queryCustomTimes()                          → tuple([float], int)

    Returns
    -------
    bool
        True if all checks pass within tolerance.
    """
    enums = _resolve_enums(ifm)
    ok    = True

    # --- final time ---
    t_end = doc.getFinalSimulationTime()
    if abs(t_end - cfg.t_final) > 0.5:
        log.error(
            "t_final: expected %.0f d, got %.4f d", cfg.t_final, t_end,
        )
        ok = False
    else:
        log.info("  t_final        : %.0f d [OK]", t_end)

    # --- initial time ---
    t_ini = doc.getInitialSimulationTime()
    if abs(t_ini) > 1e-12:
        log.error("t_initial: expected 0 d, got %.4e d", t_ini)
        ok = False
    else:
        log.info("  t_initial      : %.0f d [OK]", t_ini)

    # --- initial time step ---
    dt0 = doc.getInitialTimeIncrement()
    rel = abs(dt0 - cfg.dt_initial) / max(cfg.dt_initial, 1e-20)
    if rel > 1e-4:
        log.error(
            "dt_initial: expected %.2e d, got %.4e d (rel=%.2e)",
            cfg.dt_initial, dt0, rel,
        )
        ok = False
    else:
        log.info("  dt_initial     : %.2e d [OK]", dt0)

    # --- time stepping kind ---
    kts = doc.getTimeSteppingKind()
    if kts != enums["KTS_PCS"]:
        log.error(
            "TimeSteppingKind: expected KTS_PCS (%d), got %d",
            enums["KTS_PCS"], kts,
        )
        ok = False
    else:
        log.info("  TimeSteppingKind: KTS_PCS (%d) [OK]", kts)

    # --- predictor-corrector method ---
    pcs = doc.getPredictorCorrectorMethod()
    if pcs != enums["PCS_FEBE"]:
        log.error(
            "PCMethod: expected PCS_FEBE (%d), got %d",
            enums["PCS_FEBE"], pcs,
        )
        ok = False
    else:
        log.info("  PCMethod       : PCS_FEBE (%d) [OK]", pcs)

    # --- maximum time step ---
    dt_max = doc.getPredictorCorrectorTimeStepMaximumSize()
    if abs(dt_max - cfg.dt_max) > 0.5:
        log.error(
            "dt_max: expected %.0f d, got %.4f d", cfg.dt_max, dt_max,
        )
        ok = False
    else:
        log.info("  dt_max         : %.0f d [OK]", dt_max)

    # --- custom times ---
    # queryCustomTimes() returns tuple([float], int) — the int is the count.
    result = doc.queryCustomTimes()
    if result is None or len(result) < 2:
        log.warning(
            "queryCustomTimes() returned unexpected format: %r. "
            "Cannot verify output schedule.",
            result,
        )
    else:
        # result[0] = list of times; result[1] = nFlags int (NOT a count).
        # Derive count from the list itself.
        times_read = result[0]
        n_read     = len(times_read)
        n_exp      = len(cfg.output_times)
        if n_read != n_exp:
            log.error(
                "Custom times count: expected %d, got %d", n_exp, n_read,
            )
            ok = False
        else:
            # Spot-check first and last
            t_first   = float(times_read[0])  if times_read else None
            t_last    = float(times_read[-1]) if times_read else None
            exp_first = cfg.output_times[0]
            exp_last  = cfg.output_times[-1]
            if t_first is not None and abs(t_first - exp_first) > 0.5:
                log.error(
                    "Custom times[0]: expected %.0f d, got %.4f d",
                    exp_first, t_first,
                )
                ok = False
            elif t_last is not None and abs(t_last - exp_last) > 0.5:
                log.error(
                    "Custom times[-1]: expected %.0f d, got %.4f d",
                    exp_last, t_last,
                )
                ok = False
            else:
                log.info(
                    "  Custom times   : %d snapshots, %.0f...%.0f d [OK]",
                    n_read, t_first, t_last,
                )

    if ok:
        log.info("Simulation settings verification: ALL PASSED")
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
            "Stage 08 must complete before Stage 09."
        )

    doc = ifm.loadDocument(str(fem_path))

    apply_simulation_settings(doc, cfg, ifm)

    log.info("Verifying simulation settings (readback):")
    if not verify_simulation_settings(doc, cfg, ifm):
        raise RuntimeError(
            "Simulation settings verification failed. See log for details."
        )

    doc.saveDocument(str(fem_path))
    log.info("Stage 9 complete — simulation settings saved to %s", fem_path.name)


if __name__ == "__main__":
    main()
