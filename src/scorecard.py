"""
scorecard.py - live model success-rate tracker (LinkedIn-ready).

Joins played WC2026 results (sofascore_events) to our pre-match predictions
and computes, per match and running:
  - P(actual outcome), correct? (argmax == actual)
  - log-loss, Brier
  - vs coin-flip baseline (ln 3 = 1.0986)
  - 5-bin calibration (predicted prob vs realized frequency)

Tracks models:
  - elo_host: current deployed simulator (host bonus + ELO form blend)
  - player_blend: player-strength heuristic ensemble

Writes:
  artifacts/model_scorecard.csv          (per-match, idempotent on match_number+model)
  dashboard/data/scorecard_data.js       (window.SCORECARD for accuracy.html)

Class order everywhere: [home_loss, draw, home_win] = [0,1,2].
"""
from __future__ import annotations

import csv
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "fifa_wc_data" / "db" / "football.db"
DASH = ROOT / "dashboard" / "data"
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)

COINFLIP = math.log(3)  # 1.0986 nats — uniform 3-way baseline

# SofaScore name -> our canonical (sim) name. Extend as new teams play.
ALIASES = {
    "South Korea": "Korea Republic",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "USA": "USA",
    "Türkiye": "Türkiye",
    "Côte d'Ivoire": "Côte d'Ivoire",
}


def canon(name: str) -> str:
    return ALIASES.get(name, name)


def load_predictions():
    """Latest sim match_probs keyed by (home, away) canonical -> {p, match_number, exp_goals}."""
    sim = json.loads((DASH / "sim_results.json").read_text(encoding="utf-8"))
    by_pair = {}
    by_num = {}
    for m in sim.get("match_probs", []):
        rec = {"p": m["p"], "match_number": m["match_number"],
               "home": m["home"], "away": m["away"], "exp_goals": m.get("exp_goals")}
        by_pair[(m["home"], m["away"])] = rec
        by_num[m["match_number"]] = rec
    return by_pair, by_num, sim.get("meta", {}).get("as_of", "?")


def load_player_probs():
    """Load player_blend predictions from wc2026_player_probs.csv."""
    csv_path = ROOT / "research_ready_dataset" / "wc2026_player_probs.csv"
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path)
    by_pair = {}
    by_num = {}
    for _, r in df.iterrows():
        rec = {"p": [r["ensemble_away"], r["ensemble_draw"], r["ensemble_home"]],
               "match_number": r["match_id"],
               "home": r["home_team"], "away": r["away_team"]}
        by_pair[(r["home_team"], r["away_team"])] = rec
        by_num[r["match_id"]] = rec
    return by_pair, by_num


def played_results():
    con = sqlite3.connect(str(DB))
    rows = con.execute(
        "SELECT home_team, away_team, home_score, away_score, start_timestamp "
        "FROM sofascore_events WHERE home_score IS NOT NULL ORDER BY start_timestamp"
    ).fetchall()
    con.close()
    out = []
    for h, a, hs, as_, ts in rows:
        out.append({
            "home": canon(h), "away": canon(a),
            "hs": int(hs), "as": int(as_),
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "?",
        })
    return out


def outcome_index(hs, as_):
    if hs > as_:
        return 2  # home win
    if hs == as_:
        return 1  # draw
    return 0      # away win


OUTCOME_NAME = {0: "away win", 1: "draw", 2: "home win"}


def evaluate_model(results, predictions, model_name):
    """Evaluate a single model against results."""
    rows = []
    for r in results:
        pred = predictions.get((r["home"], r["away"]))
        if not pred:
            for (h, a), rec in predictions.items():
                if {h, a} == {r["home"], r["away"]}:
                    pred = rec
                    break
        if not pred:
            print(f"  WARN no {model_name} prediction for {r['home']} vs {r['away']}")
            continue
        p = pred["p"]
        oc = outcome_index(r["hs"], r["as"])
        p_oc = max(p[oc], 1e-12)
        ll = -math.log(p_oc)
        onehot = [0, 0, 0]
        onehot[oc] = 1
        brier = sum((p[i] - onehot[i]) ** 2 for i in range(3))
        correct = (max(range(3), key=lambda i: p[i]) == oc)
        rows.append({
            "match_number": pred["match_number"],
            "date": r["date"],
            "home": r["home"], "away": r["away"],
            "score": f"{r['hs']}-{r['as']}",
            "outcome": OUTCOME_NAME[oc],
            "model": model_name,
            "p_home": round(p[2], 4), "p_draw": round(p[1], 4), "p_away": round(p[0], 4),
            "p_outcome": round(p_oc, 4),
            "correct": bool(correct),
            "logloss": round(ll, 4),
            "brier": round(brier, 4),
        })
    return rows


def aggregate(model_rows):
    n = len(model_rows)
    if n == 0:
        return None
    hit = sum(1 for r in model_rows if r["correct"]) / n
    mll = sum(r["logloss"] for r in model_rows) / n
    mbrier = sum(r["brier"] for r in model_rows) / n
    bins = [{"lo": i / 5, "hi": (i + 1) / 5, "n": 0, "pred_sum": 0.0, "hit": 0} for i in range(5)]
    for r in model_rows:
        pmax = max(r["p_home"], r["p_draw"], r["p_away"])
        b = min(4, int(pmax * 5))
        bins[b]["n"] += 1
        bins[b]["pred_sum"] += pmax
        bins[b]["hit"] += 1 if r["correct"] else 0
    cal = [{"lo": b["lo"], "hi": b["hi"], "n": b["n"],
            "pred": round(b["pred_sum"] / b["n"], 3) if b["n"] else None,
            "obs": round(b["hit"] / b["n"], 3) if b["n"] else None} for b in bins]
    return {
        "model": model_rows[0]["model"],
        "n_matches": n,
        "hit_rate": round(hit, 4),
        "mean_logloss": round(mll, 4),
        "vs_coinflip": round(COINFLIP - mll, 4),
        "mean_brier": round(mbrier, 4),
        "calibration": cal,
    }


def build():
    by_pair, by_num, run_id = load_predictions()
    player_by_pair, player_by_num = load_player_probs()
    results = played_results()

    # Evaluate models
    all_rows = []
    
    # elo_host (current deployed model)
    elo_host_rows = evaluate_model(results, by_pair, "elo_host")
    all_rows.extend(elo_host_rows)
    
    # player_blend
    if player_by_pair:
        player_rows = evaluate_model(results, player_by_pair, "player_blend")
        all_rows.extend(player_rows)
    
    all_rows.sort(key=lambda x: (x["match_number"], x["model"]))

    # Write CSV
    csv_path = ART / "model_scorecard.csv"
    fields = ["match_number", "date", "home", "away", "score", "outcome", "model",
              "p_home", "p_draw", "p_away", "p_outcome", "correct", "logloss", "brier"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    # Aggregate per model
    models = {}
    for r in all_rows:
        models.setdefault(r["model"], []).append(r)
    summaries = [aggregate(v) for v in models.values() if v]

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "coinflip_logloss": round(COINFLIP, 4),
        "models": summaries,
        "matches": all_rows,
    }
    (DASH / "scorecard_data.js").write_text(
        f"window.SCORECARD = {json.dumps(data, ensure_ascii=False)};\n", encoding="utf-8")

    # Console summary
    print(f"Scorecard: {len(results)} played matches")
    for s in summaries:
        print(f"  [{s['model']}] hit-rate {s['hit_rate']*100:.0f}%  "
              f"log-loss {s['mean_logloss']:.3f}  (coin-flip {COINFLIP:.3f}, "
              f"beats by {s['vs_coinflip']:+.3f})  Brier {s['mean_brier']:.3f}")
    print(f"  -> {csv_path}")
    print(f"  -> {DASH / 'scorecard_data.js'}")


if __name__ == "__main__":
    build()
