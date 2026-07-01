# Energy Production & Economic Assessment — Group 3

Two spreadsheets covering the second and third deliverables of the BIP group
assignment (`Geothermal BIP group work instructions.pdf`): electrical power
production from the FEFLOW result, and the CAPEX/LCOE/sensitivity analysis.

## `ORC_Group3.xlsx`

Adapted from the course template `GeothermalORCturbines_Casasso.xlsx`
(A. Casasso). Computes ORC electrical power via the Lorentz-cycle method.

| Sheet | Content |
|---|---|
| `Base_Case_Group3` | Annual estimate. `Tsource-in` = 124.5327 °C (average production-well temperature at t = 100 yr); `Tsource-out` = 50 °C (= `cfg.T_inj`, same value used in the FEFLOW model); flow rate = 150 L/s (5 × 30 L/s production wells, `welldata` sheet). |
| `Monthly_Production` | Monthly refinement: outdoor dry-bulb temperature from Volterra/Pomarance climate normals (near Larderello, climate-data.org, 1991–2021), varying the condenser side only; source-side temperatures held constant. |

**Result:** ~4.22 MW net electrical, ~33,791 MWh/yr (annual estimate) /
~33,783 MWh/yr (monthly sum) — cross-check within 0.02%.

> **Production-temperature provenance:** `Tsource-in` was originally set to
> 125 °C from a chart-based reading of `../figures/F3_breakthrough_curve.png` /
> `../figures/F4_thermal_power.png` (cross-checked two independent ways,
> agreement within ~0.5 °C). Stage 12 (`../scripts/12_extract_avgT.py`) has since
> extracted the exact figure directly from the FEFLOW post-processing output:
> **124.53 °C** at t ≈ 100 yr (`../outputs/Average_Production_Temperature.csv`,
> plotted in `../figures/F8_average_production_temperature.png`). `Base_Case_Group3!B2`
> now holds this exact value (124.5327 °C, updated from the original 125 °C
> chart-based estimate — a 0.47 °C correction), and the resulting `Pel` has
> been re-copied into `Economic_Assessment_Group3.xlsx` (`Assumptions!B10`),
> so both workbooks and the Sensitivity sheet's base case are derived from
> the same figure; see the main
> [README § Assumptions](../README.md#engineering-assumptions).

## `Economic_Assessment_Group3.xlsx`

Unit costs derived from Dr. Luca Xodo's lecture (*Geothermal Power Plant
General Design and Business Plan*, STEAM Srl, slides 75–79, zero-emission
binary example), scaled to Group 3's plant.

| Sheet | Content |
|---|---|
| `Assumptions` | Wellfield data, unit costs, financial parameters (i = 10%, n = 20 yr, CF = 95%). All yellow cells are editable. |
| `CAPEX_Group3` | Full cost breakdown → **Total CAPEX ≈ €51.9M** (≈ €12,294/kW net). |
| `LCOE_Group3` | Simplified NREL-style LCOE → **186.5 €/MWh**. Formula validated by reproducing Xodo's own example (156.4 €/MWh) with the same method. |
| `Sensitivity` | Spider diagram varying `T_source-in`, `T_source-out`, flow rate, well depth, and drilling cost/m by ±10%/±20%. The base-case (0% variation) cell in all five columns now references `LCOE_Group3!$B$12` directly, so all five lines cross at exactly the base LCOE by construction, not merely by coincidence of two parallel calculations. Plotted (in Dr. Xodo's chart style, with endpoint value labels) as `../figures/F9_spider_diagram.png` (see [README § Sensitivity Analysis](../README.md#sensitivity-analysis)). |

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
   the same case. 95% / 8,322 h/yr was used in `Economic_Assessment_Group3.xlsx`
   (internally consistent with the slide's own CO₂ calculation).
4. **Load-factor discrepancy between the two workbooks:** the annual
   electricity production reported above (`Prod-el-year` in `ORC_Group3.xlsx`,
   `Base_Case_Group3!A19`) is computed using a load factor of **8,000 h/yr**,
   not the 8,322 h/yr (95% capacity factor) used for the LCOE denominator in
   `Economic_Assessment_Group3.xlsx` (`Assumptions!A30`). The two workbooks
   were not cross-linked when this assumption was set, so this ~4% difference
   in full-load hours was not reconciled. It does not change either reported
   headline figure (~33.8 GWh/yr production, 186.5 €/MWh LCOE), since each was
   computed with its own workbook's own assumption; it is flagged here so the
   two are not mistaken for the same number. This is unrelated to the
   `Tsource-in` update above and remains open.

## Source data

- FEFLOW result: `../outputs/Group3.npz`, `../outputs/Average_Production_Temperature.csv`
  (exact average production temperature, Stage 12), `../figures/F3_breakthrough_curve.png`,
  `../figures/F4_thermal_power.png`, `../figures/F8_average_production_temperature.png`
- Reservoir properties: `../data/geoth_tutorial_data_Group3.xlsx`
- Lecture reference: Xodo, L. *Geothermal Power Plant General Design and Business Plan*, PoliTO BIP 2026, Lezione 2.
