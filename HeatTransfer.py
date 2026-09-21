# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo==0.24.2", "numpy>=2,<3", "scipy>=1.14,<2", "plotly>=6,<7", "autograd>=1.7,<2"]
# ///
"""Standalone biphilic condensation laboratory. All equations and data are embedded.

Run: uv run --with marimo marimo edit --sandbox HeatTransfer.py
Validate: uv run HeatTransfer.py --self-test
Single HTML export and GitHub Pages deployment: .github/workflows/checks.yml
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="medium",
    app_title="HeatTransfer · Biphilic condensation",
)


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    def _row(items, minimum=180):
        # Use the available cell width, including when the outline is open.
        return mo.Html(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
            f'minmax(min(100%, {minimum}px), 1fr));gap:1rem;width:100%">'
            + "".join(
                mo.vstack([item]).style({"min-width": "0"}).text for item in items
            )
            + "</div>"
        )

    def _controls(fields):
        return mo.Html(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
            'minmax(min(100%, 280px), 1fr));gap:1rem;align-items:center">'
            + "".join('<div style="min-width:0">{' + field + "}</div>" for field in fields)
            + "</div>"
        )

    from types import SimpleNamespace

    ht_layout = SimpleNamespace(row=_row, controls=_controls)
    return (ht_layout,)


@app.cell
def _(mo):
    mo.md("""
    # HeatTransfer · Biphilic condensation laboratory
    **Xie 2020 · Croce 2024 · Lee 2020**

    One self-contained notebook: NumPy, SciPy, Plotly and Autograd.
    Use the outline to move between the three papers, design searches, numerical checks,
    extended figure studies, and the equation/reference sections. Submit each form to recalculate.

    **Scope:** numerically verified reduced models, not complete experimental reproductions.
    Croce Fig. 7a remains discrepant by 27–39%; the 10 mm disk radius is an unconfirmed assumption.
    Lee's humid-air mass objective is distinct from the steam heat-flux objectives.
    Browser execution can take a little longer, especially for searches and extended studies.
    """)
    return


@app.cell
def _(mo):
    mo.sidebar(mo.outline(label="Sections"))
    return


@app.cell
def _():
    def _build():
        """Public inputs are validated and immutable. Temperatures in K, angles in radians."""

        from dataclasses import asdict, dataclass
        from math import isfinite, pi

        @dataclass(frozen=True)
        class SteamConditions:
            temperature: float = 373.15
            subcooling: float = 6.0

            def __post_init__(self):
                if not (
                    273.15 < self.temperature < 647
                    and 0 <= self.subcooling < self.temperature - 273.15
                ):
                    raise ValueError(
                        "Require liquid-water steam temperature and nonnegative subcooling above freezing"
                    )

        @dataclass(frozen=True)
        class Surface:
            theta: float = 120 * pi / 180
            advancing: float = 142 * pi / 180
            receding: float = 102 * pi / 180
            coating_resistance: float = 3.39e-7
            nucleation_density: float = 2.5e11

            def __post_init__(self):
                if not (0 < self.receding <= self.theta <= self.advancing < pi):
                    raise ValueError("Require 0 < receding <= static <= advancing < pi")
                if not (
                    isfinite(self.coating_resistance)
                    and self.coating_resistance >= 0
                    and self.nucleation_density > 0
                ):
                    raise ValueError("Invalid coating resistance or nucleation density")

        @dataclass(frozen=True)
        class Geometry:
            dwc_width: float = 0.55e-3
            fwc_width: float = 0.45e-3
            radius: float = 0.01

            def __post_init__(self):
                if not all(isfinite(v) for v in asdict(self).values()):
                    raise ValueError("Geometry must be finite")
                if min(self.dwc_width, self.fwc_width) < 0 or self.radius <= 0:
                    raise ValueError("Widths must be nonnegative, radius positive")
                if self.dwc_width + self.fwc_width <= 0:
                    raise ValueError("At least one stripe width must be positive")

            @property
            def dwc_fraction(self):
                return self.dwc_width / (self.dwc_width + self.fwc_width)

        @dataclass(frozen=True)
        class SteamResult:
            model: str
            heat_flux: float
            dwc_flux: float
            fwc_flux: float
            htc: float
            film_thickness: float
            transferred_flux: float
            flooding_ratio: float = 0.0
            valid: bool = True
            notes: tuple[str, ...] = ()

            def to_dict(self):
                return asdict(self)

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_types = _build()
    return (ht_types,)


@app.cell
def _():
    def _build():
        """Fixed saturation properties; never call an external property backend inside Autograd."""

        from dataclasses import dataclass
        from functools import lru_cache

        @dataclass(frozen=True)
        class Water:
            temperature: float
            rho_l: float
            rho_v: float
            latent_heat: float
            conductivity: float
            viscosity: float
            tension: float
            source: str
            gas_constant: float = 461.52
            gravity: float = 9.81

        # Xie Table 2, converted from kJ/kg, mW/mK, mPa s, mN/m.
        _TABLE = {
            60: (983.16, 0.130, 2357620.0, 0.65435, 0.000466, 0.066238),
            90: (965.30, 0.424, 2282460.0, 0.67525, 0.000314, 0.060816),
            120: (943.11, 1.122, 2202090.0, 0.68319, 0.000232, 0.054968),
            150: (917.01, 2.548, 2113720.0, 0.68204, 0.000182, 0.048741),
            # Rounded standard saturation data, explicitly distinct from Xie's Table 2.
            100: (958.35, 0.59817, 2256400.0, 0.677, 0.0002816, 0.05891),
        }

        @lru_cache(maxsize=64)
        def water(temperature=373.15, backend="table"):
            """No silent interpolation/extrapolation of the paper property table."""
            if backend != "table":
                raise ValueError("This portable notebook uses the embedded table backend")
            tc = round(temperature - 273.15, 8)
            if tc not in _TABLE:
                raise ValueError(
                    "Table supports 60, 90, 100, 120, 150 C; other temperatures require a separately verified property source"
                )
            source = "rounded 100 C saturation reference" if tc == 100 else "Xie 2020 Table 2"
            return Water(temperature, *_TABLE[tc], source)

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_properties = _build()
    return (ht_properties,)


@app.cell
def _():
    def _build():
        """Fixed nodes are constants; mapping and weights retain parameter derivatives."""

        from functools import lru_cache

        import autograd.numpy as anp
        import numpy as np
        from scipy.integrate import quad

        @lru_cache(maxsize=16)
        def rule(order=96):
            x, w = np.polynomial.legendre.leggauss(order)
            x.setflags(write=False)
            w.setflags(write=False)
            return x, w

        def integrate(func, lower, upper, order=96):
            x, w = rule(order)
            half = (upper - lower) / 2
            return half * anp.sum(w * func(lower + (x + 1) * half), axis=-1)

        def log_integrate(func, lower, upper, order=96):
            return integrate(
                lambda z: func(anp.exp(z)) * anp.exp(z), anp.log(lower), anp.log(upper), order
            )

        def reference_log_integrate(func, lower, upper):
            if upper <= lower:
                return 0.0
            return quad(
                lambda z: float(func(np.exp(z))) * np.exp(z),
                np.log(lower),
                np.log(upper),
                epsabs=1e-6,
                epsrel=2e-8,
                limit=250,
            )[0]

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_quadrature = _build()
    return (ht_quadrature,)


@app.cell
def _():
    def _build():
        """Single-drop heat and growth; paper-specific liquid resistance is explicit."""

        import autograd.numpy as np

        def critical_radius(subcooling, p):
            return 2 * p.temperature * p.tension / (p.rho_l * p.latent_heat * subcooling)

        def interface_coefficient(p, accommodation=1.0):
            return (
                2
                * accommodation
                / (2 - accommodation)
                / np.sqrt(2 * np.pi * p.gas_constant * p.temperature)
                * p.rho_v
                * p.latent_heat**2
                / p.temperature
            )

        def resistance_terms(r, theta, coating, p, convention="kim"):
            """Denominator of Q/(pi*r^2), units m2 K/W. Xie Eq. 11 has an extra pi."""
            if convention not in ("kim", "xie"):
                raise ValueError("Unknown single-drop convention")
            liquid_factor = np.pi if convention == "xie" else 1.0
            return (
                coating / np.sin(theta) ** 2 + 0 * r,
                theta * r / (4 * p.conductivity * np.sin(theta) * liquid_factor),
                1 / (2 * interface_coefficient(p) * (1 - np.cos(theta))) + 0 * r,
            )

        def heat_rate(r, subcooling, theta, coating, p, convention="kim"):
            r0 = critical_radius(subcooling, p)
            rc, rl, ri = resistance_terms(r, theta, coating, p, convention)
            return subcooling * np.pi * r * (r - r0) / (rc + rl + ri)

        def growth_coefficients(subcooling, theta, coating, p, convention="kim"):
            """G=A*(r-r0)/(r*(r+B)) from spherical-cap energy conservation."""
            factor = np.pi if convention == "xie" else 1.0
            slope = theta / (4 * p.conductivity * np.sin(theta) * factor)
            offset = coating / np.sin(theta) ** 2 + 1 / (
                2 * interface_coefficient(p) * (1 - np.cos(theta))
            )
            cap = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
            return subcooling / (p.rho_l * p.latent_heat * cap * slope), offset / slope

        def sliding_radius(theta, advancing, receding, p, model="xie"):
            shape = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
            if model == "xie":
                return np.sqrt(
                    12
                    / np.pi**2
                    * np.sin(theta)
                    * (np.cos(receding) - np.cos(advancing))
                    * p.tension
                    / ((p.rho_l - p.rho_v) * p.gravity * shape)
                )
            if model == "croce":
                return (
                    12
                    / np.pi**2
                    * np.sqrt(
                        p.tension
                        * (np.cos(receding) - np.cos(advancing))
                        / (p.rho_l * p.gravity * shape)
                    )
                )
            raise ValueError("Unknown departure model")

        def nusselt_flux(subcooling, height, p):
            if subcooling == 0:
                return 0.0
            return (
                0.943
                * (
                    p.rho_l
                    * (p.rho_l - p.rho_v)
                    * p.gravity
                    * p.latent_heat
                    * p.conductivity**3
                    / (p.viscosity * height)
                )
                ** 0.25
                * subcooling**0.75
            )

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_droplets = _build()
    return (ht_droplets,)


@app.cell
def _(ht_droplets, ht_quadrature):
    def _build():
        """Population balance integrals, with analytic Q*n cancellation at the critical radius."""

        import autograd.numpy as np

        critical_radius = ht_droplets.critical_radius
        growth_coefficients = ht_droplets.growth_coefficients
        heat_rate = ht_droplets.heat_rate
        log_integrate = ht_quadrature.log_integrate
        reference_log_integrate = ht_quadrature.reference_log_integrate

        def large_distribution(r, rmax):
            return (rmax / r) ** (2 / 3) / (3 * np.pi * r * r * rmax)

        def sweeping_time(re, r0, a, b):
            return (
                3
                * re**2
                * (re + b) ** 2
                / (a * (11 * re**2 - 14 * re * r0 + 8 * b * re - 11 * b * r0))
            )

        def log_population_ratio(r, re, r0, a, b, linear):
            tau = sweeping_time(re, r0, a, b)
            logterm = np.log((re - r0) / (r - r0))
            if linear:
                return re / (tau * a) * ((re - r) + (r0 + b) * logterm)
            return ((re**2 - r**2) / 2 + (r0 + b) * (re - r) + r0 * (r0 + b) * logterm) / (tau * a)

        def small_distribution(r, re, r0, rmax, a, b, linear=False):
            ratio = r / re * (re - r0) / (r - r0) * (r + b) / (re + b)
            return (
                large_distribution(re, rmax)
                * ratio
                * np.exp(log_population_ratio(r, re, r0, a, b, linear))
            )

        def flux_components(
            subcooling,
            theta,
            coating,
            p,
            rn,
            re,
            rmax,
            linear=False,
            convention="kim",
            order=96,
            reference=False,
        ):
            """Truncate a population at rmax; keep its specified matching radius re.

            The small-radius singularity cancels analytically in Q*n. Nodes never touch rn.
            For Xie rmax<re this retains Eq.12's reference population while truncating Eq.8.
            """
            if rmax <= rn:
                return 0.0, 0.0
            r0 = critical_radius(subcooling, p)
            if re <= r0 or rn < r0 * (1 - 1e-12):
                raise ValueError("Population requires r0 <= rn < re")
            a, b = growth_coefficients(subcooling, theta, coating, p, convention)
            if sweeping_time(re, r0, a, b) <= 0:
                raise ValueError("Nonpositive sweeping time: outside population-model domain")
            # Q/G = rho*hfg*pi*r^2*cap_factor; removes the 0*infinity endpoint.
            ge = a * (re - r0) / (re * (re + b))
            cap = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))

            def small_integrand(r):
                return (
                    p.rho_l
                    * p.latent_heat
                    * np.pi
                    * r
                    * r
                    * cap
                    * large_distribution(re, rmax)
                    * ge
                    * np.exp(log_population_ratio(r, re, r0, a, b, linear))
                )

            fn = (
                reference_log_integrate
                if reference
                else lambda f, lo, hi: log_integrate(f, lo, hi, order)
            )
            upper = np.minimum(re, rmax)
            small = fn(small_integrand, rn, upper) if upper > rn else 0.0
            large = (
                fn(
                    lambda r: (
                        heat_rate(r, subcooling, theta, coating, p, convention)
                        * large_distribution(r, rmax)
                    ),
                    re,
                    rmax,
                )
                if rmax > re
                else 0.0
            )
            return small, large

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_populations = _build()
    return (ht_populations,)


@app.cell
def _():
    def _build():
        """First-order implicit differentiation of scalar, bracketed residual roots."""

        import numpy as np
        from autograd import grad
        from autograd.extend import defvjp, primitive
        from scipy.optimize import brentq

        def implicit_solver(residual, lower, upper):
            """Residual signature (scalar_state, parameter_vector); bracket must contain a simple root.

            Derivatives are valid inside one smooth branch. Higher derivatives are not promised.
            """

            @primitive
            def solve(parameters):
                return brentq(
                    lambda z: float(residual(z, parameters)), lower, upper, xtol=1e-12, rtol=1e-12
                )

            def vjp(answer, parameters):
                fz = grad(residual, 0)(answer, parameters)
                fp = grad(residual, 1)(answer, parameters)
                if not np.isfinite(fz) or abs(fz) < 1e-20:
                    raise ValueError("Degenerate implicit root; sensitivity is undefined")
                return lambda cotangent: -cotangent * fp / fz

            defvjp(solve, vjp)
            return solve

        def normalized_sensitivity(function, parameters):
            parameters = np.array(parameters, dtype=float)
            value = function(parameters)
            if value == 0:
                raise ValueError("Normalized sensitivity undefined at zero output")
            return parameters * grad(function)(parameters) / value

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_differentiation = _build()
    return (ht_differentiation,)


@app.cell
def _():
    def _build():
        """Explicit finite and paper-approximate stripe geometry."""

        import numpy as np

        def disk_heights(radius, dwc_width, fwc_width):
            """Croce Eq.29 centers, retaining only centers strictly inside the disk.

            Fractional n is floored by the integer loop. This convention is recorded in the ledger.
            """
            pitch = dwc_width + fwc_width
            n = int(np.floor(2 * radius / pitch))
            if n < 1:
                raise ValueError("No full stripe period fits inside the disk")
            k = np.arange(1, n + 1)
            x = pitch * k - dwc_width - fwc_width / 2 - radius
            x = x[np.abs(x) < radius]
            return 2 * np.sqrt(radius**2 - x**2)

        def finite_stripes(dwc_width, fwc_width, width=0.04, height=0.04):
            """Start with a DWC stripe at the left edge; clip the last stripe exactly."""
            if min(dwc_width, fwc_width) <= 0 or width <= 0 or height <= 0:
                raise ValueError("Finite hybrid stripes require positive dimensions")
            if width / min(dwc_width, fwc_width) > 100000:
                raise ValueError("Too many stripes")
            position = 0.0
            segments = []
            hydrophilic = 0.0
            while position < width - 1e-14:
                for kind, span in (("DWC", dwc_width), ("FWC", fwc_width)):
                    stop = min(position + span, width)
                    if stop > position + 1e-14:
                        segments.append((position, stop, kind))
                        if kind == "FWC":
                            hydrophilic += stop - position
                    position = stop
            return {
                "sar": hydrophilic / width,
                "interface_length": (len(segments) - 1) * height,
                "area": width * height,
                "segments": segments,
            }

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_geometry = _build()
    return (ht_geometry,)


@app.cell
def _(ht_droplets, ht_populations, ht_properties, ht_types):
    def _build():
        """Xie 2020 Eqs.1-24; default restores Kim-Kim's liquid resistance (see ledger)."""

        from dataclasses import replace

        import numpy as np
        from scipy.optimize import brentq

        critical_radius = ht_droplets.critical_radius
        interface_coefficient = ht_droplets.interface_coefficient
        nusselt_flux = ht_droplets.nusselt_flux
        sliding_radius = ht_droplets.sliding_radius
        flux_components = ht_populations.flux_components
        water = ht_properties.water
        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        SteamResult = ht_types.SteamResult
        Surface = ht_types.Surface

        def preset():
            return (
                SteamConditions(333.15, 5),
                Surface(np.deg2rad(110), np.deg2rad(120), np.deg2rad(105), 5e-9),
                Geometry(0.2e-3, 0.2e-3, 0.01),
            )

        def stripe_profile(
            conditions,
            surface,
            geometry,
            p=None,
            mode="mixed",
            dx=1e-6,
            order=96,
            reference=False,
            convention="kim",
        ):
            if mode not in ("dss", "oss", "mixed") or dx <= 0:
                raise ValueError("Invalid departure mode or spatial step")
            p = p or water(conditions.temperature)
            dt, theta = conditions.subcooling, surface.theta
            if dt <= 0 or geometry.dwc_width <= 0:
                raise ValueError("Stripe profile requires positive DWC width and subcooling")
            r0 = critical_radius(dt, p)
            re = 0.5 / np.sqrt(surface.nucleation_density)
            slide = sliding_radius(theta, surface.advancing, surface.receding, p)
            half = geometry.dwc_width / 2
            # Split the suction/sliding boundary exactly to conserve transferred mass.
            boundary = min(half, slide * np.sin(theta)) if mode == "mixed" else half
            edges = [0.0]
            for lo, hi in ((0, boundary), (boundary, half)):
                if hi > lo:
                    edges.extend(np.linspace(lo, hi, int(np.ceil((hi - lo) / dx)) + 1)[1:])
            edges = np.array(edges)
            x = (edges[1:] + edges[:-1]) / 2
            weights = np.diff(edges) / half
            rmax = x / np.sin(theta)
            if mode == "dss":
                rmax = np.full_like(x, half / np.sin(theta))
            elif mode == "mixed":
                rmax = np.minimum(rmax, slide)
            q = np.array(
                [
                    sum(
                        flux_components(
                            dt,
                            theta,
                            surface.coating_resistance,
                            p,
                            r0,
                            re,
                            r,
                            convention=convention,
                            order=order,
                            reference=reference,
                        )
                    )
                    for r in rmax
                ]
            )
            suction = x <= boundary if mode == "mixed" else np.ones(len(x), dtype=bool)
            return {
                "x": x,
                "weights": weights,
                "rmax": rmax,
                "heat_flux": q,
                "suction": suction,
                "sliding_radius": slide,
                "critical_width": 2 * slide * np.sin(theta),
                "rn": r0,
                "re": re,
            }

        def solve(
            conditions=None,
            surface=None,
            geometry=None,
            *,
            mode="mixed",
            dx=1e-6,
            order=96,
            reference=False,
            convention="kim",
            properties=None,
        ):
            pc, ps, pg = preset()
            c, s, g = conditions or pc, surface or ps, geometry or pg
            p = properties or water(c.temperature)
            dt = c.subcooling
            if dt == 0:
                return SteamResult("Xie 2020", 0, 0, 0, 0, 0, 0)
            if g.dwc_width == 0:
                q = float(nusselt_flux(dt, 2 * g.radius, p))
                return SteamResult(
                    "Xie 2020", q, 0, q, q / dt, 0, 0, notes=("Pure FWC uses Nusselt plate limit",)
                )
            if g.fwc_width == 0:
                slide = sliding_radius(s.theta, s.advancing, s.receding, p)
                q = float(
                    sum(
                        flux_components(
                            dt,
                            s.theta,
                            s.coating_resistance,
                            p,
                            critical_radius(dt, p),
                            0.5 / np.sqrt(s.nucleation_density),
                            slide,
                            convention=convention,
                            order=order,
                            reference=reference,
                        )
                    )
                )
                return SteamResult("Xie 2020", q, q, 0, q / dt, 0, 0)
            profile = stripe_profile(c, s, g, p, mode, dx, order, reference, convention)
            qd = float(np.sum(profile["heat_flux"] * profile["weights"]))
            transfer = float(np.sum(profile["heat_flux"] * profile["weights"] * profile["suction"]))
            hi = interface_coefficient(p)
            coeff = (
                3 * np.pi * g.radius * p.viscosity / (2 * p.rho_l**2 * p.gravity * p.latent_heat)
            )

            def residual(logdelta):
                delta = np.exp(logdelta)
                hf = 1 / (1 / hi + delta / p.conductivity)
                return delta**3 / coeff - (g.dwc_width / g.fwc_width * transfer + hf * dt)

            delta = np.exp(brentq(residual, np.log(1e-12), np.log(1.0)))
            qf = float(dt / (1 / hi + delta / p.conductivity))
            q = g.dwc_fraction * qd + (1 - g.dwc_fraction) * qf
            return SteamResult(
                "Xie 2020",
                q,
                qd,
                qf,
                q / dt,
                delta,
                transfer,
                notes=(
                    "Uniform-film model; flooding is not predicted",
                    f"Drop convention: {convention}",
                ),
            )

        def sweep_widths(widths, conditions=None, surface=None, geometry=None, **kwargs):
            g = geometry or preset()[2]
            return [
                solve(conditions, surface, replace(g, dwc_width=float(w)), **kwargs) for w in widths
            ]

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_xie2020 = _build()
    return (ht_xie2020,)


@app.cell
def _(
    ht_differentiation,
    ht_droplets,
    ht_geometry,
    ht_populations,
    ht_properties,
    ht_quadrature,
    ht_types,
):
    def _build():
        """Croce 2024, with dimensionally corrected population formulas and published film closure."""

        from functools import lru_cache

        import autograd.numpy as anp
        import numpy as np
        from autograd import grad
        from scipy.optimize import brentq

        implicit_solver = ht_differentiation.implicit_solver
        critical_radius = ht_droplets.critical_radius
        heat_rate = ht_droplets.heat_rate
        nusselt_flux = ht_droplets.nusselt_flux
        sliding_radius = ht_droplets.sliding_radius
        disk_heights = ht_geometry.disk_heights
        flux_components = ht_populations.flux_components
        water = ht_properties.water
        integrate = ht_quadrature.integrate
        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        SteamResult = ht_types.SteamResult
        Surface = ht_types.Surface

        def availability_scaled(log_ratio, parameters, p):
            dt, theta, coating = parameters
            r0 = critical_radius(dt, p)
            r = r0 * anp.exp(log_ratio)
            q = heat_rate(r, dt, theta, coating, p)

            def angular(phi):
                thermal = (
                    -dt
                    + q * coating / (anp.pi * r * r * anp.sin(theta) ** 2)
                    + q * phi / (4 * anp.pi * r * anp.sin(theta) * p.conductivity)
                )
                return thermal / (1 + anp.cos(phi)) ** 2

            psi = (
                p.rho_l
                * p.latent_heat
                / p.temperature
                * anp.pi
                * (r * anp.sin(theta)) ** 3
                * integrate(angular, 0, theta, 48)
                + p.tension * (2 - 3 * anp.cos(theta) + anp.cos(theta) ** 3) * anp.pi * r * r
            )
            return psi / (anp.pi * p.tension * r0 * r0)

        @lru_cache(maxsize=16)
        def _nucleation_solver(p):
            def residual(z, parameters):
                return grad(availability_scaled, 0)(z, parameters, p)

            return implicit_solver(residual, 0.0, anp.log(1e5))

        def nucleation_radius(subcooling, theta, coating, p):
            """Availability stationary point; test suite verifies negative curvature."""
            params = anp.array([subcooling, theta, coating])
            z = _nucleation_solver(p)(params)
            return critical_radius(subcooling, p) * anp.exp(z)

        def dwc_components(dt, theta, coating, p, rmax, order=96, reference=False, linear=True):
            rn = nucleation_radius(dt, theta, coating, p)
            re = rn / (2 * anp.sqrt(0.037))
            return flux_components(
                dt, theta, coating, p, rn, re, rmax, linear=linear, order=order, reference=reference
            )

        def rivulet_factor(ratio):
            """F_theta = integral of (local thickness / maximum thickness)^3.

            Direct section quadrature avoids cancellation in Eq.18 for theta -> 0.
            ratio is delta/L_F and must be in [0, .5] (pre-flooding branch).
            """
            v = 2 * ratio

            def integrand(s):
                h = 2 * (1 - s * s) / (anp.sqrt((1 + v * v) ** 2 - 4 * v * v * s * s) + (1 - v * v))
                return h**3

            return integrate(integrand, 0, 1, 64)

        def film_height_relation(delta, width, migration, dt, p):
            """Stable integral equivalent of Eqs.23-24 at the endpoint's fixed angle."""
            ratio = delta / width
            theta = 2 * anp.arctan(2 * ratio)
            sinc = anp.sinc(theta / anp.pi)
            a = p.conductivity * dt / p.latent_heat * sinc
            b = migration / width
            integral = delta**4 * integrate(lambda u: u**3 / (a + b * delta * u), 0, 1, 48)
            return (
                rivulet_factor(ratio)
                * p.rho_l
                * (p.rho_l - p.rho_v)
                * p.gravity
                / p.viscosity
                * integral
            )

        def film_flow(delta, width, p):
            return (
                rivulet_factor(delta / width)
                * p.rho_l
                * (p.rho_l - p.rho_v)
                * p.gravity
                * delta**3
                * width
                / (3 * p.viscosity)
            )

        def critical_flow(width, p):
            return anp.pi / 128 * p.rho_l * (p.rho_l - p.rho_v) * p.gravity * width**4 / p.viscosity

        @lru_cache(maxsize=16)
        def _film_solver(p):
            # parameters = [width, migration kg/(m s), subcooling, height]
            def residual(z, params):
                width, migration, dt, height = params
                return (
                    film_height_relation(width * anp.exp(z), width, migration, dt, p) / height - 1
                )

            return implicit_solver(residual, -24.0, anp.log(0.5))

        def film_state(width, migration, dt, height, p):
            """Return thickness, total outflow, FWC flux and flood-height ratio.

            A flooded geometry has no valid pre-flood film solution; flux is NaN, not extrapolated.
            """
            flood_height = film_height_relation(width / 2, width, migration, dt, p)
            ratio = height / flood_height
            if ratio > 1 + 1e-10:
                return float("nan"), float("nan"), float("nan"), ratio
            params = anp.array([width, migration, dt, height])
            if abs(ratio - 1) < 1e-10:
                delta = width / 2
            else:
                delta = width * anp.exp(_film_solver(p)(params))
            outflow = film_flow(delta, width, p)
            qf = (outflow - migration * height) * p.latent_heat / (height * width)
            return delta, outflow, qf, ratio

        def minimum_fwc_width(dwc_width, dt, theta, coating, p, height, order=96):
            qd = sum(dwc_components(dt, theta, coating, p, dwc_width / (2 * anp.sin(theta)), order))
            migration = qd * dwc_width / p.latent_heat

            def residual(logw):
                return float(
                    film_height_relation(anp.exp(logw) / 2, anp.exp(logw), migration, dt, p)
                    / height
                    - 1
                )

            return np.exp(brentq(residual, np.log(1e-7), np.log(0.1)))

        def solve(
            conditions=None,
            surface=None,
            geometry=None,
            *,
            order=96,
            reference=False,
            properties=None,
            linear=True,
        ):
            c, s, g = conditions or SteamConditions(), surface or Surface(), geometry or Geometry()
            p = properties or water(c.temperature)
            dt = c.subcooling
            if dt == 0:
                return SteamResult("Croce 2024", 0, 0, 0, 0, 0, 0)
            if g.dwc_width == 0:
                q = float(nusselt_flux(dt, 2 * g.radius, p))
                return SteamResult(
                    "Croce 2024",
                    q,
                    0,
                    q,
                    q / dt,
                    0,
                    0,
                    notes=("Pure FWC uses Nusselt plate limit",),
                )
            rmax = (
                g.dwc_width / (2 * np.sin(s.theta))
                if g.fwc_width > 0
                else sliding_radius(s.theta, s.advancing, s.receding, p, "croce")
            )
            rn = nucleation_radius(dt, s.theta, s.coating_resistance, p)
            re = rn / (2 * np.sqrt(0.037))
            if rmax <= re:
                raise ValueError(
                    "Croce requires rmax > re; stripe is outside the two-population domain"
                )
            qd = float(
                sum(
                    dwc_components(
                        dt, s.theta, s.coating_resistance, p, rmax, order, reference, linear
                    )
                )
            )
            if g.fwc_width == 0:
                return SteamResult("Croce 2024", qd, qd, 0, qd / dt, 0, 0)
            migration = qd * g.dwc_width / p.latent_heat
            longest = film_state(g.fwc_width, migration, dt, 2 * g.radius, p)
            if longest[3] > 1 + 1e-10:
                return SteamResult(
                    "Croce 2024",
                    np.nan,
                    qd,
                    np.nan,
                    np.nan,
                    np.nan,
                    qd,
                    float(longest[3]),
                    False,
                    ("Flooding: no valid pre-flood heat-flux prediction",),
                )
            heights = disk_heights(g.radius, g.dwc_width, g.fwc_width)
            states = [film_state(g.fwc_width, migration, dt, float(h), p) for h in heights]
            qf = float(np.average([state[2] for state in states], weights=heights))
            q = g.dwc_fraction * qd + (1 - g.dwc_fraction) * qf
            return SteamResult(
                "Croce 2024",
                q,
                qd,
                qf,
                q / dt,
                float(longest[0]),
                qd,
                float(longest[3]),
                True,
                (
                    "Eqs.8/13 corrected; local-angle film closure; disk-center quadrature",
                    "Specimen radius is an explicit assumption; see preset provenance",
                ),
            )

        def smooth_plate_flux(parameters, p, height=0.02, theta=2 * np.pi / 3, order=96):
            """AD-ready plate variant [LD, LF, DT, coating]; no discrete disk stripe count.

            This is a labeled rectangular-plate extension, valid strictly below flooding.
            """
            ld, lf, dt, coating = parameters
            qd = sum(dwc_components(dt, theta, coating, p, ld / (2 * anp.sin(theta)), order))
            migration = qd * ld / p.latent_heat
            _, _, qf, ratio = film_state(lf, migration, dt, height, p)
            if ratio >= 1:
                raise ValueError("Sensitivity requires an interior, non-flooded design")
            return (qd * ld + qf * lf) / (ld + lf)

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_croce2024 = _build()
    return (ht_croce2024,)


@app.cell
def _(ht_geometry):
    def _build():
        """Humid-air film balance and four-hour empirical recovery, kept as separate observables."""

        from dataclasses import asdict, dataclass

        import autograd.numpy as np
        from scipy.optimize import brentq

        finite_stripes = ht_geometry.finite_stripes

        def moisture_ratio(temperature_c):
            """Lee Eq.3.3a; saturation polynomial with Celsius input, calibrated near 14 C."""
            return (
                0.0037444
                + 0.0003078 * temperature_c
                + 0.0000046 * temperature_c**2
                + 0.0000004 * temperature_c**3
            )

        def dwc_mass_4h(interface_length):
            """Eq.6: kilograms collected over four hours, with L in meters."""
            return 0.000695 * (-np.expm1(-4.2488 * interface_length)) ** 6.744

        def recovery_from_interface(interface_length, sar, baseline_g_per_hour=0.4):
            """Return kg/4h; measured FWC baseline is explicit, not confused with the transport model."""
            if interface_length < 0 or not 0 <= sar <= 1 or baseline_g_per_hour < 0:
                raise ValueError("Invalid interface length, SAR, or baseline")
            return sar * baseline_g_per_hour * 4 / 1000 + dwc_mass_4h(interface_length)

        @dataclass(frozen=True)
        class FilmResult:
            interface_temperature_c: float
            sensible_flux: float
            latent_flux: float
            conduction_flux: float
            thickness: float
            recovery_4h_kg: float
            energy_residual: float

        def film_balance(air_c=14.0, wall_c=5.0, velocity=0.6, length=0.04, area=0.0016):
            """Lee saturated-air model, Eqs.3-4. wall_c is a wall assumption, not coolant temperature.

            Fixed near-10 C water / near-14 C air engineering properties are recorded in the ledger.
            A new RH law is deliberately not inferred from the saturated-air fit.
            """
            if not (0 <= wall_c < air_c <= 30) or min(velocity, length, area) <= 0:
                raise ValueError("Require 0 <= wall < air <= 30 C and positive geometry/velocity")
            kl, mu, rhol, rhoa, hfg = 0.58, 0.001307, 999.7, 1.23, 2.477e6
            ka, mua, cp, pr = 0.0253, 1.79e-5, 1006.0, 0.71
            re = rhoa * velocity * length / mua
            nu = 0.3387 * np.sqrt(re) * pr ** (1 / 3) / (1 + (0.0468 / pr) ** (2 / 3)) ** 0.25
            hv = 2 * nu * ka / length
            delta = (
                4 * kl * mu * (air_c - wall_c) * length / (9.81 * rhol * (rhol - rhoa) * hfg)
            ) ** 0.25

            def components(ti):
                sensible = hv * (air_c - ti)
                latent = hv * hfg / cp * (moisture_ratio(air_c) - moisture_ratio(ti))
                conduction = kl / delta * (ti - wall_c)
                return sensible, latent, conduction

            ti = brentq(
                lambda t: components(t)[0] + components(t)[1] - components(t)[2], wall_c, air_c
            )
            qs, ql, qd = components(ti)
            return FilmResult(ti, qs, ql, qd, delta, ql * area / hfg * 14400, qs + ql - qd)

        def solve(dwc_width=0.6e-3, fwc_width=3.4e-3, *, baseline="measured", finite=True):
            if baseline not in ("measured", "paper_theory", "transport"):
                raise ValueError("baseline must be measured, paper_theory or transport")
            g = finite_stripes(dwc_width, fwc_width)
            if not finite:
                g["sar"] = fwc_width / (dwc_width + fwc_width)
                g["interface_length"] = 2 * g["area"] / (dwc_width + fwc_width)
            film = film_balance()
            baseline_rate = {
                "measured": 0.4,
                "paper_theory": 0.355,
                "transport": film.recovery_4h_kg * 1000 / 4,
            }[baseline]
            mf = g["sar"] * baseline_rate * 4 / 1000
            md = float(dwc_mass_4h(g["interface_length"]))
            in_envelope = dwc_width >= 0.5e-3 and fwc_width >= 0.5e-3 and 0.5 <= g["sar"] <= 0.851
            return {
                "model": "Lee 2020",
                "mass_4h_kg": mf + md,
                "fwc_mass_4h_kg": mf,
                "dwc_mass_4h_kg": md,
                "average_kg_per_s": (mf + md) / 14400,
                "sar": g["sar"],
                "interface_length_m": g["interface_length"],
                "baseline": baseline,
                "baseline_g_per_h": baseline_rate,
                "within_design_envelope": in_envelope,
                "finite_geometry": finite,
                "film_transport": asdict(film),
                "segments": g["segments"],
                "notes": [
                    "Four-hour calibrated mass; not a transient or arbitrary-RH model",
                    "40 mm square; starts with DWC at left edge",
                    "Film model assumes wall 5 C; paper specifies coolant inlet 5 C",
                ],
            }

        def departure_diameter(theta, advancing, receding, tension=0.074, rho=999.7):
            """Lee Eqs.1-2, vertical plate. theta is theta_avg in Eq.2."""
            shape = (2 - 3 * np.cos(theta) + np.cos(theta) ** 3) / np.sin(theta) ** 3
            return np.sqrt(
                (24 / np.pi**3 * tension * (np.cos(receding) - np.cos(advancing)))
                / (rho * 9.81 * np.pi / 24 * shape)
            )

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_lee2020 = _build()
    return (ht_lee2020,)


@app.cell
def _(ht_croce2024, ht_lee2020, ht_properties, ht_types, ht_xie2020):
    def _build():
        """Constrained searches with explicit feasibility, grid evidence and reference reevaluation."""

        from dataclasses import replace

        import numpy as np
        from autograd import grad
        from scipy.optimize import minimize, minimize_scalar

        croce2024 = ht_croce2024
        lee2020 = ht_lee2020
        xie2020 = ht_xie2020
        water = ht_properties.water
        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        Surface = ht_types.Surface

        def optimize_croce(
            conditions=None,
            surface=None,
            radius=0.01,
            margin=0.02,
            bounds=(0.05e-3, 2e-3),
            grid_size=30,
        ):
            """Disk search along the flood boundary + a fractional FWC-width margin."""
            if margin < 0 or grid_size < 3 or not 0 < bounds[0] < bounds[1]:
                raise ValueError("Invalid search bounds, grid or margin")
            c, s = conditions or SteamConditions(), surface or Surface()
            if c.subcooling <= 0:
                raise ValueError("Optimization requires positive subcooling")
            p = water(c.temperature)

            def evaluate(ld, reference=False):
                lf = croce2024.minimum_fwc_width(
                    ld, c.subcooling, s.theta, s.coating_resistance, p, 2 * radius
                )
                lf *= 1 + margin
                result = croce2024.solve(c, s, Geometry(ld, lf, radius), reference=reference)
                return lf, result

            widths = np.geomspace(*bounds, grid_size)
            values = np.array([evaluate(w)[1].heat_flux for w in widths])
            index = int(np.nanargmax(values))
            local = (
                np.log(widths[max(index - 1, 0)]),
                np.log(widths[min(index + 1, grid_size - 1)]),
            )
            fit = minimize_scalar(
                lambda z: -evaluate(np.exp(z))[1].heat_flux,
                bounds=local,
                method="bounded",
                options={"xatol": 1e-7},
            )
            candidates = [(widths[index], values[index]), (np.exp(fit.x), -fit.fun)]
            ld = max(candidates, key=lambda x: x[1])[0]
            lf, result = evaluate(ld, True)
            return {
                "dwc_width": float(ld),
                "fwc_width": float(lf),
                "result": result.to_dict(),
                "grid_widths": widths.tolist(),
                "grid_fluxes": values.tolist(),
                "margin": margin,
                "method": "grid + bounded local search, reference radial quadrature",
                "scope": "Disk Eq.29 has discrete stripe-count changes; no global-optimum guarantee",
            }

        def optimize_plate(initial, p=None, height=0.02, theta=2 * np.pi / 3):
            """Autograd refinement of LD/LF at fixed DT and coating, rectangular extension."""
            p = p or water()
            initial = np.asarray(initial, float)
            if initial.shape != (4,) or np.any(initial[:3] <= 0) or initial[3] < 0:
                raise ValueError("Initial vector is [LD, LF, subcooling, coating]")
            import autograd.numpy as anp

            dwc_components = croce2024.dwc_components
            film_height_relation = croce2024.film_height_relation

            def params(z):
                return anp.concatenate((anp.exp(z), initial[2:]))

            def flood(z):
                ld, lf, dt, coat = params(z)
                qd = sum(dwc_components(dt, theta, coat, p, ld / (2 * anp.sin(theta))))
                return (
                    film_height_relation(lf / 2, lf, qd * ld / p.latent_heat, dt, p) / height - 1.02
                )

            # Feasible-only objective to avoid ever interpreting a flooded flux as valid.
            def objective(z):
                if flood(z) <= -0.019:
                    return 1e3 + float(-flood(z))
                return -croce2024.smooth_plate_flux(params(z), p, height, theta) / 1e6

            def jac(z):
                if flood(z) <= -0.019:
                    return -grad(flood)(z)
                return grad(
                    lambda zz: -croce2024.smooth_plate_flux(params(zz), p, height, theta) / 1e6
                )(z)

            fit = minimize(
                objective,
                np.log(initial[:2]),
                jac=jac,
                method="SLSQP",
                bounds=[(np.log(0.05e-3), np.log(2e-3))] * 2,
                constraints=[{"type": "ineq", "fun": flood, "jac": grad(flood)}],
                options={"maxiter": 120, "ftol": 1e-9},
            )
            return {
                "parameters": np.asarray(params(fit.x)).tolist(),
                "success": bool(fit.success),
                "message": str(fit.message),
                "flux": -float(fit.fun) * 1e6,
                "feasibility": float(flood(fit.x)),
                "scope": "Smooth rectangular-plate extension",
            }

        def optimize_xie(
            conditions=None, surface=None, geometry=None, bounds=(0.05e-3, 3e-3), grid_size=25
        ):
            g = geometry or xie2020.preset()[2]
            widths = np.geomspace(*bounds, grid_size)
            results = xie2020.sweep_widths(widths, conditions, surface, g, dx=4e-6)
            best = int(np.argmax([r.heat_flux for r in results]))
            ld = widths[best]
            result = xie2020.solve(
                conditions, surface, replace(g, dwc_width=float(ld)), dx=1e-6, reference=True
            )
            return {
                "dwc_width": float(ld),
                "fwc_width": g.fwc_width,
                "result": result.to_dict(),
                "method": "Width grid, reference-quadrature recheck; optimum is grid-resolved",
            }

        def optimize_lee():
            # Restrict to the reported minimum widths and SAR bands; no unbounded fit extrapolation.
            candidates = []
            for sar in (0.5, 0.6, 0.75, 0.85):
                for ld in np.linspace(0.5e-3, 2.7e-3, 45):
                    lf = ld * sar / (1 - sar)
                    result = lee2020.solve(ld, lf)
                    if result["within_design_envelope"]:
                        candidates.append((result["mass_4h_kg"], ld, lf, result))
            _, ld, lf, result = max(candidates, key=lambda row: row[0])
            return {
                "dwc_width": float(ld),
                "fwc_width": float(lf),
                "result": result,
                "scope": "Discrete width/SAR search with finite edges; measured FWC baseline",
            }

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_optimization = _build()
    return (ht_optimization,)


@app.cell
def _():
    def _build():
        """Plotly figures shared by the marimo notebooks and reproducible batch studies."""

        import plotly.graph_objects as go

        COLORS = ["#0f766e", "#e97935", "#4969b1", "#ad4a80", "#718096"]

        def style(fig, title, xlabel=None, ylabel=None):
            fig.update_layout(
                title=dict(text=title, font=dict(size=16), automargin=True),
                template="plotly_white",
                colorway=COLORS,
                font=dict(family="Arial", color="#24364b"),
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                autosize=True,
                height=360,
                margin=dict(l=55, r=20, t=55, b=55),
                legend=dict(orientation="h", y=-0.25, x=0, yanchor="top"),
                hovermode="x unified",
            )
            if xlabel:
                fig.update_xaxes(title_text=xlabel, automargin=True)
            if ylabel:
                fig.update_yaxes(title_text=ylabel, automargin=True)
            return fig

        def curves(x, series, title, xlabel, ylabel, logx=False, logy=False):
            fig = go.Figure()
            for name, y in series.items():
                fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines", line=dict(width=2.5)))
            style(fig, title, xlabel, ylabel)
            if logx:
                fig.update_xaxes(type="log")
            if logy:
                fig.update_yaxes(type="log")
            return fig

        def stripe_schematic(ld, lf, height=0.004):
            fig = go.Figure()
            pitch = ld + lf
            for i in range(4):
                for start, end, color in (
                    (i * pitch, i * pitch + ld, "#dbe7f0"),
                    (i * pitch + ld, (i + 1) * pitch, "#0f766e"),
                ):
                    fig.add_shape(
                        type="rect",
                        x0=start * 1e3,
                        x1=end * 1e3,
                        y0=0,
                        y1=height * 1e3,
                        fillcolor=color,
                        line=dict(width=0),
                    )
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    name="Hydrophobic / DWC",
                    marker=dict(color="#b9d0e2", size=12),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    name="Hydrophilic / FWC",
                    marker=dict(color="#0f766e", size=12),
                )
            )
            style(fig, "Stripe geometry · four periods", "Across surface (mm)", "Downhill (mm)")
            fig.update_xaxes(range=[0, 4 * pitch * 1e3])
            fig.update_yaxes(range=[height * 1e3, 0])
            fig.update_layout(height=280, margin=dict(b=100), legend=dict(y=-0.6))
            return fig

        def heatmap(x, y, z, title, xlabel, ylabel, zlabel):
            fig = go.Figure(
                go.Heatmap(
                    x=x, y=y, z=z, colorscale="Teal", colorbar=dict(title=zlabel), hoverongaps=False
                )
            )
            return style(fig, title, xlabel, ylabel)

        def benchmark_plot(rows, title):
            fig = go.Figure()
            for case in dict.fromkeys(row["case"] for row in rows):
                selected = [r for r in rows if r["case"] == case]
                x = [r["subcooling_K"] for r in selected]
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=[r["paper_flux_W_m2"] / 1000 for r in selected],
                        name=case + " · paper curve",
                        mode="markers",
                        error_y=dict(
                            type="data",
                            array=[r["reading_uncertainty_W_m2"] / 1000 for r in selected],
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=[r["computed_flux_W_m2"] / 1000 for r in selected],
                        name=case + " · implemented",
                        mode="lines+markers",
                    )
                )
            return style(fig, title, "Subcooling (K)", "Heat flux (kW/m²)")

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_plots = _build()
    return (ht_plots,)


@app.cell
def _(ht_croce2024, ht_properties, ht_types, ht_xie2020):
    def _build():
        """Reproducible sweeps and transparent figure checks (not claimed as full validation)."""

        import json
        from dataclasses import asdict

        import numpy as np

        croce = ht_croce2024
        xie = ht_xie2020
        water = ht_properties.water
        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        Surface = ht_types.Surface

        FIGURE_DATA = {
            "provenance": "Manual approximate readings of published MODEL curves from attached PDFs rendered at 1.7x, 2026-09-21. Not experimental raw data; no marker data fitted. Pixel-based visual readings have conservative 15-20 kW/m2 uncertainty.",
            "points": [
                {
                    "case": "Croce Fig.7a",
                    "page": 11,
                    "subcooling_K": 2,
                    "paper_flux_W_m2": 180000,
                    "reading_uncertainty_W_m2": 15000,
                },
                {
                    "case": "Croce Fig.7a",
                    "page": 11,
                    "subcooling_K": 4,
                    "paper_flux_W_m2": 375000,
                    "reading_uncertainty_W_m2": 15000,
                },
                {
                    "case": "Croce Fig.7a",
                    "page": 11,
                    "subcooling_K": 6,
                    "paper_flux_W_m2": 580000,
                    "reading_uncertainty_W_m2": 15000,
                },
                {
                    "case": "Croce Fig.8b",
                    "page": 12,
                    "subcooling_K": 2,
                    "paper_flux_W_m2": 210000,
                    "reading_uncertainty_W_m2": 20000,
                },
                {
                    "case": "Croce Fig.8b",
                    "page": 12,
                    "subcooling_K": 4,
                    "paper_flux_W_m2": 435000,
                    "reading_uncertainty_W_m2": 20000,
                },
                {
                    "case": "Croce Fig.8b",
                    "page": 12,
                    "subcooling_K": 6,
                    "paper_flux_W_m2": 660000,
                    "reading_uncertainty_W_m2": 20000,
                },
                {
                    "case": "Xie Fig.5a",
                    "page": 10,
                    "subcooling_K": 2,
                    "paper_flux_W_m2": 190000,
                    "reading_uncertainty_W_m2": 15000,
                },
                {
                    "case": "Xie Fig.5a",
                    "page": 10,
                    "subcooling_K": 4,
                    "paper_flux_W_m2": 385000,
                    "reading_uncertainty_W_m2": 15000,
                },
                {
                    "case": "Xie Fig.5a",
                    "page": 10,
                    "subcooling_K": 6,
                    "paper_flux_W_m2": 585000,
                    "reading_uncertainty_W_m2": 15000,
                },
            ],
        }

        def figure_checks():
            data = FIGURE_DATA
            rows = []
            for point in data["points"]:
                c = SteamConditions(subcooling=point["subcooling_K"])
                if point["case"] == "Croce Fig.7a":
                    q = float(
                        sum(
                            croce.dwc_components(
                                c.subcooling,
                                2 * np.pi / 3,
                                3.39e-7,
                                water(),
                                0.00125,
                                reference=True,
                            )
                        )
                    )
                elif point["case"] == "Croce Fig.8b":
                    q = croce.solve(c, reference=True).heat_flux
                else:
                    q = xie.solve(
                        c,
                        Surface(coating_resistance=5e-9),
                        Geometry(0.00046, 0.00044),
                        reference=True,
                    ).heat_flux
                rows.append(
                    {
                        **point,
                        "computed_flux_W_m2": q,
                        "relative_error": q / point["paper_flux_W_m2"] - 1,
                    }
                )
            return rows

        def croce_heatmap(ld_values, lf_values, conditions=None, surface=None):
            rows = []
            flood = []
            for lf in lf_values:
                results = [
                    croce.solve(conditions, surface, Geometry(float(ld), float(lf)))
                    for ld in ld_values
                ]
                rows.append([r.heat_flux / 1000 for r in results])
                flood.append([r.flooding_ratio for r in results])
            return np.array(rows), np.array(flood)

        def export_record(model, inputs, result):
            import importlib.metadata as metadata

            def package_version(name):
                try:
                    return metadata.version(name)
                except metadata.PackageNotFoundError:
                    # Pyodide's bundled marimo has no distribution metadata.
                    from importlib import import_module

                    return getattr(import_module(name), "__version__", "unavailable")

            def convert(obj):
                if hasattr(obj, "to_dict"):
                    return obj.to_dict()
                if hasattr(obj, "__dataclass_fields__"):
                    return asdict(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, np.generic):
                    return obj.item()
                raise TypeError(type(obj).__name__)

            record = {
                "model": model,
                "inputs": inputs,
                "result": result,
                "versions": {
                    name: package_version(name)
                    for name in ("numpy", "scipy", "autograd", "plotly", "marimo")
                },
                "units": "SI except explicitly labeled fields",
            }

            # Non-finite numbers are serialized as null, never nonstandard JSON NaN.
            def sanitize(obj):
                if isinstance(obj, dict):
                    return {k: sanitize(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [sanitize(v) for v in obj]
                if isinstance(obj, float) and not np.isfinite(obj):
                    return None
                return obj

            return json.dumps(
                sanitize(json.loads(json.dumps(record, default=convert))), indent=2, allow_nan=False
            )

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_studies = _build()
    return (ht_studies,)


@app.cell
def _(ht_plots, ht_studies, ht_types, ht_xie2020):
    import marimo as s1_mo
    import numpy as s1_np
    from dataclasses import replace as s1_replace

    s1_model = ht_xie2020
    s1_Geometry = ht_types.Geometry
    s1_curves = ht_plots.curves
    s1_stripe_schematic = ht_plots.stripe_schematic
    s1_benchmark_plot = ht_plots.benchmark_plot
    s1_figure_checks = ht_studies.figure_checks
    s1_export_record = ht_studies.export_record
    return (
        s1_Geometry,
        s1_benchmark_plot,
        s1_curves,
        s1_export_record,
        s1_figure_checks,
        s1_mo,
        s1_model,
        s1_np,
        s1_replace,
        s1_stripe_schematic,
    )


@app.cell
def _(s1_mo):
    s1_mo.md(
        "\n    # Suction, sliding, and the liquid film\n    **Xie et al. · 2020** / Steam condensation on vertical biphilic stripes\n\n    Follow condensate from a growing droplet to its departure mode and the hydrophilic channel.\n    [Paper](https://doi.org/10.1016/j.ijheatmasstransfer.2019.119273) · SI calculations, display units below.\n\n    The default restores the Kim–Kim liquid resistance. The printed Eq. (11) contains an\n    extra π and gives substantially higher flux than the published curves. Both are available.\n    Disk radius **10 mm** is an unconfirmed specimen assumption. This model does not predict flooding.\n    "
    )
    return


@app.cell
def _(ht_layout, s1_mo):
    s1_controls = (
        ht_layout.controls(['ld', 'lf', 'dt', 'coating', 'mode', 'convention'])
        .batch(
            **{
                "ld": s1_mo.ui.number(0.05, 4.0, step=0.05, value=0.2, label="DWC width (mm)"),
                "lf": s1_mo.ui.number(0.05, 3.0, step=0.05, value=0.2, label="FWC width (mm)"),
                "dt": s1_mo.ui.slider(1.0, 10.0, step=0.5, value=5.0, label="Subcooling (K)"),
                "coating": s1_mo.ui.number(
                    0.0, 1000.0, step=1.0, value=1.0, label="Coating thickness (nm), k = 0.2 W/mK"
                ),
                "mode": s1_mo.ui.dropdown(
                    ["dss", "oss", "mixed"], value="mixed", label="Departure model"
                ),
                "convention": s1_mo.ui.dropdown(
                    ["kim", "xie"], value="kim", label="Liquid resistance: kim / printed xie"
                ),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    s1_controls
    return (s1_controls,)


@app.cell
def _(s1_Geometry, s1_controls, s1_model, s1_replace):
    s1_settings = s1_controls.value or {
        "ld": 0.2,
        "lf": 0.2,
        "dt": 5.0,
        "coating": 1.0,
        "mode": "mixed",
        "convention": "kim",
    }
    s1_conditions, s1_surface, _ = s1_model.preset()
    s1_conditions = s1_replace(s1_conditions, subcooling=s1_settings["dt"])
    s1_surface = s1_replace(s1_surface, coating_resistance=s1_settings["coating"] * 1e-09 / 0.2)
    s1_geometry = s1_Geometry(s1_settings["ld"] * 0.001, s1_settings["lf"] * 0.001)
    s1_result = s1_model.solve(
        s1_conditions,
        s1_surface,
        s1_geometry,
        mode=s1_settings["mode"],
        convention=s1_settings["convention"],
    )
    s1_profile = s1_model.stripe_profile(
        s1_conditions,
        s1_surface,
        s1_geometry,
        mode=s1_settings["mode"],
        convention=s1_settings["convention"],
    )
    return (
        s1_conditions,
        s1_geometry,
        s1_profile,
        s1_result,
        s1_settings,
        s1_surface,
    )


@app.cell
def _(ht_layout, s1_mo, s1_result):
    ht_layout.row(
        [
            s1_mo.stat(label="Total heat flux", value=f"{s1_result.heat_flux / 1000:,.1f} kW/m²"),
            s1_mo.stat(label="Overall HTC", value=f"{s1_result.htc / 1000:,.1f} kW/m²K"),
            s1_mo.stat(
                label="Film thickness", value=f"{s1_result.film_thickness * 1000000.0:,.1f} µm"
            ),
            s1_mo.stat(
                label="DWC liquid sent to film",
                value=f"{100 * s1_result.transferred_flux / s1_result.dwc_flux:.1f}%",
            ),
        ]
    )
    return


@app.cell
def _(ht_layout, s1_curves, s1_geometry, s1_mo, s1_profile, s1_stripe_schematic):
    s1_geometry_chart = s1_stripe_schematic(s1_geometry.dwc_width, s1_geometry.fwc_width)
    s1_radius_chart = s1_curves(
        s1_profile["x"] * 1000.0,
        {"Departure radius": s1_profile["rmax"] * 1000000.0},
        "Departure along the half-stripe",
        "Distance from boundary (mm)",
        "Cap radius (µm)",
    )
    s1_flux_chart = s1_curves(
        s1_profile["x"] * 1000.0,
        {"Local DWC": s1_profile["heat_flux"] / 1000},
        "Local condensation heat flux",
        "Distance from boundary (mm)",
        "Heat flux (kW/m²)",
    )
    s1_mo.vstack(
        [
            s1_mo.ui.plotly(s1_geometry_chart),
            ht_layout.row([s1_mo.ui.plotly(s1_radius_chart), s1_mo.ui.plotly(s1_flux_chart)], minimum=420),
        ]
    )
    return


@app.cell
def _(
    s1_conditions,
    s1_curves,
    s1_geometry,
    s1_mo,
    s1_model,
    s1_np,
    s1_settings,
    s1_surface,
):
    s1_widths = s1_np.geomspace(5e-05, 0.003, 28)
    s1_sweep = s1_model.sweep_widths(
        s1_widths,
        s1_conditions,
        s1_surface,
        s1_geometry,
        dx=4e-06,
        mode=s1_settings["mode"],
        convention=s1_settings["convention"],
    )
    s1_width_chart = s1_curves(
        s1_widths * 1000.0,
        {
            "Total": [s1_r.heat_flux / 1000 for s1_r in s1_sweep],
            "DWC region": [s1_r.dwc_flux / 1000 for s1_r in s1_sweep],
            "FWC region": [s1_r.fwc_flux / 1000 for s1_r in s1_sweep],
        },
        "Width sweep · region fluxes are before area weighting",
        "DWC width (mm)",
        "Heat flux (kW/m²)",
        True,
    )
    s1_mo.ui.plotly(s1_width_chart)
    return


@app.cell
def _(s1_benchmark_plot, s1_figure_checks, s1_mo):
    s1_benchmarks = [s1_r for s1_r in s1_figure_checks() if s1_r["case"].startswith("Xie")]
    s1_mo.vstack(
        [
            s1_mo.md(
                "### Published-curve check\nApproximate readings of Fig. 5a's model line, not raw experimental data. Fixed paper preset; independent of the controls above."
            ),
            s1_benchmark_plot(s1_benchmarks, "Xie Fig. 5a · Kim–Kim resistance convention"),
        ]
    )
    return


@app.cell
def _(
    s1_conditions,
    s1_export_record,
    s1_geometry,
    s1_mo,
    s1_result,
    s1_settings,
    s1_surface,
):
    s1_record = s1_export_record(
        "Xie 2020",
        {
            "controls": s1_settings,
            "conditions": s1_conditions,
            "surface": s1_surface,
            "geometry": s1_geometry,
            "dx_m": 1e-06,
            "radial_order": 96,
        },
        s1_result,
    )
    s1_mo.download(
        s1_record.encode(),
        filename="xie2020-result.json",
        label="Download calculation + provenance",
    )
    return


@app.cell
def _(
    ht_croce2024,
    ht_droplets,
    ht_plots,
    ht_populations,
    ht_properties,
    ht_studies,
    ht_types,
):
    import marimo as s2_mo
    import numpy as s2_np

    s2_model = ht_croce2024
    s2_SteamConditions = ht_types.SteamConditions
    s2_Surface = ht_types.Surface
    s2_Geometry = ht_types.Geometry
    s2_water = ht_properties.water
    s2_critical_radius = ht_droplets.critical_radius
    s2_growth_coefficients = ht_droplets.growth_coefficients
    s2_heat_rate = ht_droplets.heat_rate
    s2_resistance_terms = ht_droplets.resistance_terms
    s2_small_distribution = ht_populations.small_distribution
    s2_large_distribution = ht_populations.large_distribution
    s2_curves = ht_plots.curves
    s2_benchmark_plot = ht_plots.benchmark_plot
    s2_stripe_schematic = ht_plots.stripe_schematic
    s2_figure_checks = ht_studies.figure_checks
    s2_export_record = ht_studies.export_record
    return (
        s2_Geometry,
        s2_SteamConditions,
        s2_Surface,
        s2_benchmark_plot,
        s2_critical_radius,
        s2_curves,
        s2_export_record,
        s2_figure_checks,
        s2_growth_coefficients,
        s2_large_distribution,
        s2_mo,
        s2_model,
        s2_np,
        s2_resistance_terms,
        s2_small_distribution,
        s2_water,
    )


@app.cell
def _(s2_mo):
    s2_mo.md(
        "\n    # From nanometer droplets to draining rivulets\n    **Croce & Suzzi · 2024** / Coating, population balance, and flooding\n\n    [Paper](https://doi.org/10.3390/en17112742). The model includes coating-dependent nucleation,\n    radius-dependent sweeping, capillary cross-flow, and a finite drainage capacity.\n    Eqs. (8) and (13) use the documented exponential and interfacial-coefficient corrections.\n\n    **Reproduction status:** the implemented equations do not fully match the published curves,\n    especially the pure-DWC Fig. 7a. The comparison below exposes that discrepancy.\n    Optimization is exploratory until it is resolved. Disk radius **10 mm** is an explicit assumption.\n    "
    )
    return


@app.cell
def _(ht_layout, s2_mo):
    s2_controls = (
        ht_layout.controls(['ld', 'lf', 'dt', 'coating', 'linear'])
        .batch(
            **{
                "ld": s2_mo.ui.number(0.05, 2.0, step=0.01, value=0.55, label="DWC width (mm)"),
                "lf": s2_mo.ui.number(0.05, 2.0, step=0.01, value=0.45, label="FWC width (mm)"),
                "dt": s2_mo.ui.slider(1.0, 10.0, step=0.5, value=6.0, label="Subcooling (K)"),
                "coating": s2_mo.ui.number(
                    0.0, 20.0, step=0.01, value=3.39, label="Coating resistance (×10⁻⁷ m²K/W)"
                ),
                "linear": s2_mo.ui.checkbox(value=True, label="Radius-dependent sweeping (Croce)"),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    s2_controls
    return (s2_controls,)


@app.cell
def _(
    s2_Geometry,
    s2_SteamConditions,
    s2_Surface,
    s2_controls,
    s2_model,
    s2_water,
):
    s2_settings = s2_controls.value or {
        "ld": 0.55,
        "lf": 0.45,
        "dt": 6.0,
        "coating": 3.39,
        "linear": True,
    }
    s2_conditions = s2_SteamConditions(subcooling=s2_settings["dt"])
    s2_surface = s2_Surface(coating_resistance=s2_settings["coating"] * 1e-07)
    s2_geometry = s2_Geometry(s2_settings["ld"] * 0.001, s2_settings["lf"] * 0.001)
    s2_properties = s2_water()
    s2_result = s2_model.solve(s2_conditions, s2_surface, s2_geometry, linear=s2_settings["linear"])
    s2_rn = s2_model.nucleation_radius(
        s2_conditions.subcooling, s2_surface.theta, s2_surface.coating_resistance, s2_properties
    )
    return (
        s2_conditions,
        s2_geometry,
        s2_properties,
        s2_result,
        s2_rn,
        s2_settings,
        s2_surface,
    )


@app.cell
def _(ht_layout, s2_mo, s2_result, s2_rn):
    s2_status = (
        "Within modeled drainage capacity"
        if s2_result.valid
        else "FLOODING · total flux is undefined"
    )
    s2_mo.vstack(
        [
            s2_mo.callout(s2_status, kind="success" if s2_result.valid else "warn"),
            ht_layout.row(
                [
                    s2_mo.stat(
                        label="Total heat flux",
                        value=f"{s2_result.heat_flux / 1000:,.1f} kW/m²"
                        if s2_result.valid
                        else "Outside model",
                    ),
                    s2_mo.stat(label="Nucleation radius", value=f"{s2_rn * 1000000000.0:.2f} nm"),
                    s2_mo.stat(
                        label="Height / flooding height", value=f"{s2_result.flooding_ratio:.3f}"
                    ),
                    s2_mo.stat(
                        label="Maximum film thickness",
                        value=f"{s2_result.film_thickness * 1000000.0:.1f} µm"
                        if s2_result.valid
                        else "—",
                    ),
                ]
            ),
        ]
    )
    return


@app.cell
def _(
    ht_layout,
    s2_conditions,
    s2_critical_radius,
    s2_curves,
    s2_geometry,
    s2_growth_coefficients,
    s2_large_distribution,
    s2_mo,
    s2_np,
    s2_properties,
    s2_resistance_terms,
    s2_rn,
    s2_small_distribution,
    s2_surface,
):
    s2_dt = s2_conditions.subcooling
    s2_theta = s2_surface.theta
    s2_coating = s2_surface.coating_resistance
    s2_r0 = s2_critical_radius(s2_dt, s2_properties)
    s2_re = s2_rn / (2 * s2_np.sqrt(0.037))
    s2_rmax = s2_geometry.dwc_width / (2 * s2_np.sin(s2_theta))
    s2_radii = s2_np.geomspace(s2_rn * 1.00001, s2_rmax, 220)
    s2_a, s2_b = s2_growth_coefficients(s2_dt, s2_theta, s2_coating, s2_properties)
    s2_distribution = s2_np.array(
        [
            s2_small_distribution(s2_r, s2_re, s2_r0, s2_rmax, s2_a, s2_b, True)
            if s2_r < s2_re
            else s2_large_distribution(s2_r, s2_rmax)
            for s2_r in s2_radii
        ]
    )
    s2_baseline_distribution = s2_np.array(
        [
            s2_small_distribution(s2_r, s2_re, s2_r0, s2_rmax, s2_a, s2_b, False)
            if s2_r < s2_re
            else s2_large_distribution(s2_r, s2_rmax)
            for s2_r in s2_radii
        ]
    )
    s2_populations = s2_curves(
        s2_radii * 1000000.0,
        {"Croce sweeping": s2_distribution, "Constant sweeping": s2_baseline_distribution},
        "Population density · same nucleation and departure radii",
        "Cap radius (µm)",
        "Population density (m⁻³)",
        True,
        True,
    )
    s2_rc, s2_rl, s2_ri = s2_resistance_terms(s2_radii, s2_theta, s2_coating, s2_properties)
    s2_resistances = s2_curves(
        s2_radii * 1000000.0,
        {"Coating": s2_rc, "Liquid": s2_rl, "Interface": s2_ri},
        "Single-drop resistance terms",
        "Cap radius (µm)",
        "Denominator resistance (m²K/W)",
        True,
        True,
    )
    ht_layout.row([s2_mo.ui.plotly(s2_populations), s2_mo.ui.plotly(s2_resistances)], minimum=420)
    return


@app.cell
def _(
    s2_conditions,
    s2_curves,
    s2_geometry,
    s2_mo,
    s2_model,
    s2_np,
    s2_properties,
    s2_result,
):
    s2_heights = s2_np.linspace(0.0001, 2 * s2_geometry.radius, 60)
    s2_migration = s2_result.dwc_flux * s2_geometry.dwc_width / s2_properties.latent_heat
    s2_film = [
        s2_model.film_state(
            s2_geometry.fwc_width,
            s2_migration,
            s2_conditions.subcooling,
            float(s2_h),
            s2_properties,
        )
        for s2_h in s2_heights
    ]
    s2_film_plot = s2_curves(
        s2_heights * 1000,
        {"Rivulet maximum thickness": [float(s2_s[0]) * 1000000.0 for s2_s in s2_film]},
        "Rivulet profile · stops at flooding",
        "Distance from top (mm)",
        "Thickness (µm)",
    )
    s2_mo.ui.plotly(s2_film_plot)
    return


@app.cell
def _(s2_benchmark_plot, s2_figure_checks, s2_mo):
    s2_checks = [s2_r for s2_r in s2_figure_checks() if s2_r["case"].startswith("Croce")]
    s2_mo.vstack(
        [
            s2_mo.md(
                "### Reproduction audit\nPaper model curves were read approximately with conservative reading uncertainty. The disagreement is retained; no coefficient was fitted to conceal it. Fixed figure presets are independent of the controls."
            ),
            s2_benchmark_plot(s2_checks, "Published curves vs implemented equations"),
            s2_mo.ui.table(s2_checks),
        ]
    )
    return


@app.cell
def _(
    s2_conditions,
    s2_export_record,
    s2_geometry,
    s2_mo,
    s2_result,
    s2_settings,
    s2_surface,
):
    s2_mo.download(
        s2_export_record(
            "Croce 2024",
            {
                "controls": s2_settings,
                "conditions": s2_conditions,
                "surface": s2_surface,
                "geometry": s2_geometry,
                "equation_convention": "corrected Eqs.8/13",
                "radial_order": 96,
            },
            s2_result,
        ).encode(),
        filename="croce2024-result.json",
        label="Download calculation + provenance",
    )
    return


@app.cell
def _(ht_lee2020, ht_plots, ht_studies):
    import marimo as s3_mo
    import numpy as s3_np
    import plotly.graph_objects as s3_go

    s3_model = ht_lee2020
    s3_curves = ht_plots.curves
    s3_stripe_schematic = ht_plots.stripe_schematic
    s3_style = ht_plots.style
    s3_export_record = ht_studies.export_record
    return s3_curves, s3_export_record, s3_go, s3_mo, s3_model, s3_np, s3_style


@app.cell
def _(s3_mo):
    s3_mo.md(
        "\n    # Recovering water from humid air\n    **Lee et al. · 2020** / A four-hour condensate collection experiment\n\n    [Paper](https://doi.org/10.1016/j.ijheatmasstransfer.2020.120206).\n    Saturated air at 14–15 °C, 0.6 m/s, over a 40 × 40 mm specimen; coolant inlet 5 °C.\n    Eq. (6) predicts **collected mass over four hours**, not a universal mass-transfer rate.\n    The 5 °C wall temperature in the transport calculation is an explicit approximation.\n\n    Measured FWC baseline: **0.400 g/h**. Paper's theoretical baseline: **0.355 g/h**.\n    These are selectable below; the film energy balance is also calculated independently.\n    "
    )
    return


@app.cell
def _(ht_layout, s3_mo):
    s3_controls = (
        ht_layout.controls(['ld', 'lf', 'baseline', 'finite'])
        .batch(
            **{
                "ld": s3_mo.ui.number(0.5, 3.0, step=0.1, value=0.6, label="DWC width (mm)"),
                "lf": s3_mo.ui.number(0.5, 8.5, step=0.1, value=3.4, label="FWC width (mm)"),
                "baseline": s3_mo.ui.dropdown(
                    ["measured", "paper_theory", "transport"],
                    value="measured",
                    label="FWC baseline",
                ),
                "finite": s3_mo.ui.checkbox(value=True, label="Count finite specimen edges"),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    s3_controls
    return (s3_controls,)


@app.cell
def _(s3_controls, s3_model):
    s3_settings = s3_controls.value or {
        "ld": 0.6,
        "lf": 3.4,
        "baseline": "measured",
        "finite": True,
    }
    s3_result = s3_model.solve(
        s3_settings["ld"] * 0.001,
        s3_settings["lf"] * 0.001,
        baseline=s3_settings["baseline"],
        finite=s3_settings["finite"],
    )
    return s3_result, s3_settings


@app.cell
def _(ht_layout, s3_mo, s3_result):
    s3_mo.vstack(
        [
            ht_layout.row(
                [
                    s3_mo.stat(
                        label="Collected in four hours",
                        value=f"{s3_result['mass_4h_kg'] * 1000:.3f} g",
                    ),
                    s3_mo.stat(
                        label="Hydrophilic area fraction", value=f"{s3_result['sar'] * 100:.1f}%"
                    ),
                    s3_mo.stat(
                        label="Internal interface length",
                        value=f"{s3_result['interface_length_m']:.3f} m",
                    ),
                    s3_mo.stat(
                        label="Average recovery", value=f"{s3_result['mass_4h_kg'] * 250:.3f} g/h"
                    ),
                ]
            ),
            s3_mo.callout(
                "Within the implemented width/SAR envelope"
                if s3_result["within_design_envelope"]
                else "Extrapolation: outside the implemented width/SAR envelope",
                kind="info" if s3_result["within_design_envelope"] else "warn",
            ),
        ]
    )
    return


@app.cell
def _(ht_layout, s3_curves, s3_go, s3_mo, s3_model, s3_np, s3_result, s3_style):
    s3_lengths = s3_np.linspace(0, 2.1, 150)
    s3_families = {
        f"SAR {s3_sar:.0%}": s3_np.array(
            [
                s3_model.recovery_from_interface(float(s3_l), s3_sar, s3_result["baseline_g_per_h"])
                * 1000
                for s3_l in s3_lengths
            ]
        )
        for s3_sar in (0.5, 0.6, 0.75, 0.85)
    }
    s3_recovery_plot = s3_curves(
        s3_lengths,
        s3_families,
        "Four-hour recovery · Eq. (5) + Eq. (6)",
        "Internal interface length (m)",
        "Collected mass (g)",
    )
    s3_recovery_plot.add_trace(
        s3_go.Scatter(
            x=[s3_result["interface_length_m"]],
            y=[s3_result["mass_4h_kg"] * 1000],
            mode="markers",
            marker=dict(size=14, color="#182e45"),
            name="Current specimen",
        )
    )
    s3_bars = s3_go.Figure(
        s3_go.Bar(
            x=["Film contribution", "Dropwise contribution"],
            y=[s3_result["fwc_mass_4h_kg"] * 1000, s3_result["dwc_mass_4h_kg"] * 1000],
            marker_color=["#0f766e", "#e97935"],
        )
    )
    s3_style(s3_bars, "Recovery contributions", ylabel="Collected mass (g / 4 h)")
    ht_layout.row([s3_mo.ui.plotly(s3_recovery_plot), s3_mo.ui.plotly(s3_bars)], minimum=420)
    return


@app.cell
def _(s3_mo, s3_result):
    s3_transport = s3_result["film_transport"]
    s3_mo.vstack(
        [
            s3_mo.md(
                "### Independent humid-air energy balance\nSensible + latent heat = film conduction. This calculation uses fixed engineering properties; it is not forced to equal either paper baseline."
            ),
            s3_mo.ui.table(
                [
                    {"quantity": s3_key, "value": s3_value}
                    for s3_key, s3_value in s3_transport.items()
                ]
            ),
            s3_mo.md(
                "The paper reports 1.84 g at 0.6 / 3.4 mm and approximately 2 g for its predicted optimum at 0.5 / 2.8 mm. Finite edge counting and the choice of FWC baseline change the comparison. No transient accumulation law is inferred from this fit."
            ),
        ]
    )
    return


@app.cell
def _(s3_export_record, s3_mo, s3_result, s3_settings):
    s3_mo.download(
        s3_export_record("Lee 2020", s3_settings, s3_result).encode(),
        filename="lee2020-result.json",
        label="Download calculation + provenance",
    )
    return


@app.cell
def _(
    ht_croce2024,
    ht_differentiation,
    ht_optimization,
    ht_plots,
    ht_properties,
    ht_studies,
    ht_types,
    ht_xie2020,
):
    import marimo as s4_mo
    import numpy as s4_np
    import plotly.graph_objects as s4_go

    s4_croce2024 = ht_croce2024
    s4_xie2020 = ht_xie2020
    s4_water = ht_properties.water
    s4_SteamConditions = ht_types.SteamConditions
    s4_Surface = ht_types.Surface
    s4_Geometry = ht_types.Geometry
    s4_optimize_croce = ht_optimization.optimize_croce
    s4_optimize_plate = ht_optimization.optimize_plate
    s4_optimize_lee = ht_optimization.optimize_lee
    s4_optimize_xie = ht_optimization.optimize_xie
    s4_normalized_sensitivity = ht_differentiation.normalized_sensitivity
    s4_croce_heatmap = ht_studies.croce_heatmap
    s4_export_record = ht_studies.export_record
    s4_heatmap = ht_plots.heatmap
    s4_curves = ht_plots.curves
    s4_style = ht_plots.style
    return (
        s4_Geometry,
        s4_SteamConditions,
        s4_Surface,
        s4_croce2024,
        s4_croce_heatmap,
        s4_curves,
        s4_export_record,
        s4_go,
        s4_heatmap,
        s4_mo,
        s4_normalized_sensitivity,
        s4_np,
        s4_optimize_croce,
        s4_optimize_lee,
        s4_optimize_plate,
        s4_optimize_xie,
        s4_style,
        s4_water,
        s4_xie2020,
    )


@app.cell
def _(s4_mo):
    s4_mo.md(
        "\n    # Biphilic surface design explorer\n    **Geometry, drainage, and sensitivity** / NumPy · SciPy · Plotly · Autograd\n\n    Compare steam models under explicitly matched conditions. Lee's humid-air recovery stays\n    in a separate objective. Blank map cells are flooded geometries with no valid Croce flux.\n    **These are model studies, not validated design recommendations:** Croce's published-curve\n    discrepancy and the disk-radius assumption remain unresolved.\n    "
    )
    return


@app.cell
def _(ht_layout, s4_mo):
    s4_controls = (
        ht_layout.controls(['dt', 'coating'])
        .batch(
            **{
                "dt": s4_mo.ui.slider(2.0, 10.0, step=1.0, value=6.0, label="Steam subcooling (K)"),
                "coating": s4_mo.ui.number(
                    0.1, 10.0, step=0.01, value=3.39, label="Coating resistance (×10⁻⁷ m²K/W)"
                ),
            }
        )
        .form(submit_button_label="Update map", show_clear_button=False)
    )
    s4_controls
    return (s4_controls,)


@app.cell
def _(s4_SteamConditions, s4_Surface, s4_controls, s4_croce_heatmap, s4_np):
    s4_settings = s4_controls.value or {"dt": 6.0, "coating": 3.39}
    s4_conditions = s4_SteamConditions(subcooling=s4_settings["dt"])
    s4_surface = s4_Surface(coating_resistance=s4_settings["coating"] * 1e-07)
    s4_ld_values = s4_np.linspace(0.1, 0.9, 10) * 0.001
    s4_lf_values = s4_np.linspace(0.1, 0.7, 9) * 0.001
    s4_flux_map, s4_flood_map = s4_croce_heatmap(
        s4_ld_values, s4_lf_values, s4_conditions, s4_surface
    )
    return (
        s4_conditions,
        s4_flux_map,
        s4_ld_values,
        s4_lf_values,
        s4_settings,
        s4_surface,
    )


@app.cell
def _(s4_flux_map, s4_heatmap, s4_ld_values, s4_lf_values, s4_mo):
    s4_design_map = s4_mo.ui.plotly(
        s4_heatmap(
            s4_ld_values * 1000.0,
            s4_lf_values * 1000.0,
            s4_flux_map,
            "Croce disk model · feasible heat flux",
            "DWC width (mm)",
            "FWC width (mm)",
            "kW/m²",
        )
    )
    s4_mo.vstack(
        [
            s4_design_map,
            s4_mo.md(
                "Flooding is assessed at the longest stripe. The map uses the corrected population equations and published local-angle film closure."
            ),
        ]
    )
    return


@app.cell
def _(
    s4_croce2024,
    s4_go,
    s4_mo,
    s4_normalized_sensitivity,
    s4_np,
    s4_settings,
    s4_style,
    s4_water,
):
    s4_parameters = s4_np.array(
        [0.00055, 0.0006, s4_settings["dt"], s4_settings["coating"] * 1e-07]
    )
    s4_sensitivities = s4_normalized_sensitivity(
        lambda v: s4_croce2024.smooth_plate_flux(v, s4_water()), s4_parameters
    )
    s4_sensitivity_plot = s4_go.Figure(
        s4_go.Bar(
            x=["DWC width", "FWC width", "Subcooling", "Coating resistance"],
            y=s4_sensitivities,
            marker_color=["#0f766e" if s4_x >= 0 else "#e97935" for s4_x in s4_sensitivities],
        )
    )
    s4_style(
        s4_sensitivity_plot,
        "Autograd · normalized local sensitivities",
        ylabel="∂ln(flux) / ∂ln(parameter)",
    )
    s4_mo.vstack(
        [
            s4_mo.ui.plotly(s4_sensitivity_plot),
            s4_mo.md(
                "Sensitivities use a **20 mm tall rectangular plate**, widths 0.55 / 0.60 mm, and fixed 100 °C fluid properties. Nucleation and film roots are implicitly differentiated. This smooth extension avoids discrete disk stripe counts; it is not the paper's disk optimization."
            ),
        ]
    )
    return


@app.cell
def _(
    s4_Geometry,
    s4_conditions,
    s4_croce2024,
    s4_curves,
    s4_mo,
    s4_np,
    s4_surface,
    s4_xie2020,
):
    s4_comparison_widths = s4_np.linspace(0.1, 1.2, 20) * 0.001
    s4_comparison_xie = [
        s4_xie2020.solve(s4_conditions, s4_surface, s4_Geometry(float(s4_w), 0.00045), dx=4e-06)
        for s4_w in s4_comparison_widths
    ]
    s4_comparison_croce = [
        s4_croce2024.solve(s4_conditions, s4_surface, s4_Geometry(float(s4_w), 0.00045))
        for s4_w in s4_comparison_widths
    ]
    s4_comparison_plot = s4_curves(
        s4_comparison_widths * 1000.0,
        {
            "Xie · fixed nucleation density": [s4_r.heat_flux / 1000 for s4_r in s4_comparison_xie],
            "Croce · coating-dependent nucleation": [
                s4_r.heat_flux / 1000 for s4_r in s4_comparison_croce
            ],
        },
        "Matched steam conditions · distinct model assumptions",
        "DWC width (mm)",
        "Heat flux (kW/m²)",
    )
    s4_mo.vstack(
        [
            s4_mo.ui.plotly(s4_comparison_plot),
            s4_mo.md(
                "Both curves use 100 °C saturation properties, the selected subcooling/coating, a 10 mm radius, and 0.45 mm FWC stripes. Departure, nucleation, population and film assumptions remain paper-specific."
            ),
        ]
    )
    return


@app.cell
def _(s4_mo):
    s4_run_search = s4_mo.ui.run_button(label="Run constrained geometry searches")
    s4_run_search
    return (s4_run_search,)


@app.cell
def _(
    s4_conditions,
    s4_export_record,
    s4_mo,
    s4_optimize_croce,
    s4_optimize_lee,
    s4_optimize_plate,
    s4_optimize_xie,
    s4_run_search,
    s4_settings,
    s4_surface,
    s4_water,
):
    s4_mo.stop(
        not s4_run_search.value,
        s4_mo.md(
            "Run the searches to compare a flooding-constrained disk design, an Autograd plate refinement, and Lee's finite-stripe recovery optimum."
        ),
    )
    s4_disk_optimum = s4_optimize_croce(s4_conditions, s4_surface, grid_size=20)
    s4_plate_optimum = s4_optimize_plate(
        [0.00055, 0.0006, s4_settings["dt"], s4_settings["coating"] * 1e-07], s4_water()
    )
    s4_lee_optimum = s4_optimize_lee()
    s4_xie_optimum = s4_optimize_xie(s4_conditions, s4_surface, grid_size=20)
    s4_search_results = {
        "croce_disk": s4_disk_optimum,
        "croce_plate_extension": s4_plate_optimum,
        "xie_fixed_fwc": s4_xie_optimum,
        "lee_mass": s4_lee_optimum,
    }
    s4_mo.vstack(
        [
            s4_mo.md(
                "### Search results\nEach objective retains its own units and model assumptions. Disk optima are re-evaluated with adaptive radial quadrature."
            ),
            s4_mo.json(s4_search_results),
            s4_mo.download(
                s4_export_record("Design searches", s4_settings, s4_search_results).encode(),
                filename="design-searches.json",
                label="Download search results",
            ),
        ]
    )
    return


@app.cell
def _(
    ht_croce2024,
    ht_droplets,
    ht_geometry,
    ht_lee2020,
    ht_optimization,
    ht_populations,
    ht_properties,
    ht_studies,
    ht_types,
    ht_xie2020,
):
    def _build():

        from contextlib import contextmanager
        import itertools
        import time

        class _Approx:
            def __init__(self, expected, rel=1e-6, abs=1e-12):
                self.expected, self.rel, self.abs = expected, rel, abs

            def __eq__(self, actual):
                return bool(np.allclose(actual, self.expected, rtol=self.rel, atol=self.abs))

        @contextmanager
        def _raises(exception):
            try:
                yield
            except exception:
                pass
            else:
                raise AssertionError(f"Expected {exception.__name__}")

        def _parametrize(name, values):
            def decorate(fn):
                fn.cases = [{name: value} for value in values]
                return fn

            return decorate

        from dataclasses import replace

        import numpy as np

        from autograd import grad
        from autograd.numpy import exp as np_exp
        from autograd.numpy import log as np_log

        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        Surface = ht_types.Surface
        water = ht_properties.water
        croce = ht_croce2024
        lee = ht_lee2020
        xie = ht_xie2020
        critical_radius = ht_droplets.critical_radius
        growth_coefficients = ht_droplets.growth_coefficients
        heat_rate = ht_droplets.heat_rate
        finite_stripes = ht_geometry.finite_stripes
        flux_components = ht_populations.flux_components
        large_distribution = ht_populations.large_distribution
        small_distribution = ht_populations.small_distribution

        def test_population_boundary_and_slope():
            p = water()
            theta = np.deg2rad(120)
            dt = 6.0
            coat = 3.39e-7
            r0 = critical_radius(dt, p)
            rn = croce.nucleation_radius(dt, theta, coat, p)
            re = rn / (2 * np.sqrt(0.037))
            rm = 0.00125
            a, b = growth_coefficients(dt, theta, coat, p)
            for linear in (False, True):

                def fn(r):
                    return small_distribution(r, re, r0, rm, a, b, linear)

                assert fn(re) == _Approx(large_distribution(re, rm))
                assert grad(lambda log_r: np_log(fn(np_exp(log_r))))(np.log(re)) == _Approx(
                    -8 / 3, rel=1e-10
                )

        def test_nucleation_stationary_maximum_and_trends():
            p = water()
            v = np.array([6.0, 2 * np.pi / 3, 3.39e-7])
            rn = croce.nucleation_radius(*v, p)
            z = np.log(rn / critical_radius(v[0], p))
            assert abs(grad(croce.availability_scaled, 0)(z, v, p)) < 1e-7
            assert grad(grad(croce.availability_scaled, 0), 0)(z, v, p) < 0
            assert rn > croce.nucleation_radius(6.0, v[1], 0.0, p) > critical_radius(6.0, p)

        @_parametrize("linear", [False, True])
        def test_radial_reference_convergence(linear):
            p = water()
            theta = 2 * np.pi / 3
            dt = 6.0
            coat = 3.39e-7
            rn = croce.nucleation_radius(dt, theta, coat, p) if linear else critical_radius(dt, p)
            re = rn / (2 * np.sqrt(0.037)) if linear else 1e-6
            args = (dt, theta, coat, p, rn, re, 0.00125)
            q64 = sum(flux_components(*args, linear=linear, order=64))
            q128 = sum(flux_components(*args, linear=linear, order=128))
            ref = sum(flux_components(*args, linear=linear, reference=True))
            assert q128 == _Approx(ref, rel=5e-3)
            assert q64 == _Approx(q128, rel=5e-3)

        def test_rivulet_cross_section_and_mass_energy():
            p = water()
            width = 0.00045
            dt = 6.0
            migration = 1e-4
            height = 0.02
            assert croce.rivulet_factor(1e-6) == _Approx(16 / 35, rel=1e-7)
            assert croce.film_flow(width / 2, width, p) == _Approx(
                croce.critical_flow(width, p), rel=1e-7
            )
            delta, out, qf, ratio = croce.film_state(width, migration, dt, height, p)
            assert delta > 0 and qf > 0 and ratio < 1
            assert out == _Approx(
                migration * height + qf * height * width / p.latent_heat, rel=1e-12
            )
            assert croce.film_height_relation(delta, width, migration, dt, p) == _Approx(
                height, rel=1e-9
            )
            assert croce.film_state(width, 0, dt, height, p)[2] > qf

        def test_flooding_is_not_extrapolated():
            r = croce.solve(geometry=Geometry(0.0005, 0.00003))
            assert not r.valid and np.isnan(r.heat_flux) and r.flooding_ratio > 1
            w = croce.minimum_fwc_width(0.0005, 6.0, 2 * np.pi / 3, 3.39e-7, water(), 0.02)
            r = croce.solve(geometry=Geometry(0.0005, w * 1.001))
            assert r.valid and r.flooding_ratio < 1

        def test_xie_partial_transfer_and_spatial_convergence():
            c, s, g = xie.preset()
            g = replace(g, dwc_width=0.003)
            r = xie.solve(c, s, g, dx=2e-6)
            fine = xie.solve(c, s, g, dx=1e-6)
            assert 0 < fine.transferred_flux < fine.dwc_flux
            assert fine.heat_flux == _Approx(r.heat_flux, rel=0.005)
            q = xie.stripe_profile(c, s, g, dx=4e-6)
            assert q["weights"].sum() == _Approx(1)
            assert np.all(q["rmax"] <= q["sliding_radius"])

        @_parametrize("model", [xie, croce])
        def test_endpoints(model):
            assert model.solve(SteamConditions(subcooling=0)).heat_flux == 0
            for g in (Geometry(0, 0.001), Geometry(0.001, 0)):
                r = model.solve(geometry=g)
                assert r.valid and np.isfinite(r.heat_flux) and r.heat_flux > 0

        def test_lee_finite_geometry_mass_and_balance():
            g = finite_stripes(0.0006, 0.0034)
            assert g["sar"] == _Approx(0.85)
            assert g["interface_length"] == _Approx(0.76)
            r = lee.solve()
            film = r["film_transport"]
            assert r["mass_4h_kg"] == _Approx(r["fwc_mass_4h_kg"] + r["dwc_mass_4h_kg"])
            assert abs(film["energy_residual"]) < 1e-7
            assert r["mass_4h_kg"] == _Approx(0.00184, rel=0.08)
            assert lee.solve(0.0005, 0.0028)["mass_4h_kg"] == _Approx(0.002, rel=0.04)
            assert lee.dwc_mass_4h(0.0) == 0
            assert lee.dwc_mass_4h(10.0) == _Approx(0.000695)
            assert lee.solve(baseline="paper_theory")["mass_4h_kg"] < r["mass_4h_kg"]

        def test_implicit_autograd_against_finite_differences():
            p = water()
            v = np.array([0.00055, 0.00045, 6.0, 3.39e-7])

            def fn(z):
                return croce.smooth_plate_flux(z, p)

            analytic = grad(fn)(v)
            for i in range(4):
                h = abs(v[i]) * 1e-4
                vp = v.copy()
                vm = v.copy()
                vp[i] += h
                vm[i] -= h
                numeric = (fn(vp) - fn(vm)) / (2 * h)
                assert analytic[i] == _Approx(numeric, rel=1e-3)

        def test_invalid_inputs():
            with _raises(ValueError):
                Geometry(-1, 0.001)
            with _raises(ValueError):
                Surface(receding=3.0)
            with _raises(ValueError):
                water(350)
            with _raises(ValueError):
                lee.film_balance(wall_c=20)

        def test_single_drop_energy_and_coating():
            p = water()
            r = 1e-5
            dt = 6.0
            theta = 2 * np.pi / 3
            r0 = critical_radius(dt, p)
            assert heat_rate(r0, dt, theta, 0.0, p) == 0
            assert heat_rate(r, dt, theta, 1e-7, p) < heat_rate(r, dt, theta, 0.0, p)
            a, b = growth_coefficients(dt, theta, 1e-7, p)
            growth = a * (r - r0) / (r * (r + b))
            dvolume = np.pi * r * r * (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
            assert heat_rate(r, dt, theta, 1e-7, p) == _Approx(
                p.rho_l * p.latent_heat * dvolume * growth
            )

        import numpy as np

        croce = ht_croce2024
        water = ht_properties.water
        optimize_croce = ht_optimization.optimize_croce
        optimize_lee = ht_optimization.optimize_lee
        optimize_plate = ht_optimization.optimize_plate
        export_record = ht_studies.export_record

        def test_plate_optimizer_and_reference_recheck():
            r = optimize_plate([0.00055, 0.0006, 6.0, 3.39e-7])
            assert r["success"]
            assert r["feasibility"] >= -1e-7
            ld, lf, dt, coat = r["parameters"]
            p = water()
            theta = 2 * np.pi / 3
            qd = sum(
                croce.dwc_components(dt, theta, coat, p, ld / (2 * np.sin(theta)), reference=True)
            )
            qf = croce.film_state(lf, qd * ld / p.latent_heat, dt, 0.02, p)[2]
            ref = (qd * ld + qf * lf) / (ld + lf)
            assert r["flux"] == _Approx(ref, rel=0.005)

        def test_disk_optimizer_beats_grid_and_is_feasible():
            r = optimize_croce(grid_size=8)
            assert r["result"]["valid"]
            assert r["result"]["flooding_ratio"] < 1
            assert r["result"]["heat_flux"] >= max(r["grid_fluxes"]) * 0.999

        def test_lee_search_stays_in_envelope():
            r = optimize_lee()
            assert r["result"]["within_design_envelope"]
            assert r["dwc_width"] >= 0.0005
            assert r["result"]["mass_4h_kg"] == _Approx(0.002, rel=0.05)

        def test_json_invalid_flux_is_null():
            import json

            record = json.loads(export_record("test", {}, {"flux": float("nan")}))
            assert record["result"]["flux"] is None

        def run():
            rows = []
            for name, fn in tests_registry:
                for case in getattr(fn, "cases", [{}]):
                    start = time.perf_counter()
                    fn(**case)
                    rows.append(
                        {
                            "check": name.removeprefix("test_"),
                            "case": str(case),
                            "status": "PASS",
                            "seconds": round(time.perf_counter() - start, 3),
                        }
                    )
            return rows

        tests_registry = [
            (name, value) for name, value in locals().items() if name.startswith("test_")
        ]
        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_checks = _build()
    return (ht_checks,)


@app.cell
def _(mo):
    mo.md(
        "## Numerical verification\nRun the embedded regression suite: quadrature, conservation, limiting cases, implicit gradients, flooding, and constrained optimization. Assertion failures stop the check; passing does not resolve the publication discrepancies."
    )
    check_button = mo.ui.run_button(label="Run all numerical checks")
    mo.vstack(
        [
            mo.md(
                "## Numerical verification\nRun the embedded regression suite: quadrature, conservation, limiting cases, implicit gradients, flooding, and optimization."
            ),
            check_button,
        ]
    )
    return (check_button,)


@app.cell
def _(check_button, ht_checks, mo):
    import sys as _sys

    mo.stop(
        not check_button.value and "--self-test" not in _sys.argv, mo.md("Checks are ready to run.")
    )
    check_results = ht_checks.run()
    print(f"{len(check_results)} / {len(check_results)} numerical checks passed")
    mo.vstack(
        [
            mo.md(f"**{len(check_results)} / {len(check_results)} checks passed**"),
            mo.ui.table(check_results, selection=None),
        ]
    )
    return


@app.cell
def _(
    ht_croce2024,
    ht_droplets,
    ht_optimization,
    ht_plots,
    ht_properties,
    ht_studies,
    ht_types,
    ht_xie2020,
):
    def _build():
        from dataclasses import replace

        import numpy as np

        Geometry = ht_types.Geometry
        SteamConditions = ht_types.SteamConditions
        water = ht_properties.water
        croce = ht_croce2024
        xie = ht_xie2020
        heat_rate = ht_droplets.heat_rate
        optimize_croce = ht_optimization.optimize_croce
        benchmark_plot = ht_plots.benchmark_plot
        curves = ht_plots.curves
        heatmap = ht_plots.heatmap
        export_record = ht_studies.export_record
        figure_checks = ht_studies.figure_checks

        _figures = []

        def save(name, fig, inputs, result):
            _figures.append((name, fig, export_record(name, inputs, result)))

        def run(paper):
            _figures.clear()
            if paper == "Croce":
                croce_figures()
            else:
                xie_figures()
            return list(_figures)

        def croce_figures():
            p = water()
            theta = 2 * np.pi / 3
            dt_values = np.linspace(0.5, 10, 24)
            coats = (0.0, 1e-7, 1e-6, 1e-5)
            series = {
                f"Rcoat={coat:g}": [
                    croce.nucleation_radius(float(dt), theta, coat, p) * 1e6 for dt in dt_values
                ]
                for coat in coats
            }
            save(
                "croce_fig3_nucleation",
                curves(
                    dt_values,
                    series,
                    "Croce Fig.3 study · nucleation radius",
                    "Subcooling (K)",
                    "Radius (µm)",
                    logy=True,
                ),
                {"temperature_K": 373.15, "theta_deg": 120, "coating_resistances": coats},
                {"subcooling_K": dt_values, "series": series},
            )
            radii = np.geomspace(1e-8, 1e-3, 120)
            series = {
                f"Rcoat={coat:g}": heat_rate(radii, 6.0, theta, coat, p) / (np.pi * radii * radii)
                for coat in coats
            }
            save(
                "croce_fig4_single_drop",
                curves(
                    radii * 1e6,
                    series,
                    "Croce Fig.4a study · heat rate / πr²",
                    "Radius (µm)",
                    "W/m²",
                    True,
                    True,
                ),
                {"temperature_K": 373.15, "subcooling_K": 6.0, "normalization": "pi*r^2"},
                {"radii_m": radii, "series": series},
            )
            series = {
                f"Rcoat={coat:g}": [
                    sum(croce.dwc_components(float(dt), theta, coat, p, 0.00125)) / 1000
                    for dt in dt_values
                ]
                for coat in (0.0, 1e-8, 1e-7, 1e-6)
            }
            save(
                "croce_fig5_dwc",
                curves(
                    dt_values, series, "Croce Fig.5 study · pure DWC", "Subcooling (K)", "kW/m²"
                ),
                {"rmax_m": 0.00125, "formula_convention": "corrected Eqs.8/13"},
                {"subcooling_K": dt_values, "series": series},
            )
            widths = np.linspace(0.1, 1.5, 28) * 1e-3
            series = {
                f"ΔT={dt:g} K": [
                    croce.solve(
                        SteamConditions(subcooling=dt), geometry=Geometry(float(w), 0.00045)
                    ).heat_flux
                    / 1000
                    for w in widths
                ]
                for dt in (2.0, 4.0, 6.0, 8.0, 10.0)
            }
            save(
                "croce_fig9_width",
                curves(
                    widths * 1e3,
                    series,
                    "Croce Fig.9 study · fixed FWC width",
                    "DWC width (mm)",
                    "kW/m²",
                ),
                {"fwc_width_m": 0.00045, "radius_m": 0.01},
                {"dwc_widths_m": widths, "series": series},
            )
            optima = [
                optimize_croce(SteamConditions(subcooling=dt), margin=0.0, grid_size=18)
                for dt in (2.0, 4.0, 6.0, 8.0, 10.0)
            ]
            series = {
                f"ΔT={dt:g} K": np.array(r["grid_fluxes"]) / 1000
                for dt, r in zip((2, 4, 6, 8, 10), optima)
            }
            save(
                "croce_fig10_boundary",
                curves(
                    np.array(optima[0]["grid_widths"]) * 1e3,
                    series,
                    "Croce Fig.10 study · flooding boundary",
                    "DWC width (mm)",
                    "kW/m²",
                    True,
                ),
                {"margin": 0, "radius_m": 0.01},
                {"optima": optima},
            )

        def xie_figures():
            c, s, g = xie.preset()
            widths = np.geomspace(0.05e-3, 3e-3, 32)
            results = {
                mode: xie.sweep_widths(widths, c, s, g, mode=mode, dx=4e-6)
                for mode in ("dss", "oss", "mixed")
            }
            series = {
                mode: [r.heat_flux / c.subcooling / 1000 for r in rows]
                for mode, rows in results.items()
            }
            save(
                "xie_fig4_7_modes",
                curves(
                    widths * 1e3,
                    series,
                    "Xie Figs.4/7 study · departure modes",
                    "DWC width (mm)",
                    "HTC (kW/m²K)",
                    True,
                ),
                {"conditions": c, "surface": s, "geometry": g, "dx_m": 4e-6},
                {"dwc_widths_m": widths, "results": results},
            )
            coats = np.geomspace(1e-9, 1e-6, 16)
            fws = np.geomspace(0.1e-3, 1e-3, 9)
            candidates = np.geomspace(0.05e-3, 1.5e-3, 18)
            ratios = []
            best_widths = []
            for lf in fws:
                ratio_row = []
                width_row = []
                for thickness in coats:
                    surf = replace(s, coating_resistance=float(thickness) / 0.2)
                    pure = xie.solve(c, surf, Geometry(0.001, 0)).heat_flux
                    rs = xie.sweep_widths(
                        candidates, c, surf, replace(g, fwc_width=float(lf)), dx=8e-6
                    )
                    best = int(np.argmax([r.heat_flux for r in rs]))
                    ratio_row.append(rs[best].heat_flux / pure)
                    width_row.append(candidates[best] * 1000)
                ratios.append(ratio_row)
                best_widths.append(width_row)
            save(
                "xie_fig13_15_regime",
                heatmap(
                    np.log10(coats * 1e9),
                    fws * 1e3,
                    ratios,
                    "Xie Figs.13–15 study · optimized enhancement",
                    "log10 coating thickness (nm)",
                    "FWC width (mm)",
                    "qhybrid / qDWC",
                ),
                {"conditions": c, "radius_m": 0.01, "dx_m": 8e-6, "candidate_widths_m": candidates},
                {
                    "coating_thicknesses_m": coats,
                    "fwc_widths_m": fws,
                    "enhancement": ratios,
                    "optimal_dwc_mm": best_widths,
                },
            )

        from types import SimpleNamespace

        return SimpleNamespace(**locals())

    ht_figure_studies = _build()
    return (ht_figure_studies,)


@app.cell
def _(mo):
    mo.md(
        "## Extended paper figure studies\nOptional, longer calculations: coating/nucleation, single drops, regimes and departure modes. These retain the original sampled grids and assumptions; they are not exact reproductions of the paper figures."
    )
    study_form = mo.ui.dropdown(["Croce", "Xie"], value="Croce", label="Paper study").form(
        submit_button_label="Generate extended studies"
    )
    mo.vstack(
        [
            mo.md(
                "## Extended paper figure studies\nOptional longer calculations using the original sampled grids and assumptions."
            ),
            study_form,
        ]
    )
    return (study_form,)


@app.cell
def _(ht_figure_studies, mo, study_form):
    mo.stop(
        study_form.value is None,
        mo.md("Choose a paper and generate its extended studies when needed."),
    )
    study_figures = ht_figure_studies.run(study_form.value)
    mo.vstack(
        [
            mo.vstack(
                [
                    mo.md("### " + name),
                    mo.ui.plotly(fig),
                    mo.download(
                        record.encode(), filename=name + ".json", label="Download study data"
                    ),
                ]
            )
            for name, fig, record in study_figures
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Equations and conventions

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
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## References and existing implementations

    ## Attached papers

    - Xie, She, Xu, Liang & Li (2020). *Mixed dropwise-filmwise condensation heat transfer on biphilic surface*. [DOI](https://doi.org/10.1016/j.ijheatmasstransfer.2019.119273).
    - Croce & Suzzi (2024). *Optimization of Dropwise Condensation of Steam over Hybrid Hydrophobic-Hydrophilic Surfaces via Enhanced Statistically Based Heat Transfer Modelization*. [DOI](https://doi.org/10.3390/en17112742).
    - Lee, Lee & Lee (2020). *Improved humid air condensation heat transfer through promoting condensate drainage on vertically stripe patterned bi-philic surfaces*. [DOI](https://doi.org/10.1016/j.ijheatmasstransfer.2020.120206).

    The source PDFs remain local and are ignored by Git. Approximate model-line readings and cited scientific formulas are included; full paper text and figures are not redistributed.

    ## Supporting models

    - [Kim & Kim 2011](https://doi.org/10.1115/1.4003742): single-drop resistances and population balance.
    - [Liu & Cheng 2015, Part I](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.009) and [Part II](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.008): coating-dependent nucleation and population density.
    - [Peng et al. 2014](https://doi.org/10.1016/j.ijheatmasstransfer.2014.05.052): hybrid DWC/FWC model.
    - Peng et al. 2015, IJHMT 83, 27-38: common steam experimental benchmark cited by Xie and Croce. Comparisons against the two papers are not independent experimental validation datasets.
    - [Croce & Suzzi 2023](https://air.uniud.it/handle/11390/1269787): individual-droplet simulation background.
    - [Suzzi & Croce 2024 companion paper](https://doi.org/10.1088/1742-6596/2766/1/012143): coating and revised populations.

    ## Public code examined

    - [JSablowski/DWCmod](https://github.com/JSablowski/DWCmod), MIT, revision `b18786ffc7d824e42407137c56c7c609d5d4cd75`. Used as an independently executed Kim-Kim numerical check, not vendored. The recorded validation evidence below preserves the comparison. Its pressure inputs are mbar and nucleation density uses 1e9/m2, so unit conversion is explicit.
    - [CalebBell/ht](https://github.com/CalebBell/ht) and [condensation documentation](https://ht.readthedocs.io/en/latest/ht.condensation.html): Nusselt correlation reference.
    - [CoolProp](https://github.com/CoolProp/CoolProp) and [humid-air documentation](https://coolprop.org/fluid_properties/HumidAir.html): property reference used for the independent native baseline; this portable notebook uses embedded saturation tables.
    - [MahdiNabil/CFD-PC](https://github.com/MahdiNabil/CFD-PC): related OpenFOAM phase-change work, not a dependency.
    - [HIPS/autograd](https://github.com/HIPS/autograd): differentiable NumPy and custom primitive derivatives.
    - [marimo documentation](https://docs.marimo.io/guides/working_with_data/plotting/): reactive Plotly interface.

    No verified public repository implementing the exact three attached papers was found in the planning search. No upstream solver is claimed to be author code for these papers.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Recorded validation evidence

    Run date: 2026-09-21. The implementation is numerically verified but **not a complete reproduction of all published results**. In particular, Croce Fig.7a remains inconsistent with the implemented equations. No fitting parameter was changed to conceal this discrepancy.

    ## Numerical evidence

    - 17 tests pass: population value/slope matching, availability maximum, radial quadrature convergence, spatial refinement, limiting cases, implicit derivatives, film mass/energy accounting, flooding rejection, Lee mass units/finite geometry, optimizer feasibility, and strict JSON serialization.
    - Four first-order Autograd derivatives of the smooth plate heat flux agree with centered finite differences to a maximum relative difference of approximately **8.1e-9** at the recorded test point. This is a local check, not a proof over every parameter or branch.
    - The independent Kim–Kim baseline matches DWCmod revision `b18786ffc7d824e42407137c56c7c609d5d4cd75` to about **3.0e-8 relative error** at 2, 6 and 10 K subcooling with matched CoolProp properties, radii and coating. This checks the common baseline, not the exact Xie/Croce models.
    - All four marimo notebooks passed static checks and executed through HTML export. Live browser checks exercised an input change in Xie and the design explorer's optimization action.
    - Both constrained searches are checked for feasibility; the smooth plate optimizer reports successful convergence. The disk optimizer uses a sampled search and local refinement across a discrete stripe-count geometry and is not guaranteed globally optimal.

    ## Approximate published model-curve checks

    Values below are manual readings of **model lines**, not raw experimental measurements. The source is the embedded `ht_studies.FIGURE_DATA`, with 15-20 kW/m2 reading uncertainty. Disk radius is assumed 10 mm. Error is `(computed/paper)-1`.

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
    5. Extend quantitative validation beyond the sampled figures, including independent data and broad parameter ranges. The embedded extended figure studies support this work but does not replace it.

    The original native validation snapshot is embedded below. Run this notebook's numerical verification section for current checks.
    """)
    return


@app.cell
def _(mo):
    import json as _json

    recorded_evidence = {
        "run_date": "2026-09-21",
        "validation": {
            "model": "Validation and exploratory optimization",
            "inputs": {"plate_parameters": [0.00055, 0.0006, 6.0, 3.39e-07]},
            "result": {
                "paper_curve_checks": [
                    {
                        "case": "Croce Fig.7a",
                        "page": 11,
                        "subcooling_K": 2,
                        "paper_flux_W_m2": 180000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 228972.07617851335,
                        "relative_error": 0.27206708988062966,
                    },
                    {
                        "case": "Croce Fig.7a",
                        "page": 11,
                        "subcooling_K": 4,
                        "paper_flux_W_m2": 375000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 508724.5920558907,
                        "relative_error": 0.3565989121490418,
                    },
                    {
                        "case": "Croce Fig.7a",
                        "page": 11,
                        "subcooling_K": 6,
                        "paper_flux_W_m2": 580000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 803814.7475133847,
                        "relative_error": 0.3858874957127323,
                    },
                    {
                        "case": "Croce Fig.8b",
                        "page": 12,
                        "subcooling_K": 2,
                        "paper_flux_W_m2": 210000,
                        "reading_uncertainty_W_m2": 20000,
                        "computed_flux_W_m2": 207189.22597245508,
                        "relative_error": -0.013384638226404344,
                    },
                    {
                        "case": "Croce Fig.8b",
                        "page": 12,
                        "subcooling_K": 4,
                        "paper_flux_W_m2": 435000,
                        "reading_uncertainty_W_m2": 20000,
                        "computed_flux_W_m2": 453531.8118086485,
                        "relative_error": 0.042601866226778196,
                    },
                    {
                        "case": "Croce Fig.8b",
                        "page": 12,
                        "subcooling_K": 6,
                        "paper_flux_W_m2": 660000,
                        "reading_uncertainty_W_m2": 20000,
                        "computed_flux_W_m2": 712148.3097183818,
                        "relative_error": 0.07901259048239684,
                    },
                    {
                        "case": "Xie Fig.5a",
                        "page": 10,
                        "subcooling_K": 2,
                        "paper_flux_W_m2": 190000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 192321.41876667933,
                        "relative_error": 0.012217993508838676,
                    },
                    {
                        "case": "Xie Fig.5a",
                        "page": 10,
                        "subcooling_K": 4,
                        "paper_flux_W_m2": 385000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 381547.66722605017,
                        "relative_error": -0.008967098114155414,
                    },
                    {
                        "case": "Xie Fig.5a",
                        "page": 10,
                        "subcooling_K": 6,
                        "paper_flux_W_m2": 585000,
                        "reading_uncertainty_W_m2": 15000,
                        "computed_flux_W_m2": 569789.7707881589,
                        "relative_error": -0.026000391815113044,
                    },
                ],
                "croce_default": {
                    "model": "Croce 2024",
                    "heat_flux": 712148.3097183822,
                    "dwc_flux": 1262856.8073708706,
                    "fwc_flux": 39060.14592089623,
                    "htc": 118691.3849530637,
                    "film_thickness": 0.00013704191491064347,
                    "transferred_flux": 1262856.8073708706,
                    "flooding_ratio": 0.19343493574488282,
                    "valid": True,
                    "notes": [
                        "Eqs.8/13 corrected; local-angle film closure; disk-center quadrature",
                        "Specimen radius is an explicit assumption; see preset provenance",
                    ],
                },
                "xie_default": {
                    "model": "Xie 2020",
                    "heat_flux": 637248.0609258454,
                    "dwc_flux": 1244181.0711376213,
                    "fwc_flux": 30315.050714069515,
                    "htc": 127449.61218516908,
                    "film_thickness": 0.00010777667559116189,
                    "transferred_flux": 1244181.0711376213,
                    "flooding_ratio": 0.0,
                    "valid": True,
                    "notes": [
                        "Uniform-film model; flooding is not predicted",
                        "Drop convention: kim",
                    ],
                },
                "lee_default": {
                    "model": "Lee 2020",
                    "mass_4h_kg": 0.0018892509625885899,
                    "fwc_mass_4h_kg": 0.0013599999999999999,
                    "dwc_mass_4h_kg": 0.0005292509625885899,
                    "average_kg_per_s": 1.311979835130965e-07,
                    "sar": 0.8499999999999999,
                    "interface_length_m": 0.76,
                    "baseline": "measured",
                    "baseline_g_per_h": 0.4,
                    "within_design_envelope": True,
                    "finite_geometry": True,
                    "film_transport": {
                        "interface_temperature_c": 5.042750598284328,
                        "sensible_flux": 133.88134579637946,
                        "latent_flux": 168.84735975097533,
                        "conduction_flux": 302.72870554735283,
                        "thickness": 8.190616400277765e-05,
                        "recovery_4h_kg": 0.001570546293363937,
                        "energy_residual": 1.9895196601282805e-12,
                    },
                    "segments": [
                        [0.0, 0.0006, "DWC"],
                        [0.0006, 0.004, "FWC"],
                        [0.004, 0.0046, "DWC"],
                        [0.0046, 0.008, "FWC"],
                        [0.008, 0.0086, "DWC"],
                        [0.0086, 0.012, "FWC"],
                        [0.012, 0.0126, "DWC"],
                        [0.0126, 0.016, "FWC"],
                        [0.016, 0.0166, "DWC"],
                        [0.0166, 0.02, "FWC"],
                        [0.02, 0.0206, "DWC"],
                        [0.0206, 0.024, "FWC"],
                        [0.024, 0.0246, "DWC"],
                        [0.0246, 0.028, "FWC"],
                        [0.028, 0.0286, "DWC"],
                        [0.0286, 0.032, "FWC"],
                        [0.032, 0.032600000000000004, "DWC"],
                        [0.032600000000000004, 0.036000000000000004, "FWC"],
                        [0.036000000000000004, 0.03660000000000001, "DWC"],
                        [0.03660000000000001, 0.04, "FWC"],
                    ],
                    "notes": [
                        "Four-hour calibrated mass; not a transient or arbitrary-RH model",
                        "40 mm square; starts with DWC at left edge",
                        "Film model assumes wall 5 C; paper specifies coolant inlet 5 C",
                    ],
                },
                "autograd": [
                    184093335.8585691,
                    -488586033.5171933,
                    114989.07058753722,
                    -1041588472888.4661,
                ],
                "finite_difference": [
                    184093337.34730765,
                    -488586034.91486675,
                    114989.07056908743,
                    -1041588479411.585,
                ],
                "croce_optimization": {
                    "dwc_width": 0.0004373899054134384,
                    "fwc_width": 0.0002930302440959085,
                    "result": {
                        "model": "Croce 2024",
                        "heat_flux": 827191.5911672071,
                        "dwc_flux": 1361191.2907097947,
                        "fwc_flux": 30120.0165440393,
                        "htc": 137865.26519453453,
                        "film_thickness": 0.00014315197787821105,
                        "transferred_flux": 1361191.2907097947,
                        "flooding_ratio": 0.9238454260270219,
                        "valid": True,
                        "notes": [
                            "Eqs.8/13 corrected; local-angle film closure; disk-center quadrature",
                            "Specimen radius is an explicit assumption; see preset provenance",
                        ],
                    },
                    "grid_widths": [
                        5e-05,
                        6.0714014672692926e-05,
                        7.372383155351929e-05,
                        8.952139581335026e-05,
                        0.000108704066778634,
                        0.0001319972061075874,
                        0.0001602816061674107,
                        0.00019462679577221908,
                        0.00023633148268427438,
                        0.00028697266214624596,
                        0.0003484652484041786,
                        0.00042313448409069725,
                        0.000513803865512099,
                        0.0006239019085917579,
                        0.0007575917926512215,
                        0.0009199287842987601,
                        0.0011170513941549498,
                        0.001356413494697513,
                        0.0016470661763860685,
                        0.002,
                    ],
                    "grid_fluxes": [
                        567618.4013406304,
                        603360.8240021763,
                        638591.047227479,
                        672677.4678935426,
                        704938.7345001586,
                        734671.1789284548,
                        761183.1475757544,
                        783928.7153513998,
                        802161.7517614156,
                        815644.1868534159,
                        824000.6686132867,
                        827119.0422096954,
                        825143.0634663845,
                        818196.8755250513,
                        806630.8323755484,
                        790911.187187013,
                        771641.6931499679,
                        749324.1271343183,
                        724549.2166769201,
                        697931.4874766602,
                    ],
                    "margin": 0.02,
                    "method": "grid + bounded local search, reference radial quadrature",
                    "scope": "Disk Eq.29 has discrete stripe-count changes; no global-optimum guarantee",
                },
                "plate_optimization": {
                    "parameters": [0.0004270796130333979, 0.00028756837871101614, 6.0, 3.39e-07],
                    "success": True,
                    "message": "Optimization terminated successfully",
                    "flux": 830740.3476349574,
                    "feasibility": -1.7763568394002505e-15,
                    "scope": "Smooth rectangular-plate extension",
                },
                "lee_optimization": {
                    "dwc_width": 0.0005,
                    "fwc_width": 0.0028333333333333327,
                    "result": {
                        "model": "Lee 2020",
                        "mass_4h_kg": 0.001966214401884607,
                        "fwc_mass_4h_kg": 0.0013600000000000003,
                        "dwc_mass_4h_kg": 0.0006062144018846066,
                        "average_kg_per_s": 1.3654266679754218e-07,
                        "sar": 0.8500000000000001,
                        "interface_length_m": 0.92,
                        "baseline": "measured",
                        "baseline_g_per_h": 0.4,
                        "within_design_envelope": True,
                        "finite_geometry": True,
                        "film_transport": {
                            "interface_temperature_c": 5.042750598284328,
                            "sensible_flux": 133.88134579637946,
                            "latent_flux": 168.84735975097533,
                            "conduction_flux": 302.72870554735283,
                            "thickness": 8.190616400277765e-05,
                            "recovery_4h_kg": 0.001570546293363937,
                            "energy_residual": 1.9895196601282805e-12,
                        },
                        "segments": [
                            [0.0, 0.0005, "DWC"],
                            [0.0005, 0.0033333333333333327, "FWC"],
                            [0.0033333333333333327, 0.0038333333333333327, "DWC"],
                            [0.0038333333333333327, 0.006666666666666665, "FWC"],
                            [0.006666666666666665, 0.007166666666666665, "DWC"],
                            [0.007166666666666665, 0.009999999999999998, "FWC"],
                            [0.009999999999999998, 0.010499999999999999, "DWC"],
                            [0.010499999999999999, 0.013333333333333332, "FWC"],
                            [0.013333333333333332, 0.013833333333333333, "DWC"],
                            [0.013833333333333333, 0.016666666666666666, "FWC"],
                            [0.016666666666666666, 0.017166666666666667, "DWC"],
                            [0.017166666666666667, 0.02, "FWC"],
                            [0.02, 0.0205, "DWC"],
                            [0.0205, 0.023333333333333334, "FWC"],
                            [0.023333333333333334, 0.023833333333333335, "DWC"],
                            [0.023833333333333335, 0.02666666666666667, "FWC"],
                            [0.02666666666666667, 0.02716666666666667, "DWC"],
                            [0.02716666666666667, 0.030000000000000002, "FWC"],
                            [0.030000000000000002, 0.030500000000000003, "DWC"],
                            [0.030500000000000003, 0.03333333333333333, "FWC"],
                            [0.03333333333333333, 0.03383333333333333, "DWC"],
                            [0.03383333333333333, 0.03666666666666667, "FWC"],
                            [0.03666666666666667, 0.03716666666666667, "DWC"],
                            [0.03716666666666667, 0.04, "FWC"],
                        ],
                        "notes": [
                            "Four-hour calibrated mass; not a transient or arbitrary-RH model",
                            "40 mm square; starts with DWC at left edge",
                            "Film model assumes wall 5 C; paper specifies coolant inlet 5 C",
                        ],
                    },
                    "scope": "Discrete width/SAR search with finite edges; measured FWC baseline",
                },
            },
            "versions": {
                "numpy": "2.5.3",
                "scipy": "1.18.1",
                "autograd": "1.9.1",
                "plotly": "6.9.0",
                "marimo": "0.24.2",
            },
            "units": "SI except explicitly labeled fields",
        },
        "independent_baseline": {
            "revision": "b18786ffc7d824e42407137c56c7c609d5d4cd75",
            "url": "https://raw.githubusercontent.com/JSablowski/DWCmod/b18786ffc7d824e42407137c56c7c609d5d4cd75/DWC_models.py",
            "license": "MIT",
            "results": [
                {
                    "subcooling_K": 2.0,
                    "upstream_flux": 118746.46127671248,
                    "implemented_flux": 118746.46479350941,
                    "relative_error": 2.9616014529665335e-08,
                    "rmax_m": 0.0013348035810569747,
                },
                {
                    "subcooling_K": 6.0,
                    "upstream_flux": 357516.6711686125,
                    "implemented_flux": 357516.6818447316,
                    "relative_error": 2.986187763731607e-08,
                    "rmax_m": 0.0013348035810569747,
                },
                {
                    "subcooling_K": 10.0,
                    "upstream_flux": 596287.496325317,
                    "implemented_flux": 596287.5140873608,
                    "relative_error": 2.9787718069940183e-08,
                    "rmax_m": 0.0013348035810569747,
                },
            ],
        },
    }
    embedded_presets = {
        "units": "SI except explicitly suffixed fields",
        "geometry_note": "Disk radius 0.01 m is an explicit working assumption: the attached Xie/Croce texts define R but do not state its value in the inspected model/validation sections. Change it to match the original Peng specimen when confirmed.",
        "xie_fig4": {
            "temperature_K": 333.15,
            "subcooling_K": 5,
            "theta_deg": 110,
            "advancing_deg": 120,
            "receding_deg": 105,
            "coating_thickness_m": 1e-09,
            "coating_conductivity_W_mK": 0.2,
            "nucleation_density_m2": 250000000000.0,
            "fwc_width_m": 0.0002,
        },
        "xie_fig5": {
            "temperature_K": 373.15,
            "theta_deg": 120,
            "advancing_deg": 142,
            "receding_deg": 102,
            "coating_resistance_m2K_W": 5e-09,
            "nucleation_density_m2": 250000000000.0,
            "dwc_width_m": 0.00046,
            "fwc_width_m": 0.00044,
        },
        "croce_fig7": {
            "temperature_K": 373.15,
            "theta_deg": 120,
            "coating_resistance_m2K_W": 3.39e-07,
            "rmax_m": 0.00125,
        },
        "croce_fig8b": {
            "temperature_K": 373.15,
            "theta_deg": 120,
            "coating_resistance_m2K_W": 3.39e-07,
            "dwc_width_m": 0.00055,
            "fwc_width_m": 0.00045,
        },
        "lee": {
            "air_C": 14,
            "relative_humidity": 1,
            "air_velocity_m_s": 0.6,
            "coolant_inlet_C": 5,
            "assumed_wall_C": 5,
            "width_m": 0.04,
            "height_m": 0.04,
            "duration_s": 14400,
            "measured_fwc_g_h": 0.4,
            "paper_theory_fwc_g_h": 0.355,
            "reported_best_observed_kg": 0.00184,
            "reported_best_predicted_kg": 0.002,
        },
    }
    mo.accordion(
        {
            "Original native validation snapshot": mo.json(recorded_evidence),
            "Paper presets": mo.json(embedded_presets),
        }
    )
    return


if __name__ == "__main__":
    app.run()
