"""
Integrate SofaScore player data into football.db + dashboard.

Reads:  scrapers/sofascore_players/players/player_*.json
Writes: DB tables
          sofascore_player_attributes  (current + historical FIFA-style ratings)
          sofascore_player_career       (national-team apps/goals)
          sofascore_team_strength       (squad-aggregated position-group ratings)
        dashboard/data/players_data.js  (window.PLAYERS)
"""
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "fifa_wc_data" / "db" / "football.db"
PLAYER_DIR = Path(__file__).resolve().parent / "sofascore_players" / "players"
OUTJS = ROOT / "dashboard" / "data" / "players_data.js"

# position -> group
POS_GROUP = {"G": "GK", "D": "DEF", "M": "MID", "F": "ATT"}


def load_players():
    players = []
    for pf in sorted(PLAYER_DIR.glob("player_*.json")):
        try:
            players.append(json.loads(pf.read_text(encoding="utf-8")))
        except:
            pass
    return players


def integrate():
    players = load_players()
    print(f"Loaded {len(players)} player files")

    con = sqlite3.connect(str(DB))
    cur = con.cursor()

    # ---- attributes (current yearShift=0 + historical) ----
    # outfield: attacking/technical/tactical/defending/creativity
    # goalkeeper: saves/anticipation/ballDistribution/aerial/tactical
    cur.execute("DROP TABLE IF EXISTS sofascore_player_attributes")
    cur.execute("""
        CREATE TABLE sofascore_player_attributes (
            player_id INTEGER, name TEXT, team TEXT, team_id INTEGER,
            position TEXT, pos_group TEXT, year_shift INTEGER,
            attacking INTEGER, technical INTEGER, tactical INTEGER,
            defending INTEGER, creativity INTEGER,
            saves INTEGER, anticipation INTEGER, ball_distribution INTEGER, aerial INTEGER
        )
    """)
    # ---- career ----
    cur.execute("DROP TABLE IF EXISTS sofascore_player_career")
    cur.execute("""
        CREATE TABLE sofascore_player_career (
            player_id INTEGER, name TEXT, team TEXT,
            nt_appearances INTEGER, nt_goals INTEGER, debut_ts INTEGER
        )
    """)

    attr_rows = []
    career_rows = []
    # team -> pos_group -> list of current attribute dicts
    team_pos = defaultdict(lambda: defaultdict(list))

    for p in players:
        pid = p.get("player_id")
        name = p.get("name", "?")
        team = p.get("team", "?")
        tid = p.get("team_id")

        ao = p.get("attribute-overviews", {})
        povs = ao.get("playerAttributeOverviews", []) if isinstance(ao, dict) else []
        for o in povs:
            pos = o.get("position", "?")
            grp = POS_GROUP.get(pos, pos)
            ys = o.get("yearShift", 0)
            attr_rows.append((
                pid, name, team, tid, pos, grp, ys,
                o.get("attacking"), o.get("technical"), o.get("tactical"),
                o.get("defending"), o.get("creativity"),
                o.get("saves"), o.get("anticipation"), o.get("ballDistribution"), o.get("aerial")
            ))
            if ys == 0:
                team_pos[team][grp].append(o)

        nts = p.get("national-team-statistics", {})
        stats = nts.get("statistics", []) if isinstance(nts, dict) else []
        if stats:
            s = stats[0]
            career_rows.append((
                pid, name, team,
                s.get("appearances"), s.get("goals"), s.get("debutTimestamp")
            ))

    cur.executemany("INSERT INTO sofascore_player_attributes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", attr_rows)
    cur.executemany("INSERT INTO sofascore_player_career VALUES (?,?,?,?,?,?)", career_rows)
    print(f"  attributes: {len(attr_rows)} rows ({sum(1 for r in attr_rows if r[6]==0)} current)")
    print(f"  career: {len(career_rows)} rows")

    # ---- team strength (squad-avg current ratings by position group) ----
    cur.execute("DROP TABLE IF EXISTS sofascore_team_strength")
    cur.execute("""
        CREATE TABLE sofascore_team_strength (
            team TEXT, pos_group TEXT, n_players INTEGER, avg_overall REAL,
            avg_attacking REAL, avg_technical REAL, avg_tactical REAL,
            avg_defending REAL, avg_creativity REAL,
            avg_saves REAL, avg_anticipation REAL, avg_ball_distribution REAL, avg_aerial REAL
        )
    """)
    ts_rows = []
    for team, groups in team_pos.items():
        for grp, ovs in groups.items():
            n = len(ovs)
            if n == 0:
                continue
            def avg(key):
                vals = [o.get(key) for o in ovs if o.get(key) is not None]
                return round(sum(vals) / len(vals), 1) if vals else None
            # position-appropriate overall
            if grp == "GK":
                metric_keys = ("tactical", "saves", "anticipation", "ballDistribution", "aerial")
            else:
                metric_keys = ("attacking", "technical", "tactical", "defending", "creativity")
            per_player = []
            for o in ovs:
                vals = [o.get(k) for k in metric_keys if o.get(k) is not None]
                if vals:
                    per_player.append(sum(vals) / len(vals))
            overall = round(sum(per_player) / len(per_player), 1) if per_player else None
            ts_rows.append((team, grp, n, overall, avg("attacking"), avg("technical"),
                            avg("tactical"), avg("defending"), avg("creativity"),
                            avg("saves"), avg("anticipation"), avg("ballDistribution"), avg("aerial")))
    cur.executemany("INSERT INTO sofascore_team_strength VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ts_rows)
    print(f"  team_strength: {len(ts_rows)} rows ({len(team_pos)} teams)")

    con.commit()

    # ---- dashboard JS ----
    # top players by overall current rating (mean of available attrs; GK uses GK metrics)
    top = []
    for r in attr_rows:
        if r[6] != 0:  # year_shift 0 only
            continue
        grp = r[5]
        if grp == "GK":
            vals = [v for v in (r[9], r[12], r[13], r[14], r[15]) if v is not None]  # tactical+saves+antic+dist+aerial
        else:
            vals = [v for v in r[7:12] if v is not None]
        if not vals:
            continue
        overall = round(sum(vals) / len(vals), 1)
        top.append({
            "name": r[1], "team": r[2], "position": r[4], "group": r[5],
            "attacking": r[7], "technical": r[8], "tactical": r[9],
            "defending": r[10], "creativity": r[11],
            "saves": r[12], "anticipation": r[13], "ball_distribution": r[14], "aerial": r[15],
            "overall": overall
        })
    top.sort(key=lambda x: -x["overall"])

    # rank within position group (overall is position-relative, so a global
    # leaderboard mixes scales — group_rank lets the UI compare like-for-like)
    grp_counter = {}
    for t in top:
        g = t["group"]
        grp_counter[g] = grp_counter.get(g, 0) + 1
        t["group_rank"] = grp_counter[g]

    team_strength = [
        {"team": r[0], "group": r[1], "n": r[2], "overall": r[3],
         "attacking": r[4], "technical": r[5], "tactical": r[6],
         "defending": r[7], "creativity": r[8],
         "saves": r[9], "anticipation": r[10], "ball_distribution": r[11], "aerial": r[12]}
        for r in ts_rows
    ]

    data = {
        "top_players": top,  # all rated players (team/position filters need full coverage)
        "team_strength": team_strength,
        "source": "SofaScore attribute-overviews",
        "n_players": len(players),
    }
    OUTJS.write_text(f"window.PLAYERS = {json.dumps(data, ensure_ascii=False)};\n", encoding="utf-8")
    print(f"  dashboard JS: {OUTJS} ({len(top)} rated players)")

    # summary
    print("\nTop 10 players by overall rating:")
    for t in top[:10]:
        print(f"  {t['overall']:.1f}  {t['name']:22s} {t['team']:14s} [{t['position']}] "
              f"ATK={t['attacking']} DEF={t['defending']} CRE={t['creativity']}")

    con.close()


if __name__ == "__main__":
    integrate()
