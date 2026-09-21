"""Plotly figures shared by the marimo notebooks and reproducible batch studies."""

import plotly.graph_objects as go

COLORS = ["#0f766e", "#e97935", "#4969b1", "#ad4a80", "#718096"]


def style(fig, title, xlabel=None, ylabel=None):
    fig.update_layout(
        title=dict(text=title, font=dict(size=20)),
        template="plotly_white",
        colorway=COLORS,
        font=dict(family="Arial", color="#24364b"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        height=420,
        margin=dict(l=55, r=25, t=65, b=55),
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    if xlabel:
        fig.update_xaxes(title_text=xlabel)
    if ylabel:
        fig.update_yaxes(title_text=ylabel)
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
    fig.update_layout(height=240)
    return fig


def heatmap(x, y, z, title, xlabel, ylabel, zlabel):
    fig = go.Figure(
        go.Heatmap(x=x, y=y, z=z, colorscale="Teal", colorbar=dict(title=zlabel), hoverongaps=False)
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
                    type="data", array=[r["reading_uncertainty_W_m2"] / 1000 for r in selected]
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
