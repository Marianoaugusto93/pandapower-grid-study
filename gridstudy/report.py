"""Figures for the study (matplotlib, headless)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import LIMITS


def plot_timeseries(summary, loading_static, loading_adj, line, path):
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].fill_between(summary.index, summary.vmin_pu, summary.vmax_pu, alpha=0.3, label="bus voltage envelope")
    ax[0].axhline(LIMITS.v_max_pu, color="r", ls="--", lw=1)
    ax[0].axhline(LIMITS.v_min_pu, color="r", ls="--", lw=1, label="limits")
    ax[0].set_ylabel("Voltage [p.u.]")
    ax[0].legend(loc="lower right")
    ax[1].plot(loading_static.index, loading_static[line], label="static rating (Tamb = 40 °C)")
    ax[1].plot(loading_adj.index, loading_adj[line], label="ambient-adjusted rating (simplified)")
    ax[1].axhline(LIMITS.loading_max_pct, color="r", ls="--", lw=1)
    ax[1].set_ylabel(f"{line} loading [%]")
    ax[1].legend(loc="upper left")
    fig.suptitle("Synthetic week: voltage envelope and OHL loading with a new 10 MW wind plant")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_n1(n1, path):
    df = n1[n1.converged & ((n1.unserved_mw > 0) | (n1.violations > 0))]
    fig, ax = plt.subplots(figsize=(9, 4))
    x = range(len(df))
    ax.bar([i - 0.2 for i in x], df.unserved_mw, width=0.4, label="after outage")
    ax.bar([i + 0.2 for i in x], df.unserved_after_mw, width=0.4, label="after tie-switch restoration")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df.name, rotation=45, ha="right")
    ax.set_ylabel("Unserved load [MW]")
    ax.legend()
    fig.suptitle("N-1: unserved load per outage")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_hosting(matrix, path):
    fig, ax = plt.subplots(figsize=(7, 4))
    for pf, grp in matrix.groupby("pf"):
        ax.plot(grp.ambient_c, grp.hosting_mw, marker="o", label=f"cos φ = {pf:.2f} (absorbing)")
    ax.set_xlabel("Ambient temperature [°C]  (40 °C = static rating)")
    ax.set_ylabel("Wind hosting capacity at bus 14 [MW]")
    ax.invert_xaxis()
    ax.legend()
    fig.suptitle("Hosting capacity: voltage-limited vs thermal-limited")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
