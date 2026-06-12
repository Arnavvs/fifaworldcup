"""
Integrate SofaScore WC2026 data into the prediction pipeline.
Reads: scrapers/sofascore_data/*.json
Writes: football.db tables (sofascore_*), live standings update
"""
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "fifa_wc_data" / "db" / "football.db"
SSDIR = Path(__file__).resolve().parent / "sofascore_data"


def load_json(name):
    fpath = SSDIR / f"{name}.json"
    if fpath.exists():
        return json.loads(fpath.read_text(encoding="utf-8"))
    # Try cap_ prefix
    fpath2 = SSDIR / f"cap_{name}.json"
    if fpath2.exists():
        return json.loads(fpath2.read_text(encoding="utf-8"))
    return None


def integrate():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()

    # ========================================
    # 1. SOFASCORE POWER RANKINGS
    # ========================================
    pr = load_json("unique-tournament_16_season_58210_power-rankings_round_133")
    if pr:
        cur.execute("DROP TABLE IF EXISTS sofascore_power_rankings")
        cur.execute("""
            CREATE TABLE sofascore_power_rankings (
                rank INTEGER,
                team TEXT,
                team_id INTEGER,
                points INTEGER,
                rank_diff INTEGER,
                name_code TEXT
            )
        """)
        rows = []
        for r in pr.get("powerRankings", []):
            team = r["team"]["name"]
            tid = r["team"]["id"]
            rank = r["rank"]
            pts = r["points"]
            diff = r.get("rankDiff", 0)
            code = r["team"].get("nameCode", "")
            rows.append((rank, team, tid, pts, diff, code))
        cur.executemany("INSERT INTO sofascore_power_rankings VALUES (?,?,?,?,?,?)", rows)
        print(f"  Power rankings: {len(rows)} teams")

    # ========================================
    # 2. STANDINGS (live group tables)
    # ========================================
    st = load_json("unique-tournament_16_season_58210_standings_total")
    if not st:
        st = load_json("standings")
    if st:
        cur.execute("DROP TABLE IF EXISTS sofascore_standings")
        cur.execute("""
            CREATE TABLE sofascore_standings (
                group_name TEXT,
                team TEXT,
                team_id INTEGER,
                position INTEGER,
                matches_played INTEGER,
                wins INTEGER,
                draws INTEGER,
                losses INTEGER,
                goals_for INTEGER,
                goals_against INTEGER,
                points INTEGER
            )
        """)
        rows = []
        for g in st.get("standings", []):
            gname = g.get("tournament", {}).get("name", "?")
            if "Third" in gname:
                continue
            # Extract group letter
            group_letter = gname.split("Group ")[-1] if "Group" in gname else gname
            for i, r in enumerate(g.get("rows", [])):
                team = r["team"]["name"]
                tid = r["team"]["id"]
                rows.append((
                    f"Group {group_letter}",
                    team, tid, i + 1,
                    r.get("matches", 0),
                    r.get("wins", 0),
                    r.get("draws", 0),
                    r.get("losses", 0),
                    r.get("scoresFor", 0),
                    r.get("scoresAgainst", 0),
                    r.get("points", 0)
                ))
        cur.executemany("INSERT INTO sofascore_standings VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        print(f"  Standings: {len(rows)} rows across {len(set(r[0] for r in rows))} groups")

    # ========================================
    # 3. EVENTS (match schedule + results)
    # ========================================
    events_data = load_json("all_events")
    if events_data:
        cur.execute("DROP TABLE IF EXISTS sofascore_events")
        cur.execute("""
            CREATE TABLE sofascore_events (
                event_id INTEGER PRIMARY KEY,
                home_team TEXT,
                away_team TEXT,
                home_team_id INTEGER,
                away_team_id INTEGER,
                home_score INTEGER,
                away_score INTEGER,
                status TEXT,
                start_timestamp INTEGER,
                round_num INTEGER,
                group_name TEXT,
                slug TEXT
            )
        """)
        rows = []
        for ev in events_data.get("events", []):
            eid = ev.get("id")
            ht = ev.get("homeTeam", {}).get("name")
            at = ev.get("awayTeam", {}).get("name")
            htid = ev.get("homeTeam", {}).get("id")
            atid = ev.get("awayTeam", {}).get("id")
            hs = ev.get("homeScore", {}).get("current")
            as_ = ev.get("awayScore", {}).get("current")
            status = ev.get("status", {}).get("description", "")
            ts = ev.get("startTimestamp", 0)
            rnd = ev.get("roundInfo", {}).get("round")
            grp = ev.get("tournament", {}).get("name", "")
            slug = ev.get("slug", "")
            if ht and at:
                rows.append((eid, ht, at, htid, atid, hs, as_, status, ts, rnd, grp, slug))
        cur.executemany("INSERT OR REPLACE INTO sofascore_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        print(f"  Events: {len(rows)} matches")

    # ========================================
    # 4. ODDS (from captured featured odds)
    # ========================================
    odds_file = load_json("event_15186720_odds_1_featured")
    if odds_file:
        cur.execute("DROP TABLE IF EXISTS sofascore_odds")
        cur.execute("""
            CREATE TABLE sofascore_odds (
                event_id INTEGER,
                market TEXT,
                home_odds REAL,
                draw_odds REAL,
                away_odds REAL
            )
        """)
        # Parse the captured odds
        for market_key, mkt in odds_file.items():
            if not isinstance(mkt, dict) or "choices" not in mkt:
                continue
            mname = mkt.get("marketName", "?")
            choices = mkt.get("choices", [])
            if len(choices) >= 3 and mname == "Full time":
                # Convert fractional to decimal
                def frac_to_dec(frac_str):
                    if not frac_str or "/" not in str(frac_str):
                        return None
                    parts = str(frac_str).split("/")
                    return round(float(parts[0]) / float(parts[1]) + 1, 3)

                h = frac_to_dec(choices[0].get("fractionalValue"))
                d = frac_to_dec(choices[1].get("fractionalValue"))
                a = frac_to_dec(choices[2].get("fractionalValue"))
                if h and d and a:
                    cur.execute("INSERT INTO sofascore_odds VALUES (?,?,?,?,?)",
                                (15186720, mname, h, d, a))
                    print(f"  Odds for event 15186720: H={h}, D={d}, A={a}")

    con.commit()

    # ========================================
    # SUMMARY
    # ========================================
    print(f"\n{'='*50}")
    print("DATABASE SUMMARY")
    print(f"{'='*50}")
    for table in ["sofascore_power_rankings", "sofascore_standings", "sofascore_events", "sofascore_odds"]:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {cnt} rows")
        except:
            print(f"  {table}: not created")

    con.close()
    print(f"\nDone. Database: {DB}")


if __name__ == "__main__":
    integrate()
