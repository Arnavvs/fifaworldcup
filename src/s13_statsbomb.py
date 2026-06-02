"""
Stage 13 - StatsBomb open data: real xG + starting lineups for World Cups.

Pulls FIFA World Cup 2022 + 2018 (competition_id 43) from the free StatsBomb
open-data repo. For each match it reads the events JSON once and extracts:
  - starting XI per team (-> starting_lineups)            [objective #5]
  - team xG / shots / goals per match (-> sb_team_match_stats)  [objective #6]
  - player xG / shots / goals per match (-> sb_player_match_stats)
Checkpointed per match (resumable). Raw aggregates -> raw/statsbomb/, DB tables.
"""
from __future__ import annotations

import sqlite3
import sys

import pandas as pd
import requests

from common import (RAW, DB_PATH, get_logger, log_attempt, save_df,
                    checkpoint_done, mark_done)

log = get_logger("s13_sb")
OUT = RAW / "statsbomb"
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
H = {"User-Agent": "Mozilla/5.0 (wc2026-research)"}
# (competition_id, season_id, label)
SEASONS = [(43, 106, "WC2022"), (43, 3, "WC2018")]


def get_json(url: str):
    try:
        r = requests.get(url, headers=H, timeout=40)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning(f"fetch fail {url}: {e}")
    return None


def parse_match(events: list, match_id: int, label: str):
    starters, team_rows, player_rows = [], {}, {}
    for ev in events:
        etype = ev.get("type", {}).get("name")
        team = ev.get("team", {}).get("name")
        if etype == "Starting XI":
            for p in ev.get("tactics", {}).get("lineup", []):
                starters.append({
                    "match_id": match_id, "tournament": label, "team": team,
                    "player": p.get("player", {}).get("name"),
                    "position": p.get("position", {}).get("name"),
                    "jersey_number": p.get("jersey_number"), "starter": 1,
                })
        elif etype == "Shot":
            xg = ev.get("shot", {}).get("statsbomb_xg", 0) or 0
            goal = 1 if ev.get("shot", {}).get("outcome", {}).get("name") == "Goal" else 0
            player = ev.get("player", {}).get("name")
            tr = team_rows.setdefault(team, {"xg": 0.0, "shots": 0, "goals": 0})
            tr["xg"] += xg; tr["shots"] += 1; tr["goals"] += goal
            pr = player_rows.setdefault((team, player), {"xg": 0.0, "shots": 0, "goals": 0})
            pr["xg"] += xg; pr["shots"] += 1; pr["goals"] += goal
    team_stats = [{"match_id": match_id, "tournament": label, "team": t,
                   "xg": round(v["xg"], 3), "shots": v["shots"], "goals": v["goals"]}
                  for t, v in team_rows.items()]
    player_stats = [{"match_id": match_id, "tournament": label, "team": t, "player": p,
                     "xg": round(v["xg"], 3), "shots": v["shots"], "goals": v["goals"]}
                    for (t, p), v in player_rows.items()]
    return starters, team_stats, player_stats


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_line, all_team, all_player, all_matches = [], [], [], []

    for comp, season, label in SEASONS:
        matches = get_json(f"{BASE}/matches/{comp}/{season}.json")
        if not matches:
            log_attempt("statsbomb", f"matches/{comp}/{season}", "fail", 0, "no matches")
            continue
        log.info(f"{label}: {len(matches)} matches")
        for mt in matches:
            mid = mt["match_id"]
            all_matches.append({
                "match_id": mid, "tournament": label, "date": mt.get("match_date"),
                "home_team": mt.get("home_team", {}).get("home_team_name"),
                "away_team": mt.get("away_team", {}).get("away_team_name"),
                "home_score": mt.get("home_score"), "away_score": mt.get("away_score"),
                "stage": mt.get("competition_stage", {}).get("name"),
                "stadium": (mt.get("stadium") or {}).get("name"),
                "referee": (mt.get("referee") or {}).get("name"),
            })
            ck = f"{label}_{mid}"
            if checkpoint_done("statsbomb", ck):
                continue
            events = get_json(f"{BASE}/events/{mid}.json")
            if not events:
                log_attempt("statsbomb", f"events/{mid}", "fail", 0, label)
                continue
            line, team_s, player_s = parse_match(events, mid, label)
            all_line += line; all_team += team_s; all_player += player_s
            mark_done("statsbomb", ck)
        log.info(f"{label}: cumulative starters={len(all_line)} team-rows={len(all_team)}")

    # persist
    dfm = pd.DataFrame(all_matches).drop_duplicates("match_id")
    dfl = pd.DataFrame(all_line)
    dft = pd.DataFrame(all_team)
    dfp = pd.DataFrame(all_player)
    save_df(dfm, OUT / "sb_matches.csv")
    if len(dfl): save_df(dfl, OUT / "starting_lineups.csv")
    if len(dft): save_df(dft, OUT / "sb_team_match_stats.csv")
    if len(dfp): save_df(dfp, OUT / "sb_player_match_stats.csv")

    con = sqlite3.connect(DB_PATH)
    dfm.to_sql("sb_matches", con, if_exists="replace", index=False)
    if len(dfl): dfl.to_sql("starting_lineups", con, if_exists="replace", index=False)
    if len(dft): dft.to_sql("sb_team_match_stats", con, if_exists="replace", index=False)
    if len(dfp): dfp.to_sql("sb_player_match_stats", con, if_exists="replace", index=False)
    con.commit(); con.close()

    log_attempt("statsbomb", "WC2022+2018", "ok", len(dft), "xg+lineups")
    log.info(f"StatsBomb done: {len(dfm)} matches, {len(dfl)} starter rows, "
             f"{len(dft)} team-xg rows, {len(dfp)} player-xg rows")


if __name__ == "__main__":
    sys.exit(main())
