"""Evaluate model predictions vs actual results for completed WC2026 matches."""
import json
import sqlite3
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard" / "data"

# Load latest sim
sim = json.loads((DASH / "sim_results.json").read_text(encoding="utf-8"))

# Load SofaScore completed results
con = sqlite3.connect(str(ROOT / "fifa_wc_data" / "db" / "football.db"))
con.row_factory = sqlite3.Row
ss = con.execute("SELECT home_team, away_team, home_score, away_score FROM sofascore_events WHERE home_score IS NOT NULL").fetchall()
locked = con.execute("SELECT MatchNumber, HomeTeam, AwayTeam, HomeTeamScore, AwayTeamScore FROM wc2026_fixtures WHERE HomeTeamScore IS NOT NULL").fetchall()
con.close()

print("=== Completed results ===")
for r in locked:
    print(f"  M{r['MatchNumber']}: {r['HomeTeam']} {r['HomeTeamScore']:.0f}-{r['AwayTeamScore']:.0f} {r['AwayTeam']}")

# Match probs from sim
mp = {m["match_number"]: m for m in sim.get("match_probs", [])}

print("\n=== Model predictions for completed matches ===")
total_ll = 0
n = 0
for r in locked:
    mn = r["MatchNumber"]
    if mn not in mp:
        print(f"  M{mn}: not in match_probs")
        continue
    m = mp[mn]
    p = m["p"]  # [home_loss, draw, home_win]
    hs, as_ = r["HomeTeamScore"], r["AwayTeamScore"]
    if hs > as_:
        outcome = 2  # home win
        oname = "home win"
    elif hs == as_:
        outcome = 1
        oname = "draw"
    else:
        outcome = 0
        oname = "away win"
    pred_prob = p[outcome]
    ll = -math.log(max(pred_prob, 1e-12))
    total_ll += ll
    n += 1
    # What did model favor?
    favored = ["away win", "draw", "home win"][p.index(max(p))]
    print(f"  M{mn}: {m['home']} vs {m['away']}")
    print(f"    actual: {hs:.0f}-{as_:.0f} ({oname})")
    print(f"    model p: away={p[0]:.3f} draw={p[1]:.3f} home={p[2]:.3f}  (favored: {favored})")
    print(f"    prob assigned to actual outcome: {pred_prob:.3f}  -> log-loss {ll:.3f}")
    # scoreline check
    eg = m.get("exp_goals", [])
    if eg:
        print(f"    expected goals: {eg[0]} - {eg[1]}")

if n:
    print(f"\n=== Match outcome log-loss: {total_ll/n:.4f} (n={n}) ===")
    print(f"(uniform baseline = {-math.log(1/3):.4f})")
