"""
Export SofaScore data to dashboard JS files.
Generates: dashboard/data/sofascore_data.js (window.SOFASCORE)
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "fifa_wc_data" / "db" / "football.db"
OUTJS = ROOT / "dashboard" / "data" / "sofascore_data.js"
SSDIR = Path(__file__).resolve().parent / "sofascore_data"


def export():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row

    # Power rankings
    pr = [dict(r) for r in con.execute(
        "SELECT rank, team, points, rank_diff, name_code FROM sofascore_power_rankings ORDER BY rank"
    ).fetchall()]

    # Standings
    standings = {}
    for row in con.execute(
        "SELECT group_name, team, position, matches_played, wins, draws, losses, goals_for, goals_against, points FROM sofascore_standings ORDER BY group_name, position"
    ).fetchall():
        g = dict(row)["group_name"]
        if g not in standings:
            standings[g] = []
        standings[g].append({
            "team": g and dict(row)["team"],
            "pos": dict(row)["position"],
            "mp": dict(row)["matches_played"],
            "w": dict(row)["wins"],
            "d": dict(row)["draws"],
            "l": dict(row)["losses"],
            "gf": dict(row)["goals_for"],
            "ga": dict(row)["goals_against"],
            "pts": dict(row)["points"],
        })

    # Events
    events = []
    for row in con.execute(
        "SELECT event_id, home_team, away_team, home_score, away_score, status, start_timestamp, group_name FROM sofascore_events ORDER BY start_timestamp"
    ).fetchall():
        r = dict(row)
        events.append({
            "id": r["event_id"],
            "home": r["home_team"],
            "away": r["away_team"],
            "hs": r["home_score"],
            "as": r["away_score"],
            "status": r["status"],
            "ts": r["start_timestamp"],
            "group": r["group_name"],
        })

    con.close()

    data = {
        "power_rankings": pr,
        "standings": standings,
        "events": events,
        "source": "SofaScore",
        "season_id": 58210,
        "tournament_id": 16,
    }

    js = f"window.SOFASCORE = {json.dumps(data, indent=2, ensure_ascii=False)};\n"
    OUTJS.write_text(js, encoding="utf-8")
    print(f"Exported to {OUTJS} ({len(js)} bytes)")
    print(f"  {len(pr)} power rankings")
    print(f"  {len(standings)} groups")
    print(f"  {len(events)} events")


if __name__ == "__main__":
    export()
