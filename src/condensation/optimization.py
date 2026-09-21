"""Constrained searches with explicit feasibility, grid evidence and reference reevaluation."""

from dataclasses import replace

import numpy as np
from autograd import grad
from scipy.optimize import minimize, minimize_scalar

from . import croce2024, lee2020, xie2020
from .properties import water
from .types import Geometry, SteamConditions, Surface


def optimize_croce(
    conditions=None, surface=None, radius=0.01, margin=0.02, bounds=(0.05e-3, 2e-3), grid_size=30
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
    local = (np.log(widths[max(index - 1, 0)]), np.log(widths[min(index + 1, grid_size - 1)]))
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

    from .croce2024 import dwc_components, film_height_relation

    def params(z):
        return anp.concatenate((anp.exp(z), initial[2:]))

    def flood(z):
        ld, lf, dt, coat = params(z)
        qd = sum(dwc_components(dt, theta, coat, p, ld / (2 * anp.sin(theta))))
        return film_height_relation(lf / 2, lf, qd * ld / p.latent_heat, dt, p) / height - 1.02

    # Feasible-only objective to avoid ever interpreting a flooded flux as valid.
    def objective(z):
        if flood(z) <= -0.019:
            return 1e3 + float(-flood(z))
        return -croce2024.smooth_plate_flux(params(z), p, height, theta) / 1e6

    def jac(z):
        if flood(z) <= -0.019:
            return -grad(flood)(z)
        return grad(lambda zz: -croce2024.smooth_plate_flux(params(zz), p, height, theta) / 1e6)(z)

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
