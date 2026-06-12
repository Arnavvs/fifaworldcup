"""
ask.py — deterministic CLI for the prediction system.  TASK 7 id:ASK

Usage:
  python ask.py predict <home> <away> [--stage group|r32|r16|qf|sf|final] [--neutral]
  python ask.py cup-odds [--top N]
  python ask.py group <A..L>
  python ask.py match <match_number>
  python ask.py scorers [--top N]
  python ask.py chaos
  python ask.py status

All output = single-line JSON to stdout. Reads ONLY latest artifacts/run_*.
Team names resolved via team_mapping.csv + difflib fuzzy match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import difflib

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard" / "data"

def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}

# Load latest sim
def latest_sim():
    data = load_json(DASH / "sim_results.json")
    return data

# Team mapping
def load_canon():
    import pandas as pd
    df = pd.read_csv(ROOT / "research_ready_dataset" / "team_mapping.csv")
    return dict(zip(df["raw_name"], df["canonical_name"]))

def resolve_team(name, canon):
    if name in canon.values():
        return name
    if name in canon:
        return canon[name]
    matches = difflib.get_close_matches(name, list(canon.values()) + list(canon.keys()), n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return None


def cmd_predict(args):
    canon = load_canon()
    home = resolve_team(args[0], canon)
    away = resolve_team(args[1], canon)
    if not home or not away:
        return json.dumps({"error": "ambiguous team name", "home": home, "away": away})
    sim = latest_sim()
    # Find match in match_probs
    match = None
    for m in sim.get("match_probs", []):
        if m["home"] == home and m["away"] == away:
            match = m
            break
    if not match:
        return json.dumps({"error": "match not found", "home": home, "away": away})
    p = match["p"]
    H = float(-sum(pi * __import__("math").log(pi) for pi in p if pi > 0))
    return json.dumps({
        "home": home, "away": away,
        "p": p,
        "exp_goals": match.get("exp_goals"),
        "H": round(H, 3),
        "run_id": sim.get("meta", {}).get("as_of", "?"),
    }, default=str)


def cmd_cup_odds(args):
    top = 20
    if args and args[0] == "--top":
        top = int(args[1]) if len(args) > 1 else 20
    sim = latest_sim()
    champ = sim.get("champion", {})
    items = sorted(champ.items(), key=lambda x: -x[1])[:top]
    return json.dumps({
        "champion_odds": [{"team": t, "prob": round(p, 4)} for t, p in items],
        "run_id": sim.get("meta", {}).get("as_of", "?"),
    }, default=str)


def cmd_group(args):
    if not args:
        return json.dumps({"error": "group letter required"})
    g = args[0].upper()
    sim = latest_sim()
    tables = sim.get("group_tables_expected", {})
    if g not in tables:
        return json.dumps({"error": f"group {g} not found"})
    return json.dumps({
        "group": g,
        "table": tables[g],
        "run_id": sim.get("meta", {}).get("as_of", "?"),
    }, default=str)


def cmd_match(args):
    if not args:
        return json.dumps({"error": "match_number required"})
    n = int(args[0])
    sim = latest_sim()
    for m in sim.get("match_probs", []):
        if m["match_number"] == n:
            return json.dumps({
                "match_number": n,
                "home": m["home"], "away": m["away"],
                "p": m["p"],
                "exp_goals": m.get("exp_goals"),
                "run_id": sim.get("meta", {}).get("as_of", "?"),
            }, default=str)
    return json.dumps({"error": f"match {n} not found"})


def cmd_scorers(args):
    top = 20
    if args and args[0] == "--top":
        top = int(args[1]) if len(args) > 1 else 20
    # scorers.json not yet built
    return json.dumps({"error": "scorers model not yet built", "top": top})


def cmd_chaos(args):
    sim = latest_sim()
    C = sim.get("chaos", {})
    return json.dumps({
        "expected_total_H": C.get("expected_total_surprisal_H"),
        "sim_p10": C.get("sim_surprisal_p10"),
        "sim_p90": C.get("sim_surprisal_p90"),
        "run_id": sim.get("meta", {}).get("as_of", "?"),
    }, default=str)


def cmd_status(args):
    sim = latest_sim()
    meta = sim.get("meta", {})
    return json.dumps({
        "last_run": meta.get("as_of", "?"),
        "n_sims": meta.get("n_sims", 0),
        "locked_matches": meta.get("locked_matches", 0),
        "engine": meta.get("engine", "?"),
    }, default=str)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "subcommand required"}))
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "predict":
        print(cmd_predict(args))
    elif cmd == "cup-odds":
        print(cmd_cup_odds(args))
    elif cmd == "group":
        print(cmd_group(args))
    elif cmd == "match":
        print(cmd_match(args))
    elif cmd == "scorers":
        print(cmd_scorers(args))
    elif cmd == "chaos":
        print(cmd_chaos(args))
    elif cmd == "status":
        print(cmd_status(args))
    else:
        print(json.dumps({"error": f"unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
