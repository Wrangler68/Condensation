"""Humid-air film balance and four-hour empirical recovery, kept as separate observables."""

from dataclasses import asdict, dataclass

import autograd.numpy as np
from scipy.optimize import brentq

from .geometry import finite_stripes


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
    delta = (4 * kl * mu * (air_c - wall_c) * length / (9.81 * rhol * (rhol - rhoa) * hfg)) ** 0.25

    def components(ti):
        sensible = hv * (air_c - ti)
        latent = hv * hfg / cp * (moisture_ratio(air_c) - moisture_ratio(ti))
        conduction = kl / delta * (ti - wall_c)
        return sensible, latent, conduction

    ti = brentq(lambda t: components(t)[0] + components(t)[1] - components(t)[2], wall_c, air_c)
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
