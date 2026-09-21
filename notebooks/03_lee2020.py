import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Lee · Humid-air recovery")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import plotly.graph_objects as go
    from condensation import lee2020 as model
    from condensation.plots import curves, stripe_schematic, style
    from condensation.studies import export_record

    return curves, export_record, go, mo, model, np, style


@app.cell
def _(mo):
    mo.md("""
    # Recovering water from humid air
    **Lee et al. · 2020** / A four-hour condensate collection experiment

    [Paper](https://doi.org/10.1016/j.ijheatmasstransfer.2020.120206).
    Saturated air at 14–15 °C, 0.6 m/s, over a 40 × 40 mm specimen; coolant inlet 5 °C.
    Eq. (6) predicts **collected mass over four hours**, not a universal mass-transfer rate.
    The 5 °C wall temperature in the transport calculation is an explicit approximation.

    Measured FWC baseline: **0.400 g/h**. Paper's theoretical baseline: **0.355 g/h**.
    These are selectable below; the film energy balance is also calculated independently.
    """)
    return


@app.cell
def _(mo):
    controls = (
        mo.md("""
    {ld} &nbsp; {lf}

    {baseline}

    {finite}
    """)
        .batch(
            **{
                "ld": mo.ui.number(0.5, 3.0, step=0.1, value=0.6, label="DWC width (mm)"),
                "lf": mo.ui.number(0.5, 8.5, step=0.1, value=3.4, label="FWC width (mm)"),
                "baseline": mo.ui.dropdown(
                    ["measured", "paper_theory", "transport"],
                    value="measured",
                    label="FWC baseline",
                ),
                "finite": mo.ui.checkbox(value=True, label="Count finite specimen edges"),
            }
        )
        .form(submit_button_label="Calculate", show_clear_button=False)
    )
    controls
    return (controls,)


@app.cell
def _(controls, model):
    settings = controls.value or {"ld": 0.6, "lf": 3.4, "baseline": "measured", "finite": True}
    result = model.solve(
        settings["ld"] * 1e-3,
        settings["lf"] * 1e-3,
        baseline=settings["baseline"],
        finite=settings["finite"],
    )
    return result, settings


@app.cell
def _(mo, result):
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(
                        label="Collected in four hours",
                        value=f"{result['mass_4h_kg'] * 1000:.3f} g",
                    ),
                    mo.stat(label="Hydrophilic area fraction", value=f"{result['sar'] * 100:.1f}%"),
                    mo.stat(
                        label="Internal interface length",
                        value=f"{result['interface_length_m']:.3f} m",
                    ),
                    mo.stat(
                        label="Average recovery", value=f"{result['mass_4h_kg'] * 250:.3f} g/h"
                    ),
                ]
            ),
            mo.callout(
                "Within the implemented width/SAR envelope"
                if result["within_design_envelope"]
                else "Extrapolation: outside the implemented width/SAR envelope",
                kind="info" if result["within_design_envelope"] else "warn",
            ),
        ]
    )
    return


@app.cell
def _(curves, go, mo, model, np, result, style):
    lengths = np.linspace(0, 2.1, 150)
    families = {
        f"SAR {sar:.0%}": np.array(
            [
                model.recovery_from_interface(float(l), sar, result["baseline_g_per_h"]) * 1000
                for l in lengths
            ]
        )
        for sar in (0.5, 0.6, 0.75, 0.85)
    }
    recovery_plot = curves(
        lengths,
        families,
        "Four-hour recovery · Eq. (5) + Eq. (6)",
        "Internal interface length (m)",
        "Collected mass (g)",
    )
    recovery_plot.add_trace(
        go.Scatter(
            x=[result["interface_length_m"]],
            y=[result["mass_4h_kg"] * 1000],
            mode="markers",
            marker=dict(size=14, color="#182e45"),
            name="Current specimen",
        )
    )
    bars = go.Figure(
        go.Bar(
            x=["Film contribution", "Dropwise contribution"],
            y=[result["fwc_mass_4h_kg"] * 1000, result["dwc_mass_4h_kg"] * 1000],
            marker_color=["#0f766e", "#e97935"],
        )
    )
    style(bars, "Recovery contributions", ylabel="Collected mass (g / 4 h)")
    mo.hstack([mo.ui.plotly(recovery_plot), bars])
    return


@app.cell
def _(mo, result):
    transport = result["film_transport"]
    mo.vstack(
        [
            mo.md(
                "### Independent humid-air energy balance\nSensible + latent heat = film conduction. This calculation uses fixed engineering properties; it is not forced to equal either paper baseline."
            ),
            mo.ui.table([{"quantity": key, "value": value} for key, value in transport.items()]),
            mo.md(
                "The paper reports 1.84 g at 0.6 / 3.4 mm and approximately 2 g for its predicted optimum at 0.5 / 2.8 mm. Finite edge counting and the choice of FWC baseline change the comparison. No transient accumulation law is inferred from this fit."
            ),
        ]
    )
    return


@app.cell
def _(export_record, mo, result, settings):
    mo.download(
        export_record("Lee 2020", settings, result).encode(),
        filename="lee2020-result.json",
        label="Download calculation + provenance",
    )
    return


if __name__ == "__main__":
    app.run()
