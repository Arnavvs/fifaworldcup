"""
f1 / T0.1 - Feature store v2: repaired ELO + second-pipeline features.

1. Replaces the broken year-end-ELO features in ml_match_features with the
   per-match values from elo_match (m1) -> ~100% coverage.
2. Joins WC-2026 static squad features (squad_aggregates, manager_tenure,
   qualification_strength, fifa_rankings_updated override) on canonical names
   -- only for rows dated >= 2025-06-01 (historical rows stay NaN by design).
3. Adds sample_weight = 0.5 ** (years_before_2026 / 10).
4. Writes match_features_v2 (DB + csv) and regenerates
   classification_dataset_v2.csv / regression_dataset_v2.csv with the SAME
   split assignment as v1 (merged by match_id -> no split drift).
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT, get_logger

log = get_logger("f1_features")
OUT = ROOT / "research_ready_dataset"
P2 = ROOT / "data_collection_pipeline" / "collected_data" / "processed"


def main():
    con = sqlite3.connect(DB_PATH)
    fs = pd.read_sql("SELECT * FROM ml_match_features", con)
    elo = pd.read_sql("SELECT * FROM elo_match", con)
    fs = fs.merge(elo, on="match_id", how="left")
    log.info(f"base {len(fs)} rows; elo_match joined "
             f"{fs['elo_diff_pre'].notna().mean():.1%}")

    # ---- 1. repair ELO family ----
    eps = 1e-6
    fs["elo_home"] = fs["elo_home_pre"]
    fs["elo_away"] = fs["elo_away_pre"]
    fs["elo_diff"] = fs["elo_diff_pre"]
    fs["relative_strength"] = fs["elo_diff"]
    fs["strength_ratio"] = (fs["elo_home"] + eps) / (fs["elo_away"] + eps)
    fs["elo_expected_home"] = 1.0 / (1.0 + 10 ** (-fs["elo_diff"] / 400.0))
    fs["upset_proxy"] = 1.0 - np.maximum(fs["elo_expected_home"], 1 - fs["elo_expected_home"])
    fs["elo_trend_diff"] = fs["elo_trend_home"] - fs["elo_trend_away"]
    fs["elo_diff_x_stage"] = fs["elo_diff"] * fs["stage_weight"]
    fs["elo_diff_x_homefield"] = fs["elo_diff"] * fs["home_field"]
    fs["formdiff10_x_elodiff"] = fs["form_diff_last_10"] * fs["elo_diff"]
    fs = fs.drop(columns=["elo_home_pre", "elo_away_pre", "elo_diff_pre",
                          "elo_trend_home", "elo_trend_away", "k_used"])

    # ---- 2. 2026 squad statics (rows >= 2025-06-01 only) ----
    tm = pd.read_csv(OUT / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    fs["ch"] = fs["team_home"].map(lambda t: canon.get(t, t))
    fs["ca"] = fs["team_away"].map(lambda t: canon.get(t, t))
    recent = pd.to_datetime(fs["date"], errors="coerce") >= pd.Timestamp("2025-06-01")

    def team_map(df, key_col, val_col):
        d = df.copy()
        d["c"] = d[key_col].map(lambda t: canon.get(str(t).strip(), str(t).strip()))
        return dict(zip(d["c"], d[val_col]))

    sq = pd.read_csv(P2 / "squad_aggregates.csv")
    mg = pd.read_csv(P2 / "manager_tenure.csv")
    ql = pd.read_csv(P2 / "qualification_strength.csv")
    for feat, src, val in [("mean_age", sq, "mean_age"), ("mean_caps", sq, "mean_caps"),
                           ("club_quality", sq, "mean_club_quality"),
                           ("mgr_tenure", mg, "tenure_years_at_wc"),
                           ("qual_ppg", ql, "qual_ppg")]:
        mp = team_map(src, "team", val)
        fs[f"{feat}_diff"] = np.where(
            recent,
            fs["ch"].map(mp).astype(float) - fs["ca"].map(mp).astype(float),
            np.nan)

    # ---- real-xG aggregates from StatsBomb modern tournaments ----
    # WC18/22 + EURO20/24 + COPA24 + AFCON23 all ended by 2024-07, so gating the
    # feature to rows dated >= 2025-01-01 is leakage-free.
    try:
        sb = pd.read_sql(
            "SELECT s.match_id, s.team, s.xg, m.tournament FROM sb_team_match_stats s "
            "JOIN sb_matches m ON s.match_id = m.match_id", con)
        modern = sb[sb["tournament"].isin(
            ["WC2022", "WC2018", "EURO2024", "EURO2020", "COPA2024", "AFCON2023"])].copy()
        opp = modern.merge(modern, on="match_id", suffixes=("", "_opp"))
        opp = opp[opp["team"] != opp["team_opp"]]
        agg = (opp.groupby("team")
               .agg(xg_pm=("xg", "mean"), xga_pm=("xg_opp", "mean"), n=("xg", "size"))
               .query("n >= 3"))
        agg.index = [canon.get(t, t) for t in agg.index]
        xg_map, xga_map = agg["xg_pm"].to_dict(), agg["xga_pm"].to_dict()
        recent_xg = pd.to_datetime(fs["date"], errors="coerce") >= pd.Timestamp("2025-01-01")
        fs["xg_pm_diff"] = np.where(
            recent_xg, fs["ch"].map(xg_map).astype(float) - fs["ca"].map(xg_map).astype(float), np.nan)
        fs["xga_pm_diff"] = np.where(
            recent_xg, fs["ch"].map(xga_map).astype(float) - fs["ca"].map(xga_map).astype(float), np.nan)
        fs["xg_net_diff"] = fs["xg_pm_diff"] - fs["xga_pm_diff"]
        cov = fs.loc[recent_xg, "xg_pm_diff"].notna().mean()
        log.info(f"xG features: {len(agg)} teams w/ >=3 tournament matches; "
                 f"coverage on 2025+ rows {cov:.1%}")
    except Exception as e:
        log.warning(f"xG feature join skipped: {e}")

    # fifa rank override for matches after the stale boundary
    fr = pd.read_csv(P2 / "fifa_rankings_updated.csv")
    rmap = team_map(fr, "team", "rank")
    after = pd.to_datetime(fs["date"], errors="coerce") >= pd.Timestamp("2024-04-05")
    for side, c in [("home", "ch"), ("away", "ca")]:
        newr = fs[c].map(rmap).astype(float)
        fs[f"fifa_rank_{side}"] = np.where(after & newr.notna(), newr,
                                           fs[f"fifa_rank_{side}"])
    fs["fifa_rank_diff"] = fs["fifa_rank_away"] - fs["fifa_rank_home"]
    fs["fifa_rank_ratio"] = (fs["fifa_rank_away"] + eps) / (fs["fifa_rank_home"] + eps)

    # ---- 3. sample weight ----
    yrs = 2026 - pd.to_datetime(fs["date"], errors="coerce").dt.year
    fs["sample_weight"] = 0.5 ** (yrs / 10.0)

    fs = fs.drop(columns=["ch", "ca"])
    fs.to_sql("match_features_v2", con, if_exists="replace", index=False)
    fs.to_csv(OUT / "match_features_v2.csv", index=False)

    # ---- 4. regenerate model datasets with v1 split assignment ----
    for name, tgt_cols in [("classification_dataset", ["home_win_draw_loss"]),
                           ("regression_dataset", ["home_goals", "away_goals"])]:
        v1 = pd.read_csv(OUT / f"{name}.csv", usecols=["match_id", "split"] + tgt_cols)
        v2 = fs.merge(v1, on="match_id", how="inner")
        v2.to_csv(OUT / f"{name}_v2.csv", index=False)
        log.info(f"{name}_v2.csv: {len(v2)} rows x {v2.shape[1]} cols")

    con.commit(); con.close()
    elo_cov_test = fs.loc[pd.to_datetime(fs['date']) > pd.Timestamp('2018-10-11'),
                          'elo_diff'].notna().mean()
    log.info(f"f1 complete; test-era elo coverage now {elo_cov_test:.1%}")


if __name__ == "__main__":
    main()
