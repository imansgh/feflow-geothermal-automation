# Independent Technical Validation

This document summarizes an independent technical and documentation review
of this repository, performed prior to public release. It is not a
restatement of the README; it exists to answer one question: **why should a
reader trust the results reported here?**

---

## Validation Overview

The review covered three areas:

1. **Numerical methods** — the formulas and calculation logic used for
   thermal power, ORC electrical output, CAPEX, and LCOE were checked
   against their documented sources and, where feasible, recomputed
   independently from the committed input data.
2. **Documentation** — README.md, `economics/README.md`, `CITATION.cff`,
   `CONTRIBUTING.md`, and `CHANGELOG.md` were checked against each other and
   against the actual repository contents (file names, paths, script names,
   licensing statements).
3. **Workflow consistency** — the chain from reservoir input data through
   the FEFLOW simulation, thermal post-processing, ORC estimate, and
   economic assessment was checked for whether each stage's output is
   actually consumed, unmodified, by the next.

**The FEFLOW simulation itself was not re-run.** Doing so requires a
licensed FEFLOW 8.1 installation, which was not available for this review.
Instead, the review worked from the artifacts the simulation already
produced and that are committed to this repository: the NPZ snapshot
archive, the extracted CSV time series, the post-processing scripts, and
the resulting figures. Where a calculation could be independently repeated
from these committed artifacts using the documented formulas, it was.
Where it could not (the FEFLOW run itself, and the five-parameter
sensitivity sweep, which would require re-running each scenario), this is
stated explicitly below rather than implied.

---

## Independent Checks

| Component | Validation Method | Status |
|---|---|---|
| Reservoir properties (K, φ, Cᵥ, λ per layer) | Read once from the source workbook into `scripts/config.py`; automated tests assert physically expected ordering (e.g., K_caprock < K_reservoir, φ_reservoir < φ_caprock) | Verified — automated tests pass (`tests/test_config.py`) |
| Temperature profile (initial T per slice) | Computed analytically from Fourier's law in `config.py`, cross-checked against the workbook's `sliceT` sheet at load time (0.05 °C tolerance); re-derived directly from `scripts/config.py` during this review | Verified — re-derived value (Slice 2 = 134.13 °C) matches the reported 134.1 °C |
| Hydraulic head | Uniform 200 m initial/boundary condition, read consistently from `Group3.npz`'s `h` array for Figures F5/F6 | Consistency check only — a fixed boundary condition, not an independently derivable quantity |
| Thermal power | Recomputed in this review from the documented formula (P = ρCp·Q·ΔT) using the verified injection temperature, undisturbed reservoir temperature, and the extracted average production temperature; also covered by an automated regression test | Verified — recomputed 52.84 → 46.81 MW_th matches the reported 52.8 → 46.8 MW_th and the test's expected range (`tests/test_thermal_power.py::test_thermal_power_group3_final`) |
| Average production temperature | Extracted directly from raw FEFLOW NPZ node values (Stage 12); the resulting CSV was re-read directly in this review | Verified — final value 124.5327 °C at t = 99.93 yr, rounding to the reported 124.53 °C |
| ORC annual production | Two independent calculation paths (annual estimate and monthly-resolved sum) within `ORC_Group3.xlsx`; both re-read and the monthly figures independently summed in this review | Verified — annual estimate 33,790.81 MWh/yr vs. monthly sum 33,782.97 MWh/yr, agreement within 0.02%, matching the reported ~33.8 GWh/yr |
| CAPEX calculations | Re-read directly from `Economic_Assessment_Group3.xlsx` (`CAPEX_Group3`, `LCOE_Group3` sheets) in this review | Verified — €51,928,588.24 total (≈ €51.9 M), €12,293.99/kW (≈ €12,294/kW), matching the reported figures |
| LCOE equations | Formula validated by first reproducing an independent worked example (156.4 €/MWh, Xodo's reference case) with the identical method; LCOE re-read directly from the workbook in this review | Verified — 186.52 €/MWh matches the reported 186.5 €/MWh |
| Sensitivity analysis | The base-case (0% variation) cell in each of the five columns now references `LCOE_Group3!$B$12` directly, rather than duplicating the CAPEX/LCOE calculation inline; the ±10%/±20% scenario cells retain their own self-contained formulas and were not independently recomputed in this review | Verified for the base case — all five columns equal `LCOE_Group3!B12` exactly (186.5217 €/MWh), by construction rather than coincidence. Off-base-case scenarios reviewed structurally only |
| Cross-document consistency | README.md, `economics/README.md`, `CITATION.cff`, `CONTRIBUTING.md`, and `CHANGELOG.md` checked against each other and against actual file names/paths; all internal and cross-file Markdown links, anchors, and image paths verified programmatically | Verified — no broken links, anchors, or stale script/file references found at the time of this review |
| Repository reproducibility | Checked that the committed inputs (scripts, workbook, CSVs) needed to regenerate each figure/table are present and correctly referenced; the licence-free automated test suite was executed | Verified for licence-free stages — 51/51 tests passing. FEFLOW-dependent stages (1–10, 12) were not re-run (require a licensed installation) and are accepted on the basis of their committed, versioned outputs (NPZ, DAC, CSV) |

---

## Cross-Validation

The workflow was checked end to end by following one number through every
stage that touches it, rather than validating each stage in isolation:

```
FEFLOW (NPZ node values)
        │
        ▼
CSV (Average_Production_Temperature.csv — Stage 12, exact extraction)
        │
        ▼
ORC workbook (Tsource-in, ORC_Group3.xlsx)
        │
        ▼
Economic workbook (CAPEX_Group3 / LCOE_Group3, Economic_Assessment_Group3.xlsx)
```

The average production temperature extracted from the FEFLOW NPZ
(124.53 °C) was traced into the CSV, and from there into the ORC workbook's
`Tsource-in` cell. This cell previously held an earlier, chart-based estimate
of 125 °C (a 0.47 °C gap); it has since been updated to the exact value
(124.5327 °C), and the resulting `Pel` was re-copied into
`Economic_Assessment_Group3.xlsx` (`Assumptions!B10`), so CAPEX, LCOE, and
the Sensitivity sheet's base case are now all derived from the same
FEFLOW-extracted figure rather than two independently-set numbers.

Downstream of that point, the chain is numerically consistent: the ORC
workbook's net electrical output and annual production figures were
independently re-derived from its own cells (see table above), and the
economic workbook's CAPEX and LCOE were independently re-derived from its
own cells. A separate inconsistency found *within* the economic side of the
chain — not between FEFLOW and the workbooks, but between the two
workbooks' own load-factor assumptions — remains open and is documented in
[Known Limitations](#known-limitations); it is unrelated to the
production-temperature synchronization described above.

---

## Verified Numerical Results

The values below are taken directly from the repository (README.md § Key
Results, `economics/README.md`) and were cross-checked against the live
source files as part of this review (see Independent Checks above). No
value below has been recalculated or adjusted for this document.

| Quantity | Value |
|---|---|
| Reservoir temperature (initial) | 134.1 °C |
| Average production temperature (t = 100 yr) | 124.53 °C |
| Injection temperature | 50.0 °C |
| Thermal power (t = 0 → t = 100 yr) | 52.8 → 46.8 MW_th (~11% degradation) |
| Annual electricity production | ~33.8 GWh/yr |
| CAPEX | ≈ €51.9 M |
| Specific CAPEX | ≈ €12,294/kW net |
| LCOE | 186.5 €/MWh |

---

## Engineering Assumptions

The repository documents its simplifying assumptions explicitly (see
README.md § Engineering Assumptions); this review confirms they are stated
rather than hidden. Notable examples:

- **Constant flow rate** (150 L/s production, 150 L/s injection) held fixed
  over the full 100-year simulation, rather than an operationally variable
  schedule.
- **Spreadsheet-based ORC model** (Lorenz/Lorentz-cycle method, following
  the source workbook's own terminology) rather than a full process
  simulation.
- **Linear drilling-cost scaling** with depth, extrapolated from a single
  literature reference well rather than a depth-resolved cost model.
- **Simplified economic model**: a deterministic, single-scenario NREL-style
  LCOE calculation rather than a full project-finance model.

Each of these assumptions is named in the source documentation together
with its rationale, and — where it materially affects the headline
economic result — its influence is quantified through the five-parameter
sensitivity (spider-diagram) analysis rather than left unexamined.

---

## Known Limitations

The following limitations are disclosed in the repository's own
documentation (README.md § Limitations, `economics/README.md` § Known
assumptions / caveats) and are restated here as part of the basis for
trusting the results, not as new findings:

- **Drilling-cost scaling** is linear and based on a single reference well
  (2,500 m, >250 °C) applied to a much shallower (1,120 m) doublet.
- **Spreadsheet-based ORC model** — no detailed heat-exchanger sizing,
  working-fluid selection study, or part-load behaviour.
- **Simplified economics** — the LCOE calculation excludes taxes, inflation,
  escalation, component replacement, well workovers, electricity-price
  uncertainty, and carbon credits.
- **No thermo-hydro-mechanical (THM) coupling** — the reservoir model is
  thermo-hydraulic (TH) only.
- **No fracture networks** — the reservoir is modelled as an equivalent
  porous medium.
- **No reactive transport** — no geochemical reactions (scaling, mineral
  dissolution/precipitation) are modelled.
- **No stochastic uncertainty treatment** — all parameters are deterministic,
  single-value inputs; sensitivity is explored only through a ±10%/±20%
  spider diagram, not a probabilistic (e.g., Monte Carlo) analysis.
- **Load-factor inconsistency between workbooks** (identified during the
  documentation review, disclosed in `economics/README.md`): the annual
  electricity production figure is computed using 8,000 h/yr in
  `ORC_Group3.xlsx`, while the LCOE denominator in
  `Economic_Assessment_Group3.xlsx` independently uses 8,322 h/yr (95%
  capacity factor). The two workbooks were not cross-linked when this
  assumption was set. This does not invalidate either individual reported
  figure, but the two should not be read as sharing the same underlying
  operating-hours assumption.

These limitations should be treated as boundary conditions on
interpretation, not as defects to be silently corrected: the value of this
repository is in showing a complete, coupled workflow clearly enough that
its limitations are legible.

---

## Audit Findings

A prior documentation audit and repair pass (recorded in `CHANGELOG.md`
under "Fixed") addressed several inconsistencies before this review began:

- A missing `LICENSE` file was added (the MIT licence was previously only
  declared in a badge and `CITATION.cff`, with no license text in the
  repository).
- README.md contained a self-contradiction regarding which pipeline stages
  require a FEFLOW licence (two steps had the requirement stated
  backwards); this was corrected and re-verified against the Installation
  and License sections.
- `economics/README.md` referenced a script that had since been renamed
  (`scripts/12_extract_avg_production_temperature.py` →
  `scripts/12_extract_avgT.py`) and stated that the average production
  temperature was "not yet confirmed," which was no longer accurate once
  Stage 12 had been run; both were corrected.
- Author-name formatting in `CITATION.cff` was made consistent with the name
  used elsewhere in the repository.
- Cross-references between `README.md`, `CONTRIBUTING.md`, and
  `CHANGELOG.md` were verified, and all internal Markdown anchors and image
  paths were checked programmatically rather than by inspection alone.
- Repository metadata (`CITATION.cff` scope/keywords, the Repository
  Structure tree, and the Reproducibility section) was synchronized with
  the actual tracked contents of the repository, including previously
  undocumented tracked files.

A subsequent workbook maintenance pass (recorded in `CHANGELOG.md`)
removed the last hardcoded occurrences of the production temperature from
`Economic_Assessment_Group3.xlsx`'s `Sensitivity` sheet, replacing them with
references to a single authoritative cell (`Assumptions!B11`); updated
`ORC_Group3.xlsx`'s `Tsource-in` from the earlier chart-based 125 °C to the
exact 124.5327 °C figure; re-copied the resulting `Pel` into
`Economic_Assessment_Group3.xlsx`; and cell-linked the Sensitivity sheet's
base case to `LCOE_Group3!B12` so it no longer duplicates that calculation.
This is what changed the CAPEX/LCOE/production figures reported in this
document relative to earlier versions of it.

This review independently re-checked those fixes (see Independent Checks
above) and found them consistent with the current state of the repository.

---

## Reproducibility Statement

All figures and tables reported in this repository can be reproduced using
the committed scripts and input files, subject to the availability of a
licensed FEFLOW 8.1 installation for the simulation stages (Stages 1–10 and
12). The post-processing stage (Stage 11, Figures F1–F8), the licence-free
automated test suite, and the ORC/economic workbook calculations do not
require a FEFLOW licence and were confirmed runnable during this review.

---

## Validation Statement

The repository demonstrates a technically consistent and internally
validated educational workflow for geothermal reservoir simulation, ORC
performance estimation, and preliminary techno-economic assessment.
Although several engineering assumptions have been adopted, they are
explicitly documented and their impact is quantified through sensitivity
analysis. One previously undisclosed inconsistency between the two economic
workbooks' operating-hours assumptions was identified during this review
and is now disclosed in the repository's documentation rather than
concealed. The repository is therefore suitable for educational use,
methodological demonstration, and reproducible research — but not, as its
own documentation states, as a bankable feasibility study.
