"""Xie 2020 Eqs.1-24; default restores Kim-Kim's liquid resistance (see ledger)."""

from dataclasses import replace

import numpy as np
from scipy.optimize import brentq

from .droplets import critical_radius, interface_coefficient, nusselt_flux, sliding_radius
from .populations import flux_components
from .properties import water
from .types import Geometry, SteamConditions, SteamResult, Surface


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
    coeff = 3 * np.pi * g.radius * p.viscosity / (2 * p.rho_l**2 * p.gravity * p.latent_heat)

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
        notes=("Uniform-film model; flooding is not predicted", f"Drop convention: {convention}"),
    )


def sweep_widths(widths, conditions=None, surface=None, geometry=None, **kwargs):
    g = geometry or preset()[2]
    return [solve(conditions, surface, replace(g, dwc_width=float(w)), **kwargs) for w in widths]
