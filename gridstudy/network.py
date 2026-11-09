"""Network construction and base-case power flow."""
import numpy as np
import pandapower as pp
import pandapower.networks as pn

from .config import LIMITS


NEW_WIND_BUS = 14   # end of the overhead-line section 12-13-14 (feeder 2)


def build_network(new_wind_mw=0.0, new_wind_pf=0.95):
    """CIGRE MV benchmark (20 kV, 2 feeders, normally-open tie points) with PV and wind DER.

    new_wind_mw > 0 adds a wind plant at the end of the overhead section (bus 14): the
    typical "new renewable connection on a rural OHL feeder" case used in the rating / hosting study.
    The plant absorbs reactive power at power factor new_wind_pf (voltage-rise mitigation, grid-code style).
    """
    net = pn.create_cigre_network_mv(with_der="pv_wind")
    if new_wind_mw > 0:
        pp.create_sgen(net, bus=NEW_WIND_BUS, p_mw=new_wind_mw, q_mvar=-new_wind_mw * np.tan(np.arccos(new_wind_pf)),
                       sn_mva=new_wind_mw, name="WKA 14 (new)", type="wind")
    return net


def violations(net, limits=LIMITS):
    """Count voltage and thermal violations in the current power-flow results (NaN = de-energised)."""
    vm = net.res_bus.vm_pu
    n_v = int(((vm < limits.v_min_pu) | (vm > limits.v_max_pu)).sum())
    n_l = int((net.res_line.loading_percent > limits.loading_max_pct).sum())
    n_t = int((net.res_trafo.loading_percent > limits.loading_max_pct).sum())
    return {"voltage": n_v, "line_loading": n_l, "trafo_loading": n_t, "total": n_v + n_l + n_t}


def base_case(net):
    """Run AC power flow and return a summary dict (used in the report and in tests)."""
    pp.runpp(net)
    losses = net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum()
    return {
        "load_mw": net.res_load.p_mw.sum(),
        "der_mw": net.res_sgen.p_mw.sum(),
        "slack_mw": net.res_ext_grid.p_mw.sum(),
        "losses_mw": losses,
        "vmin_pu": net.res_bus.vm_pu.min(),
        "vmax_pu": net.res_bus.vm_pu.max(),
        "max_line_loading_pct": net.res_line.loading_percent.max(),
        **{f"violations_{k}": v for k, v in violations(net).items()},
    }
