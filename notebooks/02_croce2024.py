import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Croce · Droplets and rivulets")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    from condensation import croce2024 as model
    from condensation import SteamConditions, Surface, Geometry, water
    from condensation.droplets import (
        critical_radius,
        growth_coefficients,
        heat_rate,
        resistance_terms,
    )
    from condensation.populations import small_distribution, large_distribution
    from condensation.plots import curves, benchmark_plot, stripe_schematic
    from condensation.studies import figure_checks, export_record

    return (
        Geometry,
        SteamConditions,
        Surface,
        benchmark_plot,
        critical_radius,
        curves,
        export_record,
        figure_checks,
        growth_coefficients,
        large_distribution,
        mo,
        model,
        np,
        resistance_terms,
        small_distribution,
        water,
    )


@app.cell
def _(mo):
    mo.md("""
    # From nanometer droplets to draining rivulets
    **Croce & Suzzi · 2024** / Coating, population balance, and flooding

    [Paper](https://doi.org/10.3390/en17112742). The model includes coating-dependent nucleation,
    radius-dependent sweeping, capillary cross-flow, and a finite drainage capacity.
    Eqs. (8) and (13) use the documented exponential and interfacial-coefficient corrections.

    **Reproduction status:** the implemented equations do not fully match the published curves,
    especially the pure-DWC Fig. 7a. The comparison below exposes that discrepancy.
    Optimization is exploratory until it is resolved. Disk radius **10 mm** is an explicit assumption.
    """)
    return


@app.cell
def _(mo):
    controls = (
        mo.md("""
    {ld} &nbsp; {lf}

    {dt}

    {coating}

    {linear}
    """)
        .batch(
            **{
                "ld": mo.ui.number(0.05, 2.0, step=0.01, value=0.55, label="DWC width (mm)"),
                "lf": mo.ui.number(0.05, 2.0, step=0.01, value=0.45, label="FWC width (mm)"),
                "dt": mo.ui.slider(1.0, 10.0, step=0.5, value=6.0, label="Subcooling (K)"),
                "coating": mo.ui.number(
                    0.0, 20.0, step=0.01, value=3.39, label="Coating resistance (×10⁻⁷ m²K/W)"
                ),
                "linear": mo.ui.checkbox(value=True, label="Radius-dependent sweeping (Croce)"),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    controls
    return (controls,)


@app.cell
def _(Geometry, SteamConditions, Surface, controls, model, water):
    settings = controls.value or {
        "ld": 0.55,
        "lf": 0.45,
        "dt": 6.0,
        "coating": 3.39,
        "linear": True,
    }
    conditions = SteamConditions(subcooling=settings["dt"])
    surface = Surface(coating_resistance=settings["coating"] * 1e-7)
    geometry = Geometry(settings["ld"] * 1e-3, settings["lf"] * 1e-3)
    properties = water()
    result = model.solve(conditions, surface, geometry, linear=settings["linear"])
    rn = model.nucleation_radius(
        conditions.subcooling, surface.theta, surface.coating_resistance, properties
    )
    return conditions, geometry, properties, result, rn, settings, surface


@app.cell
def _(mo, result, rn):
    status = (
        "Within modeled drainage capacity" if result.valid else "FLOODING · total flux is undefined"
    )
    mo.vstack(
        [
            mo.callout(status, kind="success" if result.valid else "warn"),
            mo.hstack(
                [
                    mo.stat(
                        label="Total heat flux",
                        value=f"{result.heat_flux / 1000:,.1f} kW/m²"
                        if result.valid
                        else "Outside model",
                    ),
                    mo.stat(label="Nucleation radius", value=f"{rn * 1e9:.2f} nm"),
                    mo.stat(label="Height / flooding height", value=f"{result.flooding_ratio:.3f}"),
                    mo.stat(
                        label="Maximum film thickness",
                        value=f"{result.film_thickness * 1e6:.1f} µm" if result.valid else "—",
                    ),
                ]
            ),
        ]
    )
    return


@app.cell
def _(
    conditions,
    critical_radius,
    curves,
    geometry,
    growth_coefficients,
    large_distribution,
    mo,
    np,
    properties,
    resistance_terms,
    rn,
    small_distribution,
    surface,
):
    dt = conditions.subcooling
    theta = surface.theta
    coating = surface.coating_resistance
    r0 = critical_radius(dt, properties)
    re = rn / (2 * np.sqrt(0.037))
    rmax = geometry.dwc_width / (2 * np.sin(theta))
    radii = np.geomspace(rn * 1.00001, rmax, 220)
    a, b = growth_coefficients(dt, theta, coating, properties)
    distribution = np.array(
        [
            small_distribution(r, re, r0, rmax, a, b, True)
            if r < re
            else large_distribution(r, rmax)
            for r in radii
        ]
    )
    baseline_distribution = np.array(
        [
            small_distribution(r, re, r0, rmax, a, b, False)
            if r < re
            else large_distribution(r, rmax)
            for r in radii
        ]
    )
    populations = curves(
        radii * 1e6,
        {"Croce sweeping": distribution, "Constant sweeping": baseline_distribution},
        "Population density · same nucleation and departure radii",
        "Cap radius (µm)",
        "Population density (m⁻³)",
        True,
        True,
    )
    rc, rl, ri = resistance_terms(radii, theta, coating, properties)
    resistances = curves(
        radii * 1e6,
        {"Coating": rc, "Liquid": rl, "Interface": ri},
        "Single-drop resistance terms",
        "Cap radius (µm)",
        "Denominator resistance (m²K/W)",
        True,
        True,
    )
    mo.hstack([mo.ui.plotly(populations), mo.ui.plotly(resistances)])
    return


@app.cell
def _(conditions, curves, geometry, mo, model, np, properties, result):
    heights = np.linspace(0.0001, 2 * geometry.radius, 60)
    migration = result.dwc_flux * geometry.dwc_width / properties.latent_heat
    film = [
        model.film_state(geometry.fwc_width, migration, conditions.subcooling, float(h), properties)
        for h in heights
    ]
    film_plot = curves(
        heights * 1000,
        {"Rivulet maximum thickness": [float(s[0]) * 1e6 for s in film]},
        "Rivulet profile · stops at flooding",
        "Distance from top (mm)",
        "Thickness (µm)",
    )
    mo.ui.plotly(film_plot)
    return


@app.cell
def _(benchmark_plot, figure_checks, mo):
    checks = [r for r in figure_checks() if r["case"].startswith("Croce")]
    mo.vstack(
        [
            mo.md(
                "### Reproduction audit\nPaper model curves were read approximately with conservative reading uncertainty. The disagreement is retained; no coefficient was fitted to conceal it. Fixed figure presets are independent of the controls."
            ),
            benchmark_plot(checks, "Published curves vs implemented equations"),
            mo.ui.table(checks),
        ]
    )
    return


@app.cell
def _(conditions, export_record, geometry, mo, result, settings, surface):
    mo.download(
        export_record(
            "Croce 2024",
            {
                "controls": settings,
                "conditions": conditions,
                "surface": surface,
                "geometry": geometry,
                "equation_convention": "corrected Eqs.8/13",
                "radial_order": 96,
            },
            result,
        ).encode(),
        filename="croce2024-result.json",
        label="Download calculation + provenance",
    )
    return


if __name__ == "__main__":
    app.run()
