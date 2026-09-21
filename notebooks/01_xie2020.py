import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Xie · Biphilic condensation")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    from dataclasses import replace
    from condensation import xie2020 as model
    from condensation import Geometry
    from condensation.plots import curves, stripe_schematic, benchmark_plot
    from condensation.studies import figure_checks, export_record

    return (
        Geometry,
        benchmark_plot,
        curves,
        export_record,
        figure_checks,
        mo,
        model,
        np,
        replace,
        stripe_schematic,
    )


@app.cell
def _(mo):
    mo.md("""
    # Suction, sliding, and the liquid film
    **Xie et al. · 2020** / Steam condensation on vertical biphilic stripes

    Follow condensate from a growing droplet to its departure mode and the hydrophilic channel.
    [Paper](https://doi.org/10.1016/j.ijheatmasstransfer.2019.119273) · SI calculations, display units below.

    The default restores the Kim–Kim liquid resistance. The printed Eq. (11) contains an
    extra π and gives substantially higher flux than the published curves. Both are available.
    Disk radius **10 mm** is an unconfirmed specimen assumption. This model does not predict flooding.
    """)
    return


@app.cell
def _(mo):
    controls = (
        mo.md("""
    {ld} &nbsp; {lf}

    {dt}

    {coating}

    {mode} &nbsp; {convention}
    """)
        .batch(
            **{
                "ld": mo.ui.number(0.05, 4.0, step=0.05, value=0.2, label="DWC width (mm)"),
                "lf": mo.ui.number(0.05, 3.0, step=0.05, value=0.2, label="FWC width (mm)"),
                "dt": mo.ui.slider(1.0, 10.0, step=0.5, value=5.0, label="Subcooling (K)"),
                "coating": mo.ui.number(
                    0.0, 1000.0, step=1.0, value=1.0, label="Coating thickness (nm), k = 0.2 W/mK"
                ),
                "mode": mo.ui.dropdown(
                    ["dss", "oss", "mixed"], value="mixed", label="Departure model"
                ),
                "convention": mo.ui.dropdown(
                    ["kim", "xie"], value="kim", label="Liquid resistance: kim / printed xie"
                ),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    controls
    return (controls,)


@app.cell
def _(Geometry, controls, model, replace):
    settings = controls.value or {
        "ld": 0.2,
        "lf": 0.2,
        "dt": 5.0,
        "coating": 1.0,
        "mode": "mixed",
        "convention": "kim",
    }
    conditions, surface, _ = model.preset()
    conditions = replace(conditions, subcooling=settings["dt"])
    surface = replace(surface, coating_resistance=settings["coating"] * 1e-9 / 0.2)
    geometry = Geometry(settings["ld"] * 1e-3, settings["lf"] * 1e-3)
    result = model.solve(
        conditions, surface, geometry, mode=settings["mode"], convention=settings["convention"]
    )
    profile = model.stripe_profile(
        conditions, surface, geometry, mode=settings["mode"], convention=settings["convention"]
    )
    return conditions, geometry, profile, result, settings, surface


@app.cell
def _(mo, result):
    mo.hstack(
        [
            mo.stat(label="Total heat flux", value=f"{result.heat_flux / 1000:,.1f} kW/m²"),
            mo.stat(label="Overall HTC", value=f"{result.htc / 1000:,.1f} kW/m²K"),
            mo.stat(label="Film thickness", value=f"{result.film_thickness * 1e6:,.1f} µm"),
            mo.stat(
                label="DWC liquid sent to film",
                value=f"{100 * result.transferred_flux / result.dwc_flux:.1f}%",
            ),
        ]
    )
    return


@app.cell
def _(curves, geometry, mo, profile, stripe_schematic):
    geometry_chart = stripe_schematic(geometry.dwc_width, geometry.fwc_width)
    radius_chart = curves(
        profile["x"] * 1e3,
        {"Departure radius": profile["rmax"] * 1e6},
        "Departure along the half-stripe",
        "Distance from boundary (mm)",
        "Cap radius (µm)",
    )
    flux_chart = curves(
        profile["x"] * 1e3,
        {"Local DWC": profile["heat_flux"] / 1000},
        "Local condensation heat flux",
        "Distance from boundary (mm)",
        "Heat flux (kW/m²)",
    )
    mo.vstack([geometry_chart, mo.hstack([mo.ui.plotly(radius_chart), mo.ui.plotly(flux_chart)])])
    return


@app.cell
def _(conditions, curves, geometry, mo, model, np, settings, surface):
    widths = np.geomspace(0.05e-3, 3e-3, 28)
    sweep = model.sweep_widths(
        widths,
        conditions,
        surface,
        geometry,
        dx=4e-6,
        mode=settings["mode"],
        convention=settings["convention"],
    )
    width_chart = curves(
        widths * 1e3,
        {
            "Total": [r.heat_flux / 1000 for r in sweep],
            "DWC region": [r.dwc_flux / 1000 for r in sweep],
            "FWC region": [r.fwc_flux / 1000 for r in sweep],
        },
        "Width sweep · region fluxes are before area weighting",
        "DWC width (mm)",
        "Heat flux (kW/m²)",
        True,
    )
    mo.ui.plotly(width_chart)
    return


@app.cell
def _(benchmark_plot, figure_checks, mo):
    benchmarks = [r for r in figure_checks() if r["case"].startswith("Xie")]
    mo.vstack(
        [
            mo.md(
                "### Published-curve check\nApproximate readings of Fig. 5a's model line, not raw experimental data. Fixed paper preset; independent of the controls above."
            ),
            benchmark_plot(benchmarks, "Xie Fig. 5a · Kim–Kim resistance convention"),
        ]
    )
    return


@app.cell
def _(conditions, export_record, geometry, mo, result, settings, surface):
    record = export_record(
        "Xie 2020",
        {
            "controls": settings,
            "conditions": conditions,
            "surface": surface,
            "geometry": geometry,
            "dx_m": 1e-6,
            "radial_order": 96,
        },
        result,
    )
    mo.download(
        record.encode(), filename="xie2020-result.json", label="Download calculation + provenance"
    )
    return


if __name__ == "__main__":
    app.run()
