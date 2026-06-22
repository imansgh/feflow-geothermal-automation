# FEFLOW GUI Step-by-Step Guide — Group 3 Geothermal Doublet

**Course:** Geothermal Energy Systems — Politecnico di Torino  
**Software:** FEFLOW 8.1 (DHI)  
**Audience:** Master's students with no programming experience  
**Tutorial reference:** FEFLOW Geothermal Energy Tutorial, Alessandro Casasso, rev00, 03/06/2024

---

> **How to read this guide**
>
> Every parameter carries a source label so you know exactly where it comes from:
>
> - 🔵 **[Tutorial]** — exact value or GUI step from the official FEFLOW tutorial PDF (Casasso, rev00)
> - 🟢 **[Workbook]** — value taken from `geoth_tutorial_data_Group3.xlsx`
> - ⚪ **[FEFLOW default]** — accept whatever FEFLOW pre-fills; do not change it
>
> Where Group 3 values differ from the tutorial's generic example scenario, **both** are shown.  
> If a value is not confirmed by one of these sources, this guide states **"Use the FEFLOW default"** and does not invent a number.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Supermesh and mesh generation](#2-supermesh-and-mesh-generation)
3. [3D layer configuration](#3-3d-layer-configuration)
4. [Problem settings](#4-problem-settings)
5. [Material properties](#5-material-properties)
6. [Initial and boundary conditions](#6-initial-and-boundary-conditions)
7. [Multilayer wells](#7-multilayer-wells)
8. [Simulation output settings](#8-simulation-output-settings)
9. [Running the simulation](#9-running-the-simulation)
10. [Post-processing in FEFLOW GUI](#10-post-processing-in-feflow-gui)
11. [Expected results](#11-expected-results)
12. [Troubleshooting](#12-troubleshooting)

---

## 1  Introduction

### 1.1  Geological and hydrogeological setup

The Group 3 reservoir is a limestone unit covered by a thick caprock and underlain by a granite basement.

| Feature | Group 3 value | Tutorial generic value | Source |
|---------|--------------|------------------------|--------|
| Ground surface elevation | **600 m a.s.l.** | 500 m a.s.l. | 🟢 Workbook |
| Reservoir top elevation | **−270 m a.s.l.** | −300 m a.s.l. | 🟢 Workbook |
| Reservoir bottom elevation | **−520 m a.s.l.** | −600 m a.s.l. | 🟢 Workbook |
| Basement bottom elevation | **−2 500 m a.s.l.** | −1 600 m a.s.l. | 🟢 Workbook |
| Geothermal heat flux | **0.241 W/m²** | 0.200 W/m² | 🟢 Workbook |
| Surface temperature | 15 °C | 15 °C | 🔵 Tutorial |
| Hydraulic head | 200 m a.s.l. | 200 m a.s.l. | 🔵 Tutorial |

### 1.2  The plant

| Parameter | Value | Source |
|-----------|-------|--------|
| Production wells | 5 | 🟢 Workbook |
| Injection wells | 5 | 🟢 Workbook |
| Flow rate per well | 30 L/s | 🟢 Workbook |
| Injection temperature | 50 °C | 🟢 Workbook |
| Simulation duration | 36 500 days (100 years) | 🔵 Tutorial |

### 1.3  Expected initial thermal power

From the tutorial formula 🔵:

```
P = 5 × Q × ρ·c_w × ΔT
  = 5 × 108 m³/h × 1.16 kWh/(m³·K) × (135 − 50) K
  ≈ 53 000 kW = 53 MW_th
```

For Group 3 with T_reservoir ≈ 134 °C:  **P₀ ≈ 52.8 MW_th**  🟢 Workbook

---

## 2  Supermesh and mesh generation

> 🔵 Tutorial reference: §2.1 "Creating the supermesh and the mesh" (pp. 4–10)

### 2.1  Project folder structure

Before starting, create the following subfolders in your working directory 🔵:

```
your_project/
├── supermsh/         ← supermesh files (.smhx)
├── femdata/          ← FEFLOW model files (.fem)
├── Import+export/    ← Excel, shapefiles, etc.
└── Results/          ← simulation results (.dac)
```

### 2.2  Create a new model

1. Open **FEFLOW 8.1**.
2. Click the **New** icon (top-left) or go to **File → New**.
3. In the dialog that appears, select **"2D or layered 3D mesh"**, then click **Next**. 🔵
4. Select **"Manual domain setup"**, then click **Next**. 🔵
5. Define the x–y limits: set **x from 0 to 8 000 m** and **y from 0 to 8 000 m**, then click **Next** and **Finish**. 🔵

![Screenshot: New model wizard, "2D or layered 3D mesh" option selected](screenshots/01_new_model_wizard.png)

### 2.3  Draw the domain polygon

The model domain is a **square with side 8 000 m**. 🔵

1. Click the **"Add Polygons"** icon in the supermesh toolbar. 🔵
2. A cross (+) pointer appears.  Do **not** click freely on screen — instead, press the **F2** key to enter precise coordinates. 🔵
3. Type **`0,0`** and press **Enter**.  The first corner appears.
4. Press **F2** again, type **`8000,0`**, press **Enter**.
5. Press **F2**, type **`8000,8000`**, press **Enter**.
6. Press **F2**, type **`0,8000`**, press **Enter**.
7. Click on the **first point** to close the polygon.  A grey-shaded square appears. 🔵
8. Save the supermesh: click the **Save** icon and save in the **supermsh** folder as `Group3_geothermal.smhx`. 🔵

![Screenshot: Grey square domain polygon with corners at 0,0 and 8000,8000](screenshots/02_domain_polygon.png)

> **Tip:** If the polygon does not close properly, press Escape to cancel and repeat from Step 1.

### 2.4  Import well node coordinates

The well positions come from the `wellnodecoordinates` sheet of `geoth_tutorial_data_Group3.xlsx`.  Each of the 10 wells has a centre node plus 6 cluster nodes arranged on a hexagon (the BHE rule), giving 70 points total. 🔵

1. In the **lower-left corner**, find the **Maps** panel.  If not visible, go to **View → Panels → Maps**. 🔵
2. **Right-click** anywhere in the Maps panel and select **"Add Map(s)"**. 🔵
3. Browse to `geoth_tutorial_data_Group3.xlsx`.
4. From the drop-down sheet selector, choose **wellnodecoordinates**. 🟢
5. Click **OK**.  Small cross markers appear on the map, representing the 70 well points. 🔵

![Screenshot: Maps panel after loading wellnodecoordinates — crosses visible near domain centre](screenshots/03_maps_panel_crosses.png)

6. In the Maps panel, **double-click on "Default"** to display the imported points in the model view. 🔵
7. Now convert them to supermesh points: in the Maps panel, **right-click** on `wellcoordinates@geoth_tutorial_data_Group3` and select **"Convert to" → "Supermesh Points"**. 🔵
8. Brown circles appear below the crosses — these are now supermesh points. 🔵
9. **Save** the supermesh again (Save icon, same supermsh folder).

![Screenshot: Brown supermesh point circles overlaid on the cross markers near domain centre](screenshots/04_supermesh_points_converted.png)

### 2.5  Generate the triangular mesh

1. Find the **Meshing panel** in the top-right of the screen.  If not visible, go to **View → Panels → Meshing**. 🔵
2. You can close the "Rate budget" window to see the Meshing panel better. 🔵
3. In the Meshing panel, select **"Triangle"** from the meshing method drop-down. 🔵
4. Click **"From Supermesh Elements"** and then select **Polygon1**. A menu showing proposed element counts appears. 🔵
5. In the upper part of the Meshing panel, configure **local refinement** around the well supermesh points 🔵:
   - Double-click **"Refine points"** until it shows **"True"**.
   - Set **"Point Gradation"** = **4**
   - Set **"Point Target Size"** = **5 m**
6. Click **"Generate Mesh"**. 🔵

![Screenshot: Meshing panel with Triangle method, Point Target Size=5, Point Gradation=4](screenshots/05_meshing_panel.png)

> **What do these settings mean?** 🔵
> - **Point Target Size (PTS) = 5 m:** The mesh elements immediately around each well point will be approximately 5 m in size.
> - **Point Gradation (PG) = 4:** Controls how gradually the mesh coarsens away from the well points. Higher = more gradual transition.
> - **Expected result with PTS=5, PG=4:** approximately 9 332 elements and **4 706 nodes** per slice. 🔵

7. After the mesh is generated, press **Alt+Enter** and choose **"Problem summary"** to verify the node and element counts. 🔵
8. Save the model: press **F12** (Save As), navigate to the **femdata** folder, and save as `Group3.fem`. 🔵

![Screenshot: Generated triangular mesh — finer near well cluster in centre, coarser at edges](screenshots/06_mesh_generated.png)

> **Licence note:** If you are using a FEFLOW lab-kit licence, be aware it is limited to **50 000 nodes total**.  With 4 706 nodes per slice × 6 slices = 28 236 nodes, the default mesh fits well within this limit.  If you increase PTS or PG and exceed 50 000 nodes when saving, FEFLOW will warn you. 🔵

---

## 3  3D layer configuration

> 🔵 Tutorial reference: §3.1 "Defining slices and their elevation" (pp. 10–12)

### 3.1  Open the Layer Configurator

Press **Ctrl+L**. 🔵

The layer configurator dialog opens showing the current (2D) mesh with Slice 1 only.

![Screenshot: Layer Configurator dialog, initial state with one slice](screenshots/07_layer_configurator.png)

### 3.2  Set the outermost slices as "Fixed"

1. Select **Slice 1** in the list.
2. Set its elevation to **600 m** (Group 3 ground surface 🟢) and mark it as **"Fixed"**. 🔵
3. Select **Slice 2** (the last slice, initially).
4. Set its elevation to **−2 500 m** (Group 3 basement bottom 🟢) and mark it as **"Fixed"**. 🔵

> The tutorial uses 500 m and −1 600 m for its generic scenario.  Group 3 uses 600 m and −2 500 m from the workbook.

### 3.3  Insert the four intermediate slices

After setting the fixed top and bottom, insert slices one by one using the **"Insert slice(s) below"** button 🔵:

1. With **Slice 1 (600 m)** selected, click **"Insert slice(s) below"** and add **1 slice**, positioned **870 m below** Slice 1.  
   → Result: Slice 2 at **−270 m a.s.l.** 🟢 (top of reservoir)

2. With **Slice 2 (−270 m)** selected, click **"Insert slice(s) below"** and add **1 slice**, **100 m below**.  
   → Result: Slice 3 at **−370 m a.s.l.** 🟢

3. With **Slice 3 (−370 m)** selected, insert **1 slice**, **100 m below**.  
   → Result: Slice 4 at **−470 m a.s.l.** 🟢

4. With **Slice 4 (−470 m)** selected, insert **1 slice**, **50 m below**.  
   → Result: Slice 5 at **−520 m a.s.l.** 🟢 (bottom of reservoir / top of basement)

> **Alternative:** The tutorial suggests that after inserting Slice 2, you can add 3 slices spaced 100 m (or appropriate spacing) below it in one operation. 🔵

### 3.4  Verify slice elevations

After all insertions, the Layer Configurator should show exactly:

| Slice | Elevation [m a.s.l.] | Geological meaning | Source |
|-------|---------------------|--------------------|--------|
| 1 | **600** | Ground surface | 🟢 Workbook |
| 2 | **−270** | Top of reservoir / base of caprock | 🟢 Workbook |
| 3 | **−370** | Internal reservoir | 🟢 Workbook |
| 4 | **−470** | Internal reservoir | 🟢 Workbook |
| 5 | **−520** | Bottom of reservoir / top of basement | 🟢 Workbook |
| 6 | **−2 500** | Bottom of basement | 🟢 Workbook |

Click **OK** to close the Layer Configurator and generate the 3D mesh.

### 3.5  Resulting layer structure

| Layer | Between slices | Geological unit | Thickness |
|-------|---------------|----------------|-----------|
| 1 | Slice 1 → Slice 2 | Caprock | 870 m |
| 2 | Slice 2 → Slice 3 | Reservoir | 100 m |
| 3 | Slice 3 → Slice 4 | Reservoir | 100 m |
| 4 | Slice 4 → Slice 5 | Reservoir | 50 m |
| 5 | Slice 5 → Slice 6 | Basement | 1 980 m |

### 3.6  Verify the 3D model

Press **Alt+Enter** to check the total node count. 🔵

With 4 706 nodes/slice × 6 slices = **28 236 total nodes**. Save with **F12**.

![Screenshot: 3D perspective view after layer generation, showing five geological layers](screenshots/08_3d_view.png)

---

## 4  Problem settings

> 🔵 Tutorial reference: §3.2 "Problem settings" (pp. 12–14)

### 4.1  Open Problem Settings

Press **Alt+Enter**. 🔵

The Problem Settings dialog appears.

### 4.2  Problem class

1. Select **"Problem class"** in the left panel. 🔵
2. Set **Problem type** to **"Heat"** transport (this activates the coupled flow + heat transport problem). 🔵
3. Set **Time regime** to **"Transient"** for **both flow and heat transport**. 🔵
4. Click **Apply**.

![Screenshot: Problem class dialog — Heat transport, Transient selected for both](screenshots/09_problem_class.png)

### 4.3  Simulation-Time control

Still in the Alt+Enter dialog, select **"Simulation-Time control"**. 🔵

Enter the following values:

| Parameter | Value | Source |
|-----------|-------|--------|
| Initial time-step length | **1 × 10⁻¹⁰ d** | 🔵 Tutorial |
| Predictor-corrector scheme | **First-order accurate (FE/BE)** | 🔵 Tutorial |
| Final simulation time | **36 500 d** | 🔵 Tutorial |
| Maximum time-step size | **100 d** | 🔵 Tutorial |

![Screenshot: Simulation-Time control tab with the four values filled in](screenshots/10_time_control.png)

> **Why FE/BE and 1×10⁻¹⁰ d initial step?** The predictor-corrector FE/BE scheme is unconditionally stable for coupled thermo-hydraulic problems. 🔵  The extremely small first step allows the solver to correctly initialise before growing the time step adaptively.

### 4.4  Transport settings — fluid viscosity

Select **"Transport settings"** in the dialog. 🔵

Under the **"General settings"** tab: 🔵
- **Fluid viscosity:** set to **"Variable — dependent on temperature"**

![Screenshot: Transport settings — General settings tab, viscosity set to variable](screenshots/11_transport_viscosity.png)

### 4.5  Transport settings — fluid density

Click the **"Fluid density"** tab. 🔵
- **Dependency on temperature:** set to **"Linear"**

![Screenshot: Fluid density tab — Linear dependency on temperature selected](screenshots/12_fluid_density.png)

### 4.6  Transport settings — reference values

Click the **"Reference values"** tab. 🔵

Verify (or enter) the following:

| Parameter | Value | Source |
|-----------|-------|--------|
| Reference temperature | **10 °C** | 🔵 Tutorial |
| Reference density | **999.793 kg/m³** | 🔵 Tutorial |
| Reference viscosity | **97.1136 kg/(m·d)** = 1.124 × 10⁻³ Pa·s | 🔵 Tutorial |

> These reference values are used by FEFLOW to convert intrinsic permeability [m²] to hydraulic conductivity [m/d].  Do not change them. 🔵

![Screenshot: Reference values tab with T=10°C, ρ=999.793 kg/m³, μ=97.1136 kg/(m·d)](screenshots/13_reference_values.png)

Click **OK** to close Problem Settings.  Save with **F12**.

---

## 5  Material properties

> 🔵 Tutorial reference: §4 "Material properties" (pp. 15–20)

### 5.1  Open material properties

In the **lower-left panel "Data"**, double-click on **"Material properties"**. 🔵

![Screenshot: Data panel with Material properties node expanded](screenshots/14_data_panel_materials.png)

### 5.2  Group 3 material property values

The following tables show the values for Group 3 from the workbook.  The tutorial's generic scenario uses different values (shown for reference only).

#### Hydraulic conductivity

FEFLOW works with hydraulic conductivity K [m/d], not with permeability k [m²]. 🔵  
The conversion formula is: **K [m/d] = k [m²] × ρ × g / μ × 86 400** 🔵

| Layer | Unit | k [m²] | K [m/d] | Tutorial K [m/d] | Source |
|-------|------|---------|---------|-----------------|--------|
| 1 | Caprock | 1.243 × 10⁻¹⁵ | **9.371 × 10⁻⁴** | 7.57 × 10⁻⁴ | 🟢 Workbook |
| 2 | Reservoir | 9.133 × 10⁻¹⁴ | **6.886 × 10⁻²** | 9.08 × 10⁻² | 🟢 Workbook |
| 3 | Reservoir | 9.133 × 10⁻¹⁴ | **6.886 × 10⁻²** | 9.08 × 10⁻² | 🟢 Workbook |
| 4 | Reservoir | 9.133 × 10⁻¹⁴ | **6.886 × 10⁻²** | 9.08 × 10⁻² | 🟢 Workbook |
| 5 | Basement | 7.226 × 10⁻¹⁶ | **5.448 × 10⁻⁴** | 7.57 × 10⁻⁵ | 🟢 Workbook |

#### Porosity, heat capacity and thermal conductivity

| Layer | Unit | Porosity φ | C_v [10⁶ J/(m³·K)] | λ_s [W/(m·K)] | Source |
|-------|------|-----------|---------------------|----------------|--------|
| 1 | Caprock | **0.27** | **2.228** | **1.76** | 🟢 Workbook |
| 2,3,4 | Reservoir | **0.025** | **2.247** | **2.30** | 🟢 Workbook |
| 5 | Basement | **0.01** | **2.611** | **4.87** | 🟢 Workbook |

> **Comparison with tutorial generic scenario:** Caprock φ=0.2, C_v=2.1×10⁶, λ=1.333 W/(m·K); Reservoir φ=0.02, C_v=2.2×10⁶, λ=3 W/(m·K); Basement φ=0.01, C_v=2.6×10⁶, λ=4 W/(m·K). 🔵  Group 3 uses its own values from the workbook.

### 5.3  How to assign hydraulic conductivity

#### Layer 1 (Caprock)

1. In the Data panel under Material properties, **double-click on "Kxx"**. 🔵
2. Press **Ctrl+A** to select all elements of the current layer. 🔵
3. **Right-click** on "Conductivity" in the panel and select **"Assign Multiple…"**. 🔵
4. Enter **9.371e-4** in the K_xx, K_yy, and K_zz fields. 🟢
5. Select **"Apply to current slice/layer"**. 🔵
6. Press **OK**.
7. Press the **red X button** to deselect all elements. 🔵

![Screenshot: Assign Multiple dialog for Kxx with 9.371e-4 in all three fields](screenshots/15_assign_kxx_layer1.png)

#### Layers 2, 3, 4 (Reservoir)

1. Click on the mesh and press **PgDn** (Page Down) to move to the next layer. 🔵  
   The current slice/layer number is shown in the display.
2. Navigate to **Layer 2** (below Slice 2).
3. Press **Ctrl+A** to select all elements.
4. Click the **"Copy Selection to Slices/Layers"** icon in the toolbar. 🔵
5. In the dialog that appears, hold **Ctrl** and click on **Layer 2, Layer 3, and Layer 4** to extend the selection to all three reservoir layers. 🔵
6. Click **OK**.
7. The elements in all 3 reservoir layers are now selected.
8. **Right-click → Assign Multiple…** and enter **6.886e-2** in K_xx, K_yy, K_zz. 🟢
9. Select **"Apply to current selection"**. 🔵
10. Press **OK**, then the red X to deselect.

![Screenshot: Copy Selection to Slices/Layers dialog with Layers 2, 3, 4 highlighted](screenshots/16_copy_to_layers.png)

#### Layer 5 (Basement)

1. Press **PgDn** to reach Layer 5.
2. **Ctrl+A** to select all, right-click → **Assign Multiple…** → enter **5.448e-4** for K_xx, K_yy, K_zz. 🟢
3. **Apply to current slice/layer** → **OK** → red X to deselect.

### 5.4  Assign porosity, heat capacity and thermal conductivity

In the Data panel, expand **"Heat transport"** under Material properties.  There are three properties to assign 🔵:
- **Porosity**
- **Volumetric heat capacity of solid**
- **Thermal conductivity of solid**

For each property, use **exactly the same assignment procedure** described in §5.3 above (Ctrl+A → right-click → Assign Multiple, layer by layer or with Copy Selection to Layers). 🔵

The tutorial notes that for each layer selection (Layer 1; Layers 2–3–4; Layer 5), you can **assign all heat transport parameters simultaneously** in the same Assign Multiple dialog. 🔵

After assigning all material properties, press **Ctrl+3** to open a 3D view and visualise, for example, Kxx to verify the three different conductivity values. 🔵  Save with **F12**.

---

## 6  Initial and boundary conditions

> 🔵 Tutorial reference: §5 "Initial and boundary conditions" (pp. 21–29)

### 6.1  Flow initial conditions — hydraulic head

> 🔵 Tutorial §5.1.1, p. 21

The hydraulic head of the geothermal reservoir is set to **200 m a.s.l.** everywhere. 🔵

1. In the **Data panel**, open **"Process Variables"** → **"Fluid flow"**.
2. **Double-click on "Hydraulic head"**. 🔵
3. Press **Ctrl+A** to select all nodes on the current slice. 🔵
4. Click the **"Copy Selection to Slices/Layers"** icon. 🔵
5. In the dialog, click **"Select/deselect all"** to select all slices. 🔵
6. Enter the value **200** m and press the **"✓" (tick/V) button**. 🔵
7. Deselect all nodes.
8. Save with **F12**.

![Screenshot: Hydraulic head initial condition — all nodes on all slices selected, value 200 m](screenshots/17_head_initial_condition.png)

### 6.2  Heat transport initial conditions — temperature

> 🔵 Tutorial §5.1.2, p. 22

Assign the undisturbed geothermal temperature **slice by slice**. 🔵

1. In the **Data panel**, open **"Process Variables"** → **"Heat transport"**.
2. **Double-click on "Temperature"**. 🔵
3. Navigate to **Slice 1** using **PgUp**. 🔵
4. Press **Ctrl+A** to select all nodes on Slice 1.
5. Enter **15.0 °C** and press the **"✓" button**. 🔵
6. Deselect nodes, then press **PgDn** to go to the next slice. 🔵
7. Repeat for all 6 slices, using the values in the table below.

| Slice | Elevation [m a.s.l.] | Initial temperature [°C] | Source |
|-------|---------------------|--------------------------|--------|
| 1 | 600 | **15.00** | 🔵 Tutorial (T_surface) |
| 2 | −270 | **134.13** | 🟢 Workbook |
| 3 | −370 | **144.61** | 🟢 Workbook |
| 4 | −470 | **155.09** | 🟢 Workbook |
| 5 | −520 | **160.33** | 🟢 Workbook |
| 6 | −2 500 | **258.31** | 🟢 Workbook |

> **Comparison with tutorial generic scenario temperatures:** 15, 135, 141.67, 148.33, 155, 205 °C. 🔵  Group 3 uses its own temperatures derived from a heat flux of 241 mW/m².

![Screenshot: Temperature initial condition assigned — Slice 2 appears uniformly coloured at 134 °C](screenshots/18_temperature_initial_condition.png)

Save with **F12**.

### 6.3  Heat transport boundary conditions — temperature at borders (1st kind)

> 🔵 Tutorial §5.2.1.1, pp. 22–24

Apply the same geothermal temperature as a **fixed (Dirichlet) BC** to all **border nodes** of each slice.  This prevents the lateral boundaries from drifting over time.

1. In the **Data panel**, open **"Boundary Conditions (BC)"** → **"Heat transport"**.
2. **Double-click on "Temperature BC"**. 🔵
3. Navigate to **Slice 1** (PgUp).
4. Select the border nodes using the **"Select along a border"** tool: 🔵  
   click on a border mesh node and drag along the entire perimeter until all border nodes are selected.
5. Enter **15.0 °C** and press **"✓"**. 🔵
6. Deselect, press **PgDn**, go to the next slice, repeat.

Use the same temperatures as in §6.2 for each slice. 🔵

> The tutorial acknowledges this step is repetitive but necessary. 🔵

![Screenshot: Border nodes on Slice 2 selected using "Select along a border" tool, temperature BC = 134 °C](screenshots/19_temperature_bc_border.png)

### 6.4  Heat transport boundary conditions — geothermal heat flux (2nd kind)

> 🔵 Tutorial §5.2.1.2, p. 24

Apply an upward geothermal heat flux at the **bottom of the model (Slice 6)**.

1. Navigate to **Slice 6** using **PgDn**. 🔵
2. In the **Data panel**, open **"Boundary Conditions (BC)"** → **"Heat transport"**.
3. **Double-click on "Heat-flux BC"**. 🔵
4. Press **Ctrl+A** to select all nodes on Slice 6. 🔵
5. Convert the heat flux to FEFLOW units:

| | Group 3 | Tutorial generic |
|-|---------|-----------------|
| Heat flux [W/m²] | **0.241** | 0.200 |
| Converted to J/(m²·d) | **0.241 × 86 400 = 20 822.4** | 0.200 × 86 400 = 17 280 |
| FEFLOW sign (negative = into domain) | **−20 822.4** | −17 280 |

Enter **−20 822.4** J/(m²·d). 🟢

> **Sign convention:** FEFLOW uses the convention that a flux **entering** the domain has a **negative** sign. 🔵  The geothermal heat enters from below, so the value is negative.

6. Press **"✓"** to assign.  The bottom slice will change colour. 🔵
7. Deselect all nodes.  Save with **F12**.

![Screenshot: Slice 6 selected with heat-flux BC dialog showing −20822.4 J/(m²·d)](screenshots/20_heat_flux_bc.png)

### 6.5  Flow boundary conditions — hydraulic head at borders (1st kind)

> 🔵 Tutorial §5.2.2.1, p. 25

Assign a fixed hydraulic head of **200 m** to all border nodes on **all slices**. 🔵

1. In the **Data panel**, open **"Boundary Conditions (BC)"** → **"Fluid flow"**.
2. **Double-click on "Hydraulic-head BC"**. 🔵
3. Select border nodes on each slice using the same **"Select along a border"** method as §6.3. 🔵
4. **Extend the selection to all slices** using "Copy Selection to Slices/Layers" and selecting all. 🔵
5. Assign **200 m** and press **"✓"**.
6. Deselect all nodes.  Save with **F12**.

> **No-flow lateral faces:** FEFLOW applies zero-flux (no-flow) automatically to all faces where no boundary condition is assigned. Since we are assigning a fixed head at the **border nodes** (not a zero-flux condition on the **lateral faces**), the head BC controls the lateral boundaries. ⚪ FEFLOW default for all unassigned faces.

---

## 7  Multilayer wells

> 🔵 Tutorial reference: §5.2.2.2 "4th kind BC (wells)" (pp. 25–27) and §5.2.2.3 "Reinjection temperature" (pp. 28–29)

### 7.1  Load well data from Excel

The well configuration is imported via the Maps panel, linking the Excel `welldata` sheet directly to FEFLOW parameters. 🔵

1. Go to the **Maps panel** (lower-left). 🔵
2. **Right-click** → **"Add Map(s)"**. 🔵
3. Select `geoth_tutorial_data_Group3.xlsx`, then choose the sheet **"welldata"**. 🟢
4. Click **OK**.

The `welldata` sheet contains these columns 🔵🟢:

| Column | Meaning | Unit |
|--------|---------|------|
| name | Well identifier | — |
| X | Easting coordinate | m |
| Y | Northing coordinate | m |
| depth_top | Top of screen (below ground surface) | m |
| depth_bottom | Bottom of screen (below ground surface) | m |
| radius | Well radius | m |
| rate | Flow rate (positive = production, negative = injection) | L/s |

> **Radius:** 0.15 m for all wells. 🔵  
> **Rate:** +30 L/s for production, −30 L/s for injection. 🟢

### 7.2  Link Excel columns to FEFLOW MLW parameters

1. In the Maps panel, **right-click** on `@welldata@geoth_tutorial_data_Group3` and select **"Link to Parameter(s)"**. 🔵
2. The **"Parameter association"** window appears with a list of Excel columns on the left and FEFLOW parameters on the right. 🔵
3. Perform the following associations **one at a time** 🔵:

| Excel column | FEFLOW parameter path |
|-------------|----------------------|
| `depth_top` | Boundary Conditions → Fluid flow → Multilayer Well → **Depth to Top** |
| `depth_bottom` | Boundary Conditions → Fluid flow → Multilayer Well → **Depth to Bottom** |
| `name` | Boundary Conditions → Fluid flow → Multilayer Well → **Name** |
| `radius` | Boundary Conditions → Fluid flow → Multilayer Well → **Radius** |
| `rate` | Boundary Conditions → Fluid flow → Multilayer Well → **Type** (change unit from m³/d to **L/s**) |

For each association: **double-click** the column name on the left → navigate to the FEFLOW parameter on the right → configure as needed → accept with default options. 🔵

> **Important — flow rate unit:** When associating the `rate` column, you must **change the unit from m³/d to L/s** in the association dialog, because the workbook stores rates in L/s. 🔵

4. Click **OK** and save. 🔵

![Screenshot: Parameter association window with depth_top linked to Multilayer Well — Depth to Top](screenshots/21_parameter_association.png)

### 7.3  Assign wells to the mesh (edges)

Wells in FEFLOW are assigned to **edges** (not nodes or elements). 🔵

1. In the **Data panel**, open **"Boundary Conditions (BC)"** → **"Fluid flow"**.
2. **Double-click on "Multilayer Well"**. 🔵
3. Press **Ctrl+A** to select all edges. 🔵
4. Use **"Copy Selection to Slices/Layers"** → select all layers (extend to all). 🔵
5. In the assignment panel, click the **red icon** (import from linked map). 🔵  
   The previously configured parameter associations will appear.
6. Press the **"✓" (V) button** to assign the wells. 🔵
7. Deselect edges.  Save. 🔵

![Screenshot: Multilayer Well assigned — well symbols appear at the 10 well locations](screenshots/22_mlw_assigned.png)

### 7.4  Assign reinjection temperature (injection wells only)

> 🔵 Tutorial §5.2.2.3, pp. 28–29

A fixed temperature of **50 °C** is applied to the **nodes** at the injection well locations within the reservoir slices. 🟢

#### Step 1 — Lock the Multilayer Well view

1. **Double-click "Multilayer Well"** in the Data panel to make well locations visible. 🔵
2. In the top-right of the screen, find the **"View Components"** panel. 🔵
3. **Right-click on "Multilayer Well"** in that panel and click **"Lock Data View"**. 🔵  
   This keeps well icons visible while you switch to the temperature BC tool.

#### Step 2 — Apply temperature BC at injection nodes

1. In the **Data panel**, open **"Boundary Conditions (BC)"** → **"Heat transport"**.
2. **Double-click on "Temperature BC"**. 🔵
3. Click the **"Select individual mesh items"** icon to switch to node-selection mode. 🔵
4. Browse slices with **PgDn** until you can see the injection well icons in the mesh. 🔵  
   Well icons appear in the slices where the screen interval intersects (reservoir slices 2–5 for Group 3).
5. Select the **5 injection well nodes** on the current slice by clicking them individually. 🔵
6. Use **"Copy Selection to Slices/Layers"** to extend the selection to **all reservoir slices** (Slices 2, 3, 4, and 5) where well icons appear. 🔵
7. Assign **50 °C** and press **"✓"**. 🔵🟢

![Screenshot: Injection well nodes selected on Slice 2, temperature BC dialog showing 50°C](screenshots/23_injection_temp_bc.png)

> **Production wells:** Do **not** apply any temperature BC to production well nodes.  The temperature at production nodes is a model output, not an imposed value.

8. Deselect all nodes.  Save with **F12**.  

You are now ready to run the simulation. 🔵

---

## 8  Simulation output settings

> 🔵 Tutorial reference: §6 "Running the simulation" (pp. 30–32)

Before pressing Start, you must configure **what results to save and when**.

### 8.1  Open the Record settings

Click the **red "Record" icon** in the top toolbar row. 🔵

A dialog appears where you set the output file and output schedule.

### 8.2  Set the results file

1. Browse to your **Results/** folder.
2. Name the file **`Group3.dac`**.
3. Select **Binary** format. ⚪ FEFLOW default (recommended for speed and file size).

### 8.3  Set custom output times

Define output times every **5 years (1 825 days)** over 100 years. 🔵

1. In the Record dialog, select **"Custom time sequence"**. 🔵
2. The tutorial recommends **copying the times from an Excel spreadsheet and pasting them** into the FEFLOW dialog. 🔵

Prepare the following list in Excel (or type manually):

| # | Time [d] | Time [yr] |
|---|----------|-----------|
| 1 | 1 825 | 5 |
| 2 | 3 650 | 10 |
| 3 | 5 475 | 15 |
| 4 | 7 300 | 20 |
| 5 | 9 125 | 25 |
| 6 | 10 950 | 30 |
| 7 | 12 775 | 35 |
| 8 | 14 600 | 40 |
| 9 | 16 425 | 45 |
| 10 | 18 250 | 50 |
| 11 | 20 075 | 55 |
| 12 | 21 900 | 60 |
| 13 | 23 725 | 65 |
| 14 | 25 550 | 70 |
| 15 | 27 375 | 75 |
| 16 | 29 200 | 80 |
| 17 | 31 025 | 85 |
| 18 | 32 850 | 90 |
| 19 | 34 675 | 95 |
| 20 | 36 500 | 100 |

3. Copy the 20 time values from Excel, paste into the FEFLOW custom time dialog. 🔵
4. Press **OK** twice. 🔵
5. Save the model with **F12**.

![Screenshot: Custom time sequence dialog with 20 entries at 1825 d intervals pasted](screenshots/24_custom_times.png)

---

## 9  Running the simulation

> 🔵 Tutorial reference: §6 (pp. 30–32)

### 9.1  Start the simulation

Click the **"Start" icon** in the toolbar. 🔵

The simulation begins.  FEFLOW displays the Simulation Control panel showing progress.

![Screenshot: Simulation Control panel at t=0, starting up](screenshots/25_simulation_start.png)

### 9.2  Monitor the run

While the simulation runs, you can observe 🔵:

- **Current simulation time [d]:** Advances from 0 toward 36 500 d.
- **Time-step size [d]:** Starts at ~10⁻¹⁰ d, grows rapidly to ~100 d within the first few simulated days, and remains near 100 d for most of the run.
- **Well temperatures:** Open a time-series chart at a production node to watch T(t) evolve in real time.
- **Hydraulic heads:** Open a time-series chart at a production node and an injection node to watch h(t).

![Screenshot: Real-time well temperature chart during the run — temperature at production wells visible](screenshots/26_simulation_running_temp.png)

![Screenshot: Real-time hydraulic head chart during the run — production well head drops, injection rises](screenshots/27_simulation_running_head.png)

### 9.3  Simulation complete

When the run finishes:
- The final time should be **36 500 d** exactly.
- The `.dac` results file in your Results/ folder contains 20 snapshots.
- **Expected runtime:** approximately **5–15 minutes** on a modern laptop.

Save the model with **F12**.

---

## 10  Post-processing in FEFLOW GUI

### 10.1  Load existing results

If you reopen the model after the simulation:
1. **File → Open** → select `Group3.fem`.
2. FEFLOW automatically attaches the `Group3.dac` results file.
3. The **Time Steps** panel (bottom of screen) shows all 20 saved snapshots.

### 10.2  F1 — Temperature maps (plan view, five times)

**Goal:** Colour contour map of temperature at Slice 2 (top of reservoir) at t = 0, 10, 30, 50, and 100 yr.

1. In the **Data panel**, select **Temperature** under **Results**.
2. Press **Ctrl+2** or use the view toggle to go to **2D plan view**.
3. Navigate to **Slice 2** (PgDn from Slice 1).
4. In the **Time Steps** panel, select **t = 1 825 d (5 yr)** as the first snapshot. The t = 0 yr state is the initial condition (uniformly 134 °C).
5. Set the colour scale:
   - Minimum = **50 °C** (injection temperature)
   - Maximum = **134 °C** (initial reservoir temperature)
6. **Lock the colour scale** (right-click the colour bar → Lock) so it stays the same across all time steps.
7. Step through the time steps at t ≈ 10, 30, 50, 100 yr and take a screenshot at each.

> As time progresses, a cold blue plume spreads from the injection wells toward the production wells.

![Screenshot: Temperature plan view, Slice 2, t=100yr — cold plume visible around injection wells](screenshots/28_temperature_map_t100.png)

### 10.3  F2 — Vertical cross-section

**Goal:** Temperature cross-section along the doublet axis at t = 100 yr.

1. Use the **Cross Section** tool in the toolbar.
2. Draw a line from an injection well to the nearest production well.
3. Set the results variable to **Temperature** at **t = 36 500 d**.
4. The horizontal axis shows distance along the doublet [m]; the vertical axis shows elevation [m a.s.l.].

![Screenshot: Vertical cross-section, t=100yr — cold wedge descending from injection well](screenshots/29_cross_section.png)

### 10.4  F3 — Thermal breakthrough curve

**Goal:** Production temperature vs. time for all production wells.

1. Click a node at a production well location on **Slice 2**.
2. Go to **View → Time Series → Temperature**.
3. Ctrl-click nodes at the remaining 4 production wells to add them to the chart.

**Expected shape:** Temperature starts at ~134 °C at t = 0 yr and decreases to ~124 °C at t = 100 yr.

![Screenshot: Time-series temperature chart for 5 production wells, 0–100 yr](screenshots/30_breakthrough_curve.png)

### 10.5  F4 — Thermal power evolution

**Goal:** P_th [MW_th] vs. time.

FEFLOW does not compute thermal power directly.  Calculate it from the production temperature time series:

```
P_th [MW] = ρ_w · c_w · Q_total [m³/s] · (T_prod_avg − T_inj) / 10⁶
```

Where (from tutorial 🔵):
- ρ_w · c_w = 1.16 kWh/(m³·K) = **4.176 × 10⁶ J/(m³·K)**
- Q_total = 5 wells × 30 L/s = **0.150 m³/s** 🟢
- T_inj = **50 °C** 🟢

**Procedure:**
1. Export the production temperature time series: right-click chart → **Export to CSV**.
2. Open in Excel.
3. Compute for each time step: `P_th = 4.176e6 × 0.150 × (T_prod_avg − 50) / 1e6`
4. Plot P_th vs. time [yr].

### 10.6  F5 — Hydraulic head map

**Goal:** Plan-view hydraulic head at Slice 2 at t = 100 yr.

1. Data panel → **Hydraulic head** under Results.
2. Navigate to **Slice 2**, time step **t = 36 500 d**.
3. Display as a filled contour map.

The map shows the pumping cone (low head around production wells) and the injection mound (high head around injection wells).

### 10.7  F6 — Hydraulic head evolution at wells

**Goal:** h(t) at a representative production and injection well.

1. Click a production well node on Slice 2 → **View → Time Series → Hydraulic head**.
2. Ctrl-click an injection well node to add to the chart.

**Expected pattern:** Production head drops immediately below 200 m; injection head rises above 200 m; both stabilise within the first few years.

### 10.8  F7 — Time-step evolution

**Goal:** Time-step size [d] vs. simulation time [d], log scale.

During or after the run, check the simulation log or the Diagnostics panel for the time-step history.

**Expected pattern 🔵:**
- Starts at ~10⁻¹⁰ d.
- Grows exponentially over the first few hundred simulated days.
- Reaches the **100 d maximum** and holds there for most of the simulation.

---

## 11  Expected results

### 11.1  Thermal results

| Quantity | t = 0 yr | t = 100 yr | Tolerance |
|----------|---------|----------|-----------|
| Average production temperature | ~134 °C | ~124 °C | ± 5 °C |
| Total thermal power | **~52.8 MW_th** | **~46.8 MW_th** | ± 2 MW_th |
| Thermal degradation | — | ~11 % | ± 3 % |

🟢 Workbook + 🔵 Tutorial formula

> Small differences from these values are acceptable and expected due to mesh density, time-step length, and numerical integration choices.  Differences larger than the stated tolerances suggest a configuration error — consult Section 12.

### 11.2  Hydraulic results

| Quantity | Expected behaviour | Source |
|----------|--------------------|--------|
| Head at production wells | Drops and stabilises below 200 m | 🔵 Tutorial §6 |
| Head at injection wells | Rises and stabilises above 200 m | 🔵 Tutorial §6 |
| Lateral boundaries | Remain at 200 m (fixed BC) | 🔵 Tutorial §5.2.2.1 |

### 11.3  Mesh and computation summary

| Quantity | Value | Source |
|----------|-------|--------|
| Nodes per slice | ~4 706 | 🔵 Tutorial (PTS=5m, PG=4) |
| Total nodes (6 slices) | ~28 236 | derived |
| Accepted simulation steps | ~400–500 | ⚪ FEFLOW adaptive |
| Wall-clock time | 5–15 min | ⚪ hardware-dependent |

---

## 12  Troubleshooting

### 12.1  Wrong slice elevations

**Symptom:** The 3D view shows layers at incorrect depths.  Initial temperature assignment looks wrong.

**Fix:**
1. Press **Ctrl+L** to reopen the Layer Configurator.
2. Re-enter all six elevations exactly from §3.4: **600, −270, −370, −470, −520, −2 500 m a.s.l.** 🟢
3. Remember: these are elevations above sea level — negative values mean below sea level.  Do **not** enter depths.
4. Click OK and regenerate.

### 12.2  Wells not assigned or in wrong location

**Symptom:** Multilayer Well icons do not appear, or they appear at unexpected coordinates.

**Fix:**
1. Verify the Maps panel loaded `welldata` from `geoth_tutorial_data_Group3.xlsx`. 🟢
2. Re-do the **Link to Parameter(s)** step (§7.2), confirming all five column associations are correct.
3. In the assignment step (§7.3), confirm you selected **edges** (not nodes or elements) and extended to **all layers**.
4. Check that the X, Y columns in the workbook are in uppercase (the tutorial explicitly notes this). 🔵

### 12.3  Wrong well flow rates or direction

**Symptom:** Injection wells pump water out, or production wells inject water.

**Fix:**
1. In the `welldata` sheet, confirm: production wells have **positive** rates (+30 L/s), injection wells have **negative** rates (−30 L/s). 🟢
2. In the Link to Parameter(s) dialog, confirm the rate unit was changed from m³/d to **L/s**. 🔵
3. If rates look correct but simulation runs backward, consult the FEFLOW documentation for the sign convention of MLW flow rates in your licence version.

### 12.4  Incorrect problem class

**Symptom:** No temperature field in results; run completes instantly.

**Fix:**
1. Press **Alt+Enter** → Problem class. 🔵
2. Confirm: problem type = **"Heat"** (coupled TH), time regime = **"Transient"** for **both flow and heat transport**. 🔵
3. Re-run.

### 12.5  Missing temperature-dependent fluid properties

**Symptom:** Temperatures evolve but the thermal plume shape looks wrong; density appears constant.

**Fix:**
1. Press **Alt+Enter** → Transport settings. 🔵
2. Confirm: Fluid viscosity = **Variable, temperature-dependent**; Fluid density = **Linear, temperature-dependent**; T_ref = **10 °C**; ρ_ref = **999.793 kg/m³**. 🔵
3. Re-run.

### 12.6  Missing custom output times

**Symptom:** The `.dac` results file has only 1 snapshot; post-processing shows no time evolution.

**Fix:**
1. Click the **Record icon** again before re-running. 🔵
2. Confirm 20 custom times are listed (1 825, 3 650, …, 36 500 d). 🔵
3. Paste them from Excel if needed. 🔵
4. Press **OK** twice, save, and re-run.

### 12.7  Incorrect heat-flux sign

**Symptom:** The bottom of the model becomes colder over time instead of warmer.

**Fix:**
1. Navigate to Slice 6 → Data panel → BC → Heat transport → Heat-flux BC. 🔵
2. Confirm the value is **negative**: **−20 822.4 J/(m²·d)** for Group 3. 🟢
3. In FEFLOW, a negative Neumann heat BC means heat **enters** the domain (correct for geothermal heat from below). 🔵

### 12.8  Injection temperature not applied

**Symptom:** Production temperature starts at ~134 °C but stays constant — no thermal breakthrough — or injection temperature in the model is 134 °C instead of 50 °C.

**Fix:**
1. Browse slices with PgDn until you see Multilayer Well icons in the reservoir slices. 🔵
2. Confirm that the **View Components → Multilayer Well → Lock Data View** step was done. 🔵
3. Re-apply the T = **50 °C** temperature BC to all injection well **nodes** on all reservoir slices. 🟢
4. Confirm you applied it to **injection wells only** (positive-rate wells do not receive a T BC). 🔵

### 12.9  Simulation diverges or stops before t = 36 500 d

**Symptom:** FEFLOW stops early with a convergence error.

| Possible cause | Fix |
|---------------|-----|
| Initial time step too large | Re-set to **1 × 10⁻¹⁰ d** in Simulation-Time control 🔵 |
| Maximum time step too large | Reduce from 100 d to 50 d ⚪ |
| Injection temperature BC missing | Apply T = 50 °C to injection nodes (§7.4) 🟢 |
| Mesh too coarse near wells | Reduce PTS from 5 m to 2.5 m and regenerate mesh 🔵 |

---

## Appendix A — Complete parameter reference (Group 3)

All values used in this guide, with sources confirmed from the tutorial PDF and workbook:

| Parameter | Group 3 value | Tutorial generic | Source |
|-----------|--------------|-----------------|--------|
| Domain size | 8 000 × 8 000 m | 8 000 × 8 000 m | 🔵 |
| Surface elevation | 600 m a.s.l. | 500 m a.s.l. | 🟢 |
| Slice 2 elevation | −270 m a.s.l. | −300 m a.s.l. | 🟢 |
| Slice 3 elevation | −370 m a.s.l. | −400 m a.s.l. | 🟢 |
| Slice 4 elevation | −470 m a.s.l. | −500 m a.s.l. | 🟢 |
| Slice 5 elevation | −520 m a.s.l. | −600 m a.s.l. | 🟢 |
| Slice 6 elevation | −2 500 m a.s.l. | −1 600 m a.s.l. | 🟢 |
| T at Slice 1 | 15.00 °C | 15.00 °C | 🔵 |
| T at Slice 2 | 134.13 °C | 135.00 °C | 🟢 |
| T at Slice 3 | 144.61 °C | 141.67 °C | 🟢 |
| T at Slice 4 | 155.09 °C | 148.33 °C | 🟢 |
| T at Slice 5 | 160.33 °C | 155.00 °C | 🟢 |
| T at Slice 6 | 258.31 °C | 205.00 °C | 🟢 |
| Geothermal heat flux | 0.241 W/m² | 0.200 W/m² | 🟢 |
| Heat flux BC in FEFLOW | −20 822.4 J/(m²·d) | −17 280 J/(m²·d) | 🟢 |
| Initial head | 200 m | 200 m | 🔵 |
| T_inj | 50 °C | 50 °C | 🟢 |
| Production rate/well | +30 L/s | +30 L/s | 🟢 |
| Injection rate/well | −30 L/s | −30 L/s | 🟢 |
| Well radius | 0.15 m | 0.15 m | 🔵 |
| t_final | 36 500 d | 36 500 d | 🔵 |
| dt_initial | 1 × 10⁻¹⁰ d | 1 × 10⁻¹⁰ d | 🔵 |
| dt_max | 100 d | 100 d | 🔵 |
| PC scheme | FE/BE (1st order accurate) | FE/BE | 🔵 |
| Caprock K | 9.371 × 10⁻⁴ m/d | 7.57 × 10⁻⁴ m/d | 🟢 |
| Reservoir K | 6.886 × 10⁻² m/d | 9.08 × 10⁻² m/d | 🟢 |
| Basement K | 5.448 × 10⁻⁴ m/d | 7.57 × 10⁻⁵ m/d | 🟢 |
| Caprock φ | 0.27 | 0.20 | 🟢 |
| Reservoir φ | 0.025 | 0.02 | 🟢 |
| Basement φ | 0.01 | 0.01 | 🔵 |
| Caprock λ_s | 1.76 W/(m·K) | 1.333 W/(m·K) | 🟢 |
| Reservoir λ_s | 2.30 W/(m·K) | 3.00 W/(m·K) | 🟢 |
| Basement λ_s | 4.87 W/(m·K) | 4.00 W/(m·K) | 🟢 |
| Caprock C_v | 2.228 × 10⁶ J/(m³·K) | 2.1 × 10⁶ J/(m³·K) | 🟢 |
| Reservoir C_v | 2.247 × 10⁶ J/(m³·K) | 2.2 × 10⁶ J/(m³·K) | 🟢 |
| Basement C_v | 2.611 × 10⁶ J/(m³·K) | 2.6 × 10⁶ J/(m³·K) | 🟢 |
| T_ref | 10.0 °C | 10.0 °C | 🔵 |
| ρ_ref | 999.793 kg/m³ | 999.793 kg/m³ | 🔵 |
| μ_ref | 97.1136 kg/(m·d) | 97.1136 kg/(m·d) | 🔵 |

---

## Appendix B — Keyboard shortcuts summary

All shortcuts are from the FEFLOW tutorial 🔵:

| Shortcut | Action |
|----------|--------|
| **F2** | Enter precise coordinates in supermesh |
| **F12** | Save As |
| **Alt+Enter** | Open Problem Settings / Problem Summary |
| **Ctrl+L** | Open Layer Configurator |
| **Ctrl+A** | Select all nodes/elements on current slice |
| **Ctrl+3** | Switch to 3D view |
| **PgDn** | Move to the slice/layer below |
| **PgUp** | Move to the slice/layer above |
| **Red X button** | Deselect all currently selected items |

---

## Appendix C — Screenshot checklist

Before submitting your report, confirm screenshots exist for:

- [ ] New model wizard — "2D or layered 3D mesh" and "Manual domain setup" selected
- [ ] Domain polygon — grey square 8 000 × 8 000 m with corners at 0,0 and 8000,8000
- [ ] Maps panel — 70 well point crosses after loading wellnodecoordinates
- [ ] Supermesh — brown circles (supermesh points) converted from map
- [ ] Meshing panel — Triangle, PTS=5m, PG=4
- [ ] Generated mesh — plan view showing refinement near well cluster
- [ ] Problem summary (Alt+Enter) — node and element counts
- [ ] Layer Configurator — six slice elevations (Group 3 values)
- [ ] 3D perspective view — five geological layers visible
- [ ] Problem class — Heat transport, Transient
- [ ] Simulation-Time control — dt_ini=1e-10d, FE/BE, t_final=36500d, dt_max=100d
- [ ] Fluid density tab — Linear dependency on temperature
- [ ] Reference values — T=10°C, ρ=999.793 kg/m³
- [ ] Material properties — Kxx for caprock (9.371e-4) and reservoir (6.886e-2)
- [ ] Hydraulic head IC — all nodes selected, value 200 m
- [ ] Temperature IC — Slice 2 uniformly coloured at 134 °C
- [ ] Temperature border BC — Slice 2 border nodes selected
- [ ] Heat-flux BC — Slice 6 selected, value −20 822.4 J/(m²·d)
- [ ] Parameter association — welldata linked to MLW parameters
- [ ] Multilayer Well — 10 wells assigned to edges
- [ ] Injection temperature BC — 50 °C applied to injection well nodes
- [ ] Custom output times — 20 entries at 1 825 d intervals
- [ ] Simulation running — time and time-step visible in control panel
- [ ] Temperature map (Slice 2) — at least t=0 and t=100yr with locked colour scale
- [ ] Thermal breakthrough curve — production temperature vs time for all 5 wells
- [ ] Hydraulic head map — Slice 2 at t=100yr showing pumping cone

---

*Guide prepared for Group 3 — Geothermal Energy Systems, Politecnico di Torino.*  
*Software: FEFLOW 8.1 by DHI.*  
*Tutorial reference: FEFLOW Geothermal Energy Tutorial, Alessandro Casasso, rev00 (03/06/2024), pp. 1–32.*
