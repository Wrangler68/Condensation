import numpy as np
import pytest

from condensation import croce2024 as croce
from condensation import water
from condensation.optimization import optimize_croce, optimize_lee, optimize_plate
from condensation.studies import export_record


def test_plate_optimizer_and_reference_recheck():
    r = optimize_plate([0.00055, 0.0006, 6.0, 3.39e-7])
    assert r["success"]
    assert r["feasibility"] >= -1e-7
    ld, lf, dt, coat = r["parameters"]
    p = water()
    theta = 2 * np.pi / 3
    qd = sum(croce.dwc_components(dt, theta, coat, p, ld / (2 * np.sin(theta)), reference=True))
    qf = croce.film_state(lf, qd * ld / p.latent_heat, dt, 0.02, p)[2]
    ref = (qd * ld + qf * lf) / (ld + lf)
    assert r["flux"] == pytest.approx(ref, rel=0.005)


def test_disk_optimizer_beats_grid_and_is_feasible():
    r = optimize_croce(grid_size=8)
    assert r["result"]["valid"]
    assert r["result"]["flooding_ratio"] < 1
    assert r["result"]["heat_flux"] >= max(r["grid_fluxes"]) * 0.999


def test_lee_search_stays_in_envelope():
    r = optimize_lee()
    assert r["result"]["within_design_envelope"]
    assert r["dwc_width"] >= 0.0005
    assert r["result"]["mass_4h_kg"] == pytest.approx(0.002, rel=0.05)


def test_json_invalid_flux_is_null():
    import json

    record = json.loads(export_record("test", {}, {"flux": float("nan")}))
    assert record["result"]["flux"] is None
