"""Wind hosting capacity at the end of the overhead feeder: static vs ambient-adjusted thermal limit."""
import numpy as np
import pandas as pd
import pandapower as pp

from .config import LIMITS
from .network import NEW_WIND_BUS, build_network
from .timeseries import thermal_factor


def _check(net, ambient_c=None):
    """Return (ok, limiting constraint) for the current power-flow result."""
    vm = net.res_bus.vm_pu
    loading = net.res_line.loading_percent.copy()
    if ambient_c is not None:   # ambient-adjusted ampacity on overhead lines only
        ohl = net.line.std_type.str.startswith("OHL")
        loading[ohl] = loading[ohl] / float(thermal_factor(ambient_c))
    if vm.max() > LIMITS.v_max_pu:
        return False, "overvoltage"
    if loading.max() > LIMITS.loading_max_pct:
        return False, "line thermal"
    if net.res_trafo.loading_percent.max() > LIMITS.loading_max_pct:
        return False, "transformer thermal"
    return True, ""


def wind_hosting(ambient_c=None, pf=0.95, load_factor=0.30, step_mw=0.25, max_mw=20.0):
    """Largest wind plant at bus 14 [MW] that keeps limits at minimum demand and full output.

    ambient_c=None uses the static rating; a temperature applies the simplified ambient-adjusted rating.
    Returns (sweep DataFrame, hosting capacity MW, limiting constraint at the first violation).
    """
    rows, limit, reason = [], 0.0, "none up to max_mw"
    for mw in np.arange(step_mw, max_mw + step_mw, step_mw):
        net = build_network(new_wind_mw=mw, new_wind_pf=pf)
        net.load["scaling"] = load_factor
        try:
            pp.runpp(net)
        except pp.LoadflowNotConverged:
            reason = "no convergence"
            break
        ok, why = _check(net, ambient_c)
        rows.append({"wind_mw": mw, "vmax_pu": net.res_bus.vm_pu.max(),
                     "max_ohl_loading_pct": net.res_line.loading_percent.max(), "ok": ok})
        if not ok:
            reason = why
            break
        limit = float(mw)
    return pd.DataFrame(rows), limit, reason
