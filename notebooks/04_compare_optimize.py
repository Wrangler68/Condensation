import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Condensation · Design explorer")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import plotly.graph_objects as go
    from condensation import croce2024, xie2020, water, SteamConditions, Surface, Geometry
    from condensation.optimization import optimize_croce, optimize_plate, optimize_lee, optimize_xie
    from condensation.differentiation import normalized_sensitivity
    from condensation.studies import croce_heatmap, export_record
    from condensation.plots import heatmap, curves, style

    return (
        Geometry,
        SteamConditions,
        Surface,
        croce2024,
        croce_heatmap,
        curves,
        export_record,
        go,
        heatmap,
        mo,
        normalized_sensitivity,
        np,
        optimize_croce,
        optimize_lee,
        optimize_plate,
        optimize_xie,
        style,
        water,
        xie2020,
    )


@app.cell
def _(mo):
    mo.md("""
    # Biphilic surface design explorer
    **Geometry, drainage, and sensitivity** / NumPy · SciPy · Plotly · Autograd

    Compare steam models under explicitly matched conditions. Lee's humid-air recovery stays
    in a separate objective. Blank map cells are flooded geometries with no valid Croce flux.
    **These are model studies, not validated design recommendations:** Croce's published-curve
    discrepancy and the disk-radius assumption remain unresolved.
    """)
    return


@app.cell
def _(mo):
    controls = (
        mo.md("""
    {dt}

    {coating}
    """)
        .batch(
            **{
                "dt": mo.ui.slider(2.0, 10.0, step=1.0, value=6.0, label="Steam subcooling (K)"),
                "coating": mo.ui.number(
                    0.1, 10.0, step=0.01, value=3.39, label="Coating resistance (×10⁻⁷ m²K/W)"
                ),
            }
        )
        .form(submit_button_label="Update map", show_clear_button=False)
    )
    controls
    return (controls,)


@app.cell
def _(SteamConditions, Surface, controls, croce_heatmap, np):
    settings = controls.value or {"dt": 6.0, "coating": 3.39}
    conditions = SteamConditions(subcooling=settings["dt"])
    surface = Surface(coating_resistance=settings["coating"] * 1e-7)
    ld_values = np.linspace(0.1, 0.9, 10) * 1e-3
    lf_values = np.linspace(0.1, 0.7, 9) * 1e-3
    flux_map, flood_map = croce_heatmap(ld_values, lf_values, conditions, surface)
    return conditions, flux_map, ld_values, lf_values, settings, surface


@app.cell
def _(flux_map, heatmap, ld_values, lf_values, mo):
    design_map = mo.ui.plotly(
        heatmap(
            ld_values * 1e3,
            lf_values * 1e3,
            flux_map,
            "Croce disk model · feasible heat flux",
            "DWC width (mm)",
            "FWC width (mm)",
            "kW/m²",
        )
    )
    mo.vstack(
        [
            design_map,
            mo.md(
                "Flooding is assessed at the longest stripe. The map uses the corrected population equations and published local-angle film closure."
            ),
        ]
    )
    return


@app.cell
def _(croce2024, go, mo, normalized_sensitivity, np, settings, style, water):
    parameters = np.array([0.00055, 0.0006, settings["dt"], settings["coating"] * 1e-7])
    sensitivities = normalized_sensitivity(
        lambda v: croce2024.smooth_plate_flux(v, water()), parameters
    )
    sensitivity_plot = go.Figure(
        go.Bar(
            x=["DWC width", "FWC width", "Subcooling", "Coating resistance"],
            y=sensitivities,
            marker_color=["#0f766e" if x >= 0 else "#e97935" for x in sensitivities],
        )
    )
    style(
        sensitivity_plot,
        "Autograd · normalized local sensitivities",
        ylabel="∂ln(flux) / ∂ln(parameter)",
    )
    mo.vstack(
        [
            mo.ui.plotly(sensitivity_plot),
            mo.md(
                "Sensitivities use a **20 mm tall rectangular plate**, widths 0.55 / 0.60 mm, and fixed 100 °C fluid properties. Nucleation and film roots are implicitly differentiated. This smooth extension avoids discrete disk stripe counts; it is not the paper's disk optimization."
            ),
        ]
    )
    return


@app.cell
def _(Geometry, conditions, croce2024, curves, mo, np, surface, xie2020):
    comparison_widths = np.linspace(0.1, 1.2, 20) * 1e-3
    comparison_xie = [
        xie2020.solve(conditions, surface, Geometry(float(w), 0.00045), dx=4e-6)
        for w in comparison_widths
    ]
    comparison_croce = [
        croce2024.solve(conditions, surface, Geometry(float(w), 0.00045)) for w in comparison_widths
    ]
    comparison_plot = curves(
        comparison_widths * 1e3,
        {
            "Xie · fixed nucleation density": [r.heat_flux / 1000 for r in comparison_xie],
            "Croce · coating-dependent nucleation": [r.heat_flux / 1000 for r in comparison_croce],
        },
        "Matched steam conditions · distinct model assumptions",
        "DWC width (mm)",
        "Heat flux (kW/m²)",
    )
    mo.vstack(
        [
            mo.ui.plotly(comparison_plot),
            mo.md(
                "Both curves use 100 °C saturation properties, the selected subcooling/coating, a 10 mm radius, and 0.45 mm FWC stripes. Departure, nucleation, population and film assumptions remain paper-specific."
            ),
        ]
    )
    return


@app.cell
def _(mo):
    run_search = mo.ui.run_button(label="Run constrained geometry searches")
    run_search
    return (run_search,)


@app.cell
def _(
    conditions,
    export_record,
    mo,
    optimize_croce,
    optimize_lee,
    optimize_plate,
    optimize_xie,
    run_search,
    settings,
    surface,
    water,
):
    mo.stop(
        not run_search.value,
        mo.md(
            "Run the searches to compare a flooding-constrained disk design, an Autograd plate refinement, and Lee's finite-stripe recovery optimum."
        ),
    )
    disk_optimum = optimize_croce(conditions, surface, grid_size=20)
    plate_optimum = optimize_plate(
        [0.00055, 0.0006, settings["dt"], settings["coating"] * 1e-7], water()
    )
    lee_optimum = optimize_lee()
    xie_optimum = optimize_xie(conditions, surface, grid_size=20)
    search_results = {
        "croce_disk": disk_optimum,
        "croce_plate_extension": plate_optimum,
        "xie_fixed_fwc": xie_optimum,
        "lee_mass": lee_optimum,
    }
    mo.vstack(
        [
            mo.md(
                "### Search results\nEach objective retains its own units and model assumptions. Disk optima are re-evaluated with adaptive radial quadrature."
            ),
            mo.json(search_results),
            mo.download(
                export_record("Design searches", settings, search_results).encode(),
                filename="design-searches.json",
                label="Download search results",
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
