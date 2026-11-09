"""Study-wide limits and assumptions. Change here, not in the analysis code."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    v_min_pu: float = 0.95      # steady-state voltage band (EN 50160-like +/-5 % for the study)
    v_max_pu: float = 1.05
    loading_max_pct: float = 100.0   # thermal limit (% of max_i_ka / trafo rating)


@dataclass(frozen=True)
class Thermal:
    """Simplified steady-state heat balance for overhead lines (I^2*R = h*(Tc - Ta)).

    Ignores wind speed, solar heating and R(T) -- an illustration, not an IEEE 738 / CIGRE TB 601 rating.
    """
    t_ref_c: float = 40.0    # ambient temperature assumed in the static rating
    t_cond_max_c: float = 80.0   # maximum allowed conductor temperature


LIMITS = Limits()
THERMAL = Thermal()
