"""Single-drop heat and growth; paper-specific liquid resistance is explicit."""

import autograd.numpy as np


def critical_radius(subcooling, p):
    return 2 * p.temperature * p.tension / (p.rho_l * p.latent_heat * subcooling)


def interface_coefficient(p, accommodation=1.0):
    return (
        2
        * accommodation
        / (2 - accommodation)
        / np.sqrt(2 * np.pi * p.gas_constant * p.temperature)
        * p.rho_v
        * p.latent_heat**2
        / p.temperature
    )


def resistance_terms(r, theta, coating, p, convention="kim"):
    """Denominator of Q/(pi*r^2), units m2 K/W. Xie Eq. 11 has an extra pi."""
    if convention not in ("kim", "xie"):
        raise ValueError("Unknown single-drop convention")
    liquid_factor = np.pi if convention == "xie" else 1.0
    return (
        coating / np.sin(theta) ** 2 + 0 * r,
        theta * r / (4 * p.conductivity * np.sin(theta) * liquid_factor),
        1 / (2 * interface_coefficient(p) * (1 - np.cos(theta))) + 0 * r,
    )


def heat_rate(r, subcooling, theta, coating, p, convention="kim"):
    r0 = critical_radius(subcooling, p)
    rc, rl, ri = resistance_terms(r, theta, coating, p, convention)
    return subcooling * np.pi * r * (r - r0) / (rc + rl + ri)


def growth_coefficients(subcooling, theta, coating, p, convention="kim"):
    """G=A*(r-r0)/(r*(r+B)) from spherical-cap energy conservation."""
    factor = np.pi if convention == "xie" else 1.0
    slope = theta / (4 * p.conductivity * np.sin(theta) * factor)
    offset = coating / np.sin(theta) ** 2 + 1 / (2 * interface_coefficient(p) * (1 - np.cos(theta)))
    cap = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
    return subcooling / (p.rho_l * p.latent_heat * cap * slope), offset / slope


def sliding_radius(theta, advancing, receding, p, model="xie"):
    shape = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
    if model == "xie":
        return np.sqrt(
            12
            / np.pi**2
            * np.sin(theta)
            * (np.cos(receding) - np.cos(advancing))
            * p.tension
            / ((p.rho_l - p.rho_v) * p.gravity * shape)
        )
    if model == "croce":
        return (
            12
            / np.pi**2
            * np.sqrt(
                p.tension * (np.cos(receding) - np.cos(advancing)) / (p.rho_l * p.gravity * shape)
            )
        )
    raise ValueError("Unknown departure model")


def nusselt_flux(subcooling, height, p):
    if subcooling == 0:
        return 0.0
    return (
        0.943
        * (
            p.rho_l
            * (p.rho_l - p.rho_v)
            * p.gravity
            * p.latent_heat
            * p.conductivity**3
            / (p.viscosity * height)
        )
        ** 0.25
        * subcooling**0.75
    )
