"""Three-phase short-circuit currents (IEC 60909) at maximum and minimum source strength."""
import pandas as pd
import pandapower.shortcircuit as sc


def short_circuit_table(net, ibr_k=1.2):
    """Initial symmetrical short-circuit current Ik'' [kA] per bus; max case sizes breakers, min case checks protection sensitivity.

    Inverter-based DER (sgen) are modelled as current sources limited to ibr_k x rated current
    (IEC 60909-0 style; ibr_k=1.2 is a typical converter limit) -- they add little fault current, which is
    exactly the protection-sensitivity issue of IBR-rich networks.
    """
    net.sgen["k"] = ibr_k
    net.line["endtemp_degree"] = 80.0   # conductor end temperature for the min-current resistance correction
    out = {}
    for case in ("max", "min"):
        sc.calc_sc(net, case=case, fault="3ph", ip=False, ith=False)
        out[f"ikss_{case}_ka"] = net.res_bus_sc.ikss_ka.copy()
    df = pd.DataFrame(out)
    df.insert(0, "bus", net.bus.name)
    df["max_min_ratio"] = df.ikss_max_ka / df.ikss_min_ka
    return df
