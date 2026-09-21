"""Public inputs are validated and immutable. Temperatures in K, angles in radians."""

from dataclasses import asdict, dataclass
from math import isfinite, pi


@dataclass(frozen=True)
class SteamConditions:
    temperature: float = 373.15
    subcooling: float = 6.0

    def __post_init__(self):
        if not (
            273.15 < self.temperature < 647 and 0 <= self.subcooling < self.temperature - 273.15
        ):
            raise ValueError(
                "Require liquid-water steam temperature and nonnegative subcooling above freezing"
            )


@dataclass(frozen=True)
class Surface:
    theta: float = 120 * pi / 180
    advancing: float = 142 * pi / 180
    receding: float = 102 * pi / 180
    coating_resistance: float = 3.39e-7
    nucleation_density: float = 2.5e11

    def __post_init__(self):
        if not (0 < self.receding <= self.theta <= self.advancing < pi):
            raise ValueError("Require 0 < receding <= static <= advancing < pi")
        if not (
            isfinite(self.coating_resistance)
            and self.coating_resistance >= 0
            and self.nucleation_density > 0
        ):
            raise ValueError("Invalid coating resistance or nucleation density")


@dataclass(frozen=True)
class Geometry:
    dwc_width: float = 0.55e-3
    fwc_width: float = 0.45e-3
    radius: float = 0.01

    def __post_init__(self):
        if not all(isfinite(v) for v in asdict(self).values()):
            raise ValueError("Geometry must be finite")
        if min(self.dwc_width, self.fwc_width) < 0 or self.radius <= 0:
            raise ValueError("Widths must be nonnegative, radius positive")
        if self.dwc_width + self.fwc_width <= 0:
            raise ValueError("At least one stripe width must be positive")

    @property
    def dwc_fraction(self):
        return self.dwc_width / (self.dwc_width + self.fwc_width)


@dataclass(frozen=True)
class SteamResult:
    model: str
    heat_flux: float
    dwc_flux: float
    fwc_flux: float
    htc: float
    film_thickness: float
    transferred_flux: float
    flooding_ratio: float = 0.0
    valid: bool = True
    notes: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)
