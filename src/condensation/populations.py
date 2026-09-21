"""Population balance integrals, with analytic Q*n cancellation at the critical radius."""

import autograd.numpy as np

from .droplets import critical_radius, growth_coefficients, heat_rate
from .quadrature import log_integrate, reference_log_integrate


def large_distribution(r, rmax):
    return (rmax / r) ** (2 / 3) / (3 * np.pi * r * r * rmax)


def sweeping_time(re, r0, a, b):
    return 3 * re**2 * (re + b) ** 2 / (a * (11 * re**2 - 14 * re * r0 + 8 * b * re - 11 * b * r0))


def log_population_ratio(r, re, r0, a, b, linear):
    tau = sweeping_time(re, r0, a, b)
    logterm = np.log((re - r0) / (r - r0))
    if linear:
        return re / (tau * a) * ((re - r) + (r0 + b) * logterm)
    return ((re**2 - r**2) / 2 + (r0 + b) * (re - r) + r0 * (r0 + b) * logterm) / (tau * a)


def small_distribution(r, re, r0, rmax, a, b, linear=False):
    ratio = r / re * (re - r0) / (r - r0) * (r + b) / (re + b)
    return (
        large_distribution(re, rmax) * ratio * np.exp(log_population_ratio(r, re, r0, a, b, linear))
    )


def flux_components(
    subcooling,
    theta,
    coating,
    p,
    rn,
    re,
    rmax,
    linear=False,
    convention="kim",
    order=96,
    reference=False,
):
    """Truncate a population at rmax; keep its specified matching radius re.

    The small-radius singularity cancels analytically in Q*n. Nodes never touch rn.
    For Xie rmax<re this retains Eq.12's reference population while truncating Eq.8.
    """
    if rmax <= rn:
        return 0.0, 0.0
    r0 = critical_radius(subcooling, p)
    if re <= r0 or rn < r0 * (1 - 1e-12):
        raise ValueError("Population requires r0 <= rn < re")
    a, b = growth_coefficients(subcooling, theta, coating, p, convention)
    if sweeping_time(re, r0, a, b) <= 0:
        raise ValueError("Nonpositive sweeping time: outside population-model domain")
    # Q/G = rho*hfg*pi*r^2*cap_factor; removes the 0*infinity endpoint.
    ge = a * (re - r0) / (re * (re + b))
    cap = (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))

    def small_integrand(r):
        return (
            p.rho_l
            * p.latent_heat
            * np.pi
            * r
            * r
            * cap
            * large_distribution(re, rmax)
            * ge
            * np.exp(log_population_ratio(r, re, r0, a, b, linear))
        )

    fn = reference_log_integrate if reference else lambda f, lo, hi: log_integrate(f, lo, hi, order)
    upper = np.minimum(re, rmax)
    small = fn(small_integrand, rn, upper) if upper > rn else 0.0
    large = (
        fn(
            lambda r: (
                heat_rate(r, subcooling, theta, coating, p, convention)
                * large_distribution(r, rmax)
            ),
            re,
            rmax,
        )
        if rmax > re
        else 0.0
    )
    return small, large
