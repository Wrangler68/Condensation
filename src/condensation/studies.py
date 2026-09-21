"""Reproducible sweeps and transparent figure checks (not claimed as full validation)."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import croce2024 as croce
from . import xie2020 as xie
from .properties import water
from .types import Geometry, SteamConditions, Surface

ROOT = Path(__file__).resolve().parents[2]


def figure_checks():
    data = json.loads((ROOT / "data/digitized/figure_checks.json").read_text())
    rows = []
    for point in data["points"]:
        c = SteamConditions(subcooling=point["subcooling_K"])
        if point["case"] == "Croce Fig.7a":
            q = float(
                sum(
                    croce.dwc_components(
                        c.subcooling, 2 * np.pi / 3, 3.39e-7, water(), 0.00125, reference=True
                    )
                )
            )
        elif point["case"] == "Croce Fig.8b":
            q = croce.solve(c, reference=True).heat_flux
        else:
            q = xie.solve(
                c, Surface(coating_resistance=5e-9), Geometry(0.00046, 0.00044), reference=True
            ).heat_flux
        rows.append(
            {**point, "computed_flux_W_m2": q, "relative_error": q / point["paper_flux_W_m2"] - 1}
        )
    return rows


def croce_heatmap(ld_values, lf_values, conditions=None, surface=None):
    rows = []
    flood = []
    for lf in lf_values:
        results = [
            croce.solve(conditions, surface, Geometry(float(ld), float(lf))) for ld in ld_values
        ]
        rows.append([r.heat_flux / 1000 for r in results])
        flood.append([r.flooding_ratio for r in results])
    return np.array(rows), np.array(flood)


def export_record(model, inputs, result):
    import importlib.metadata as metadata

    def convert(obj):
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        raise TypeError(type(obj).__name__)

    record = {
        "model": model,
        "inputs": inputs,
        "result": result,
        "versions": {
            name: metadata.version(name)
            for name in ("numpy", "scipy", "autograd", "plotly", "marimo")
        },
        "units": "SI except explicitly labeled fields",
    }

    # Non-finite numbers are serialized as null, never nonstandard JSON NaN.
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [sanitize(v) for v in obj]
        if isinstance(obj, float) and not np.isfinite(obj):
            return None
        return obj

    return json.dumps(
        sanitize(json.loads(json.dumps(record, default=convert))), indent=2, allow_nan=False
    )
