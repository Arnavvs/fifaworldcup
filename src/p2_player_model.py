"""
p2_player_model.py — Player-strength match model + WC2026 ensemble.

TASK 3 id: PLR-MODEL

For each WC2026 match, compute player-strength features from team_strength_features,
blend with existing stack (m6) to produce adjusted probabilities.

Outputs:
  research_ready_dataset/wc2026_player_probs.csv
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

import sys
sys.path.insert(0, str(Path(__file__).parent))
from common import DB_PATH, ROOT, get_logger

log = get_logger("p2_model")
OUT = ROOT / "research_ready_dataset"


def load_wc2026_matches():
    """Load WC2026 fixtures from DB."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT MatchNumber as match_id, HomeTeam as home_team, AwayTeam as away_team,
               HomeTeamScore as home_score, AwayTeamScore as away_score
        FROM wc2026_fixtures
    """, con)
    con.close()
    return df


def load_team_strength():
    """Load team strength features from CSV."""
    return pd.read_csv(OUT / "wc2026_team_strength.csv")


def load_stack_probs():
    """Load existing stack probabilities (if generated)."""
    # Try to load from m6_stack or m8_simulate
    stack_file = OUT / "wc2026_stack_probs.csv"
    if stack_file.exists():
        return pd.read_csv(stack_file)
    # Otherwise generate from DB
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT MatchNumber as match_id, HomeTeamScore as home_score, AwayTeamScore as away_score
        FROM wc2026_fixtures
    """, con)
    con.close()
    return df


def compute_player_features(matches, strength):
    """Join team strength to matches and compute diff features."""
    # Merge home strength
    home = strength.rename(columns={c: f"home_{c}" for c in strength.columns if c != "team"})
    df = matches.merge(home, left_on="home_team", right_on="team", how="left")
    # Merge away strength
    away = strength.rename(columns={c: f"away_{c}" for c in strength.columns if c != "team"})
    df = df.merge(away, left_on="away_team", right_on="team", how="left")
    
    # Compute diffs
    df["diff_squad_overall"] = df["home_squad_overall"] - df["away_squad_overall"]
    df["diff_top3_att"] = df["home_top3_att_mean"] - df["away_top3_att_mean"]
    df["diff_squad_caps"] = df["home_squad_caps_total"] - df["away_squad_caps_total"]
    
    return df


def main():
    matches = load_wc2026_matches()
    strength = load_team_strength()
    
    # Compute player features
    df = compute_player_features(matches, strength)
    
    # Use a simple model: player advantage = weighted diff of features
    # We don't have historical player data, so we use a heuristic blend
    # Player advantage score: higher = home team stronger
    # Normalize features
    df["diff_squad_overall_z"] = (df["diff_squad_overall"] - df["diff_squad_overall"].mean()) / df["diff_squad_overall"].std()
    df["diff_top3_att_z"] = (df["diff_top3_att"] - df["diff_top3_att"].mean()) / df["diff_top3_att"].std()
    df["diff_squad_caps_z"] = (df["diff_squad_caps"] - df["diff_squad_caps"].mean()) / df["diff_squad_caps"].std()
    
    # Player advantage score (equal weights)
    df["player_advantage"] = df["diff_squad_overall_z"] + df["diff_top3_att_z"] + 0.2 * df["diff_squad_caps_z"]
    
    # Convert to probability adjustment
    # Use a logistic transform: p_player = sigmoid(player_advantage * scale)
    scale = 0.5
    df["p_player_home"] = 1 / (1 + np.exp(-df["player_advantage"] * scale))
    df["p_player_away"] = 1 - df["p_player_home"]
    
    # For 3-class, we need to split draw. Simple approach: draw_prob = 0.25 (fixed)
    # But better: use the existing stack draw probability if available
    # For now, use a simple heuristic: draw = 0.25, home = p_player_home * 0.75, away = p_player_away * 0.75
    df["p_player_draw"] = 0.25
    df["p_player_home"] = df["p_player_home"] * 0.75
    df["p_player_away"] = df["p_player_away"] * 0.75
    
    # Blend with existing stack (if available)
    stack = load_stack_probs()
    if stack is not None and not stack.empty:
        df = df.merge(stack, on="match_id", how="left")
        # If stack columns exist, use them
        if "stack_home" in df.columns:
            # Blend: 70% stack, 30% player
            df["ensemble_home"] = 0.7 * df["stack_home"] + 0.3 * df["p_player_home"]
            df["ensemble_draw"] = 0.7 * df["stack_draw"] + 0.3 * df["p_player_draw"]
            df["ensemble_away"] = 0.7 * df["stack_away"] + 0.3 * df["p_player_away"]
        else:
            # Fallback: use davidson if available
            if "davidson_home" in df.columns:
                df["ensemble_home"] = 0.7 * df["davidson_home"] + 0.3 * df["p_player_home"]
                df["ensemble_draw"] = 0.7 * (1 - df["davidson_home"] - df["dixon_home"]) + 0.3 * df["p_player_draw"]
                df["ensemble_away"] = 0.7 * df["dixon_home"] + 0.3 * df["p_player_away"]
            else:
                df["ensemble_home"] = df["p_player_home"]
                df["ensemble_draw"] = df["p_player_draw"]
                df["ensemble_away"] = df["p_player_away"]
    else:
        df["ensemble_home"] = df["p_player_home"]
        df["ensemble_draw"] = df["p_player_draw"]
        df["ensemble_away"] = df["p_player_away"]
    
    # Normalize to sum to 1
    total = df["ensemble_home"] + df["ensemble_draw"] + df["ensemble_away"]
    df["ensemble_home"] /= total
    df["ensemble_draw"] /= total
    df["ensemble_away"] /= total
    
    # Output
    out_df = df[["match_id", "home_team", "away_team", 
                 "ensemble_home", "ensemble_draw", "ensemble_away",
                 "diff_squad_overall", "diff_top3_att", "diff_squad_caps"]]
    
    out_path = OUT / "wc2026_player_probs.csv"
    out_df.to_csv(out_path, index=False)
    log.info(f"Saved {out_path}: {len(out_df)} rows")
    
    # Top 5 biggest player advantages
    top5 = out_df.sort_values("ensemble_home", ascending=False).head(5)
    log.info("Top 5 home advantage by player strength:")
    for _, r in top5.iterrows():
        log.info(f"  {r['home_team']} vs {r['away_team']}: "
                 f"H={r['ensemble_home']:.3f} D={r['ensemble_draw']:.3f} A={r['ensemble_away']:.3f}")
    
    # Ledger
    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"PLR-MODEL,2026-06-13,p2_player_model,player_ensemble,"
                f"squad_overall+top3_att+caps+heuristic_blend,{len(out_df)},,,,,,"
                f"KEEP,top5={','.join(top5['home_team'].head(3).tolist())}\n")


if __name__ == "__main__":
    main()
