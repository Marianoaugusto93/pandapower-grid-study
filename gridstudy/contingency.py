"""N-1 security assessment with a greedy restoration step (closing normally-open tie switches)."""
import copy

import pandas as pd
import pandapower as pp

from .network import violations


def _solve(net):
    """Run power flow; return (unserved_mw, violations_total) or None if it does not converge."""
    try:
        pp.runpp(net)
    except pp.LoadflowNotConverged:
        return None
    dead = net.res_bus.index[net.res_bus.vm_pu.isna()]
    unserved = net.load.loc[net.load.in_service & net.load.bus.isin(dead), "p_mw"].sum()
    return float(unserved), violations(net)["total"]


def _candidates(net):
    """Elements that carry load current (> 1 A) in the base case; open-ended lines only draw charging current."""
    pp.runpp(net)
    lines = net.res_line.index[net.res_line.i_ka.fillna(0) > 1e-3]
    trafos = net.res_trafo.index[net.res_trafo.i_hv_ka.fillna(0) > 1e-3]
    return [("line", i) for i in lines] + [("trafo", i) for i in trafos]


def n1_analysis(net):
    """For each loaded element: outage -> isolated load / violations -> best tie-switch restoration.

    `violations` counts all voltage/thermal violations in the post-outage state, including those already present
    in the base case. `tie` is NaN when no tie closure converged or improved the outcome (no feasible restoration).
    Restoration objective: minimise (unserved MW, then violations).
    """
    tie_switches = net.switch.index[(net.switch.et == "l") & (~net.switch.closed)]
    rows = []
    for et, idx in _candidates(net):
        post = copy.deepcopy(net)
        getattr(post, et).at[idx, "in_service"] = False
        base = _solve(post)
        if base is None:
            rows.append({"element": f"{et} {idx}", "name": net[et].at[idx, "name"], "converged": False})
            continue
        best = {"tie": None, "unserved_after_mw": base[0], "violations_after": base[1]}
        for sw in tie_switches:
            trial = copy.deepcopy(post)
            trial.switch.at[sw, "closed"] = True
            res = _solve(trial)
            if res is not None and (res[0], res[1]) < (best["unserved_after_mw"], best["violations_after"]):
                best = {"tie": int(sw), "unserved_after_mw": res[0], "violations_after": res[1]}
        rows.append({
            "element": f"{et} {idx}", "name": net[et].at[idx, "name"], "converged": True,
            "unserved_mw": base[0], "violations": base[1], **best,
        })
    return pd.DataFrame(rows)
