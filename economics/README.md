# Energy Production & Economic Assessment — Group 3

Two spreadsheets covering the second and third deliverables of the BIP group
assignment (`Geothermal BIP group work instructions.pdf`): electrical power
production from the FEFLOW result, and the CAPEX/LCOE/sensitivity analysis.

## `ORC_Group3.xlsx`

Adapted from the course template `GeothermalORCturbines_Casasso.xlsx`
(A. Casasso). Computes ORC electrical power via the Lorentz-cycle method.

| Sheet | Content |
|---|---|
| `Base_Case_Group3` | Annual estimate. `Tsource-in` = 125 °C (average production-well temperature at t = 100 yr, from the FEFLOW breakthrough curve, `figures/F3_breakthrough_curve.png` / `F4_thermal_power.png`); `Tsource-out` = 50 °C (= `cfg.T_inj`, same value used in the FEFLOW model); flow rate = 150 L/s (5 × 30 L/s production wells, `welldata` sheet). |
| `Monthly_Production` | Monthly refinement: outdoor dry-bulb temperature from Volterra/Pomarance climate normals (near Larderello, climate-data.org, 1991–2021), varying the condenser side only; source-side temperatures held constant. |

**Result:** ~4.26 MW net electrical, ~34,094 MWh/yr (annual estimate) /
~34,086 MWh/yr (monthly sum) — cross-check within 0.02%.

> **Open item:** `Tsource-in` = 125 °C was read from the F3/F4 figures
> (pixel-level reading, cross-checked against the analytical thermal-power
> formula — two independent methods agreed within ~0.5 °C). It has **not**
> yet been confirmed against the raw NPZ array on a machine with FEFLOW 8.1
> installed. Run `scripts/12_extract_avg_production_temperature.py` to get
> the exact value and update `Base_Case_Group3!B2` accordingly.

## `Economic_Assessment_Group3.xlsx`

Unit costs derived from Dr. Luca Xodo's lecture (*Geothermal Power Plant
General Design and Business Plan*, STEAM Srl, slides 75–79, zero-emission
binary example), scaled to Group 3's plant.

| Sheet | Content |
|---|---|
| `Assumptions` | Wellfield data, unit costs, financial parameters (i = 10%, n = 20 yr, CF = 95%). All yellow cells are editable. |
| `CAPEX_Group3` | Full cost breakdown → **Total CAPEX ≈ €52.0M** (≈ €12,206/kW net). |
| `LCOE_Group3` | Simplified NREL-style LCOE → **185.3 €/MWh**. Formula validated by reproducing Xodo's own example (156.4 €/MWh) with the same method. |
| `Sensitivity` | Spider diagram (matches Xodo's chart style) varying `T_source-in`, `T_source-out`, flow rate, well depth, and drilling cost/m by ±10%/±20%. All five lines cross at the base LCOE, as expected. |

**Known assumptions / caveats (verbally addressed in the presentation, not bugs):**

1. Well-drilling unit cost (2,200 €/m) is derived from Xodo's example well
   (2,500 m, >250 °C) and applied linearly to Group 3's much shallower
   (1,120 m, 134 °C) well — likely an overestimate for a real shallow doublet.
   This is exactly the parameter the assignment asks to sensitivity-test
   (see `Sensitivity` sheet).
2. `Assumptions!B25` (ORC auxiliary consumption, 15%) is used to back-calculate
   an assumed gross plant MW from the ORC sheet's net `Pel`, for EPC costing
   purposes indexed to €/MWg. The exact net/gross convention in the Casasso
   ORC template is not fully unambiguous — documented as an explicit,
   editable assumption rather than resolved silently.
3. Capacity factor: Xodo's slide states both 93% and 8,322 h/yr (=95%) for
   the same case. 95% / 8,322 h/yr was used (internally consistent with the
   slide's own CO₂ calculation).

## Source data

- FEFLOW result: `../outputs/Group3.npz`, `../figures/F3_breakthrough_curve.png`, `../figures/F4_thermal_power.png`
- Reservoir properties: `../data/geoth_tutorial_data_Group3.xlsx`
- Lecture reference: Xodo, L. *Geothermal Power Plant General Design and Business Plan*, PoliTO BIP 2026, Lezione 2.
