"""Fixed saturation properties; never call an external property backend inside Autograd."""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Water:
    temperature: float
    rho_l: float
    rho_v: float
    latent_heat: float
    conductivity: float
    viscosity: float
    tension: float
    source: str
    gas_constant: float = 461.52
    gravity: float = 9.81


# Xie Table 2, converted from kJ/kg, mW/mK, mPa s, mN/m.
_TABLE = {
    60: (983.16, 0.130, 2357620.0, 0.65435, 0.000466, 0.066238),
    90: (965.30, 0.424, 2282460.0, 0.67525, 0.000314, 0.060816),
    120: (943.11, 1.122, 2202090.0, 0.68319, 0.000232, 0.054968),
    150: (917.01, 2.548, 2113720.0, 0.68204, 0.000182, 0.048741),
    # Rounded standard saturation data, explicitly distinct from Xie's Table 2.
    100: (958.35, 0.59817, 2256400.0, 0.677, 0.0002816, 0.05891),
}


@lru_cache(maxsize=64)
def water(temperature=373.15, backend="table"):
    """No silent interpolation/extrapolation of the paper property table."""
    if backend == "coolprop":
        from CoolProp.CoolProp import PropsSI

        t = float(temperature)

        def prop(key, q=0):
            return PropsSI(key, "T", t, "Q", q, "Water")

        return Water(
            t,
            prop("D"),
            prop("D", 1),
            prop("H", 1) - prop("H"),
            prop("L"),
            prop("V"),
            prop("I"),
            "CoolProp saturation",
        )
    if backend != "table":
        raise ValueError("backend must be table or coolprop")
    tc = round(temperature - 273.15, 8)
    if tc not in _TABLE:
        raise ValueError("Table supports 60, 90, 100, 120, 150 C; use optional CoolProp otherwise")
    source = "rounded 100 C saturation reference" if tc == 100 else "Xie 2020 Table 2"
    return Water(temperature, *_TABLE[tc], source)
