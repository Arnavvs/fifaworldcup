"""
Stage 04 - World Cup specific data (history 1930-2022 + WC 2026).

- WC 2026 schedule + qualified teams: fixturedownload.com JSON feed (the draw is
  done, so real team names are present).
- WC history (matches, hosts, winners): the clean Kaggle wcmatches/worldcups
  tables (stage, win conditions, scores) supplemented by Wikipedia where useful.
Outputs -> raw/worldcup/
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from common import RAW, polite_get, get_logger, log_attempt, save_df

log = get_logger("s04_wc")
OUT = RAW / "worldcup"
KAGGLE = RAW / "kaggle"


def wc2026_fixtures() -> pd.DataFrame | None:
    url = "https://fixturedownload.com/feed/json/fifa-world-cup-2026"
    resp = polite_get(url, source="worldcup", min_delay=1, max_delay=2, retries=3)
    if resp is None:
        return None
    try:
        data = resp.json()
        df = pd.DataFrame(data)
        save_df(df, OUT / "wc2026_fixtures.csv")
        log_attempt("worldcup", url, "ok", len(df), "2026 fixtures")
        return df
    except Exception as e:
        log_attempt("worldcup", url, "fail", 0, str(e)[:150])
        return None


def wc2026_qualified(fixtures: pd.DataFrame | None) -> pd.DataFrame | None:
    if fixtures is None or fixtures.empty:
        return None
    teams = set()
    for col in ("HomeTeam", "AwayTeam"):
        if col in fixtures.columns:
            teams |= set(fixtures[col].dropna().astype(str))
    # drop placeholder slots (e.g. "Winner Group A", "1A", playoff slots)
    bad = ("winner", "runner", "group", "1", "2", "3", "playoff", "tbd", "/", "vs")
    real = sorted(t for t in teams if not any(b in t.lower() for b in bad))
    grp = {}
    if "Group" in fixtures.columns:
        for _, r in fixtures.iterrows():
            for col in ("HomeTeam", "AwayTeam"):
                t = str(r.get(col, ""))
                if t in real and pd.notna(r.get("Group")):
                    grp.setdefault(t, str(r["Group"]))
    df = pd.DataFrame({"team": real})
    df["group"] = df["team"].map(grp)
    df["tournament"] = "FIFA World Cup 2026"
    save_df(df, OUT / "wc2026_qualified_teams.csv")
    log.info(f"WC2026 qualified teams parsed: {len(df)}")
    log_attempt("worldcup", "wc2026_qualified", "ok", len(df))
    return df


def wc_history() -> None:
    """Clean WC match + tournament history from the Kaggle tables."""
    src = KAGGLE / "fifa-world-cup"
    matches = src / "wcmatches.csv"
    cups = src / "worldcups.csv"
    if matches.exists():
        m = pd.read_csv(matches)
        save_df(m, OUT / "wc_matches_history.csv")
        log_attempt("worldcup", str(matches), "ok", len(m), "WC match history")
    if cups.exists():
        c = pd.read_csv(cups)
        save_df(c, OUT / "wc_tournaments.csv")
        log_attempt("worldcup", str(cups), "ok", len(c), "WC tournaments/hosts")


def wc_squads_from_kaggle() -> None:
    """Surface any squad table shipped in the Kaggle WC datasets."""
    found = 0
    for p in KAGGLE.rglob("*.csv"):
        name = p.name.lower()
        if "squad" in name or "player" in name and "world" in str(p).lower():
            try:
                df = pd.read_csv(p, nrows=5)
                if any("player" in str(c).lower() or "name" in str(c).lower() for c in df.columns):
                    full = pd.read_csv(p)
                    save_df(full, OUT / f"squad_{p.stem}.csv")
                    found += 1
            except Exception:
                pass
    log.info(f"WC squad tables surfaced: {found}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fx = wc2026_fixtures()
    wc2026_qualified(fx)
    wc_history()
    wc_squads_from_kaggle()
    log.info("stage 04 (worldcup) complete")


if __name__ == "__main__":
    sys.exit(main())
