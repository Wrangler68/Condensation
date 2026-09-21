from dataclasses import replace

import numpy as np
import pytest
from autograd import grad
from autograd.numpy import exp as np_exp
from autograd.numpy import log as np_log

from condensation import Geometry, SteamConditions, Surface, water
from condensation import croce2024 as croce
from condensation import lee2020 as lee
from condensation import xie2020 as xie
from condensation.droplets import critical_radius, growth_coefficients, heat_rate
from condensation.geometry import finite_stripes
from condensation.populations import flux_components, large_distribution, small_distribution


def test_population_boundary_and_slope():
    p = water()
    theta = np.deg2rad(120)
    dt = 6.0
    coat = 3.39e-7
    r0 = critical_radius(dt, p)
    rn = croce.nucleation_radius(dt, theta, coat, p)
    re = rn / (2 * np.sqrt(0.037))
    rm = 0.00125
    a, b = growth_coefficients(dt, theta, coat, p)
    for linear in (False, True):

        def fn(r):
            return small_distribution(r, re, r0, rm, a, b, linear)

        assert fn(re) == pytest.approx(large_distribution(re, rm))
        assert grad(lambda log_r: np_log(fn(np_exp(log_r))))(np.log(re)) == pytest.approx(
            -8 / 3, rel=1e-10
        )


def test_nucleation_stationary_maximum_and_trends():
    p = water()
    v = np.array([6.0, 2 * np.pi / 3, 3.39e-7])
    rn = croce.nucleation_radius(*v, p)
    z = np.log(rn / critical_radius(v[0], p))
    assert abs(grad(croce.availability_scaled, 0)(z, v, p)) < 1e-7
    assert grad(grad(croce.availability_scaled, 0), 0)(z, v, p) < 0
    assert rn > croce.nucleation_radius(6.0, v[1], 0.0, p) > critical_radius(6.0, p)


@pytest.mark.parametrize("linear", [False, True])
def test_radial_reference_convergence(linear):
    p = water()
    theta = 2 * np.pi / 3
    dt = 6.0
    coat = 3.39e-7
    rn = croce.nucleation_radius(dt, theta, coat, p) if linear else critical_radius(dt, p)
    re = rn / (2 * np.sqrt(0.037)) if linear else 1e-6
    args = (dt, theta, coat, p, rn, re, 0.00125)
    q64 = sum(flux_components(*args, linear=linear, order=64))
    q128 = sum(flux_components(*args, linear=linear, order=128))
    ref = sum(flux_components(*args, linear=linear, reference=True))
    assert q128 == pytest.approx(ref, rel=5e-3)
    assert q64 == pytest.approx(q128, rel=5e-3)


def test_rivulet_cross_section_and_mass_energy():
    p = water()
    width = 0.00045
    dt = 6.0
    migration = 1e-4
    height = 0.02
    assert croce.rivulet_factor(1e-6) == pytest.approx(16 / 35, rel=1e-7)
    assert croce.film_flow(width / 2, width, p) == pytest.approx(
        croce.critical_flow(width, p), rel=1e-7
    )
    delta, out, qf, ratio = croce.film_state(width, migration, dt, height, p)
    assert delta > 0 and qf > 0 and ratio < 1
    assert out == pytest.approx(migration * height + qf * height * width / p.latent_heat, rel=1e-12)
    assert croce.film_height_relation(delta, width, migration, dt, p) == pytest.approx(
        height, rel=1e-9
    )
    assert croce.film_state(width, 0, dt, height, p)[2] > qf


def test_flooding_is_not_extrapolated():
    r = croce.solve(geometry=Geometry(0.0005, 0.00003))
    assert not r.valid and np.isnan(r.heat_flux) and r.flooding_ratio > 1
    w = croce.minimum_fwc_width(0.0005, 6.0, 2 * np.pi / 3, 3.39e-7, water(), 0.02)
    r = croce.solve(geometry=Geometry(0.0005, w * 1.001))
    assert r.valid and r.flooding_ratio < 1


def test_xie_partial_transfer_and_spatial_convergence():
    c, s, g = xie.preset()
    g = replace(g, dwc_width=0.003)
    r = xie.solve(c, s, g, dx=2e-6)
    fine = xie.solve(c, s, g, dx=1e-6)
    assert 0 < fine.transferred_flux < fine.dwc_flux
    assert fine.heat_flux == pytest.approx(r.heat_flux, rel=0.005)
    q = xie.stripe_profile(c, s, g, dx=4e-6)
    assert q["weights"].sum() == pytest.approx(1)
    assert np.all(q["rmax"] <= q["sliding_radius"])


@pytest.mark.parametrize("model", [xie, croce])
def test_endpoints(model):
    assert model.solve(SteamConditions(subcooling=0)).heat_flux == 0
    for g in (Geometry(0, 0.001), Geometry(0.001, 0)):
        r = model.solve(geometry=g)
        assert r.valid and np.isfinite(r.heat_flux) and r.heat_flux > 0


def test_lee_finite_geometry_mass_and_balance():
    g = finite_stripes(0.0006, 0.0034)
    assert g["sar"] == pytest.approx(0.85)
    assert g["interface_length"] == pytest.approx(0.76)
    r = lee.solve()
    film = r["film_transport"]
    assert r["mass_4h_kg"] == pytest.approx(r["fwc_mass_4h_kg"] + r["dwc_mass_4h_kg"])
    assert abs(film["energy_residual"]) < 1e-7
    assert r["mass_4h_kg"] == pytest.approx(0.00184, rel=0.08)
    assert lee.solve(0.0005, 0.0028)["mass_4h_kg"] == pytest.approx(0.002, rel=0.04)
    assert lee.dwc_mass_4h(0.0) == 0
    assert lee.dwc_mass_4h(10.0) == pytest.approx(0.000695)
    assert lee.solve(baseline="paper_theory")["mass_4h_kg"] < r["mass_4h_kg"]


def test_implicit_autograd_against_finite_differences():
    p = water()
    v = np.array([0.00055, 0.00045, 6.0, 3.39e-7])

    def fn(z):
        return croce.smooth_plate_flux(z, p)

    analytic = grad(fn)(v)
    for i in range(4):
        h = abs(v[i]) * 1e-4
        vp = v.copy()
        vm = v.copy()
        vp[i] += h
        vm[i] -= h
        numeric = (fn(vp) - fn(vm)) / (2 * h)
        assert analytic[i] == pytest.approx(numeric, rel=1e-3)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        Geometry(-1, 0.001)
    with pytest.raises(ValueError):
        Surface(receding=3.0)
    with pytest.raises(ValueError):
        water(350)
    with pytest.raises(ValueError):
        lee.film_balance(wall_c=20)


def test_single_drop_energy_and_coating():
    p = water()
    r = 1e-5
    dt = 6.0
    theta = 2 * np.pi / 3
    r0 = critical_radius(dt, p)
    assert heat_rate(r0, dt, theta, 0.0, p) == 0
    assert heat_rate(r, dt, theta, 1e-7, p) < heat_rate(r, dt, theta, 0.0, p)
    a, b = growth_coefficients(dt, theta, 1e-7, p)
    growth = a * (r - r0) / (r * (r + b))
    dvolume = np.pi * r * r * (1 - np.cos(theta)) ** 2 * (2 + np.cos(theta))
    assert heat_rate(r, dt, theta, 1e-7, p) == pytest.approx(
        p.rho_l * p.latent_heat * dvolume * growth
    )
