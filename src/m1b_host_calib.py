"""
m1b_host_calib.py — Quantify and fit host bonus for World Cup hosts.

TASK 1 id: ELO-HOST

Fits an extra ELO bonus `host_bonus` for WC host nations playing at home,
by maximizing Davidson likelihood on historical host WC matches (1990-2022).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

import sys
sys.path.insert(0, str(Path(__file__).parent))
from common import DB_PATH, ROOT, get_logger

log = get_logger("m1b_host")
OUT = ROOT / "research_ready_dataset"

# WC host nations by year (1990-2022)
HOSTS_BY_YEAR = {
    1990: "Italy",
    1994: "USA",
    1998: "France",
    2002: ["South Korea", "Japan"],
    2006: "Germany",
    2010: "South Africa",
    2014: "Brazil",
    2018: "Russia",
    2022: "Qatar",
}

# Flatten host set
ALL_HOSTS = set()
for h in HOSTS_BY_YEAR.values():
    if isinstance(h, list):
        ALL_HOSTS.update(h)
    else:
        ALL_HOSTS.add(h)


def load_host_matches():
    """Load WC matches where a host nation played at home (not neutral)."""
    con = sqlite3.connect(DB_PATH)
    m = pd.read_sql("""
        SELECT m.match_id, m.date, m.competition, m.home_team, m.away_team,
               m.home_score, m.away_score, m.neutral,
               e.elo_home_pre, e.elo_away_pre
        FROM matches m
        JOIN elo_match e ON m.match_id = e.match_id
        WHERE m.competition LIKE '%FIFA World Cup%'
          AND m.competition NOT LIKE '%qualif%'
          AND m.home_score IS NOT NULL
        ORDER BY m.date
    """, con)
    con.close()

    # Load team mapping
    tm = pd.read_csv(OUT / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    m["h"] = m["home_team"].map(lambda t: canon.get(t, t))
    m["a"] = m["away_team"].map(lambda t: canon.get(t, t))

    # Filter: host nation playing at home (not neutral) in their own WC
    # We need to know the year of each match
    m["year"] = pd.to_datetime(m["date"]).dt.year

    def is_host_at_home(row):
        host = HOSTS_BY_YEAR.get(row["year"])
        if host is None:
            return False
        if isinstance(host, list):
            hosts = host
        else:
            hosts = [host]
        return row["h"] in hosts and row["neutral"] == 0

    host_matches = m[m.apply(is_host_at_home, axis=1)].copy()
    return host_matches


def davidson_nll_host_bonus(host_bonus, host_matches, nu, home_adv):
    """Compute NLL on host matches given host_bonus."""
    dr = (host_matches["elo_home_pre"].values - host_matches["elo_away_pre"].values
          + home_adv + host_bonus)
    pi = 10 ** (dr / 400.0)
    sq = np.sqrt(pi)
    D = pi + 1.0 + nu * sq
    p = np.stack([1.0 / D, nu * sq / D, pi / D], axis=1)  # [loss, draw, win]
    p = np.clip(p, 1e-12, 1)

    gd = host_matches["home_score"].values - host_matches["away_score"].values
    y = np.select([gd < 0, gd == 0], [0, 1], default=2)
    return -np.mean(np.log(p[np.arange(len(y)), y]))


def main():
    log.info(f"Host nations (1990-2022): {sorted(ALL_HOSTS)}")

    host_matches = load_host_matches()
    log.info(f"Historical WC host-at-home matches: {len(host_matches)}")
    if len(host_matches) == 0:
        log.error("No host matches found — aborting")
        return

    # Show sample
    log.info(f"Sample matches: {host_matches[['date', 'h', 'a', 'home_score', 'away_score']].head(5).values.tolist()}")

    # Load Davidson params
    params = json.loads((OUT / "davidson_params.json").read_text())
    nu, home_adv = params["nu"], params["home_adv"]
    log.info(f"Base Davidson: nu={nu:.3f} home_adv={home_adv:.0f}")

    # Fit host_bonus by maximizing likelihood (minimizing NLL)
    res = minimize_scalar(
        lambda b: davidson_nll_host_bonus(b, host_matches, nu, home_adv),
        bounds=(0, 200),
        method="bounded"
    )
    host_bonus = res.x
    nll_with = res.fun
    nll_without = davidson_nll_host_bonus(0, host_matches, nu, home_adv)

    log.info(f"Host bonus fitted: {host_bonus:.1f} ELO points")
    log.info(f"NLL on host matches: without bonus={nll_without:.4f}, with bonus={nll_with:.4f}")

    # Save params
    out = {
        "host_bonus": round(host_bonus, 1),
        "nll_without": round(nll_without, 4),
        "nll_with": round(nll_with, 4),
        "n_matches": len(host_matches),
        "nu": nu,
        "home_adv": home_adv,
        "fitted": datetime.utcnow().isoformat(),
    }
    (OUT / "host_bonus_params.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log.info(f"Saved to research_ready_dataset/host_bonus_params.json")

    # Ledger
    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"ELO-HOST,2026-06-12,m1b_host_calib,host_bonus,"
                f"wc host matches 1990-2022,{len(host_matches)},"
                f"{nll_with:.4f},,,,,KEEP,"
                f"host_bonus={host_bonus:.1f} nll_without={nll_without:.4f} nll_with={nll_with:.4f}\n")


if __name__ == "__main__":
    main()
