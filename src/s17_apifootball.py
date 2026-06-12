"""
s17 — API-Football WC2026 collector (free tier, 100 req/day).

Pulls fixtures, lineups, injuries, match stats, and odds for WC2026.
Saves raw JSON + flattened CSV. Writes to DB tables:
  apifb_fixtures, apifb_lineups, apifb_injuries, apifb_stats, apifb_odds

Usage:
  python src/s17_apifootball.py              # full run
  python src/s17_apifootball.py fixtures      # fixtures only
  python src/s17_apifootball.py lineups       # lineups for played matches
  python src/s17_apifootball.py injuries      # current injuries
  python src/s17_apifootball.py stats         # match statistics
  python src/s17_apifootball.py odds          # pre-match odds

Env: APIFOOTBALL_KEY (or pass via --key)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from common import DB_PATH, ROOT, get_logger

log = get_logger("s17_apifb")

BASE = "https://v3.football.api-sports.io"
WC_LEAGUE = 1
WC_SEASON = 2026
CACHE_DIR = ROOT / "fifa_wc_data" / "raw" / "apifootball"
PACING = 6.5  # seconds between requests (free tier: ~10/min)


def get_key() -> str:
    k = os.environ.get("APIFOOTBALL_KEY")
    if k:
        return k
    raise RuntimeError("No API-Football key. Set APIFOOTBALL_KEY env var.")


def api_get(endpoint: str, params: dict | None = None, key: str = "") -> dict | None:
    headers = {"x-apisports-key": key or get_key()}
    url = f"{BASE}/{endpoint.lstrip('/')}"
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                log.warning(f"rate-limited, sleeping {wait}s")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                log.warning(f"{endpoint}: HTTP {r.status_code}")
                return None
            data = r.json()
            if data.get("errors") and isinstance(data["errors"], dict) and data["errors"]:
                log.warning(f"{endpoint}: API error {data['errors']}")
            return data
        except Exception as e:
            wait = 8 * (attempt + 1)
            log.warning(f"{endpoint} attempt {attempt+1} failed: {str(e)[:80]}, sleep {wait}s")
            time.sleep(wait)
    return None


def cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}.json"


def load_cache(name: str) -> dict | list | None:
    p = cache_path(name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def save_cache(name: str, data):
    p = cache_path(name)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ---- Fixtures ----

def fetch_fixtures(key: str) -> list[dict]:
    cached = load_cache("wc2026_fixtures")
    if cached:
        log.info(f"fixtures: {len(cached)} from cache")
        return cached

    data = api_get("fixtures", {"league": WC_LEAGUE, "season": WC_SEASON}, key)
    time.sleep(PACING)
    if not data:
        return []
    fixtures = data.get("response", [])
    save_cache("wc2026_fixtures", fixtures)
    log.info(f"fixtures: fetched {len(fixtures)}")
    return fixtures


def fixtures_to_db(fixtures: list[dict]):
    rows = []
    for f in fixtures:
        fi = f.get("fixture", {})
        t = f.get("teams", {})
        g = f.get("goals", {})
        sc = f.get("score", {})
        rows.append({
            "fixture_id": fi.get("id"),
            "date": fi.get("date", "")[:10],
            "timestamp": fi.get("timestamp"),
            "venue": (fi.get("venue") or {}).get("name"),
            "city": (fi.get("venue") or {}).get("city"),
            "status_short": (fi.get("status") or {}).get("short"),
            "status_long": (fi.get("status") or {}).get("long"),
            "home_team": (t.get("home") or {}).get("name"),
            "home_id": (t.get("home") or {}).get("id"),
            "away_team": (t.get("away") or {}).get("name"),
            "away_id": (t.get("away") or {}).get("id"),
            "home_goals": g.get("home"),
            "away_goals": g.get("away"),
            "home_ht": (sc.get("halftime") or {}).get("home"),
            "away_ht": (sc.get("halftime") or {}).get("away"),
            "home_ft": (sc.get("fulltime") or {}).get("home"),
            "away_ft": (sc.get("fulltime") or {}).get("away"),
            "home_et": (sc.get("extratime") or {}).get("home"),
            "away_et": (sc.get("extratime") or {}).get("away"),
            "home_pen": (sc.get("penalty") or {}).get("home"),
            "away_pen": (sc.get("penalty") or {}).get("away"),
            "league_round": (f.get("league") or {}).get("round"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    con = sqlite3.connect(DB_PATH)
    df.to_sql("apifb_fixtures", con, if_exists="replace", index=False)
    con.close()
    log.info(f"apifb_fixtures: {len(df)} rows written")
    return df


# ---- Lineups ----

def fetch_lineups(fixtures: list[dict], key: str) -> list[dict]:
    played = [f for f in fixtures
              if (f.get("fixture", {}).get("status") or {}).get("short") in
              ("FT", "AET", "PEN", "1H", "2H", "HT", "ET", "BT", "P")]
    if not played:
        log.info("lineups: no played matches yet")
        return []

    cached = load_cache("wc2026_lineups")
    cached_ids = set()
    if cached:
        cached_ids = {r.get("fixture_id") for r in cached}

    all_lineups = list(cached) if cached else []
    for f in played:
        fid = f["fixture"]["id"]
        if fid in cached_ids:
            continue
        data = api_get("fixtures/lineups", {"fixture": fid}, key)
        time.sleep(PACING)
        if not data:
            continue
        for team_lu in data.get("response", []):
            team = team_lu.get("team", {})
            coach = team_lu.get("coach", {})
            formation = team_lu.get("formation")
            for player in team_lu.get("startXI", []):
                p = player.get("player", {})
                all_lineups.append({
                    "fixture_id": fid,
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "player_id": p.get("id"),
                    "player_name": p.get("name"),
                    "number": p.get("number"),
                    "pos": p.get("pos"),
                    "grid": p.get("grid"),
                    "starter": True,
                    "formation": formation,
                    "coach": coach.get("name"),
                })
            for player in team_lu.get("substitutes", []):
                p = player.get("player", {})
                all_lineups.append({
                    "fixture_id": fid,
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "player_id": p.get("id"),
                    "player_name": p.get("name"),
                    "number": p.get("number"),
                    "pos": p.get("pos"),
                    "grid": p.get("grid"),
                    "starter": False,
                    "formation": formation,
                    "coach": coach.get("name"),
                })

    save_cache("wc2026_lineups", all_lineups)
    log.info(f"lineups: {len(all_lineups)} rows ({len(cached_ids)} cached)")
    return all_lineups


def lineups_to_db(lineups: list[dict]):
    df = pd.DataFrame(lineups)
    if df.empty:
        return df
    con = sqlite3.connect(DB_PATH)
    df.to_sql("apifb_lineups", con, if_exists="replace", index=False)
    con.close()
    log.info(f"apifb_lineups: {len(df)} rows written")
    return df


# ---- Injuries ----

def fetch_injuries(fixtures: list[dict], key: str) -> list[dict]:
    cached = load_cache("wc2026_injuries")
    if cached:
        log.info(f"injuries: {len(cached)} from cache")
        return cached

    all_inj = []
    played_or_upcoming = [f for f in fixtures
                          if (f.get("fixture", {}).get("status") or {}).get("short")
                          not in ("CANC", "PST", "ABD", "AWD", "WO")]
    for f in played_or_upcoming[:15]:  # budget: max 15 fixtures
        fid = f["fixture"]["id"]
        data = api_get("injuries", {"fixture": fid}, key)
        time.sleep(PACING)
        if not data:
            continue
        for inj in data.get("response", []):
            player = inj.get("player", {})
            team = inj.get("team", {})
            all_inj.append({
                "fixture_id": fid,
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "type": player.get("type"),
                "reason": player.get("reason"),
            })

    save_cache("wc2026_injuries", all_inj)
    log.info(f"injuries: {len(all_inj)} rows")
    return all_inj


def injuries_to_db(injuries: list[dict]):
    df = pd.DataFrame(injuries)
    if df.empty:
        return df
    con = sqlite3.connect(DB_PATH)
    df.to_sql("apifb_injuries", con, if_exists="replace", index=False)
    con.close()
    log.info(f"apifb_injuries: {len(df)} rows written")
    return df


# ---- Match Statistics ----

def fetch_stats(fixtures: list[dict], key: str) -> list[dict]:
    played = [f for f in fixtures
              if (f.get("fixture", {}).get("status") or {}).get("short") in
              ("FT", "AET", "PEN")]
    if not played:
        log.info("stats: no finished matches yet")
        return []

    cached = load_cache("wc2026_stats")
    cached_ids = set()
    if cached:
        cached_ids = {r.get("fixture_id") for r in cached}

    all_stats = list(cached) if cached else []
    for f in played:
        fid = f["fixture"]["id"]
        if fid in cached_ids:
            continue
        data = api_get("fixtures/statistics", {"fixture": fid}, key)
        time.sleep(PACING)
        if not data:
            continue
        for team_stats in data.get("response", []):
            team = team_stats.get("team", {})
            row = {"fixture_id": fid, "team_id": team.get("id"),
                   "team_name": team.get("name")}
            for stat in team_stats.get("statistics", []):
                stype = (stat.get("type") or "").lower().replace(" ", "_")
                row[stype] = stat.get("value")
            all_stats.append(row)

    save_cache("wc2026_stats", all_stats)
    log.info(f"stats: {len(all_stats)} rows ({len(cached_ids)} cached)")
    return all_stats


def stats_to_db(stats: list[dict]):
    df = pd.DataFrame(stats)
    if df.empty:
        return df
    con = sqlite3.connect(DB_PATH)
    df.to_sql("apifb_stats", con, if_exists="replace", index=False)
    con.close()
    log.info(f"apifb_stats: {len(df)} rows written")
    return df


# ---- Odds ----

def fetch_odds(fixtures: list[dict], key: str) -> list[dict]:
    cached = load_cache("wc2026_odds")
    if cached:
        log.info(f"odds: {len(cached)} from cache")
        return cached

    all_odds = []
    for f in fixtures[:20]:  # budget: max 20 fixtures
        fid = f["fixture"]["id"]
        data = api_get("odds", {"fixture": fid}, key)
        time.sleep(PACING)
        if not data:
            continue
        for bookmaker_block in data.get("response", []):
            for bm in bookmaker_block.get("bookmakers", []):
                bm_name = bm.get("name")
                for bet in bm.get("bets", []):
                    if bet.get("name") != "Match Winner":
                        continue
                    row = {"fixture_id": fid, "bookmaker": bm_name}
                    for val in bet.get("values", []):
                        v = val.get("value", "")
                        o = val.get("odd")
                        if v == "Home":
                            row["odd_home"] = float(o) if o else None
                        elif v == "Draw":
                            row["odd_draw"] = float(o) if o else None
                        elif v == "Away":
                            row["odd_away"] = float(o) if o else None
                    if any(row.get(k) for k in ("odd_home", "odd_draw", "odd_away")):
                        all_odds.append(row)

    save_cache("wc2026_odds", all_odds)
    log.info(f"odds: {len(all_odds)} rows")
    return all_odds


def odds_to_db(odds: list[dict]):
    df = pd.DataFrame(odds)
    if df.empty:
        return df
    if "odd_home" in df.columns:
        for col in ["odd_home", "odd_draw", "odd_away"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        mask = df[["odd_home", "odd_draw", "odd_away"]].notna().all(axis=1)
        df.loc[mask, "imp_home"] = (1 / df.loc[mask, "odd_home"])
        df.loc[mask, "imp_draw"] = (1 / df.loc[mask, "odd_draw"])
        df.loc[mask, "imp_away"] = (1 / df.loc[mask, "odd_away"])
        s = df.loc[mask, ["imp_home", "imp_draw", "imp_away"]].sum(axis=1)
        for c in ["imp_home", "imp_draw", "imp_away"]:
            df.loc[mask, c] = df.loc[mask, c] / s
    con = sqlite3.connect(DB_PATH)
    df.to_sql("apifb_odds", con, if_exists="replace", index=False)
    con.close()
    log.info(f"apifb_odds: {len(df)} rows written")
    return df


# ---- Main ----

def main():
    key = get_key()
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Always need fixtures first
    fixtures = fetch_fixtures(key)
    if not fixtures:
        log.error("No fixtures retrieved — check API key and network connectivity")
        return

    fixtures_to_db(fixtures)
    played = sum(1 for f in fixtures
                 if (f.get("fixture", {}).get("status") or {}).get("short") in
                 ("FT", "AET", "PEN"))
    upcoming = sum(1 for f in fixtures
                   if (f.get("fixture", {}).get("status") or {}).get("short") in
                   ("NS", "TBD"))
    log.info(f"WC2026: {len(fixtures)} fixtures, {played} played, {upcoming} upcoming")

    if mode in ("all", "lineups"):
        lineups = fetch_lineups(fixtures, key)
        lineups_to_db(lineups)

    if mode in ("all", "injuries"):
        injuries = fetch_injuries(fixtures, key)
        injuries_to_db(injuries)

    if mode in ("all", "stats"):
        stats = fetch_stats(fixtures, key)
        stats_to_db(stats)

    if mode in ("all", "odds"):
        odds = fetch_odds(fixtures, key)
        odds_to_db(odds)

    # Summary
    data = api_get("status", key=key)
    if data:
        req = data.get("response", {}).get("requests", {})
        log.info(f"API budget: {req.get('current', '?')}/{req.get('limit_day', '?')} used today")


if __name__ == "__main__":
    main()
