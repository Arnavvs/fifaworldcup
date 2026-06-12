"""
m9 — Entropy engine (surprisal, chaos meter, historical WC chaos).  TASK 3 id:m9

Roadmap §5 formulas:
  H = -Σ p_i ln p_i      (pre-match entropy)
  I = -ln p(y)            (realized surprisal)
  X = I - H               (excess surprisal)

Outputs:
  DB table entropy_match (match_id, source, H, I, X)
  artifacts/chaos_history.json — per WC 1994-2022 aggregates
  dashboard/entropy_data.js — group chaos + history + realized surprisal
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT, get_logger

log = get_logger("m9_entropy")
ART = ROOT / "artifacts"
DASH = ROOT / "dashboard" / "data"


def davidson_probs(elo_diff, home_adv, nu, neutral=False):
    """Davidson W/D/L probabilities. Returns [loss, draw, win]."""
    dr = elo_diff + (0 if neutral else home_adv)
    pi = 10 ** (dr / 400.0)
    sq = np.sqrt(pi)
    D = pi + 1.0 + nu * sq
    return np.array([1.0 / D, nu * sq / D, pi / D])


def compute_entropy_match():
    """Compute entropy_match table for davidson and dixon sources."""
    con = sqlite3.connect(DB_PATH)

    # Load davidson params
    params = json.loads((ROOT / "research_ready_dataset" / "davidson_params.json").read_text())
    nu, H = params["nu"], params["home_adv"]

    # Load matches with ELO
    m = pd.read_sql("""
        SELECT m.match_id, m.date, m.home_score, m.away_score, m.neutral,
               e.elo_home_pre, e.elo_away_pre
        FROM matches m JOIN elo_match e ON m.match_id=e.match_id
        WHERE m.date >= '1994-01-01' AND m.home_score IS NOT NULL
    """, con)
    con.close()

    m["elo_diff"] = m["elo_home_pre"] - m["elo_away_pre"]
    m["outcome"] = np.select([m["home_score"] < m["away_score"],
                              m["home_score"] == m["away_score"]], [0, 1], default=2)

    # Davidson source
    dprobs = []
    for _, r in m.iterrows():
        p = davidson_probs(r["elo_diff"], H, nu, neutral=r["neutral"])
        p = np.clip(p, 1e-12, 1)
        H_val = float(-(p * np.log(p)).sum())
        I_val = float(-np.log(p[int(r["outcome"])]))
        dprobs.append((r["match_id"], "davidson", round(H_val, 4), round(I_val, 4), round(I_val - H_val, 4)))

    ddf = pd.DataFrame(dprobs, columns=["match_id", "source", "H", "I", "X"])

    # Dixon source (from m4_probs.csv)
    dc = pd.read_csv(ROOT / "research_ready_dataset" / "m4_probs.csv")
    dc = dc.merge(m[["match_id", "outcome"]], on="match_id", how="inner")
    dcprobs = []
    for _, r in dc.iterrows():
        p = np.array([r["dc_p_loss"], r["dc_p_draw"], r["dc_p_win"]])
        p = np.clip(p, 1e-12, 1)
        H_val = float(-(p * np.log(p)).sum())
        I_val = float(-np.log(p[int(r["outcome"])]))
        dcprobs.append((r["match_id"], "dixon", round(H_val, 4), round(I_val, 4), round(I_val - H_val, 4)))

    dcdf = pd.DataFrame(dcprobs, columns=["match_id", "source", "H", "I", "X"])

    # Save to DB
    con = sqlite3.connect(DB_PATH)
    combined = pd.concat([ddf, dcdf], ignore_index=True)
    combined.to_sql("entropy_match", con, if_exists="replace", index=False)
    con.close()
    log.info(f"entropy_match: {len(combined)} rows (davidson {len(ddf)}, dixon {len(dcdf)})")
    return m, ddf


def compute_chaos_history(m, ddf):
    """Compute chaos_history.json for each WC 1994-2022."""
    con = sqlite3.connect(DB_PATH)
    wc = pd.read_sql("""
        SELECT match_id, date, competition, home_team, away_team, home_score, away_score
        FROM matches
        WHERE date >= '1994-01-01' AND home_score IS NOT NULL
          AND competition LIKE '%FIFA World Cup%' AND competition NOT LIKE '%qualif%'
    """, con)
    con.close()

    # Merge with entropy
    wc = wc.merge(ddf[ddf["source"] == "davidson"][["match_id", "H", "I", "X"]], on="match_id", how="left")
    wc = wc.dropna(subset=["H", "I"])
    wc["year"] = pd.to_datetime(wc["date"]).dt.year

    # Group by year
    records = []
    for year, group in wc.groupby("year"):
        if len(group) < 5:
            continue
        top5 = group.nlargest(5, "I")[["date", "home_team", "away_team", "home_score", "away_score", "I"]].to_dict("records")
        records.append({
            "year": int(year),
            "n_matches": len(group),
            "sum_I": round(float(group["I"].sum()), 2),
            "sum_H": round(float(group["H"].sum()), 2),
            "sum_X": round(float(group["X"].sum()), 2),
            "mean_I": round(float(group["I"].mean()), 4),
            "mean_H": round(float(group["H"].mean()), 4),
            "top5_surprisal": [
                {"date": r["date"], "home": r["home_team"], "away": r["away_team"],
                 "score": f"{int(r['home_score'])}-{int(r['away_score'])}", "I": round(r["I"], 3)}
                for r in top5
            ],
        })

    records = sorted(records, key=lambda x: x["sum_I"], reverse=True)
    out = {"tournaments": records, "computed": datetime.now(timezone.utc).isoformat()}
    (ART / "chaos_history.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log.info(f"chaos_history.json: {len(records)} tournaments")
    return records


def compute_2026_group_chaos():
    """Expected ΣH per group from latest sim run."""
    latest = sorted(ART.glob("run_*"))[-1]
    sim = json.loads((latest / "sim_results.json").read_text())
    group_H = {}
    for m in sim.get("match_probs", []):
        g = m.get("group")
        if not g:
            continue
        p = np.array(m["p"])
        p = np.clip(p, 1e-12, 1)
        H = float(-(p * np.log(p)).sum())
        group_H.setdefault(g, []).append(H)

    forecast = {g: round(sum(Hs), 2) for g, Hs in group_H.items()}
    return forecast


def build_dashboard_entropy(history, group_chaos):
    """Write dashboard/entropy_data.js."""
    DASH.mkdir(parents=True, exist_ok=True)

    # Read realized surprisal if exists
    realized = []
    surp_file = ART / "realized_surprisal.csv"
    if surp_file.exists():
        df = pd.read_csv(surp_file)
        realized = df.sort_values("ts").tail(20).to_dict("records")

    data = {
        "history": history,
        "group_chaos_2026": group_chaos,
        "realized": realized,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    (DASH / "entropy_data.js").write_text("window.ENTROPY = " + json.dumps(data, indent=1, default=str) + ";", encoding="utf-8")
    log.info("dashboard/entropy_data.js written")


def main():
    m, ddf = compute_entropy_match()
    history = compute_chaos_history(m, ddf)
    group_chaos = compute_2026_group_chaos()
    build_dashboard_entropy(history, group_chaos)
    log.info("m9 entropy engine complete")


if __name__ == "__main__":
    main()
