"""
Stage 09 - Derived / contextual match features.

Builds the canonical match table from the maintained intl-results dataset
(1872 -> 2026), then derives per-team-per-match contextual features used by
prediction models:
  - result, goals for/against, days rest since previous match
  - rolling form: last 5/10/20 win%, goals-for avg, goals-against avg
  - current win/loss/draw streak going into the match
  - head-to-head: last-10 win% and avg goals vs the specific opponent
  - tournament stage weight (group=1 ... final=5)
  - neutral-venue + derby/rivalry flags (top historical rivalries)
  - cumulative World Cup experience (prior WC appearances) per team
  - nearest-prior ELO rating and FIFA ranking joined in

Outputs -> processed/matches.csv  (one row per match, canonical)
           processed/team_match_features.csv (one row per team-per-match)
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from common import RAW, PROCESSED, get_logger, save_df, log_attempt

log = get_logger("s09_features")

STAGE_WEIGHT = {
    "group": 1, "group stage": 1, "first round": 1, "round robin": 1,
    "round of 16": 2, "r16": 2, "second round": 2, "knockout": 2,
    "quarter": 3, "quarterfinal": 3, "quarter-finals": 3, "quarter-final": 3,
    "semi": 4, "semifinal": 4, "semi-finals": 4, "semi-final": 4,
    "final": 5, "third place": 4, "final round": 5,
}

# top historical rivalries (unordered pairs)
RIVALRIES = {
    frozenset(x) for x in [
        ("Argentina", "Brazil"), ("England", "Germany"), ("Germany", "Netherlands"),
        ("Argentina", "England"), ("Spain", "Portugal"), ("Brazil", "Uruguay"),
        ("Argentina", "Uruguay"), ("France", "Germany"), ("Italy", "France"),
        ("Mexico", "USA"), ("England", "Scotland"), ("Serbia", "Croatia"),
        ("Korea Republic", "Japan"), ("Iran", "Saudi Arabia"), ("Egypt", "Algeria"),
        ("Ghana", "Nigeria"), ("Brazil", "Italy"), ("Germany", "Italy"),
        ("Netherlands", "Belgium"), ("Colombia", "Argentina"),
    ]
}


def stage_weight(stage) -> int:
    if not isinstance(stage, str):
        return 0
    s = stage.lower().strip()
    for k, w in STAGE_WEIGHT.items():
        if k in s:
            return w
    return 1 if "cup" in s or "wc" in s else 0


def load_matches() -> pd.DataFrame:
    """Canonical match table from the maintained results dataset."""
    p = RAW / "kaggle" / "international-football-results-from-1872-to-2017" / "results.csv"
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "home_team", "away_team"]).reset_index(drop=True)
    df["match_id"] = np.arange(1, len(df) + 1)

    # attach WC stage where we can (join on year+teams from WC history)
    wc = RAW / "worldcup" / "wc_matches_history.csv"
    df["stage"] = None
    df.loc[df["tournament"].str.contains("World Cup", case=False, na=False), "stage"] = "group"
    if wc.exists():
        h = pd.read_csv(wc)
        h["key"] = (h["home_team"].astype(str) + "|" + h["away_team"].astype(str)
                    + "|" + h["year"].astype(str))
        smap = dict(zip(h["key"], h["stage"]))
        yr = df["date"].dt.year.astype(str)
        df["key"] = df["home_team"] + "|" + df["away_team"] + "|" + yr
        m = df["key"].map(smap)
        df["stage"] = m.where(m.notna(), df["stage"])
        df = df.drop(columns=["key"])
    df["stage_weight"] = df["stage"].map(stage_weight).fillna(0).astype(int)
    df["rivalry"] = [int(frozenset((h, a)) in RIVALRIES)
                     for h, a in zip(df["home_team"], df["away_team"])]
    log.info(f"canonical matches: {len(df)} ({df['date'].min().date()}..{df['date'].max().date()})")
    return df


def to_team_long(df: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match (home + away perspectives)."""
    home = df.assign(team=df["home_team"], opponent=df["away_team"],
                     gf=df["home_score"], ga=df["away_score"], is_home=1)
    away = df.assign(team=df["away_team"], opponent=df["home_team"],
                     gf=df["away_score"], ga=df["home_score"], is_home=0)
    long = pd.concat([home, away], ignore_index=True)
    long = long.dropna(subset=["gf", "ga"])
    long["result"] = np.select(
        [long["gf"] > long["ga"], long["gf"] == long["ga"]],
        ["W", "D"], default="L")
    long["points"] = long["result"].map({"W": 3, "D": 1, "L": 0})
    return long.sort_values(["team", "date"]).reset_index(drop=True)


def rolling_form(long: pd.DataFrame) -> pd.DataFrame:
    g = long.groupby("team", sort=False)
    long["days_rest"] = g["date"].diff().dt.days
    win = (long["result"] == "W").astype(float)
    for w in (5, 10, 20):
        # shift(1) so the window only uses *prior* matches (no leakage)
        long[f"win_pct_l{w}"] = (g.apply(lambda x: (x["result"].eq("W")
                                 .shift(1).rolling(w, min_periods=1).mean()))
                                 .reset_index(level=0, drop=True))
        long[f"gf_avg_l{w}"] = (g["gf"].apply(lambda s: s.shift(1)
                                .rolling(w, min_periods=1).mean())
                                .reset_index(level=0, drop=True))
        long[f"ga_avg_l{w}"] = (g["ga"].apply(lambda s: s.shift(1)
                                .rolling(w, min_periods=1).mean())
                                .reset_index(level=0, drop=True))
    return long


def streaks(long: pd.DataFrame) -> pd.DataFrame:
    """Length of current unbeaten/result streak going into each match."""
    vals = []
    for _, grp in long.groupby("team", sort=False):
        streak = 0
        prev = None
        out = []
        for res in grp["result"]:
            out.append(streak if prev is not None else 0)
            if res == prev:
                streak += 1
            else:
                streak = 1
            prev = res
        vals.extend(out)
    long["result_streak_in"] = vals
    return long


def wc_experience(long: pd.DataFrame) -> pd.DataFrame:
    """Cumulative count of prior World Cup tournaments entered, per team."""
    is_wc = long["tournament"].str.contains("World Cup", case=False, na=False)
    long["_wc_year"] = np.where(is_wc, long["date"].dt.year, np.nan)
    exp = {}
    seen = {}
    out = []
    for team, yr in zip(long["team"], long["_wc_year"]):
        out.append(exp.get(team, 0))
        if not np.isnan(yr):
            key = (team, int(yr))
            if key not in seen:
                seen[key] = True
                exp[team] = exp.get(team, 0) + 1
    long["wc_appearances_before"] = out
    return long.drop(columns=["_wc_year"])


def head_to_head(long: pd.DataFrame) -> pd.DataFrame:
    long["pair"] = long.apply(lambda r: "|".join(sorted([str(r["team"]), str(r["opponent"])])), axis=1)
    h2h_win, h2h_gf = [], []
    hist: dict = {}
    for team, opp, res, gf in zip(long["team"], long["opponent"], long["result"], long["gf"]):
        key = (team, opp)
        rec = hist.get(key, [])
        last = rec[-10:]
        h2h_win.append(np.mean([1 if r == "W" else 0 for r, _ in last]) if last else np.nan)
        h2h_gf.append(np.mean([g for _, g in last]) if last else np.nan)
        rec.append((res, gf))
        hist[key] = rec
    long["h2h_win_pct_l10"] = h2h_win
    long["h2h_gf_avg_l10"] = h2h_gf
    return long.drop(columns=["pair"])


def join_elo_ranking(long: pd.DataFrame) -> pd.DataFrame:
    """As-of join nearest *prior* ELO and FIFA ranking per team-date."""
    long = long.sort_values("date")
    elo_p = RAW / "elo" / "elo_ratings.csv"
    if elo_p.exists():
        elo = pd.read_csv(elo_p)
        elo["date"] = pd.to_datetime(elo["date"], errors="coerce")
        elo = elo.dropna(subset=["date"]).sort_values("date")
        long = pd.merge_asof(long, elo[["date", "team", "elo"]].sort_values("date"),
                             on="date", by="team", direction="backward")
    rank_p = RAW / "fifa_rankings" / "fifa_rankings.csv"
    if rank_p.exists():
        r = pd.read_csv(rank_p)
        r["date"] = pd.to_datetime(r["date"], errors="coerce")
        r = r.dropna(subset=["date"]).sort_values("date")
        cols = ["date", "team"] + [c for c in ("ranking", "points") if c in r.columns]
        long = pd.merge_asof(long, r[cols].sort_values("date"),
                             on="date", by="team", direction="backward",
                             suffixes=("", "_fifa"))
        long = long.rename(columns={"points": "fifa_points", "ranking": "fifa_rank"})
    return long


def main() -> None:
    df = load_matches()
    save_df(df, PROCESSED / "matches.csv")

    long = to_team_long(df)
    long = rolling_form(long)
    long = streaks(long)
    long = wc_experience(long)
    long = head_to_head(long)
    long = join_elo_ranking(long)

    feat_cols = ["match_id", "date", "team", "opponent", "is_home", "tournament",
                 "stage", "stage_weight", "rivalry", "neutral", "gf", "ga",
                 "result", "points", "days_rest", "result_streak_in",
                 "wc_appearances_before", "h2h_win_pct_l10", "h2h_gf_avg_l10",
                 "win_pct_l5", "win_pct_l10", "win_pct_l20",
                 "gf_avg_l5", "gf_avg_l10", "gf_avg_l20",
                 "ga_avg_l5", "ga_avg_l10", "ga_avg_l20",
                 "elo", "fifa_rank", "fifa_points"]
    feat_cols = [c for c in feat_cols if c in long.columns]
    out = long[feat_cols].sort_values(["date", "match_id"]).reset_index(drop=True)
    save_df(out, PROCESSED / "team_match_features.csv")
    log_attempt("features", "team_match_features", "ok", len(out))
    log.info(f"stage 09 (features) complete: {len(out)} team-match rows, "
             f"{len(feat_cols)} feature cols")


if __name__ == "__main__":
    sys.exit(main())
