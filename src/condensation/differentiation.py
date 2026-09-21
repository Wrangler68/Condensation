"""First-order implicit differentiation of scalar, bracketed residual roots."""

import numpy as np
from autograd import grad
from autograd.extend import defvjp, primitive
from scipy.optimize import brentq


def implicit_solver(residual, lower, upper):
    """Residual signature (scalar_state, parameter_vector); bracket must contain a simple root.

    Derivatives are valid inside one smooth branch. Higher derivatives are not promised.
    """

    @primitive
    def solve(parameters):
        return brentq(
            lambda z: float(residual(z, parameters)), lower, upper, xtol=1e-12, rtol=1e-12
        )

    def vjp(answer, parameters):
        fz = grad(residual, 0)(answer, parameters)
        fp = grad(residual, 1)(answer, parameters)
        if not np.isfinite(fz) or abs(fz) < 1e-20:
            raise ValueError("Degenerate implicit root; sensitivity is undefined")
        return lambda cotangent: -cotangent * fp / fz

    defvjp(solve, vjp)
    return solve


def normalized_sensitivity(function, parameters):
    parameters = np.array(parameters, dtype=float)
    value = function(parameters)
    if value == 0:
        raise ValueError("Normalized sensitivity undefined at zero output")
    return parameters * grad(function)(parameters) / value
