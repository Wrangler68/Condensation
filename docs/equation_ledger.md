# Equation ledger and conventions

All radii and widths are meters; heat rate Q is W, heat flux q is W/m2, HTC is W/m2/K. All trigonometric inputs use radians. Thermodynamic temperature is Kelvin; Lee's saturation polynomial uses Celsius. Geometry inputs distinguish spherical-cap curvature radius from footprint radius r sin(theta).

## Xie 2020

| Equations | Implemented behavior | Audit decision |
|---|---|---|
| 1-2 | Area-weighted DWC/FWC heat flux and HTC | Region heat fluxes are reported before area weighting |
| 3-7 | DSS, OSS, and min(OSS, gravity sliding) | Suction region is separated from sliding region for liquid transfer |
| 8-10 | Two population integrals; r0 from curvature; rc=1/(2 sqrt(Nc)) | Nc=2.5e11 m^-2 in presets |
| 11 | Single-cap heat rate | Printed denominator has theta sin(theta)/(4 pi) times r/k. Restoring Kim–Kim removes the extra pi. Default is `kim`; `xie` retains the printed denominator and uses a consistent growth law for that denominator. This is a disclosed convention, not an author-confirmed erratum |
| 12-13 | Constant-sweeping small population; Le Fevre–Rose large population | Population balance solved analytically; matching value and logarithmic slope -8/3 are tested |
| 14-15 | Half-stripe spatial average and q/DT | Midpoint cells, split exactly at the suction/sliding boundary, with default dx<=1 micrometer. Paper uses right-grid locations; midpoint is a numerical improvement. Cap-radius limits follow Eq.6, resolving inconsistent x-vs-r notation in Eq.14 |
| 16-24 | Approximate disk area fractions, transferred-liquid accounting, positive film-thickness root | Only suction-produced condensate enters the channel. Interfacial resistance is retained in film HTC |

At rmax<rc the small distribution retains its prescribed matching radius rc and is truncated at rmax. This near-boundary extension is documented and checked by spatial refinement. For rmax<=r0 no local condensate heat is assigned. No claim is made that this microscopic edge treatment is independently validated.

Pure-FWC endpoint uses the standard mean Nusselt vertical-plate law; this is an explicit endpoint extension. Pure DWC uses the selected departure law. No condensation at DT=0 returns zero without evaluating singular critical-radius formulas.

## Croce 2024

| Equations | Implemented behavior | Audit decision |
|---|---|---|
| 1-6 | Stripe-imposed rmax, area weighting, single-drop resistances, integrated populations | Uses the published cap-radius definition and Le Fevre distribution |
| 7-8 | n = ne Ge/G exp(integral dr/(G tau)) | The printed Eq.8 omits exp; otherwise n(re)=0, contradicting n(re)=ne. Correction follows direct integration of Eq.7 |
| 9-14 | G=A(r-r0)/(r(r+B)); tau proportional to r | B includes `2*k_l*sin(theta)/(alpha_i*theta*(1-cos(theta)))`; alpha_i is absent in printed Eq.13. Derived from Eq.9 and dimensions. Eq.14 is consistent with slope matching once B is corrected |
| 15-16 | Availability maximum determines rn; rho_n=.037/rn^2; re=rn/(2 sqrt(.037)) | Dimensionless log-radius root of the availability derivative; negative curvature is tested. Angular factor `(1-cos(phi))^2/sin(phi)^4` is evaluated as `1/(1+cos(phi))^2` |
| 17-19 | Circular-section rivulet, parabolic velocity | F_theta calculated by cross-section quadrature, avoiding cancellation at small angle. Verified F(0)=16/35 and flooding flow at theta=pi/2 |
| 20-24 | Endpoint-angle, iterated analytical film closure | Evaluate the integral equivalent of Eq.23: `H = F*rho*(rho-rhov)*g/mu * integral_0^delta t^3/(a+b*t) dt`, with `a=k*DT*sinc(theta)/hfg`, `b=migration/LF`, theta from endpoint delta. This also handles migration=0 without subtractive cancellation |
| 25 | Flooding at delta=LF/2 | Require H<=H_flood. Report H/H_flood as flooding_ratio; it is a height ratio, not a mass-flow ratio. Beyond the limit return undefined flux rather than continue the pre-flood formula |
| 26-27 | Migration=qD LD/hfg; qF=(outflow-migration H)hfg/(H LF) | Transferred condensate is subtracted to avoid counting its latent heat twice |
| 28 | Pure-DWC gravity departure | Implemented as printed; Fig.7 comparison explicitly fixes rmax=1.25 mm as its caption specifies |
| 29 | Center-height weighted disk stripes | Integer stripe loop uses floor(2R/pitch), and only centers inside the disk are retained. Edge-area fractions remain the paper approximation |

The general variable-angle derivative of mass flow is **not** substituted for the paper's locally fixed-angle closure: it would define a different film model. The rectangular-plate function is separately named `smooth_plate_flux` and labeled as an extension in the UI.

**Unresolved:** Fig.7a disagreement (about +27 to +39% at sampled DT) is not removed by quadrature refinement. The shared Kim–Kim implementation independently matches DWCmod, but that does not validate the revised Croce distribution/nucleation combination. Original author code or clarification is needed before claiming complete reproduction. The model is left auditable rather than empirically rescaled.

## Lee 2020

| Equations | Implemented behavior | Audit decision |
|---|---|---|
| 1-2 | Departure diameter from gravity/capillary balance | Auxiliary function takes radians, returns diameter, and uses the specified average angle explicitly |
| 3.1-3.4a | Sensible + latent = film conduction, solved for interface temperature | Saturated air only. Average Nu=2 local Nu. Moisture polynomial Celsius input; interpreted as humidity ratio. No arbitrary RH extrapolation |
| 4-5 | Latent condensation mass, scaled by hydrophilic area | Baselines remain separate: measured .400 g/h, paper theory .355 g/h, or independently computed transport result |
| 6-7 | `.695*(1-exp(-4.2488*L))^6.744` grams plus FWC contribution | Figure 11 shows grams for four-hour recovery despite dotted-m notation. Convert output to kg, and divide by 14400 only when reporting average kg/s |

The independent energy balance assumes wall=5 C (coolant inlet is the measured 5 C quantity). Fixed properties: water k=.58 W/mK, mu=.001307 Pa s, rho=999.7 kg/m3, hfg=2.477e6 J/kg; air rho=1.23 kg/m3, k=.0253 W/mK, mu=1.79e-5 Pa s, cp=1006 J/kg/K, Pr=.71. These rounded engineering inputs are approximations and are not silently fitted to reproduce .355 g/h.

Finite geometry starts with DWC at the left edge, clips the final stripe, and counts each internal boundary once. An optional periodic approximation uses SAR=LF/(LD+LF) and interface length=2A/(LD+LF). Edge alignment is not uniquely specified by the paper. The design envelope is an implementation restriction (minimum .5 mm widths, SAR .50-.85), not a fully reconstructed printing-process feasibility map.

## Differentiation and numerical domain

Fixed Gauss-Legendre nodes are mapped to log-radius intervals. Q*n is simplified before evaluation to cancel the critical-radius 0*infinity product. SciPy adaptive integration provides the reference path. No Autograd derivative is taken through an opaque SciPy iteration.

For scalar roots, first derivatives use dz/dp=-(partial F/partial p)/(partial F/partial z). Brackets and branch choices remain nondifferentiable at switches. The current derivative contract is first order, fixed fluid properties, interior roots and non-flooded geometry. Values at a departure-mode switch, stripe-count change, or flooding boundary must not be interpreted as ordinary smooth design gradients.
