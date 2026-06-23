# Group 3 — Automated Geothermal Doublet Simulation in FEFLOW 8.1 - BIP_2026

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FEFLOW 8.1](https://img.shields.io/badge/FEFLOW-8.1-0078A8)](https://www.mikepoweredbydhi.com/products/feflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)
[![Tests: pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](tests/)
[![Code style: PEP 8](https://img.shields.io/badge/Code%20style-PEP%208-black)](https://peps.python.org/pep-0008/)

A fully automated Python pipeline for building, running, and post-processing a
**coupled thermo-hydraulic (TH) geothermal doublet simulation** in FEFLOW 8.1.
The pipeline takes a single Excel workbook as input and produces a completed
100-year simulation and seven publication-quality diagnostic figures without any
manual interaction with the FEFLOW GUI.

The core technical contribution is a **`singleStep()` workaround** for a
verified regression in the FEFLOW 8.1 IFM Python API that prevents enumeration
of multi-snapshot DAC result files — enabling reliable access to all simulation
snapshots through a parallel NumPy archive.

> **Context:** Developed for the MSc course *Geothermal Energy Systems* at
> Politecnico di Torino, following the FEFLOW Geothermal Energy Tutorial
> (Casasso, rev00, 03/06/2024). The numerical experiment simulates 100 years
> of doublet operation in a sedimentary reservoir at 870–1120 m depth below
> a 600 m a.s.l. ground surface.

---

## Table of Contents

1. [Features](#features)
2. [Workflow](#workflow)
3. [Repository Structure](#repository-structure)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Quick Start](#quick-start)
7. [Pipeline Stages](#pipeline-stages)
8. [Configuration](#configuration)
9. [Output Files](#output-files)
10. [Figures](#figures)
11. [Known Limitation — FEFLOW 8.1 IFM DAC Enumeration](#known-limitation--feflow-81-ifm-dac-enumeration)
12. [Reproducibility](#reproducibility)
13. [Example Results](#example-results)
14. [Testing](#testing)
15. [Adapting for Groups 1–6](#adapting-for-groups-16)
16. [Future Work](#future-work)
17. [Contributing](#contributing)
18. [Citation](#citation)
19. [License](#license)

---

## Features

- **Zero-click pipeline** — 11 sequential stages from raw Excel workbook to
  final figures, driven by a single `python build_group3_model.py` command.
- **Coupled TH simulation** — transient thermo-hydraulic coupling with
  temperature-dependent fluid viscosity and density (linear).
- **Adaptive time-stepping** — FEFLOW's FE/BE predictor-corrector scheme;
  `dt_initial = 1 × 10⁻¹⁰ d`, `dt_max = 100 d`.
- **Reliable multi-snapshot access** — a `singleStep()` control loop writes
  all 20 time-series snapshots to a portable NumPy `.npz` archive, bypassing
  the FEFLOW 8.1 IFM DAC enumeration regression.
- **Multilayer wells (MLW)** — five production wells and five injection wells
  screened across the reservoir interval; per-well flow rates read from the
  workbook.
- **Seven diagnostic figures** — continuous-field temperature maps via
  `tricontourf` on a Delaunay triangulation, breakthrough curves, thermal
  power evolution, hydraulic head maps, and adaptive timestep diagnostics.
- **Parameterised design** — changing four constants in `config.py` adapts
  the full pipeline to any of the six course groups.
- **Licence-free test suite** — 37 pytest tests covering configuration
  loading, mesh utilities, thermal power computation, snapshot format, and
  post-processing functions; no FEFLOW installation required.

---

## Workflow

### Part 1 — Build, configure & run (Stages 01–10)

```mermaid
flowchart TD
    IN["geoth_tutorial_data_Group3.xlsx"]
    S01["Stage 01 · Build supermesh geometry (.smhx)"]
    S02["Stage 02 · Generate triangular FE mesh (template .fem)"]
    S03["Stage 03 · Configure 3D layer elevations (6 slices / 5 layers)"]
    S04["Stage 04 · Set problem class + fluid properties (TH transient)"]
    S05["Stage 05 · Assign material properties (K, φ, Cᵥ, λ per layer)"]
    S06["Stage 06 · Apply initial conditions (h = 200 m, T per slice)"]
    S07["Stage 07 · Apply boundary conditions (T-BC, heat-flux, h-BC)"]
    S08["Stage 08 · Create multilayer wells + injection temperature BC"]
    S09["Stage 09 · Configure simulation settings (FE/BE, output times)"]
    S10["Stage 10 · Run simulation via singleStep() loop"]
    DAC["Group3.dac<br/>(FEFLOW binary results archive)"]
    NPZ["Group3.npz<br/>(NumPy snapshot archive — primary store)"]
    IN --> S01 --> S02 --> S03 --> S04 --> S05 --> S06 --> S07 --> S08 --> S09 --> S10
    S10 --> DAC
    S10 --> NPZ
    classDef store fill:#E6F1FB,stroke:#185FA5,color:#042C53;
    classDef run fill:#FAEEDA,stroke:#854F0B,color:#412402;
    class IN,DAC,NPZ store;
    class S10 run;
```

### Part 2 — Post-processing (Stage 11)

```mermaid
flowchart LR
    NPZ["Group3.npz<br/>(NumPy snapshot archive)"]
    P11["Stage 11 · Post-processing"]
    F1["figures/F1_temperature_maps.png"]
    F2["figures/F2_cross_section.png"]
    F3["figures/F3_breakthrough_curve.png"]
    F4["figures/F4_thermal_power.png"]
    F5["figures/F5_head_map.png"]
    F6["figures/F6_head_evolution.png"]
    F7["figures/F7_timestep_evolution.png"]
    CSV["outputs/thermal_power_table.csv"]
    NPZ --> P11
    P11 --> F1
    P11 --> F2
    P11 --> F3
    P11 --> F4
    P11 --> F5
    P11 --> F6
    P11 --> F7
    P11 --> CSV
    classDef store fill:#E6F1FB,stroke:#185FA5,color:#042C53;
    classDef run fill:#FAEEDA,stroke:#854F0B,color:#412402;
    class NPZ,CSV store;
    class P11 run;
```
```


---

## Repository Structure

```text
Group3_automation/
│
├── data/
│   └── geoth_tutorial_data_Group3.xlsx   # Input workbook (well data, slice T)
│
├── scripts/                              # One module per pipeline stage
│   ├── config.py                         # Central configuration + derived quantities
│   ├── utils.py                          # IFM bootstrap, mesh helpers, logging
│   ├── 01_build_geometry.py              # Supermesh polygon + well node import
│   ├── 02_generate_mesh.py               # Triangular mesh (PTS=5 m, PG=4)
│   ├── 03_create_slices.py               # 3D layer configuration
│   ├── 04_problem_settings.py            # Problem class, time control, fluid props
│   ├── 05_material_properties.py         # K, φ, Cᵥ, λ per geological unit
│   ├── 06_initial_conditions.py          # Hydraulic head + geothermal temperature IC
│   ├── 07_boundary_conditions.py         # Border T-BC, heat-flux BC, head BC
│   ├── 08_multilayer_wells.py            # MLW assignment + injection T BC
│   ├── 09_simulation_settings.py         # FE/BE, dt limits, custom output times
│   ├── 10_run_model.py                   # singleStep() loop, NPZ writer
│   └── 11_postprocess.py                 # Figures F1–F7 + CSV table
│
├── tests/
│   ├── conftest.py
│   ├── test_config.py                    # Config loading, temperature cross-check
│   ├── test_utils.py                     # Mesh node count, coordinate helpers
│   ├── test_thermal_power.py             # NPZ format contract, power calculation
│   └── test_postprocess_new.py           # F6/F7 existence, NPZ fallbacks
│
├── notebooks/
│   ├── 01_explore_results.ipynb          # Interactive snapshot exploration
│   ├── 02_breakthrough_analysis.ipynb    # Thermal breakthrough analysis
│   └── 03_thermal_power.ipynb            # Thermal power vs time
│
├── figures/                              # Generated by Stage 11 (committed)
│   ├── F1_temperature_maps.png
│   ├── F2_cross_section.png
│   ├── F3_breakthrough_curve.png
│   ├── F4_thermal_power.png
│   ├── F5_head_map.png
│   ├── F6_head_evolution.png
│   └── F7_timestep_evolution.png
│
├── outputs/                              # Generated by pipeline (gitignored)
│   ├── Group3.fem                        # FEFLOW model (post-simulation state)
│   ├── Group3.dac                        # FEFLOW binary results archive
│   ├── Group3.npz                        # NumPy snapshot archive
│   └── thermal_power_table.csv
│
├── build_group3_model.py                 # Master pipeline script
├── requirements.txt
├── environment.yml
├── CITATION.cff
├── .markdownlint.json
└── .gitignore
```

> `outputs/` is excluded from version control (see `.gitignore`). The large
> FEFLOW binaries (`Group3.fem`, `Group3.dac`, `Group3.npz`) are fully
> reproducible by running the pipeline.

---

## Requirements

### Software

| Dependency | Version | Notes |
|------------|---------|-------|
| FEFLOW | **8.1** | Commercial licence required. Provides `ifm312.pyd`. Not on PyPI. |
| Python | ≥ 3.9 | Use FEFLOW's bundled interpreter or add `bin64/python/` to `sys.path`. |

> **Compatibility note:** validated against FEFLOW 8.1 (`ifm312.pyd`). Will
> **not** work with FEFLOW 7.x — verified API method names differ. See
> `scripts/10_run_model.py` for the full list of confirmed methods and
> known absent calls.

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `numpy` | ≥ 1.24 | Array operations, NPZ archive I/O |
| `pandas` | ≥ 2.0 | Workbook parsing, well data tables |
| `openpyxl` | ≥ 3.1 | `.xlsx` backend for `pandas.read_excel` |
| `matplotlib` | ≥ 3.7 | All seven diagnostic figures |
| `pytest` | ≥ 7.4 | Test suite (development only) |

---

## Installation

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/Group3_automation.git
cd Group3_automation
```

### 2 — Create the Python environment

**With pip:**

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**With conda:**

```bash
conda env create -f environment.yml
conda activate feflow-geothermal
```

### 3 — Expose the IFM module

FEFLOW ships its own interpreter at `<FEFLOW_INSTALL>/bin64/python/python.exe`,
which has automatic access to `ifm312.pyd`. Alternatively, add the FEFLOW
Python directory to `PYTHONPATH`:

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "C:\Program Files\DHI\2024\FEFLOW 8.1\bin64\python"

# Linux / macOS
export PYTHONPATH="/opt/dhi/feflow81/bin64/python"
```

### 4 — Activate the FEFLOW licence

Stages 2–10 require an active licence. Stage 11 and the full test suite run
without one.

- **Sentinel LDK:** ensure `hasplms.exe` (Windows) or `hasplmd` (Linux) is
  running before executing the pipeline.
- **Online licence:** activate through the FEFLOW GUI
  (**Help → Licence Manager → Online Activation**).

### 5 — Build the mesh template (one-time GUI step)

Stage 2 requires a skeleton `.fem` file created once in the FEFLOW GUI.
Follow the [GUI Step-by-Step Guide](FEFLOW_GUI_Step_by_Step_Guide_Group3.md)
(Section 2) to produce `outputs/Group3_template.fem`.

---

## Quick Start

```bash
# Full run: build + simulate + figures  (~5–15 min with licence)
python build_group3_model.py

# Configure only — skip the simulation
python build_group3_model.py --skip-run

# Regenerate figures from an existing NPZ (no licence needed)
cd scripts && python 11_postprocess.py

# Run the test suite (no licence needed)
pytest tests/ -v
```

The master script runs all 11 stages sequentially. A failure in any stage is
logged but does **not** abort the pipeline — all subsequent stages are
attempted. Inspect the console output to identify failed stages.

---

## Pipeline Stages

| Stage | Script | Description | Licence |
|-------|--------|-------------|---------|
| 01 | `01_build_geometry.py` | 8 000 × 8 000 m supermesh polygon; import 70 well node coordinates | Yes |
| 02 | `02_generate_mesh.py` | Triangular mesh (PTS = 5 m, PG = 4) → ~4 706 nodes/slice | Yes |
| 03 | `03_create_slices.py` | 6 slice elevations → 5 geological layers | Yes |
| 04 | `04_problem_settings.py` | TH transient; FE/BE; variable-viscosity / linear-density fluid | Yes |
| 05 | `05_material_properties.py` | K, φ, Cᵥ, λ per layer from `config.py` | Yes |
| 06 | `06_initial_conditions.py` | Uniform head h = 200 m; geothermal temperature per slice | Yes |
| 07 | `07_boundary_conditions.py` | Fixed-T borders; heat-flux BC (−20 822.4 J/m²/d) at Slice 6; head BC | Yes |
| 08 | `08_multilayer_wells.py` | 10 MLWs from workbook; T = 50 °C BC on injection nodes | Yes |
| 09 | `09_simulation_settings.py` | FE/BE, dt_initial = 1 × 10⁻¹⁰ d, dt_max = 100 d, 20 output times | Yes |
| 10 | `10_run_model.py` | `singleStep()` loop; write `Group3.npz` and `Group3.dac` | Yes |
| 11 | `11_postprocess.py` | Figures F1–F7; `thermal_power_table.csv` | **No** |

---

## Configuration

All physical parameters and file paths are centralised in `scripts/config.py`.
Every downstream stage calls `load_config()` — no stage reads the workbook
directly.

### Group 3 geological parameters

| Parameter | Caprock | Reservoir | Basement | Unit |
|-----------|---------|-----------|----------|------|
| Intrinsic permeability *k* | 1.243 × 10⁻¹⁵ | 9.133 × 10⁻¹⁴ | 7.226 × 10⁻¹⁶ | m² |
| Hydraulic conductivity *K* | 9.371 × 10⁻⁴ | 6.886 × 10⁻² | 5.448 × 10⁻⁴ | m/d |
| Porosity *φ* | 0.27 | 0.025 | 0.01 | — |
| Volumetric heat capacity *Cᵥ* | 2.228 × 10⁶ | 2.247 × 10⁶ | 2.611 × 10⁶ | J/(m³·K) |
| Thermal conductivity *λₛ* | 1.76 | 2.30 | 4.87 | W/(m·K) |

> *K* is derived from *k* via `K = k·ρ·g/μ × 86 400`, using the reference
> fluid state *ρ* = 999.793 kg/m³, *μ* = 1.124 × 10⁻³ Pa·s, *T*_ref = 10 °C
> (FEFLOW tutorial p. 14).

### Slice elevations and initial temperatures

Temperatures are computed analytically from Fourier's law
(**T = T_surface + q/λ · Δz**) with *q* = 0.241 W/m²:

| Slice | Elevation (m a.s.l.) | Geological unit | T_initial (°C) |
|-------|---------------------|-----------------|----------------|
| 1 | +600 | Ground surface | 15.00 |
| 2 | −270 | Top of reservoir / base of caprock | 134.13 |
| 3 | −370 | Reservoir | 144.61 |
| 4 | −470 | Reservoir | 155.09 |
| 5 | −520 | Base of reservoir / top of basement | 160.33 |
| 6 | −2 500 | Base of basement | 258.31 |

### Simulation control

| Parameter | Value |
|-----------|-------|
| End time | 36 500 d (100 yr) |
| Initial time step | 1 × 10⁻¹⁰ d |
| Maximum time step | 100 d |
| Time-stepping scheme | FE/BE predictor-corrector |
| Output snapshots | 20 (every 1 825 d = 5 yr) |
| Geothermal heat-flux BC (Slice 6) | −20 822.4 J/(m²·d) |
| Hydraulic head BC (all borders) | 200 m |
| Injection temperature | 50 °C |
| Flow rate per well | ±30 L/s |

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `Group3.fem` | `outputs/` | Final FEFLOW model file (post-simulation state) |
| `Group3.dac` | `outputs/` | FEFLOW binary results archive (all 20 snapshots) |
| `Group3.npz` | `outputs/` | NumPy compressed snapshot archive — primary post-processing store |
| `thermal_power_table.csv` | `outputs/` | Thermal power P_th [MW_th] at every 5-year snapshot |

### NPZ archive format

`Group3.npz` is the canonical results store consumed by Stage 11.

| Array | Shape | dtype | Description |
|-------|-------|-------|-------------|
| `times` | (20,) | float64 | Snapshot times [d] at 5-yr intervals |
| `T` | (20, 28236) | float32 | Temperature [°C] at each snapshot |
| `h` | (20, 28236) | float32 | Hydraulic head [m] at each snapshot |
| `time_abs_d` | (n_steps,) | float64 | Absolute time [d] of every accepted adaptive step |
| `dt_d` | (n_steps,) | float64 | Step size [d] of every accepted adaptive step |

`n_steps` is typically 400–500 for a well-converged 100-year run.
`time_abs_d` and `dt_d` power Figure F7 (adaptive timestep diagnostics).

**Reading the archive:**

```python
import numpy as np

data       = np.load("outputs/Group3.npz")
T          = data["T"]            # shape (20, 28236) — °C
times      = data["times"]        # [1825, 3650, …, 36500] d
time_abs_d = data["time_abs_d"]   # all accepted-step times [d]
dt_d       = data["dt_d"]         # all accepted-step sizes [d]
```

---

## Figures

Stage 11 produces seven figures from the NPZ archive. All figures are committed
to `figures/` and can be regenerated at any time from an existing `Group3.npz`
without a FEFLOW licence.

| Figure | File | Description |
|--------|------|-------------|
| **F1** | `F1_temperature_maps.png` | Plan-view temperature at Slice 2 for t = 0, 10, 30, 50, 100 yr — continuous field via `tricontourf` on a Delaunay triangulation, with production/injection well overlays |
| **F2** | `F2_cross_section.png` | Vertical temperature cross-section along the doublet axis at t = 100 yr |
| **F3** | `F3_breakthrough_curve.png` | Thermal breakthrough — production temperature vs time at each well and the ensemble mean |
| **F4** | `F4_thermal_power.png` | Thermal power P_th [MW_th] vs time, with reference P₀ at undisturbed reservoir temperature |
| **F5** | `F5_head_map.png` | Hydraulic head plan-view at Slice 2 at t = 100 yr, showing the pumping cone and injection mound |
| **F6** | `F6_head_evolution.png` | Hydraulic head h(t) at a representative production well and injection well over 100 yr |
| **F7** | `F7_timestep_evolution.png` | Adaptive time-step size vs simulation time on a log y-axis, replicating the FEFLOW tutorial timestep diagnostic |

> **F7 dependency:** F1–F6 can be produced from any `Group3.npz` generated
> by the current pipeline. F7 additionally requires the `time_abs_d` and
> `dt_d` arrays written by the current `10_run_model.py`. If these arrays are
> absent from an older archive, F7 is silently skipped with a warning; F1–F6
> are unaffected.

---

## Known Limitation — FEFLOW 8.1 IFM DAC Enumeration

### Problem

FEFLOW 8.1 IFM's `getTimeSteps()` / `loadTimeStep()` return only **one
entry** from the DAC archive, regardless of how many output snapshots were
recorded. Binary analysis confirms the DAC file contains all snapshots, but
the Python API cannot enumerate them. This is a **verified regression from
FEFLOW 7.x**.

The following methods are also confirmed **absent** from `ifm312.pyd`:

```
readResultsFile()          openResultsFile()         closeResultsFile()
getResultsFileName()       getResultsNumberOfTimes() getResultsTimeValue(i)
setResultsTime(i)          runSimulator()             getSimulationTime()
getSimulationProgress()    setResultsFileName()       isConverged()
```

### Implemented workaround

Stage 10 replaces the blocking `startSimulator()` call with a manual
`singleStep()` control loop that captures field state at every accepted
adaptive step:

```python
doc.startSimulator(dac_path, fmode, [], False)  # initialise without running

t_prev = 0.0
while True:
    doc.singleStep()
    if doc.timeStepIsRejected():
        continue                                 # solver retries with smaller dt

    t = doc.getAbsoluteSimulationTime()
    dt_step = t - t_prev

    all_times_d.append(t)          # per-step diagnostics → F7
    all_dt_d.append(dt_step)
    t_prev = t

    if is_output_time(t):          # capture snapshot at 5-yr intervals
        snap_T.append(doc.getParamValues(ifm.Enum.P_TEMP))
        snap_h.append(doc.getParamValues(ifm.Enum.P_HEAD))

    if t >= cfg.t_final:
        break

np.savez_compressed(
    npz_path,
    times      = np.array(snap_times,  dtype=np.float64),
    T          = np.array(snap_T,      dtype=np.float32),
    h          = np.array(snap_h,      dtype=np.float32),
    time_abs_d = np.array(all_times_d, dtype=np.float64),
    dt_d       = np.array(all_dt_d,    dtype=np.float64),
)
```

Stage 11 reads `Group3.npz` and restores each snapshot to the FEFLOW document
via `setParamValues()`, making all IFM results getters available:

```python
doc.setParamValues(ifm.Enum.P_TEMP, T_row.tolist())
doc.setParamValues(ifm.Enum.P_HEAD, h_row.tolist())
# After restore: getResultsTransportHeatValue(), getResultsFlowHeadValue(),
# getResultsTransportHeatValueAtXYSlice(), getParamValues(P_TEMP) all work.
```

---

## Reproducibility

A pipeline run is deterministic given the same FEFLOW installation, workbook,
and `config.py`:

1. **Initial temperatures** are computed analytically in
   `config.__post_init__()` from Fourier's law and cross-checked against the
   `sliceT` workbook sheet at load time. A warning is emitted if any slice
   deviates by more than 0.05 °C.
2. **Hydraulic conductivities** are derived from intrinsic permeabilities via
   `_k_to_K()` using fixed reference fluid properties, so no manual unit
   conversion is required.
3. **The NPZ archive** is a self-contained, portable record of the simulation.
   All seven figures can be reproduced from it without re-running FEFLOW.
4. **No stochastic elements** are present. The only source of numerical
   non-reproducibility is the FEFLOW solver's internal tolerance for adaptive
   step acceptance.

To verify an existing archive before generating figures:

```bash
python - <<'EOF'
import numpy as np
data = np.load("outputs/Group3.npz")
print("Arrays  :", list(data.keys()))
print("T shape :", data["T"].shape)
print("Times   :", data["times"])
EOF
```

Expected output:

```
Arrays  : ['times', 'T', 'h', 'time_abs_d', 'dt_d']
T shape : (20, 28236)
Times   : [  1825.  3650.  5475. ... 36500.]
```

---

## Example Results

All values below are from a completed run on the Group 3 workbook with an
active FEFLOW 8.1 licence.

### Model summary

| Quantity | Value |
|----------|-------|
| Domain | 8 000 × 8 000 m |
| Reservoir interval | 270–520 m below ground surface |
| Mesh nodes | ~4 706/slice × 6 slices = ~28 236 total |
| Mesh elements | ~9 332/layer × 5 layers = ~46 660 total |
| Production wells | 5 × (+30 L/s) = +150 L/s total |
| Injection wells | 5 × (−30 L/s) = −150 L/s total |
| T_reservoir (initial) | 134.1 °C |
| T_injection | 50.0 °C |

### Thermal performance

| Quantity | t = 0 yr | t = 100 yr |
|----------|---------|----------|
| Average production temperature | ~134 °C | ~124 °C |
| Total thermal power P_th | **~52.8 MW_th** | **~46.8 MW_th** |
| Thermal degradation | — | ~11 % |

### Simulation diagnostics

| Quantity | Value |
|----------|-------|
| Total accepted adaptive steps | ~428 |
| Wall-clock time | ~6.9 min (FEFLOW 8.1, singleStep mode, modern laptop) |
| Initial time-step size | 1 × 10⁻¹⁰ d |
| Time-step at steady-state | ~100 d (dt_max reached within the first ~100 simulated days) |

---

## Testing

The test suite covers all stages that can run without a FEFLOW licence.

```bash
pytest tests/ -v                        # all tests
pytest tests/test_config.py -v          # configuration + temperature checks
pytest tests/test_utils.py -v           # mesh node count, coordinate utilities
pytest tests/test_thermal_power.py -v   # NPZ format, power calculation
pytest tests/test_postprocess_new.py -v # F6/F7 functions, NPZ fallbacks
```

| Module | Coverage |
|--------|---------|
| `test_config.py` | Config loading; Fourier temperature cross-check vs workbook; material property derivation; hydraulic conductivity conversion |
| `test_utils.py` | Expected node count per slice (4 706); coordinate getter wrappers; IFM bootstrap path detection |
| `test_thermal_power.py` | NPZ key contract (`times`, `T`, `h`); thermal power formula; CSV structure |
| `test_postprocess_new.py` | `plot_head_evolution` and `plot_timestep_evolution` callable; graceful fallback when NPZ is missing or lacks `time_abs_d`/`dt_d`; F7 produces a valid PNG from synthetic data; extended NPZ passes legacy key checks |

---

## Adapting for Groups 1–6

The pipeline is fully parameterised. To target a different group:

1. Copy the workbook to `data/geoth_tutorial_data_GroupN.xlsx`.
2. In `scripts/config.py`, set `GROUP_ID = "GroupN"` and update `_GEOLOGICAL`
   with the target group's *λ*, *Cᵥ*, *φ*, and *k* values.
3. Update the geometry constants (`z_surface`, `z_top_reservoir`,
   `z_bot_reservoir`, `z_bot_basement`) to match the target stratigraphy.
4. Build a new mesh template (`GroupN_template.fem`) in the FEFLOW GUI.
5. Run `python build_group3_model.py`.

All stages — physics, BCs, well creation, and post-processing — adapt
automatically.

---

## Future Work

- **CI/CD integration** — GitHub Actions workflow to run pytest on every push.
- **Sensitivity analysis** — parametric sweeps over flow rate, injection
  temperature, and well spacing using the pipeline as a forward model.
- **Uncertainty quantification** — Monte Carlo sampling of *k* and *λ* with
  ensemble post-processing.
- **FEFLOW 8.2+ compatibility** — re-evaluate the `singleStep()` workaround
  if DHI restores full DAC enumeration in a future IFM release.
- **3D cross-sections and animations** — vertical slices at arbitrary
  azimuths and temporal animations of the cold plume migration.
- **Multi-group automation** — implement `--group N` in
  `build_group3_model.py` to build all six course models in one command.

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-description
   ```
2. Write tests for any new functionality. All existing tests must pass.
3. Follow PEP 8. Use variable names consistent with the codebase
   (e.g., `K_mday`, `heat_flux_bc`).
4. Do not commit FEFLOW binaries — `.fem`, `.dac`, `.smhx`, and `.cache`
   files are gitignored.
5. Open a pull request with a clear description of the change and motivation.

For bug reports or feature requests, open an issue with:
- FEFLOW version and OS
- Python version and `pip freeze` output
- Minimal reproducer or full error traceback

---

## Citation

If you use this pipeline in published work, please cite both the software and
the tutorial it implements.

### Software

See [`CITATION.cff`](CITATION.cff). BibTeX:

```bibtex
@software{Group3_FEFLOW_2026,
  title   = {{Group 3 --- Automated Geothermal Doublet Simulation in FEFLOW 8.1}},
  author  = {Casasso, Alessandro},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/your-org/Group3_automation},
  license = {MIT},
  note    = {Coupled TH geothermal doublet pipeline for FEFLOW 8.1, including
             a singleStep() workaround for the IFM DAC enumeration regression.}
}
```

### Tutorial reference

```bibtex
@techreport{Casasso2024FEFLOW,
  title       = {{FEFLOW Geothermal Energy Tutorial}},
  author      = {Casasso, Alessandro},
  institution = {Politecnico di Torino},
  year        = {2024},
  note        = {rev00, 03/06/2024}
}
```

---

## License

Released under the **MIT License** — see [`LICENSE`](LICENSE) for the full
text.

FEFLOW is a commercial product of DHI A/S. This repository contains no FEFLOW
source code or proprietary binaries. A valid FEFLOW licence is required to
execute Stages 2–10.

---

*Developed for the MSc course Geothermal Energy Systems, Politecnico di Torino.*  
*FEFLOW 8.1 by DHI A/S.*
