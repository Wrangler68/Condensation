"""Fixed nodes are constants; mapping and weights retain parameter derivatives."""

from functools import lru_cache

import autograd.numpy as anp
import numpy as np
from scipy.integrate import quad


@lru_cache(maxsize=16)
def rule(order=96):
    x, w = np.polynomial.legendre.leggauss(order)
    x.setflags(write=False)
    w.setflags(write=False)
    return x, w


def integrate(func, lower, upper, order=96):
    x, w = rule(order)
    half = (upper - lower) / 2
    return half * anp.sum(w * func(lower + (x + 1) * half), axis=-1)


def log_integrate(func, lower, upper, order=96):
    return integrate(lambda z: func(anp.exp(z)) * anp.exp(z), anp.log(lower), anp.log(upper), order)


def reference_log_integrate(func, lower, upper):
    if upper <= lower:
        return 0.0
    return quad(
        lambda z: float(func(np.exp(z))) * np.exp(z),
        np.log(lower),
        np.log(upper),
        epsabs=1e-6,
        epsrel=2e-8,
        limit=250,
    )[0]
