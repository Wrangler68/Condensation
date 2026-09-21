"""Generate repeatable numerical and paper-comparison evidence: uv run python scripts/validate.py."""

from pathlib import Path

import numpy as np
from autograd import grad

from condensation import croce2024 as croce
from condensation import lee2020 as lee
from condensation import water
from condensation import xie2020 as xie
from condensation.optimization import optimize_croce, optimize_lee, optimize_plate
from condensation.studies import export_record, figure_checks


def main():
    out = Path("output")
    out.mkdir(exist_ok=True)
    checks = figure_checks()
    v = np.array([0.00055, 0.0006, 6.0, 3.39e-7])

    def fn(z):
        return croce.smooth_plate_flux(z, water())

    analytic = grad(fn)(v)
    numerical = []
    for i in range(4):
        h = v[i] * 1e-4
        vp = v.copy()
        vm = v.copy()
        vp[i] += h
        vm[i] -= h
        numerical.append((fn(vp) - fn(vm)) / (2 * h))
    report = {
        "paper_curve_checks": checks,
        "croce_default": croce.solve(),
        "xie_default": xie.solve(),
        "lee_default": lee.solve(),
        "autograd": analytic,
        "finite_difference": np.array(numerical),
        "croce_optimization": optimize_croce(grid_size=20),
        "plate_optimization": optimize_plate(v),
        "lee_optimization": optimize_lee(),
    }
    payload = export_record(
        "Validation and exploratory optimization", {"plate_parameters": v}, report
    )
    (out / "validation.json").write_text(payload, encoding="utf-8")
    for row in checks:
        print(f"{row['case']} DT={row['subcooling_K']}: error {row['relative_error']:+.1%}")
    print(
        "Gradient maximum relative difference:", np.max(np.abs((analytic - numerical) / analytic))
    )
    print("Wrote output/validation.json")


if __name__ == "__main__":
    main()
