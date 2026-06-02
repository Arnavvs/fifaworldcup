"""
PHASE 6 - Model-ready dataset exports.

1. classification_dataset.csv : features + target home_win_draw_loss (+ time split)
2. regression_dataset.csv     : features + home_goals, away_goals
3. tournament_dataset.csv     : WC2026 fixtures + team strength ratings for Monte Carlo

Splits are time-based (70/15/15 by date among labelled matches); unplayed
fixtures (2026) are marked split='predict'. No random shuffling.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT

OUT = ROOT / "research_ready_dataset"
HOSTS = {"USA", "Mexico", "Canada"}


def time_split(dates: pd.Series, labelled: pd.Series) -> pd.Series:
    s = pd.Series("predict", index=dates.index)
    lab = labelled & dates.notna()
    if lab.any():
        d = dates[lab]
        q70, q85 = d.quantile(0.70), d.quantile(0.85)
        s[lab & (dates <= q70)] = "train"
        s[lab & (dates > q70) & (dates <= q85)] = "val"
        s[lab & (dates > q85)] = "test"
    return s


def main():
    con = sqlite3.connect(DB_PATH)
    fs = pd.read_sql("SELECT * FROM ml_match_features", con)
    m = pd.read_sql("SELECT match_id, home_score, away_score FROM matches", con)
    fs["date"] = pd.to_datetime(fs["date"], errors="coerce")

    feat_cols = [c for c in fs.columns if c not in
                 ("match_id", "date", "team_id_home", "team_id_away",
                  "team_home", "team_away", "tournament", "stage")]

    df = fs.merge(m, on="match_id", how="left")
    labelled = df["home_score"].notna() & df["away_score"].notna()
    df["split"] = time_split(df["date"], labelled)

    # ---------- 1. classification ----------
    clf = df.copy()
    gd = clf["home_score"] - clf["away_score"]
    clf["home_win_draw_loss"] = np.select(
        [gd > 0, gd == 0, gd < 0], ["home_win", "draw", "home_loss"], default=None)
    clf_cols = ["match_id", "date", "team_home", "team_away", "team_id_home",
                "team_id_away", "split"] + feat_cols + ["home_win_draw_loss"]
    clf[clf_cols].to_csv(OUT / "classification_dataset.csv", index=False, encoding="utf-8")

    # ---------- 2. regression ----------
    reg = df.copy()
    reg["home_goals"] = reg["home_score"]
    reg["away_goals"] = reg["away_score"]
    reg_cols = ["match_id", "date", "team_home", "team_away", "team_id_home",
                "team_id_away", "split"] + feat_cols + ["home_goals", "away_goals"]
    reg[reg_cols].to_csv(OUT / "regression_dataset.csv", index=False, encoding="utf-8")

    # ---------- 3. tournament (Monte Carlo) ----------
    fx = pd.read_sql("SELECT * FROM wc2026_fixtures", con)
    mapping = pd.read_csv(OUT / "team_mapping.csv")
    raw2id = dict(zip(mapping["raw_name"], mapping["team_id"]))
    raw2canon = dict(zip(mapping["raw_name"], mapping["canonical_name"]))

    # latest per-team strength from team_match_features (map team -> canonical)
    tmf = pd.read_sql("SELECT team, date, elo, fifa_rank, gf_avg_l10, ga_avg_l10 "
                      "FROM team_match_features", con)
    tmf["date"] = pd.to_datetime(tmf["date"], errors="coerce")
    tmf["canon"] = tmf["team"].map(lambda t: raw2canon.get(t, t))
    latest = (tmf.sort_values("date").groupby("canon").tail(1)
              .set_index("canon")[["elo", "fifa_rank", "gf_avg_l10", "ga_avg_l10"]])

    def strength(team_name):
        cn = raw2canon.get(team_name, team_name)
        if cn in latest.index:
            r = latest.loc[cn]
            return r["elo"], r["fifa_rank"], r["gf_avg_l10"], r["ga_avg_l10"]
        return (np.nan, np.nan, np.nan, np.nan)

    rows = []
    for _, r in fx.iterrows():
        h, a = str(r.get("HomeTeam")), str(r.get("AwayTeam"))
        he, hr, hgf, hga = strength(h)
        ae, ar, agf, aga = strength(a)
        elo_diff = (he - ae) if pd.notna(he) and pd.notna(ae) else np.nan
        rows.append({
            "match_number": r.get("MatchNumber"), "round": r.get("RoundNumber"),
            "date_utc": r.get("DateUtc"), "group": r.get("Group"),
            "location": r.get("Location"),
            "home_team": h, "away_team": a,
            "home_team_id": raw2id.get(h), "away_team_id": raw2id.get(a),
            "home_elo": he, "away_elo": ae,
            "home_fifa_rank": hr, "away_fifa_rank": ar,
            "home_attack": hgf, "home_defense": hga,
            "away_attack": agf, "away_defense": aga,
            "elo_diff": elo_diff,
            "elo_expected_home": (1/(1+10**(-elo_diff/400))) if pd.notna(elo_diff) else np.nan,
            "host_home": int(h in HOSTS), "neutral": int(h not in HOSTS),
        })
    tour = pd.DataFrame(rows)
    tour.to_csv(OUT / "tournament_dataset.csv", index=False, encoding="utf-8")
    con.close()

    print("EXPORTS:")
    print(f"  classification_dataset.csv : {len(clf)} rows "
          f"(split: {df['split'].value_counts().to_dict()})")
    print(f"  regression_dataset.csv     : {len(reg)} rows, targets home_goals/away_goals")
    print(f"  tournament_dataset.csv     : {len(tour)} WC2026 fixtures, "
          f"{tour['home_elo'].notna().sum()} with home strength")


if __name__ == "__main__":
    main()
