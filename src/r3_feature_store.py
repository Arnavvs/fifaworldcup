"""
PHASE 3 + 5 - Feature store (ml_match_features), one row per match, target-safe.

Pivots the per-team team_match_features into home/away, computes difference and
interaction features (Phase 3), then adds advanced momentum / strength /
historical / matchup features (Phase 5). Excludes every outcome column
(home_score, away_score, result, gf, ga, points, attendance) and the
fifa_points artifact. Writes `ml_match_features` (DB) + CSV.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT

OUT = ROOT / "research_ready_dataset"
OUT.mkdir(exist_ok=True)


def add_team_timeseries(long: pd.DataFrame) -> pd.DataFrame:
    """Per-team, leakage-safe momentum + strength ratings (all use prior matches)."""
    long = long.sort_values(["team", "date"]).copy()
    g = long.groupby("team", sort=False)
    # momentum: change vs N matches ago (shifted so 'now' isn't used)
    long["elo_trend"] = g["elo"].transform(lambda s: s - s.shift(5))
    long["rank_trend"] = g["fifa_rank"].transform(lambda s: -(s - s.shift(5)))  # +ve = improving
    long["goal_trend"] = long["gf_avg_l5"] - long["gf_avg_l20"]               # recent vs baseline
    # strength ratings (from pre-match rolling form -> safe)
    long["attack_rating"] = long["gf_avg_l10"]
    long["defense_rating"] = -long["ga_avg_l10"]                              # higher = better
    long["net_rating"] = long["gf_avg_l10"] - long["ga_avg_l10"]
    return long


def pedigree_lookup(con) -> dict:
    """All-time WC pedigree reputation score per canonical team (static prior)."""
    try:
        wc = pd.read_sql("SELECT winner, second, third, fourth FROM wc_tournaments", con)
        dim = pd.read_sql("SELECT canonical_name, aliases FROM dim_team", con)
        alias2canon = {}
        for _, r in dim.iterrows():
            alias2canon[r["canonical_name"]] = r["canonical_name"]
            for a in str(r["aliases"]).split("|"):
                if a:
                    alias2canon[a] = r["canonical_name"]
        score: dict = {}
        for w, pts in [("winner", 8), ("second", 5), ("third", 3), ("fourth", 2)]:
            for name in wc[w].dropna():
                cn = alias2canon.get(str(name), str(name))
                score[cn] = score.get(cn, 0) + pts
        return score
    except Exception:
        return {}


def main():
    con = sqlite3.connect(DB_PATH)
    long = pd.read_sql("SELECT * FROM team_match_features", con)
    long["date"] = pd.to_datetime(long["date"], errors="coerce")
    long = add_team_timeseries(long)

    # team_id + pedigree + wc history
    mapping = pd.read_csv(OUT / "team_mapping.csv")
    raw2id = dict(zip(mapping["raw_name"], mapping["team_id"]))
    ped = pedigree_lookup(con)
    raw2canon = dict(zip(mapping["raw_name"], mapping["canonical_name"]))
    long["team_id"] = long["team"].map(raw2id)
    long["pedigree"] = long["team"].map(lambda t: ped.get(raw2canon.get(t, t), 0))

    # split home / away
    side_cols = ["match_id", "team", "team_id", "elo", "fifa_rank", "pedigree",
                 "win_pct_l5", "win_pct_l10", "win_pct_l20",
                 "gf_avg_l5", "gf_avg_l10", "gf_avg_l20",
                 "ga_avg_l5", "ga_avg_l10", "ga_avg_l20",
                 "h2h_win_pct_l10", "h2h_gf_avg_l10", "days_rest",
                 "wc_appearances_before", "result_streak_in",
                 "elo_trend", "rank_trend", "goal_trend",
                 "attack_rating", "defense_rating", "net_rating"]
    home = long[long["is_home"] == 1][side_cols].add_suffix("_home").rename(
        columns={"match_id_home": "match_id"})
    away = long[long["is_home"] == 0][side_cols].add_suffix("_away").rename(
        columns={"match_id_away": "match_id"})

    # match-level context (same for both sides)
    ctx = long[long["is_home"] == 1][["match_id", "date", "tournament", "stage",
                                      "stage_weight", "rivalry", "neutral"]]
    df = ctx.merge(home, on="match_id").merge(away, on="match_id")

    eps = 1e-6
    # ---------- Phase 3 difference features ----------
    df["elo_diff"] = df["elo_home"] - df["elo_away"]
    df["fifa_rank_diff"] = df["fifa_rank_away"] - df["fifa_rank_home"]      # +ve = home better
    df["fifa_rank_ratio"] = (df["fifa_rank_away"] + eps) / (df["fifa_rank_home"] + eps)
    for w in (5, 10, 20):
        df[f"form_diff_last_{w}"] = df[f"win_pct_l{w}_home"] - df[f"win_pct_l{w}_away"]
    df["goals_for_diff"] = df["gf_avg_l10_home"] - df["gf_avg_l10_away"]
    df["goals_against_diff"] = df["ga_avg_l10_home"] - df["ga_avg_l10_away"]
    df["h2h_win_pct_diff"] = df["h2h_win_pct_l10_home"] - df["h2h_win_pct_l10_away"]
    df["h2h_goal_diff"] = df["h2h_gf_avg_l10_home"] - df["h2h_gf_avg_l10_away"]
    df["days_rest_diff"] = df["days_rest_home"] - df["days_rest_away"]
    df["wc_experience_diff"] = df["wc_appearances_before_home"] - df["wc_appearances_before_away"]
    df["streak_diff"] = df["result_streak_in_home"] - df["result_streak_in_away"]
    df["neutral_flag"] = df["neutral"].astype(int)
    df["rivalry_flag"] = df["rivalry"].astype(int)

    # ---------- Phase 5 advanced ----------
    df["elo_trend_diff"] = df["elo_trend_home"] - df["elo_trend_away"]
    df["rank_trend_diff"] = df["rank_trend_home"] - df["rank_trend_away"]
    df["goal_trend_diff"] = df["goal_trend_home"] - df["goal_trend_away"]
    df["attack_rating_diff"] = df["attack_rating_home"] - df["attack_rating_away"]
    df["defense_rating_diff"] = df["defense_rating_home"] - df["defense_rating_away"]
    df["net_rating_diff"] = df["net_rating_home"] - df["net_rating_away"]
    df["pedigree_diff"] = df["pedigree_home"] - df["pedigree_away"]
    # matchup
    df["strength_ratio"] = (df["elo_home"] + eps) / (df["elo_away"] + eps)
    df["relative_strength"] = df["elo_diff"]
    df["elo_expected_home"] = 1.0 / (1.0 + 10 ** (-df["elo_diff"] / 400.0))
    df["upset_proxy"] = 1.0 - df[["elo_expected_home"]].assign(
        a=1 - df["elo_expected_home"]).max(axis=1)

    # ---------- interaction features ----------
    df["home_field"] = (1 - df["neutral_flag"])                 # 1 if home truly at home
    df["elo_diff_x_stage"] = df["elo_diff"] * df["stage_weight"]
    df["elo_diff_x_homefield"] = df["elo_diff"] * df["home_field"]
    df["formdiff10_x_elodiff"] = df["form_diff_last_10"] * df["elo_diff"]
    df["rankratio_x_formdiff10"] = df["fifa_rank_ratio"] * df["form_diff_last_10"]
    df["restdiff_x_stage"] = df["days_rest_diff"] * df["stage_weight"]
    df["netrating_x_homefield"] = df["net_rating_diff"] * df["home_field"]
    df["pedigree_x_stage"] = df["pedigree_diff"] * df["stage_weight"]

    feature_cols = [
        # diffs / context
        "elo_diff", "fifa_rank_diff", "fifa_rank_ratio",
        "form_diff_last_5", "form_diff_last_10", "form_diff_last_20",
        "goals_for_diff", "goals_against_diff", "h2h_win_pct_diff", "h2h_goal_diff",
        "days_rest_diff", "wc_experience_diff", "streak_diff",
        "neutral_flag", "stage_weight", "rivalry_flag", "home_field",
        # advanced
        "elo_trend_diff", "rank_trend_diff", "goal_trend_diff",
        "attack_rating_diff", "defense_rating_diff", "net_rating_diff", "pedigree_diff",
        "strength_ratio", "relative_strength", "elo_expected_home", "upset_proxy",
        # interactions
        "elo_diff_x_stage", "elo_diff_x_homefield", "formdiff10_x_elodiff",
        "rankratio_x_formdiff10", "restdiff_x_stage", "netrating_x_homefield",
        "pedigree_x_stage",
        # anchors (absolute, still pre-match)
        "elo_home", "elo_away", "fifa_rank_home", "fifa_rank_away",
    ]
    id_cols = ["match_id", "date", "team_id_home", "team_id_away",
               "team_home", "team_away", "tournament", "stage"]
    fs = df[id_cols + feature_cols].sort_values(["date", "match_id"]).reset_index(drop=True)

    fs.to_sql("ml_match_features", con, if_exists="replace", index=False)
    fs.to_csv(OUT / "ml_match_features.csv", index=False, encoding="utf-8")
    con.commit(); con.close()

    print(f"ml_match_features: {len(fs)} matches x {len(feature_cols)} features")
    print(f"  feature cols: {feature_cols}")
    print(f"  date range: {fs['date'].min()} .. {fs['date'].max()}")


if __name__ == "__main__":
    main()
