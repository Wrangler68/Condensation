"""Generate paper-oriented interactive sweeps, without claiming exact figure reproduction.

uv run python scripts/reproduce.py --paper all
Files go to output/figures; JSON preserves every plotted sample and its provenance.
"""

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np

from condensation import Geometry, SteamConditions, water
from condensation import croce2024 as croce
from condensation import xie2020 as xie
from condensation.droplets import heat_rate
from condensation.optimization import optimize_croce
from condensation.plots import benchmark_plot, curves, heatmap
from condensation.studies import export_record, figure_checks


def save(name, fig, inputs, result):
    out = Path("output/figures")
    out.mkdir(parents=True, exist_ok=True)
    fig.write_html(out / f"{name}.html", include_plotlyjs="cdn")
    (out / f"{name}.json").write_text(export_record(name, inputs, result), encoding="utf-8")
    print(name)


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
            sum(croce.dwc_components(float(dt), theta, coat, p, 0.00125)) / 1000 for dt in dt_values
        ]
        for coat in (0.0, 1e-8, 1e-7, 1e-6)
    }
    save(
        "croce_fig5_dwc",
        curves(dt_values, series, "Croce Fig.5 study · pure DWC", "Subcooling (K)", "kW/m²"),
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
            widths * 1e3, series, "Croce Fig.9 study · fixed FWC width", "DWC width (mm)", "kW/m²"
        ),
        {"fwc_width_m": 0.00045, "radius_m": 0.01},
        {"dwc_widths_m": widths, "series": series},
    )
    optima = [
        optimize_croce(SteamConditions(subcooling=dt), margin=0.0, grid_size=18)
        for dt in (2.0, 4.0, 6.0, 8.0, 10.0)
    ]
    series = {
        f"ΔT={dt:g} K": np.array(r["grid_fluxes"]) / 1000 for dt, r in zip((2, 4, 6, 8, 10), optima)
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
        mode: [r.heat_flux / c.subcooling / 1000 for r in rows] for mode, rows in results.items()
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
            rs = xie.sweep_widths(candidates, c, surf, replace(g, fwc_width=float(lf)), dx=8e-6)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", choices=["all", "xie", "croce"], default="all")
    args = parser.parse_args()
    if args.paper in ("all", "croce"):
        croce_figures()
    if args.paper in ("all", "xie"):
        xie_figures()
    checks = figure_checks()
    save(
        "published_curve_checks",
        benchmark_plot(checks, "Approximate published MODEL curve readings"),
        {"data": "data/digitized/figure_checks.json"},
        {"checks": checks},
    )


if __name__ == "__main__":
    main()
