"""Croce 2024, with dimensionally corrected population formulas and published film closure."""

from functools import lru_cache

import autograd.numpy as anp
import numpy as np
from autograd import grad
from scipy.optimize import brentq

from .differentiation import implicit_solver
from .droplets import critical_radius, heat_rate, nusselt_flux, sliding_radius
from .geometry import disk_heights
from .populations import flux_components
from .properties import water
from .quadrature import integrate
from .types import Geometry, SteamConditions, SteamResult, Surface


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
        rivulet_factor(ratio) * p.rho_l * (p.rho_l - p.rho_v) * p.gravity / p.viscosity * integral
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
        return film_height_relation(width * anp.exp(z), width, migration, dt, p) / height - 1

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
            film_height_relation(anp.exp(logw) / 2, anp.exp(logw), migration, dt, p) / height - 1
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
            "Croce 2024", q, 0, q, q / dt, 0, 0, notes=("Pure FWC uses Nusselt plate limit",)
        )
    rmax = (
        g.dwc_width / (2 * np.sin(s.theta))
        if g.fwc_width > 0
        else sliding_radius(s.theta, s.advancing, s.receding, p, "croce")
    )
    rn = nucleation_radius(dt, s.theta, s.coating_resistance, p)
    re = rn / (2 * np.sqrt(0.037))
    if rmax <= re:
        raise ValueError("Croce requires rmax > re; stripe is outside the two-population domain")
    qd = float(
        sum(dwc_components(dt, s.theta, s.coating_resistance, p, rmax, order, reference, linear))
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
