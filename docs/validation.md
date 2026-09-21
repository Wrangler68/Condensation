# Validation report

Run date: 2026-09-21. The implementation is numerically verified but **not a complete reproduction of all published results**. In particular, Croce Fig.7a remains inconsistent with the implemented equations. No fitting parameter was changed to conceal this discrepancy.

## Numerical evidence

- 17 tests pass: population value/slope matching, availability maximum, radial quadrature convergence, spatial refinement, limiting cases, implicit derivatives, film mass/energy accounting, flooding rejection, Lee mass units/finite geometry, optimizer feasibility, and strict JSON serialization.
- Four first-order Autograd derivatives of the smooth plate heat flux agree with centered finite differences to a maximum relative difference of approximately **8.1e-9** at the recorded test point. This is a local check, not a proof over every parameter or branch.
- The independent Kim–Kim baseline matches DWCmod revision `b18786ffc7d824e42407137c56c7c609d5d4cd75` to about **3.0e-8 relative error** at 2, 6 and 10 K subcooling with matched CoolProp properties, radii and coating. This checks the common baseline, not the exact Xie/Croce models.
- All four marimo notebooks passed static checks and executed through HTML export. Live browser checks exercised an input change in Xie and the design explorer's optimization action.
- Both constrained searches are checked for feasibility; the smooth plate optimizer reports successful convergence. The disk optimizer uses a sampled search and local refinement across a discrete stripe-count geometry and is not guaranteed globally optimal.

## Approximate published model-curve checks

Values below are manual readings of **model lines**, not raw experimental measurements. The source is `data/digitized/figure_checks.json`, with 15-20 kW/m2 reading uncertainty. Disk radius is assumed 10 mm. Error is `(computed/paper)-1`.

| Curve | 2 K | 4 K | 6 K |
|---|---:|---:|---:|
| Xie Fig.5a, Kim–Kim resistance convention | +1.2% | -0.9% | -2.6% |
| Croce Fig.8b, corrected equations | -1.3% | +4.3% | +7.9% |
| Croce Fig.7a, fixed rmax=1.25 mm | **+27.2%** | **+35.7%** | **+38.6%** |

Croce Fig.7a's disagreement is larger than the reading uncertainty and remains unresolved. Published coating resistance and stated fixed departure radius are retained. The exact author implementation, property choices, population convention, or an additional erratum may be needed to resolve it. Do not interpret Fig.8b's closer agreement as proof that the full model is validated.

Lee's finite 40 mm specimen at DWC/FWC widths .6/3.4 mm predicts **1.889 g in four hours**, compared with the reported 1.84 g (about +2.7%). This uses the **measured .400 g/h FWC baseline**; choosing the .355 g/h theoretical baseline changes the result. Its empirical DWC law was already fitted to those experiments, so this is a reconstruction check rather than held-out validation.

## Reproducible exploratory optima

At 100 C saturation, 6 K subcooling, coating resistance 3.39e-7 m2K/W:

- Croce disk search (R=10 mm, 2% width margin): DWC about **0.437 mm**, FWC about **0.293 mm**, model flux about **827 kW/m2**.
- Smooth rectangular plate extension (H=20 mm, H_flood/H>=1.02): DWC about **0.427 mm**, FWC about **0.288 mm**, model flux about **831 kW/m2**. This uses first-order Autograd derivatives and is checked against adaptive radial quadrature.
- Lee's finite-stripe grid prefers its smallest allowed DWC width near **0.5 mm**, at the high-SAR end; output is near **2 g/4h** with the measured film baseline.

These values are outputs of the implemented conventions and search bounds. They are not new experimentally supported design recommendations. Croce's flooding criterion itself was not experimentally validated in the paper.

## Remaining scientific validation work

1. Resolve Croce Fig.7a with author equations/code or independently verified source derivations.
2. Confirm the original Peng specimen radius and exact stripe-edge layout.
3. Obtain/digitize full experimental datasets with uncertainty, separating calibration from validation.
4. Confirm Lee's wall temperature and exact film-property evaluation convention; reconstruct the complete printing-feasibility envelope before claiming its optimum is exactly reproduced.
5. Extend quantitative validation beyond the sampled figures, including independent data and broad parameter ranges. The supplied figure-study script supports this work but does not replace it.

Machine-readable evidence is in `docs/validation_results.json`; rerun `scripts/validate.py` and `scripts/check_dwcmod.py` for current values. Package versions are pinned by `uv.lock`.
