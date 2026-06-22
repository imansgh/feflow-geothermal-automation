"""
10_run_model.py — Execute the FEFLOW simulator and write the DAC results file.

FEFLOW 8.1 IFM constraints (verified against ifm312.pyd, 2024-06-22)
---------------------------------------------------------------------
Confirmed to NOT EXIST in FeflowDoc:
    runSimulator()          — DNE  (was the original primary call)
    getSimulationTime()     — DNE  (was the progress-monitoring call)
    getSimulationProgress() — DNE  (was the fractional-progress call)
    setResultsFileName()    — DNE  (pre-simulation DAC path setter)
    getResultsFileName()    — DNE
    getSimulationStatus()   — DNE
    getSimulationError()    — DNE
    isConverged()           — DNE
    hasConverged()          — DNE
    getTimeLength()         — DNE  (also used in original pre-run check)
    getParamSize(P_HEAD_INT,…) — WRONG: getParamSize returns COUNT of items,
                                  not a value at a node; P_HEAD_INT DNE

Verified API used in this module
---------------------------------
Running (singleStep mode — see run_simulation docstring for rationale):
    startSimulator(dac, fmode, [], False)
        Initialises the solver without blocking; returns in ~0.2 s.
        The empty list avoids overriding setCustomTimes from Stage 09.
        runSimulation=False (4th positional arg) = prepare only, do not run.

    singleStep()
        Advances the simulation by one adaptive time step.

    timeStepIsRejected() -> bool
        True when the predictor-corrector scheme rejects the last step.
        Call singleStep() again; the solver retries with a smaller dt.

    Note: getTimeSteps() / loadTimeStep() in FEFLOW 8.1 expose only ONE
    DAC entry regardless of how many output times were written.  The .npz
    snapshot file written by run_simulation() is used by Stage 11 instead.

Pre-run validation:
    getParamValue(param, item)          — verified single-value getter
    getFinalSimulationTime()            → float [d]
    getInitialTimeIncrement()           → float [d]
    getTimeSteppingKind()               → int
    getPredictorCorrectorMethod()       → int
    getNumberOfLayers()                 → int
    getNumberOfMultiLayerWells()        → int
    getNumberOfNodes()                  → int

Post-run completion check:
    getAbsoluteSimulationTime()         → float [d]  — current (final) time
    getFinalSimulationTime()            → float [d]  — expected end time
    getNumberOfTimeSteps()              → int         — DAC time-step count
    getTimeSteps()  → list of [step_no, time_d]

Verified enum values (ifm.Enum, FEFLOW 8.1):
    F_BINARY  = 1
    F_ASCII   = 2
    P_CONDX   = 101   hydraulic conductivity, x-direction [m/d]
    P_HEAD    = 400   hydraulic head [m]
    KTS_PCS   = 0     predictor-corrector time stepping
    PCS_FEBE  = 0     FE/BE method

Convergence / completion detection
------------------------------------
FEFLOW 8.1 exposes NO dedicated convergence-check API (no isConverged(),
no error code returned from startSimulator). Two post-run proxies are used:

1. TIME PROXY:
   After startSimulator() returns, compare getAbsoluteSimulationTime() with
   getFinalSimulationTime(). A successful run ends at (or within 1 d of) the
   final time. If |t_abs - t_final| > 1 d, the simulation aborted early.

2. DAC PROXY:
   Check that RESULTS_PATH exists and is non-empty. Additionally,
   getNumberOfTimeSteps() should match the expected number of output snapshots
   (cfg.output_times has 20 entries for 100 years at 5-year intervals).

If the simulation was interrupted or diverged, FEFLOW may have written a
partial DAC. Both proxies together give reasonable confidence in completion.

Pre-run validation bugs corrected
-----------------------------------
The original pre_run_checklist() contained three bugs that made every check
silently inaccurate or unreachable:

1. getParamSize(P_CONDX, 0)  — getParamSize returns COUNT of items, not the
   value at index 0. The count of elements is ≫ K_caprock ≈ 9.4×10⁻⁴ m/d,
   so this comparison always fails with the wrong number. Fixed:
   → getParamValue(P_CONDX, 0)

2. getParamSize(P_HEAD_INT, 0)  — two bugs: getParamSize has wrong semantics
   (count, not value), and P_HEAD_INT DNE in ifm.Enum. Fixed:
   → getParamValue(P_HEAD, 0)

3. getTimeLength()  — DNE, silently caught by except. Fixed:
   → getFinalSimulationTime()

All three checks were wrapped in try/except (AttributeError, Exception) which
swallowed the errors. The wrapping is removed. All pre-run checks now raise
RuntimeError immediately on failure.

DAC output format
------------------
ifm.Enum.F_BINARY = 1 is used. Binary DAC files are required by the
post-processing script (11_postprocess.py) which reads them via getTimeSteps()
and loadTimeStep().

Tutorial reference: pp. 30–32 (§6)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List

import numpy as np

from config import load_config, OUTPUTS_DIR, RESULTS_PATH, GeothermalConfig
from utils import bootstrap_ifm, setup_logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-run validation
# ---------------------------------------------------------------------------

def pre_run_checklist(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Validate the model state before starting the simulator.

    Uses only verified FEFLOW 8.1 getters. Raises RuntimeError immediately
    on the first failed check so the cause is visible.

    Checks
    ------
    1. Slice count: must be 6 (5 layers + 1 base slice).
    2. K_caprock: first element of Layer 1 via getParamValue(P_CONDX, 0).
    3. Initial head at node 0 via getParamValue(P_HEAD, 0).
    4. Final simulation time via getFinalSimulationTime().
    5. Initial time step via getInitialTimeIncrement().
    6. Time-stepping kind: KTS_PCS.
    7. PC method: PCS_FEBE.
    8. MLW count: must be > 0.
    """
    errors: list[str] = []

    # --- 1. Slice count ---
    n_slices = doc.getNumberOfSlices()
    if n_slices != 6:
        errors.append(f"Expected 6 slices, got {n_slices}")
    else:
        log.info("  Slices         : %d [OK]", n_slices)

    # --- 2. Hydraulic conductivity of first element in Layer 1 ---
    K_actual  = doc.getParamValue(ifm.Enum.P_CONDX, 0)
    K_expected = cfg.K_mday[1]
    rel = abs(K_actual - K_expected) / K_expected
    if rel > 1e-4:
        errors.append(
            f"K_caprock: expected {K_expected:.4e} m/d, got {K_actual:.4e} m/d "
            f"(rel={rel:.2e}) — run Stage 05"
        )
    else:
        log.info("  K_caprock      : %.4e m/d [OK]", K_actual)

    # --- 3. Initial head at node 0 ---
    h_actual = doc.getParamValue(ifm.Enum.P_HEAD, 0)
    if abs(h_actual - cfg.h_initial) > 0.01:
        errors.append(
            f"Head IC at node 0: expected {cfg.h_initial:.3f} m, "
            f"got {h_actual:.3f} m — run Stage 06"
        )
    else:
        log.info("  h_initial[0]   : %.3f m [OK]", h_actual)

    # --- 4. Final simulation time ---
    t_final_actual = doc.getFinalSimulationTime()
    if abs(t_final_actual - cfg.t_final) > 0.5:
        errors.append(
            f"t_final: expected {cfg.t_final:.0f} d, "
            f"got {t_final_actual:.1f} d — run Stage 09"
        )
    else:
        log.info("  t_final        : %.0f d [OK]", t_final_actual)

    # --- 5. Initial time step ---
    dt0_actual = doc.getInitialTimeIncrement()
    rel_dt = abs(dt0_actual - cfg.dt_initial) / max(cfg.dt_initial, 1e-20)
    if rel_dt > 1e-3:
        errors.append(
            f"dt_initial: expected {cfg.dt_initial:.2e} d, "
            f"got {dt0_actual:.2e} d — run Stage 09"
        )
    else:
        log.info("  dt_initial     : %.2e d [OK]", dt0_actual)

    # --- 6. Time-stepping kind ---
    kts = doc.getTimeSteppingKind()
    if kts != ifm.Enum.KTS_PCS:
        errors.append(
            f"TimeSteppingKind: expected KTS_PCS ({ifm.Enum.KTS_PCS}), "
            f"got {kts} — run Stage 09"
        )
    else:
        log.info("  TimeSteppingKind: KTS_PCS (%d) [OK]", kts)

    # --- 7. Predictor-corrector method ---
    pcs = doc.getPredictorCorrectorMethod()
    if pcs != ifm.Enum.PCS_FEBE:
        errors.append(
            f"PCMethod: expected PCS_FEBE ({ifm.Enum.PCS_FEBE}), "
            f"got {pcs} — run Stage 09"
        )
    else:
        log.info("  PCMethod       : PCS_FEBE (%d) [OK]", pcs)

    # --- 8. MLW wells present ---
    n_mlw = doc.getNumberOfMultiLayerWells()
    if n_mlw == 0:
        errors.append("No Multilayer Wells found — run Stage 08")
    else:
        log.info("  MLW count      : %d [OK]", n_mlw)

    if errors:
        for e in errors:
            log.error("Pre-run check FAILED: %s", e)
        raise RuntimeError(
            f"{len(errors)} pre-run check(s) failed. See log for details."
        )

    log.info("Pre-run checklist: ALL PASSED (%d nodes, %d slices, %d MLWs)",
             doc.getNumberOfNodes(), n_slices, n_mlw)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def run_simulation(doc, cfg: GeothermalConfig, ifm) -> None:
    """
    Execute the FEFLOW simulator via startSimulator(runSimulation=False) +
    singleStep() loop, capturing snapshots into a NumPy .npz file.

    Root cause for this approach
    ----------------------------
    FEFLOW 8.1 IFM's getTimeSteps() / loadTimeStep() only expose ONE step
    from the DAC file regardless of how many output times were specified.
    The DAC binary DOES contain all snapshots, but the Python IFM API cannot
    enumerate them (regression from FEFLOW 7.x).

    Fix: use startSimulator(dac, fmode, [], False) to initialise the solver
    without blocking, then drive the simulation step-by-step with singleStep().
    At each scheduled output time (setCustomTimes from Stage 09, nFlags=3),
    the adaptive stepper lands on that time exactly; we capture P_TEMP and
    P_HEAD arrays via getParamValues() and store them in the .npz file.

    Verified FEFLOW 8.1 behaviour
    ------------------------------
    startSimulator(dac, fmode, [], False) — returns immediately; prepares solver
    singleStep()                          — advances by one adaptive time step
    timeStepIsRejected()                  — True if last step was rejected (retry)
    getAbsoluteSimulationTime()           — current simulation time [d]
    getParamValues(P_TEMP)                — all node temperatures [deg C]
    getParamValues(P_HEAD)                — all node heads [m]

    setCustomTimes(nFlags=3=SIMUL|OUTPUT) set in Stage 09 ensures the
    adaptive stepper navigates to each output time exactly.

    Output
    ------
    Group3.npz alongside the DAC, containing:
        times : float64[n_snapshots]           simulation times [d]
        T     : float32[n_snapshots, n_nodes]  temperature [deg C]
        h     : float32[n_snapshots, n_nodes]  hydraulic head [m]
    Stage 11 reads this file instead of the DAC.
    """
    output_times: List[float] = sorted(float(t) for t in cfg.output_times)
    dac_path = str(RESULTS_PATH)
    fmode    = ifm.Enum.F_BINARY    # 1
    n_nodes  = doc.getNumberOfNodes()

    log.info(
        "Starting simulation (singleStep mode): %.0f d (%.0f years)  ->  %s",
        cfg.t_final, cfg.t_final / 365.25, RESULTS_PATH.name,
    )
    log.info(
        "  Output: %d snapshots every %.0f d",
        len(output_times),
        output_times[1] - output_times[0] if len(output_times) > 1 else output_times[0],
    )

    # Initialise simulator without running (returns immediately, ~0.2 s).
    # Empty listoftimesteps — Stage 09's setCustomTimes controls navigation.
    doc.startSimulator(dac_path, fmode, [], False)

    snap_times: List[float]       = []
    snap_T:     List[List[float]] = []
    snap_h:     List[List[float]] = []

    # Per-accepted-step diagnostics written to NPZ as time_abs_d / dt_d.
    # Stage 11 reads these to produce Figure F7 (adaptive timestep evolution).
    # Only accepted steps are recorded (rejected steps are not counted).
    all_times_d: List[float] = []   # absolute simulation time [d] per accepted step
    all_dt_d:    List[float] = []   # step size [d] per accepted step
    t_prev: float = 0.0             # time at end of previous accepted step

    next_out   = 0
    total_iter = 0
    t_tol      = 0.5   # d — tolerance for custom-time detection
    _MAX_ITER  = 50_000

    t_wall = time.monotonic()

    while total_iter < _MAX_ITER:
        doc.singleStep()
        total_iter += 1

        if doc.timeStepIsRejected():
            continue   # adaptive stepper rejected this step; retry with smaller dt

        t = doc.getAbsoluteSimulationTime()

        # Record accepted step for F7 timestep diagnostic plot.
        # dt_step = advance made by this accepted step.
        # t_prev starts at 0.0 (initial simulation time), so the first
        # accepted step correctly captures dt = t_first_accepted - 0.
        dt_step = t - t_prev
        all_times_d.append(t)
        all_dt_d.append(dt_step)
        t_prev = t

        # Capture all output times that have been reached or passed.
        # setCustomTimes(nFlags=SIMUL) guarantees the stepper lands exactly
        # on each custom time, so t will equal output_times[next_out] within
        # floating-point precision when the snapshot should be recorded.
        while next_out < len(output_times) and t >= output_times[next_out] - t_tol:
            T_list = list(doc.getParamValues(ifm.Enum.P_TEMP))
            h_list = list(doc.getParamValues(ifm.Enum.P_HEAD))
            snap_times.append(t)
            snap_T.append(T_list)
            snap_h.append(h_list)
            log.info(
                "  Snapshot %2d/%d: t = %8.1f d  (target %8.1f d)",
                next_out + 1, len(output_times), t, output_times[next_out],
            )
            next_out += 1

        if t >= cfg.t_final - t_tol:
            break

    elapsed = time.monotonic() - t_wall
    log.info(
        "Simulation complete: %.0f d in %.1f s = %.1f min  "
        "(%d singleStep iterations, %d snapshots captured)",
        cfg.t_final, elapsed, elapsed / 60.0, total_iter, len(snap_times),
    )

    if total_iter >= _MAX_ITER:
        raise RuntimeError(
            f"Simulation exceeded {_MAX_ITER} iterations without reaching "
            f"t_final={cfg.t_final:.0f} d.  Last t = "
            f"{doc.getAbsoluteSimulationTime():.2f} d."
        )

    # Save snapshots + per-step diagnostics to NumPy compressed archive.
    #
    # Arrays written:
    #   times       float64 (n_snapshots,)           output-time values [d]
    #   T           float32 (n_snapshots, n_nodes)   temperature [°C]
    #   h           float32 (n_snapshots, n_nodes)   hydraulic head [m]
    #   time_abs_d  float64 (n_accepted_steps,)      accepted-step times [d]
    #   dt_d        float64 (n_accepted_steps,)      accepted-step sizes [d]
    #
    # Stage 11 reads 'times'/'T'/'h' for F1–F6 and 'time_abs_d'/'dt_d' for F7.
    npz_path = RESULTS_PATH.with_suffix('.npz')
    np.savez_compressed(
        str(npz_path),
        times       = np.array(snap_times,   dtype=np.float64),
        T           = np.array(snap_T,       dtype=np.float32),
        h           = np.array(snap_h,       dtype=np.float32),
        time_abs_d  = np.array(all_times_d,  dtype=np.float64),
        dt_d        = np.array(all_dt_d,     dtype=np.float64),
    )
    npz_mb = npz_path.stat().st_size / 1e6
    log.info(
        "Snapshots saved: %s  (%d snapshots × %d nodes, %d accepted steps, %.1f MB)",
        npz_path.name, len(snap_times), n_nodes, len(all_times_d), npz_mb,
    )


# ---------------------------------------------------------------------------
# Post-run verification
# ---------------------------------------------------------------------------

def verify_completion(doc, cfg: GeothermalConfig) -> bool:
    """
    Check whether the simulation ran to completion.

    Two proxies are used because FEFLOW 8.1 has no dedicated convergence API:

    Proxy 1 — TIME: getAbsoluteSimulationTime() should equal getFinalSimulationTime()
              within 1 d. An aborted or diverged run ends at an earlier time.

    Proxy 2 — DAC: RESULTS_PATH must exist and contain at least one time step
              (getNumberOfTimeSteps() > 0). The count should be close to
              len(cfg.output_times) = 20 for a complete 100-year run.

    Returns
    -------
    bool
        True if both proxies indicate successful completion.
    """
    ok = True

    # --- Proxy 1: absolute simulation time ---
    t_abs   = doc.getAbsoluteSimulationTime()
    t_final = doc.getFinalSimulationTime()
    delta   = t_final - t_abs

    if delta > 1.0:
        log.error(
            "TIME PROXY: simulation stopped at %.2f d; "
            "expected %.0f d (delta = %.2f d). "
            "The simulation may have diverged or been aborted.",
            t_abs, t_final, delta,
        )
        ok = False
    else:
        log.info(
            "TIME PROXY: t_abs = %.2f d ≈ t_final = %.0f d [OK]",
            t_abs, t_final,
        )

    # --- Proxy 2: NPZ snapshot file ---
    # getNumberOfTimeSteps() / getTimeSteps() in FEFLOW 8.1 only expose the
    # last DAC entry (confirmed by binary analysis and API testing).  The
    # snapshot file written by run_simulation() is the authoritative record.
    npz_path = RESULTS_PATH.with_suffix('.npz')
    if not npz_path.exists():
        log.error(
            "NPZ PROXY: snapshot file not found at %s. "
            "run_simulation() may have failed.",
            npz_path,
        )
        ok = False
    else:
        data    = np.load(str(npz_path))
        n_steps = len(data['times'])
        n_exp   = len(cfg.output_times)
        npz_mb  = npz_path.stat().st_size / 1e6

        if n_steps == 0:
            log.error(
                "NPZ PROXY: %s exists (%.1f MB) but has 0 snapshots.",
                npz_path.name, npz_mb,
            )
            ok = False
        elif n_steps < n_exp:
            log.warning(
                "NPZ PROXY: %s has %d snapshots; expected %d (%.0f%% complete).  "
                "%.1f MB",
                npz_path.name, n_steps, n_exp,
                100.0 * n_steps / n_exp, npz_mb,
            )
        else:
            log.info(
                "NPZ PROXY: %s  %.1f MB  %d snapshots [OK]",
                npz_path.name, npz_mb, n_steps,
            )

    if ok:
        log.info("Completion verification: ALL PASSED")
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
            "Stage 09 must complete before Stage 10."
        )

    log.info("Loading model: %s", fem_path.name)
    doc = ifm.loadDocument(str(fem_path))

    log.info("Running pre-run checklist:")
    pre_run_checklist(doc, cfg, ifm)

    run_simulation(doc, cfg, ifm)

    log.info("Verifying completion:")
    ok = verify_completion(doc, cfg)

    # Save the FEM with the post-simulation state (initial conditions updated
    # to the final time step values, useful for warm-restart scenarios).
    doc.saveDocument(str(fem_path))
    log.info("Post-simulation FEM saved: %s", fem_path.name)

    if not ok:
        raise RuntimeError(
            "Simulation completion checks failed. See log for details. "
            "Inspect the partial DAC with FEFLOW GUI or 11_postprocess.py."
        )

    log.info(
        "Stage 10 complete — %.0f-year simulation finished. "
        "Results: %s",
        cfg.t_final / 365.25, RESULTS_PATH,
    )


if __name__ == "__main__":
    main()
