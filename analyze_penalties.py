"""TASK 2 (PENS): Penalty model from real shootout data"""
import sqlite3
import pandas as pd
import numpy as np
from scipy.optimize import minimize_scalar
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))
from common import DB_PATH, ROOT, get_logger

log = get_logger("pens")

# Load shootouts
shootouts = pd.read_csv(
    ROOT / "fifa_wc_data" / "raw" / "kaggle" / "international-football-results-from-1872-to-2017" / "shootouts.csv"
)
shootouts["date"] = pd.to_datetime(shootouts["date"])

# Load elo_match
con = sqlite3.connect(DB_PATH)
elo = pd.read_sql("""
    SELECT e.match_id, m.date, m.home_team, m.away_team, e.elo_home_pre, e.elo_away_pre
    FROM elo_match e JOIN matches m ON e.match_id=m.match_id
""", con)
con.close()
elo["date"] = pd.to_datetime(elo["date"])

# Canonical names
tm = pd.read_csv(ROOT / "research_ready_dataset" / "team_mapping.csv")
canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
shootouts["h"] = shootouts["home_team"].map(lambda t: canon.get(t, t))
shootouts["a"] = shootouts["away_team"].map(lambda t: canon.get(t, t))

# Join shootouts to ELO on date + teams
merged = []
for _, s in shootouts.iterrows():
    mask = (elo["date"] == s["date"]) & (elo["home_team"] == s["h"]) & (elo["away_team"] == s["a"])
    row = elo[mask]
    if row.empty:
        # Try reversed
        mask = (elo["date"] == s["date"]) & (elo["home_team"] == s["a"]) & (elo["away_team"] == s["h"])
        row = elo[mask]
    if not row.empty:
        eh = row.iloc[0]["elo_home_pre"]
        ea = row.iloc[0]["elo_away_pre"]
        # In the shootout, the "home_team" in the shootout CSV is the first team listed
        # The winner is either home_team or away_team
        winner = s["winner"]
        if pd.isna(winner):
            continue
        winner_canon = canon.get(winner, winner)
        # Determine if the higher-ELO team won
        higher_elo_team = s["h"] if eh > ea else s["a"]
        higher_won = 1 if winner_canon == higher_elo_team else 0
        elo_diff = abs(eh - ea)
        merged.append({
            "date": s["date"],
            "home": s["h"],
            "away": s["a"],
            "winner": winner_canon,
            "elo_diff": elo_diff,
            "higher_elo_team": higher_elo_team,
            "higher_won": higher_won,
        })

df = pd.DataFrame(merged)
print(f"Joined shootouts with ELO: {len(df)} of {len(shootouts)} ({len(df)/len(shootouts)*100:.1f}%)")
print(f"Higher-ELO team win rate: {df['higher_won'].mean():.3f}")

# Bin analysis
bins = [0, 50, 100, 200, 300, 500, 1000]
df["bin"] = pd.cut(df["elo_diff"], bins=bins)
print("\nBinned win rate:")
print(df.groupby("bin")["higher_won"].agg(["mean", "count"]))

# Logistic fit: p = 0.5 + slope * elo_diff / (1 + elo_diff/scale) or similar
# Simpler: p = 0.5 + alpha * tanh(beta * elo_diff)
from scipy.optimize import minimize

def nll(params, diff, y):
    alpha, beta = params
    p = 0.5 + alpha * np.tanh(beta * diff / 400.0)
    p = np.clip(p, 1e-12, 1-1e-12)
    return -np.mean(y * np.log(p) + (1-y) * np.log(1-p))

# Alternatively, simple linear: p = 0.5 + a * sign * (1 - exp(-b*|diff|))
# Let's try a simpler logistic on ELO diff
from scipy.special import expit

def nll_logistic(params, diff, y):
    a, b = params
    # p = sigmoid(a + b * diff/400)
    z = a + b * diff / 400.0
    p = expit(z)
    p = np.clip(p, 1e-12, 1-1e-12)
    return -np.mean(y * np.log(p) + (1-y) * np.log(1-p))

res = minimize(nll_logistic, x0=[0.0, 1.0], args=(df["elo_diff"].values, df["higher_won"].values), method="Nelder-Mead")
a, b = res.x
print(f"\nLogistic fit: p = sigmoid({a:.4f} + {b:.4f} * elo_diff/400)")

# Test predictions
z = a + b * df["elo_diff"].values / 400.0
pred = (expit(z) > 0.5).astype(int)
acc = (pred == df["higher_won"]).mean()
print(f"Accuracy: {acc:.3f}")

# Also try a simple constant offset model: p = 0.5 + c * sign(elo_diff)
# The current model is 0.5 + 0.03 * sign(elo_diff)
# Let's find the optimal c
def nll_const(c, diff, y):
    p = 0.5 + c * np.sign(diff)
    p = np.clip(p, 1e-12, 1-1e-12)
    return -np.mean(y * np.log(p) + (1-y) * np.log(1-p))

from scipy.optimize import minimize_scalar
res_c = minimize_scalar(lambda c: nll_const(c, df["elo_diff"].values, df["higher_won"].values), bounds=(0, 0.3), method="bounded")
print(f"\nConstant offset fit: p = 0.5 + {res_c.x:.4f} * sign(elo_diff)")

# For the model, use the logistic fit
# p_home_win_pens = 0.5 + 0.5 * sign(elo_home - elo_away) * (sigmoid(a + b * |elo_diff|/400) - 0.5)
# Actually simpler: just use the higher-ELO win probability
# p_home_win_pens = p_higher if home has higher elo, else 1 - p_higher
# where p_higher = sigmoid(a + b * |elo_diff|/400)

print("\nSample predictions:")
for d in [0, 50, 100, 200, 400, 800]:
    z = a + b * d / 400.0
    p = expit(z)
    print(f"  elo_diff={d:4d}: p_higher_wins={p:.4f}")

# Save results
import json
result = {
    "model": "logistic",
    "formula": "p_higher = sigmoid(a + b * elo_diff/400)",
    "a": a,
    "b": b,
    "n_shootouts": len(df),
    "join_rate": len(df)/len(shootouts),
    "higher_won_rate": float(df["higher_won"].mean()),
    "accuracy": acc,
    "old_model": "0.5 + 0.03 * sign(elo_diff)",
    "constant_offset": res_c.x,
}
(ROOT / "research_ready_dataset" / "penalty_model.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"\nSaved to research_ready_dataset/penalty_model.json")
