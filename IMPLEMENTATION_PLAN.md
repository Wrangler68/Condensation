# Marimo implementation plan: condensation on biphilic surfaces

Prepared 2026-09-21 from the three attached PDFs and public repository/reference searches. This document records the original plan. The subsequent implementation is described in README.md; docs/validation.md distinguishes completed numerical checks from remaining scientific reproduction issues.

## Scope and recommended order

Build a reusable scientific Python package with a marimo interface, NumPy/Autograd numerical kernels, SciPy reference solvers, and Plotly figures. Reproduce each paper independently before offering comparisons or new combinations. Implement the common dropwise baseline, Xie, Croce, then Lee, followed by sensitivities and constrained optimization. Lee is a separate humid-air and empirical drainage branch; its measurements cannot directly validate pure-steam heat-flux predictions.

| Paper | Implement | Primary reproduction targets |
|---|---|---|
| Xie et al. (2020), DOI 10.1016/j.ijheatmasstransfer.2019.119273 | Position-dependent suction/sliding departure, Kim-Kim drop populations, uniform film with transferred condensate | Figs. 4-5, then Figs. 7 and 13-15 |
| Croce & Suzzi (2024), DOI 10.3390/en17112742 | Coating-dependent nucleation, revised small-drop population, rivulet drainage and flooding constraint | Figs. 2-8, then Figs. 9-10 |
| Lee et al. (2020), DOI 10.1016/j.ijheatmasstransfer.2020.120206 | Humid-air interface energy balance, film contribution, fitted four-hour DWC recovery versus interface length | Figs. 6 and 11-12; geometry checks against Figs. 9-10 |

The initial deliverable reproduces published reduced models. Rebuilding Croce's underlying individual-droplet Lagrangian simulator is a later, optional project, not necessary to evaluate the 2024 statistical model.

## 1. Equation and data audit

Create an equation ledger containing paper, page, equation number, original expression, implemented expression, SI units, assumptions, and any justified correction. Preserve a distinction between published formulas and proposed physical extensions.

Specific issues discovered during this review:

- **Croce p. 5, Eq. (8):** the PDF prints an integral without an exponential. At r = r_e, the printed form gives zero rather than n_e. Integrating Eq. (7) implies `n(r) = n_e G_e/G(r) * exp(integral_r^re 1/(G*tau) dr)`. Record this as a derived correction and verify against Eq. (11).
- **Croce p. 5, Eq. (13):** the second term in B appears to omit alpha_i. Deriving B from Eq. (9) gives `2*k_l*sin(theta)/(alpha_i*theta*(1-cos(theta)))`. Check dimensions, the source references, and numerical curves before accepting the corrected expression. Also rederive Eq. (14)'s sweeping time from the stated logarithmic-slope matching condition; do not assume all printed expressions are mutually consistent.
- **Croce Eqs. (17)-(24):** Eq. (23) assumes a locally fixed rivulet angle and iterates it. Reproduce that stated procedure first. A fully differentiated variable-angle mass-flow equation would include the dependence of F_theta on thickness and is a separate extension, not an interchangeable implementation.
- **Lee Eq. (6):** Fig. 11 labels recovery in grams and interface length in meters. Its coefficient 0.695 describes the experimental four-hour collected mass, despite dotted-m notation. Store the observable as `mass_collected_4h`, then convert explicitly to an average rate if required. Do not treat 0.695 as an SI mass rate or assume the fitted law predicts transient accumulation.
- **Lee temperature conventions:** audit the Celsius convention of the moisture polynomial independently of the Kelvin nomenclature; distinguish humidity ratio from moist-air mass fraction. Distinguish the 5 C cooling-water inlet temperature from the actual wall temperature. Any approximation equating them must be visible.
- **Xie geometry:** audit Eq. (14)'s spatial limits against r_max = x/sin(theta), particularly near the stripe edge and where r_max < r_c. Preserve the paper's spatial discretization as a reference before adding alternative quadrature.
- Keep cap radius, footprint radius, and Lee's departure diameter separate. Static, advancing, receding, and rivulet angles have distinct roles.

Extract paper constants into explicit presets. Digitize selected curves only where raw data are unavailable, recording figure/panel, axis transforms, units, digitization uncertainty, and whether points are experiments or model curves. Do not claim digitized points are original raw measurements.

## 2. Shared numerical foundation

Use SI internally and explicit display conversions for mm, micrometers, degrees, kW/m2, and grams. Define immutable inputs for material properties, operating conditions, geometry, and numerical settings; return structured results with flux components, radii, film state, residuals, active departure mode, and validity status.

Implement spherical-cap geometry, critical radius, interface coefficient, single-drop heat rate, large-drop distribution, and baseline small-drop distribution. Share a kernel only after proving algebraic equivalence between the paper conventions; similar-looking resistance expressions may have different prefactors.

Use the paper's fixed property tables for reproducibility, including Xie's Table 2. Optionally add CoolProp for general conditions and humid-air properties. Keep CoolProp outside the differentiated computation. Temperature-dependent gradients require an explicitly differentiable property representation or a declared fixed-property sensitivity.

Use two numerical paths:

1. **Reference:** SciPy adaptive quadrature, bracketed roots, and bounded scalar optimization.
2. **Differentiable:** `autograd.numpy` kernels with precomputed Gauss-Legendre nodes and weights. Map fixed nodes into parameter-dependent log-radius intervals so derivatives include changing bounds. Split integration at population and departure-mode boundaries. Use log-domain distributions when necessary to avoid overflow.

Do not assume Autograd differentiates arbitrary `scipy.integrate`, `scipy.optimize`, or CoolProp calls. Differentiate implicit roots through their residual, `dy/dp = -(dF/dy)^(-1) dF/dp`, with a checked custom derivative, or keep that calculation outside the differentiable scope. For the nucleation optimum, differentiate its stationarity condition only after checking an interior, nondegenerate maximum.

Treat zero coating resistance, zero stripe width, no condensation, vanishing cross-flow, and radius-order violations explicitly. Do not hide invalid states with arbitrary clipping. At zero subcooling use the physical no-condensation branch rather than evaluating singular nucleation formulas.

## 3. Xie model

- Implement Eqs. (3)-(7) as selectable DSS, OSS, and OSS-plus-sliding departure models. The full model uses `min(x/sin(theta), r_slide)` on the symmetric half-stripe.
- Integrate the single-drop heat rate against the two populations, Eqs. (8)-(13), then spatially average using Eq. (14). Start with the reported 1 micrometer spatial resolution and demonstrate refinement convergence.
- Preserve the paper's fixed nucleation density, 2.5e11 m^-2, in reproduction mode.
- Track heat generated over the complete DWC stripe separately from heat associated with liquid transferred into FWC channels. Only the suction region contributes transferred liquid when central droplets slide away.
- Solve the coupled film-thickness/HTC relations, Eqs. (23)-(24), with a positive bracketed scalar root, then form the area-weighted overall HTC.
- Reproduce removal-mode effects in Fig. 4 and validation in Fig. 5. Extend to the coating/width maps and enhancement/deterioration boundary in Fig. 15. Treat its Eq. (25) fit as condition-specific.

## 4. Croce model

- Implement Eqs. (3)-(16), resolving the audit issues first. Find the coating-dependent nucleation radius from the availability maximum; derive nucleation density and coalescence radius from it.
- Reproduce the revised radius-dependent sweeping time, while retaining the Kim-Kim baseline as a comparison.
- Implement the rivulet cross-section and flow relations, Eqs. (17)-(24), using stable small-angle expressions and a dedicated zero-cross-flow limit.
- Couple DWC to lateral mass transfer with Eq. (26). Compute FWC heat from newly condensed liquid only, Eq. (27), so transferred condensate is not counted twice.
- Use the paper's stripe-height weighting on its circular specimen, Eq. (29), with explicit treatment of stripe count and edge geometry. Offer exact clipped-stripe geometry only as a labeled extension.
- Apply the flooding limit, Eq. (25), at the longest stripe. Reproduce the paper's search along the minimum feasible FWC width; subsequently allow a configurable drainage margin for design studies.
- Use the reported coating resistance 3.39e-7 m2 K/W for the initial Fig. 7-8 reproduction. If refitting it, fit the fully hydrophobic data only and reserve hybrid cases for validation.
- Reproduce Fig. 10's flux and critical-width curves. The flooding boundary is a model prediction; the paper says it was not directly validated experimentally.

## 5. Lee model

- Represent the finite patterned specimen, hydrophilic area fraction SAR, and total hydrophilic/hydrophobic interface length. Count actual internal boundaries rather than counting both sides twice or including specimen edges.
- Implement Eqs. (3.1)-(3.4a) and solve the gas-liquid interface energy balance for interface temperature. Keep sensible heat, latent heat, and film conduction separate.
- Implement hydrophilic recovery and the empirical hydrophobic contribution, Eqs. (5)-(7), with explicit four-hour mass units. The fit is `0.695*(1-exp(-4.2488*L_interface))**6.744` grams for the published conditions.
- Reproduction presets: 14-15 C inlet air, 100% RH, air speed 0.6 m/s, cooling-water inlet 5 C, and static contact angles about 4 and 142 degrees. Recover wall-temperature and specimen details from the paper before fixing inputs.
- Compare the film-model baseline (reported 0.355 g/h) and measured baseline (0.400 g/h) explicitly; do not silently substitute one for the other to improve agreement.
- Check about 1.84 g observed recovery for W_FWC = 3.4 mm and W_DWC = 0.6 mm, and about 2 g predicted at W_FWC = 2.8 mm and W_DWC = 0.5 mm, approximately SAR = 85%.
- Restrict the empirical optimization to the paper's fabrication/geometry envelope. General humidity, speed, size, and transient predictions need a new transport/drainage model or new data and must not be presented as validated Lee predictions.

## 6. Marimo and Plotly interface

Create three reproduction notebooks and one comparison/optimization notebook backed by the same package. Each notebook includes paper context, equation references, a published preset, controls with units, model validity, reproduction overlays, and downloadable results.

Views: geometry schematic; single-droplet resistance and heat-rate curves; log-log size distribution; removal radius and mode versus stripe position; film thickness and drainage margin; heat-flux/HTC curves; Lee four-hour recovery; width/coating contour maps; experimental residuals; normalized parameter sensitivities.

Use marimo reactive inputs for cheap calculations and submitted forms/run buttons for costly sweeps. Use `mo.ui.plotly` when selected points should drive a detailed calculation. Cache immutable property/quadrature data. Record inputs, versions, model convention, solver settings, and source data with exported results. Use deterministic seeds where sampling is added.

Optimize positive widths in log coordinates. First verify optima with a coarse grid and SciPy derivative-free/global search; use Autograd-assisted constrained local refinement only in smooth, validated regions. Piecewise departure modes, flooding events, and changes in finite stripe count require branch-aware treatment; gradients at those boundaries are not ordinary smooth sensitivities. Re-evaluate every proposed optimum using the reference solver.

## 7. Proposed layout and commands

```text
pyproject.toml
uv.lock
src/condensation/
  types.py, properties.py, geometry.py
  droplets.py, populations.py, quadrature.py
  xie2020.py, croce2024.py, lee2020.py
  differentiation.py, optimization.py
notebooks/
  01_xie2020.py
  02_croce2024.py
  03_lee2020.py
  04_compare_optimize.py
data/presets/
data/digitized/
docs/equation_ledger.md
docs/references.md
tests/
```

Core dependencies: marimo, numpy, scipy, plotly, autograd. Development: pytest. Optional: CoolProp and figure-digitization tooling. Start with Python 3.12 and resolve/test compatible package versions rather than assuming compatibility. Keep the environment reproducible with uv.

After project creation: install with `uv pip install -e ".[dev]"`; run with `uv run marimo edit notebooks/01_xie2020.py`, `uv run marimo run notebooks/04_compare_optimize.py`, and `uv run pytest`. Check notebook syntax/reactivity with the installed marimo CLI before delivery.

## 8. Acceptance criteria and milestones

1. **Audited inputs:** equation ledger, reference list, presets, digitized benchmark data with provenance, and resolved or explicitly bounded formula ambiguities.
2. **Baseline:** correct units, positive heat/rates, population matching at transition radius, separate pure-FWC/pure-DWC endpoints, and comparison with DWCmod under matched assumptions.
3. **Xie:** departure modes and transferred-liquid accounting verified; target figures reproduced with documented residuals and spatial/radius convergence.
4. **Croce:** nucleation and population checks pass; drainage/latent-energy conservation passes; target figures and constrained optima reproduced with disclosed formula conventions.
5. **Lee:** correct mass/time accounting, recovered baseline discrepancy, fit and finite geometry reproduced, extrapolation visibly restricted.
6. **Differentiation and UI:** finite-difference directional checks away from nonsmooth boundaries; reference-versus-fixed-quadrature agreement; all notebooks execute from a clean environment and exported parameters reproduce results.

Suggested engineering tolerances, to finalize after the audit: under 0.5% change in integrated observables upon numerical refinement; around 1e-3 relative gradient agreement on well-scaled nonzero derivatives, plus absolute tolerances near zero. Experimental agreement must reflect digitization and measurement uncertainty, not an arbitrary universal 1% target. Croce reports up to 19.3% discrepancy for its widest-stripe case; Lee reports predictions within 8%. Neither is a numerical convergence tolerance. Agreement with calibration data is not independent validation.

## Public implementation search and useful references

Searches covered paper titles, author names, DOIs/article identifiers, and combinations of dropwise condensation, biphilic, Python, MATLAB, and GitHub. No verified public implementation of the exact three attached papers was located in these searches. This does not establish that no repository exists. Xie describes a MATLAB implementation; Croce describes an in-house code.

| Resource | Practical use and limits |
|---|---|
| [JSablowski/DWCmod](https://github.com/JSablowski/DWCmod) | Best direct starting reference. MIT-licensed Python Kim-Kim 2011 implementation, with single-drop heat transfer, populations, integrated heat flux and CoolProp. Inspect `DWC_models.py`; refactor its math/SciPy/property calls for Autograd rather than expecting automatic compatibility. It does not implement the three hybrid models. |
| [CalebBell/ht](https://github.com/CalebBell/ht), [condensation documentation](https://ht.readthedocs.io/en/latest/ht.condensation.html) | Independent Nusselt-film correlation checks. General correlation library, not a biphilic solver. |
| [CoolProp](https://github.com/CoolProp/CoolProp), [humid-air documentation](https://coolprop.org/fluid_properties/HumidAir.html) | Optional properties and psychrometric cross-checks. Keep paper constants for reproduction and property calls outside Autograd. |
| [MahdiNabil/CFD-PC](https://github.com/MahdiNabil/CFD-PC) | OpenFOAM phase-change examples and Stefan/Nusselt validation references. A separate CFD approach, not code to port into the initial marimo solver; README targets old OpenFOAM 2.4.0. |
| [HIPS/autograd](https://github.com/HIPS/autograd) | NumPy differentiation and custom derivative examples. |
| [marimo plotting documentation](https://docs.marimo.io/guides/working_with_data/plotting/) | Reactive Plotly integration and linked selections. |

Read the following in implementation order:

1. [Kim & Kim (2011), Dropwise Condensation Modeling Suitable for Superhydrophobic Surfaces](https://doi.org/10.1115/1.4003742): baseline population balance and droplet resistance model, also implemented by DWCmod.
2. [Peng et al. (2014), Droplet sizes effect](https://doi.org/10.1016/j.ijheatmasstransfer.2014.05.052): original coupled DWC/FWC model underlying later comparisons.
3. Peng et al. (2015), *Experimental investigation on steam condensation heat transfer enhancement with vertically patterned hydrophobic-hydrophilic hybrid surfaces*, IJHMT 83, 27-38: shared experimental benchmark cited by both Xie and Croce. Obtain the original data/figures to avoid treating their common benchmark as independent datasets.
4. [Liu & Cheng Part I (2015)](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.009) and [Part II (2015)](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.008): coating-dependent nucleation radius, density and heat flux needed by Croce.
5. [Croce & Suzzi (2023), institutional repository](https://air.uniud.it/handle/11390/1269787): Lagrangian model and distribution evidence supporting the reduced model.
6. [Suzzi & Croce (2024), Effect of hydrophobic coating](https://doi.org/10.1088/1742-6596/2766/1/012143): companion paper to cross-check the revised small-drop distribution and coating effects.

Before reusing source code, verify the relevant repository license and pin a reviewed revision. None of the external repositories has been executed or certified as a correct implementation during this planning pass.
