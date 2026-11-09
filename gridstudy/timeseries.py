"""Synthetic weekly profiles, hourly AC power-flow series and static vs ambient-adjusted line rating."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandapower as pp

from .config import LIMITS, THERMAL


@dataclass(frozen=True)
class Scenario:
    load_scale: float = 1.0   # multiplier on base loads (demand growth)
    pv_scale: float = 1.0     # multiplier on installed PV
    wind_scale: float = 1.0   # multiplier on installed wind


def make_profiles(hours=24 * 7, seed=42):
    """Synthetic, seeded hourly profiles: demand, PV, wind capacity factors (p.u.) and ambient temperature (degC).

    NOT measured data -- shapes are typical (evening-peak demand, clear-sky PV bell, AR(1) wind).
    """
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-01-05", periods=hours, freq="h")   # starts on a Monday
    h = t.hour.to_numpy()
    day = np.arange(hours) // 24

    bell = lambda mu, sd: np.exp(-0.5 * ((h - mu) / sd) ** 2)
    weekend = np.where(t.dayofweek >= 5, 0.92, 1.0)
    load = (0.55 + 0.30 * bell(19, 3) + 0.15 * bell(12, 3)) * weekend + rng.normal(0, 0.02, hours)

    cloud = rng.uniform(0.5, 1.0, hours // 24 + 1)[day]
    pv = np.clip(np.sin(np.pi * (h - 6) / 12), 0, None) * cloud

    x = np.zeros(hours)
    for i in range(1, hours):
        x[i] = 0.95 * x[i - 1] + rng.normal(0, 0.06)
    wind = np.clip(0.35 + x, 0, 1)

    ambient = 29 + 6 * np.sin(2 * np.pi * (h - 9) / 24) + rng.normal(0, 1.5, hours // 24 + 1)[day]
    return pd.DataFrame({"load": load.clip(0.3, 1), "pv": pv, "wind": wind, "ambient_c": ambient}, index=t)


def thermal_factor(ambient_c, t_ref=THERMAL.t_ref_c, t_max=THERMAL.t_cond_max_c):
    """Ampacity multiplier relative to the static rating: sqrt((Tmax - Ta) / (Tmax - Tref))."""
    return np.sqrt((t_max - np.asarray(ambient_c, dtype=float)) / (t_max - t_ref))


def apply_hour(net, row, scenario):
    """Write one profile row into the network (scaling factors, not absolute values)."""
    net.load["scaling"] = row["load"] * scenario.load_scale
    is_pv = net.sgen.name.str.startswith("PV")
    net.sgen.loc[is_pv, "scaling"] = row["pv"] * scenario.pv_scale
    net.sgen.loc[~is_pv, "scaling"] = row["wind"] * scenario.wind_scale


def run_timeseries(net, profiles, scenario=Scenario()):
    """Hourly power flow. Returns (summary per hour, line loading [%] per hour/line)."""
    summary, loading = [], []
    for ts, row in profiles.iterrows():
        apply_hour(net, row, scenario)
        pp.runpp(net)
        summary.append({
            "time": ts,
            "load_mw": net.res_load.p_mw.sum(),
            "der_mw": net.res_sgen.p_mw.sum(),
            "losses_mw": net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum(),
            "vmin_pu": net.res_bus.vm_pu.min(),
            "vmax_pu": net.res_bus.vm_pu.max(),
            "trafo_max_loading_pct": net.res_trafo.loading_percent.max(),
        })
        loading.append(net.res_line.loading_percent.rename(ts))
    summary = pd.DataFrame(summary).set_index("time")
    loading = pd.DataFrame(loading)
    loading.columns = net.line.name
    return summary, loading


def rating_comparison(net, loading_static, ambient_c):
    """Re-express overhead-line loading against an ambient-adjusted ampacity (cables unchanged)."""
    ohl = net.line.name[net.line.std_type.str.startswith("OHL")]
    factor = pd.Series(thermal_factor(ambient_c), index=loading_static.index)
    dyn = loading_static.copy()
    dyn[ohl] = loading_static[ohl].div(factor, axis=0)
    limit = LIMITS.loading_max_pct
    rows = []
    for name in ohl:
        rows.append({
            "line": name,
            "peak_static_pct": loading_static[name].max(),
            "peak_adjusted_pct": dyn[name].max(),
            "hours_over_static": int((loading_static[name] > limit).sum()),
            "hours_over_adjusted": int((dyn[name] > limit).sum()),
            "mean_extra_capacity_pct": float((factor.mean() - 1) * 100),
        })
    return pd.DataFrame(rows), dyn
