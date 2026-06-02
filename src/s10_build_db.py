"""
Stage 10 - Load everything into SQLite (fifa_wc_data/db/football.db).

Reads the cleaned CSVs from raw/ and processed/ and writes the schema tables.
Tables with no available source (e.g. FBref team/player match stats while
Cloudflare-blocked, odds) are created empty with the correct columns so the
schema is complete and downstream queries are well-defined. Idempotent: each
table is replaced on rerun.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

from common import RAW, PROCESSED, DB_PATH, get_logger, log_attempt

log = get_logger("s10_db")

EMPTY_SCHEMAS = {
    "team_match_stats": ["match_id", "team", "poss", "sh", "sot", "xg", "npxg",
                         "sca", "gca", "tkl", "int", "touches", "passes_cmp"],
    "player_match_stats": ["match_id", "player_id", "min", "gls", "ast", "xg",
                           "npxg", "xag", "sca", "gca", "tkl", "int"],
    "player_tournament_stats": ["tournament", "player_id", "gp", "gls", "ast",
                                "xg", "npxg", "xag"],
    "injuries": ["player_id", "injury_date", "return_date", "injury_type", "days_missed"],
    "odds": ["match_id", "bookmaker", "home_odds", "draw_odds", "away_odds",
             "over25_odds", "under25_odds"],
    "venues": ["venue_id", "name", "city", "country", "capacity", "altitude_m", "lat", "lng"],
}


def write(con, name: str, df: pd.DataFrame) -> None:
    df.to_sql(name, con, if_exists="replace", index=False)
    log.info(f"  table {name:<24} {len(df):>7} rows, {df.shape[1]} cols")
    log_attempt("db", name, "ok", len(df))


def safe_read(path: Path) -> pd.DataFrame | None:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception as e:
        log.warning(f"read fail {path.name}: {e}")
    return None


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    log.info(f"building {DB_PATH}")

    # ---- matches (canonical) ----
    m = safe_read(PROCESSED / "matches.csv")
    if m is not None:
        cols = ["match_id", "date", "tournament", "stage", "home_team", "away_team",
                "home_score", "away_score", "neutral", "city", "country"]
        m2 = m[[c for c in cols if c in m.columns]].copy()
        m2 = m2.rename(columns={"tournament": "competition"})
        m2["venue"] = m.get("city")
        m2["referee"] = None
        m2["attendance"] = None
        write(con, "matches", m2)

    # ---- team_match_features (our derived analytical table) ----
    f = safe_read(PROCESSED / "team_match_features.csv")
    if f is not None:
        write(con, "team_match_features", f)

    # ---- players ----
    p = safe_read(PROCESSED / "players.csv")
    if p is not None:
        cols = {"player_id": "player_id", "name": "name", "nationality": "nationality",
                "position": "position", "dob": "dob", "primary_club": "primary_club"}
        base = p[[c for c in cols if c in p.columns]].copy()
        # keep attribute columns too (overall, value_eur, etc.)
        attrs = [c for c in p.columns if c not in base.columns]
        players = pd.concat([base, p[attrs]], axis=1)
        write(con, "players", players)

    # ---- squads (WC2026 pool) ----
    pool = safe_read(PROCESSED / "wc2026_player_pool.csv")
    if pool is not None:
        sq = pd.DataFrame({
            "tournament": "FIFA World Cup 2026",
            "team": pool.get("nationality_norm"),
            "player_id": pool.get("player_id"),
            "age_at_tournament": pool.get("age"),
            "caps_at_tournament": None,
            "market_value": pool.get("value_eur"),
        })
        write(con, "squads", sq)

    # ---- elo_ratings ----
    e = safe_read(RAW / "elo" / "elo_ratings.csv")
    if e is not None:
        write(con, "elo_ratings", e[[c for c in ["date", "team", "elo", "elo_change"] if c in e.columns]])

    # ---- fifa_rankings ----
    r = safe_read(RAW / "fifa_rankings" / "fifa_rankings.csv")
    if r is not None:
        write(con, "fifa_rankings", r)

    # ---- market_values ----
    mv = safe_read(PROCESSED / "market_values.csv")
    if mv is not None:
        write(con, "market_values", mv)

    # ---- world cup history ----
    wch = safe_read(RAW / "worldcup" / "wc_matches_history.csv")
    if wch is not None:
        write(con, "wc_matches_history", wch)
    wct = safe_read(RAW / "worldcup" / "wc_tournaments.csv")
    if wct is not None:
        write(con, "wc_tournaments", wct)
    fx = safe_read(RAW / "worldcup" / "wc2026_fixtures.csv")
    if fx is not None:
        write(con, "wc2026_fixtures", fx)
    qt = safe_read(RAW / "worldcup" / "wc2026_qualified_teams.csv")
    if qt is not None:
        write(con, "wc2026_qualified_teams", qt)

    # ---- goalscorers ----
    gs = safe_read(RAW / "kaggle" / "international-football-results-from-1872-to-2017" / "goalscorers.csv")
    if gs is not None:
        write(con, "goalscorers", gs)

    # ---- odds (from football-data, may be empty) ----
    od = safe_read(RAW / "football_data" / "odds.csv")
    if od is not None:
        write(con, "odds", od)

    # ---- venues (geocoded WC2026) ----
    v = safe_read(PROCESSED / "venues.csv")
    if v is not None and len(v):
        write(con, "venues", v)

    # ---- empty-but-schema'd tables for blocked/unavailable sources ----
    existing = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, cols in EMPTY_SCHEMAS.items():
        if name not in existing:
            write(con, name, pd.DataFrame(columns=cols))

    con.commit()
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    con.close()
    log.info(f"stage 10 (db) complete: {len(tables)} tables -> {tables}")


if __name__ == "__main__":
    sys.exit(main())
