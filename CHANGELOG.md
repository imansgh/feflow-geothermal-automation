# Changelog

All notable changes to this repository are documented in this file.

This project does not yet follow formal [Semantic Versioning](https://semver.org/)
releases; entries are grouped by date instead of version tags, in roughly the
style of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `figures/F9_spider_diagram.png` — exported from the `Sensitivity` sheet's
  native chart in `economics/Economic_Assessment_Group3.xlsx`; added a new
  "Sensitivity Analysis" subsection to `README.md` § Results.
- `assets/workFlow_diagram2.png` — nine-step workflow diagram, replacing the
  plain-text workflow diagram in `README.md` § Overview.
- `assets/RepositoryStructure.png` — repository architecture diagram, added
  to `README.md` § Repository Structure.
- `docs/REPOSITORY_STRUCTURE.md` — full directory tree with per-file
  descriptions, moved out of `README.md` into a dedicated file; `README.md`
  § Repository Structure now shows only the architecture diagram and a
  pointer to this document.

### Fixed

- `README.md` § Repository Structure was missing `CONTRIBUTING.md`,
  `CHANGELOG.md`, `LICENSE`, and `docs/` from the directory tree (all added
  in earlier work but never reflected there); corrected before it was
  moved to `docs/REPOSITORY_STRUCTURE.md`.
- `README.md` § Economic Assessment previously stated the spider diagram
  "has not been exported as a standalone repository image," which is no
  longer accurate now that Figure F9 exists.

## [1.0.0] - 2026-07-01

### Added

- `LICENSE` — standard MIT License text (previously only declared in
  `CITATION.cff` and the README, with no standalone file).
- `CHANGELOG.md` (this file).
- `CONTRIBUTING.md` — coding conventions, test requirements, and pull-request
  guidelines, moved out of `README.md` into a dedicated file.
- `docs/VALIDATION.md` — independent technical validation summary: what was
  checked, how, and why the reported results can be trusted, distinct from
  the README.

### Changed

- `README.md` rewritten into a publication-quality structure (Overview,
  Features, Repository Structure, Installation, Running the Workflow,
  Results, Validation, Engineering Assumptions, Limitations, Future Work,
  Reproducibility, Scientific Integrity, Citation, License), with an
  explicit distinction between measured/simulated data, engineering
  assumptions, and educational simplifications.
- `CITATION.cff` abstract and keywords expanded to reflect the full coupled
  workflow (FEFLOW → thermal post-processing → ORC → economic assessment),
  not only the FEFLOW simulation pipeline; added `repository-code`,
  `version`, and `date-released` fields; corrected `family-names` formatting
  to `"Saghafi Far"`.

### Fixed

- `README.md` § Running the Workflow stated the FEFLOW-licence requirement
  backwards for steps 3 and 4 (Stage 12 was described as licence-free and
  Stage 11 as requiring a licence — the reverse of the truth, and
  inconsistent with the README's own Installation/License sections).
  Corrected to: steps 1–3 (Stages 1–10 and 12) require a FEFLOW licence;
  steps 4–6 do not.
- `economics/README.md` referenced the pre-rename script
  `scripts/12_extract_avg_production_temperature.py`, which no longer
  exists; updated to `scripts/12_extract_avgT.py`.
- `economics/README.md`'s "Open item" note said the average production
  temperature was "not yet confirmed against the raw NPZ array," which was
  no longer true — Stage 12 has been run and extracted the exact value
  (124.53 °C). Updated to state this directly, and to note that
  `Base_Case_Group3!B2` still holds the earlier 125 °C estimate pending an
  update.
- `economics/README.md` § Known assumptions now discloses a previously
  unstated ~4% discrepancy between the load factor used for annual
  production in `ORC_Group3.xlsx` (8,000 h/yr) and the capacity factor used
  for the LCOE denominator in `Economic_Assessment_Group3.xlsx` (8,322
  h/yr, 95% CF).
- `README.md` § Repository Structure and § Reproducibility now correctly
  distinguish which files under `outputs/` are actually tracked in git
  (`Average_Production_Temperature.csv`, `thermal_timeseries.csv`,
  `Group3_results.xlsx`) versus gitignored/regenerated
  (`Group3.fem`, `Group3.dac`, `Group3.npz`) versus generated-but-not-yet-committed
  (`thermal_power_table.csv`); previously the whole `outputs/` directory was
  described as excluded from version control, which was inaccurate.
  `outputs/Group3_results.xlsx` (an Excel mirror of the NPZ data) is now
  listed; it was previously tracked in git but undocumented.
- `README.md` § Reproducibility no longer implies `Group3_template.fem` is a
  tracked/available input; it is gitignored by design, and rebuilding it in
  the FEFLOW GUI is now explicitly noted as the one manual step in the
  pipeline.
- `README.md` § Future Work restores the "multi-group automation" item
  (`build_group3_model.py --group N` is a documented placeholder, not yet
  implemented), which was dropped in an earlier rewrite.
- `CONTRIBUTING.md` referenced a "Scope" section in the README that no
  longer exists as a separate heading (merged into Overview); updated the
  cross-reference.
- Minor notation harmonised across `README.md` and `economics/README.md`:
  "kW net" and "MW net electrical" used consistently in both, instead of
  `kW_net` / `MW_e` in one and `kW net` / `MW net electrical` in the other.

### Changed (workbook maintenance)

- `economics/Economic_Assessment_Group3.xlsx` § `Assumptions`: added a
  single authoritative source-temperature cell,
  "Average Production Temperature (°C)" = 124.5327 (`B11`), sourced from
  `outputs/Average_Production_Temperature.csv` / Figure F8.
- `economics/Economic_Assessment_Group3.xlsx` § `Sensitivity`: removed every
  hardcoded occurrence of the production temperature (`125`) from the
  spider-diagram formulas; all cells now reference `Assumptions!$B$11` (or
  their own row's `B` cell) instead. The base-case (0% variation) cell in
  each of the five columns (`C7`, `E7`, `G7`, `I7`, `K7`) now references
  `LCOE_Group3!$B$12` directly instead of duplicating the entire CAPEX/LCOE
  calculation inline, eliminating a pre-existing ~0.0002 €/MWh
  methodology-rounding gap between the two.
- `economics/Economic_Assessment_Group3.xlsx` § `Assumptions!D16`: replaced
  a manually-typed `#N/A` documentation placeholder with an informative
  note ("Scaled from Xodo reference example... linear depth-scaling
  assumption...").
- `economics/ORC_Group3.xlsx` § `Base_Case_Group3!B2` (`Tsource-in`):
  updated from the earlier chart-based estimate (125 °C) to the exact
  FEFLOW-extracted value (124.5327 °C); the resulting `Pel` was re-copied
  into `Economic_Assessment_Group3.xlsx` (`Assumptions!B10`).
- Recalculated both workbooks after every edit (LibreOffice) and confirmed
  zero formula errors and zero unintended cell changes in either file.
- As a consequence of the above, the reported headline figures changed:
  net electrical power 4.26 → 4.22 MW, annual electricity production
  34.1 → 33.8 GWh/yr, CAPEX €52.0M → €51.9M, specific CAPEX
  €12,206/kW → €12,294/kW, LCOE 185.3 → 186.5 €/MWh. `README.md`,
  `economics/README.md`, and `docs/VALIDATION.md` were updated to match.

## [2026-07-01] — Energy production, economic assessment, and Figure F8

### Added

- `economics/ORC_Group3.xlsx` — ORC electrical power estimate (Lorentz-cycle
  method), annual and monthly-resolved production.
- `economics/Economic_Assessment_Group3.xlsx` — CAPEX, LCOE, and
  five-parameter sensitivity (spider-diagram) analysis.
- `economics/README.md` — methodology, assumptions, and caveats for the
  energy and economic assessment.
- Stage 12 script — exact average production-temperature extraction directly
  from raw FEFLOW NPZ node values (no chart reading), writing
  `outputs/Average_Production_Temperature.csv`.
- Figure F8 (`figures/F8_average_production_temperature.png` / `.pdf`) —
  average production temperature over the 100-year simulation, generated
  from the Stage 12 CSV and appended to `scripts/11_postprocess.py`.

## [2026-06-23] — Continuous integration and citation metadata

### Added

- `.github/workflows/python-app.yml` — GitHub Actions CI (flake8 lint +
  pytest) on every push and pull request to `main`.
- `CITATION.cff` — initial citation metadata for the software.

### Fixed

- Author name corrected in `CITATION.cff` metadata.

## [2026-06-22] — Initial pipeline

### Added

- Full FEFLOW 8.1 automation pipeline (Stages 1–11): supermesh geometry,
  triangular mesh generation, slice/layer configuration, problem settings,
  material properties, initial and boundary conditions, multilayer wells,
  simulation settings, the `singleStep()` simulation loop, and
  post-processing with figures F1–F7.
- `scripts/config.py` / `scripts/utils.py` — central configuration and IFM
  bootstrap helpers.
- `tests/` — licence-free automated test suite (configuration loading, mesh
  utilities, thermal-power formula, NPZ snapshot contract).
- `notebooks/` — exploratory analysis notebooks for snapshot exploration,
  breakthrough analysis, and thermal power.
- `data/geoth_tutorial_data_Group3.xlsx` — source workbook (well data, slice
  temperatures, geological parameters).
