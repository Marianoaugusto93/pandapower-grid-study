import numpy as np
import pandapower as pp
import pytest

from gridstudy.config import THERMAL
from gridstudy.contingency import n1_analysis
from gridstudy.hosting import wind_hosting
from gridstudy.network import base_case, build_network
from gridstudy.shortcircuit import short_circuit_table
from gridstudy.timeseries import Scenario, make_profiles, rating_comparison, run_timeseries, thermal_factor


def test_power_balance_closes():
    """Slack + DER = load + losses (AC power flow must conserve active power)."""
    net = build_network()
    b = base_case(net)
    assert b["slack_mw"] + b["der_mw"] - b["load_mw"] - b["losses_mw"] == pytest.approx(0, abs=1e-6)


def test_new_wind_plant_adds_generation_and_absorbs_q():
    net = build_network(new_wind_mw=5.0, new_wind_pf=0.9)
    new = net.sgen[net.sgen.name == "WKA 14 (new)"].iloc[0]
    assert new.p_mw == 5.0
    assert new.q_mvar == pytest.approx(-5.0 * np.tan(np.arccos(0.9)))


def test_short_circuit_max_not_below_min_and_source_bus_matches_ssc():
    sc = short_circuit_table(build_network())
    assert (sc.ikss_max_ka >= sc.ikss_min_ka - 1e-9).all()
    # 5000 MVA at 110 kV -> ~26.2 kA at the slack bus (c-factor aside)
    expected = 5000 / (np.sqrt(3) * 110)
    assert sc.ikss_max_ka.iloc[0] == pytest.approx(expected, rel=0.05)


def test_n1_trafo_outage_isolates_load_and_restoration_never_worsens():
    n1 = n1_analysis(build_network())
    ok = n1[n1.converged]
    t0 = ok[ok.element == "trafo 0"].iloc[0]
    assert t0.unserved_mw > 10                       # whole feeder 1 loses supply
    assert (ok.unserved_after_mw <= ok.unserved_mw + 1e-9).all()
    assert not n1.element.str.contains("line 12").any()   # open-ended tie line is not an N-1 candidate


def test_profiles_are_deterministic_and_bounded():
    a, b = make_profiles(seed=1), make_profiles(seed=1)
    assert a.equals(b)
    assert a.load.between(0.3, 1).all() and a.pv.between(0, 1).all() and a.wind.between(0, 1).all()
    assert (a.pv[a.index.hour < 6] == 0).all()        # no PV at night


def test_thermal_factor_monotonic_and_unity_at_reference():
    assert thermal_factor(THERMAL.t_ref_c) == pytest.approx(1.0)
    assert thermal_factor(30) > 1 > thermal_factor(50)
    assert thermal_factor(20) > thermal_factor(30)


def test_adjusted_rating_never_exceeds_static_loading_below_reference_temperature():
    net = build_network(new_wind_mw=10, new_wind_pf=0.9)
    prof = make_profiles(hours=48)
    _, loading = run_timeseries(net, prof, Scenario())
    cmp, adj = rating_comparison(net, loading, prof.ambient_c.clip(upper=THERMAL.t_ref_c))
    assert (adj.values <= loading.values + 1e-9).all()
    assert (cmp.hours_over_adjusted <= cmp.hours_over_static).all()


def test_hosting_increases_with_cooler_ambient_when_thermally_limited():
    _, mw_static, why = wind_hosting(ambient_c=40, pf=0.90)
    _, mw_cool, _ = wind_hosting(ambient_c=25, pf=0.90)
    assert why == "line thermal"
    assert mw_cool > mw_static
