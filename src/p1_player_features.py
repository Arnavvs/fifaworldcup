"""
p1_player_features.py — Squad-strength feature store from player ratings.

TASK 2 id: PLR-FEAT

For each of the 48 WC2026 teams compute:
  gk_overall, def_overall, mid_overall, att_overall, squad_overall (n-weighted),
  top3_att_mean (mean overall of top 3 ATT players),
  squad_caps_total (sum of national-team appearances)

Outputs:
  research_ready_dataset/wc2026_team_strength.csv
  DB table team_strength_features
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from common import DB_PATH, ROOT, get_logger

log = get_logger("p1_features")
OUT = ROOT / "research_ready_dataset"


def load_sofa_strength():
    """Load sofascore_team_strength and pivot to team x pos_group."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM sofascore_team_strength", con)
    con.close()
    # Pivot: team -> pos_group columns
    piv = df.pivot(index="team", columns="pos_group", values="avg_overall")
    # Rename columns
    piv = piv.rename(columns={
        "GK": "gk_overall",
        "DEF": "def_overall",
        "MID": "mid_overall",
        "ATT": "att_overall",
    })
    # Compute squad_overall (n-weighted average)
    # Get n_players per position per team
    n_df = df.groupby(["team", "pos_group"])["n_players"].first().unstack()
    # Map renamed columns back to original pos_group names
    col_map = {"gk_overall": "GK", "def_overall": "DEF", "mid_overall": "MID", "att_overall": "ATT"}
    # Compute weighted average
    def weighted_squad(team_name):
        total_n = 0
        total_score = 0
        for col, pos in col_map.items():
            if col in piv.columns and pd.notna(piv.loc[team_name, col]):
                n = n_df.loc[team_name, pos] if (team_name in n_df.index and pos in n_df.columns) else 0
                if pd.notna(n) and n > 0:
                    total_n += n
                    total_score += piv.loc[team_name, col] * n
        return total_score / total_n if total_n > 0 else None
    piv["squad_overall"] = [weighted_squad(t) for t in piv.index]
    return piv


def load_top3_att():
    """Compute top 3 ATT players per team by tactical (overall)."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT team, name, tactical
        FROM sofascore_player_attributes
        WHERE pos_group='ATT' AND year_shift=0
        ORDER BY team, tactical DESC
    """, con)
    con.close()
    # Take top 3 per team
    top3 = df.groupby("team").head(3).groupby("team")["tactical"].mean()
    return top3.rename("top3_att_mean")


def load_caps_total():
    """Sum of national-team appearances per team."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT team, SUM(nt_appearances) as squad_caps_total
        FROM sofascore_player_career
        GROUP BY team
    """, con)
    con.close()
    return df.set_index("team")["squad_caps_total"]


def main():
    # Load features
    strength = load_sofa_strength()
    top3 = load_top3_att()
    caps = load_caps_total()

    # Combine
    combined = strength.join(top3, how="outer").join(caps, how="outer")
    combined = combined.reset_index()
    combined.columns = ["team"] + list(combined.columns[1:])

    # Map SofaScore names -> canonical
    tm = pd.read_csv(OUT / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    # Add SofaScore-specific aliases
    aliases = {
        "South Korea": "Korea Republic",
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "USA": "USA",
        "Türkiye": "Türkiye",
        "Côte d'Ivoire": "Côte d'Ivoire",
        "Cabo Verde": "Cabo Verde",
        "DR Congo": "Congo DR",
        "Iran": "IR Iran",
    }
    aliases.update(canon)
    combined["canonical"] = combined["team"].map(lambda t: aliases.get(t, t))

    # Handle duplicates (some teams might map to same canonical)
    combined = combined.groupby("canonical").mean(numeric_only=True).reset_index()
    combined = combined.rename(columns={"canonical": "team"})

    # Check for NaNs in key columns
    key_cols = ["gk_overall", "def_overall", "mid_overall", "att_overall", "squad_overall"]
    nans = combined[key_cols].isna().sum().sum()
    if nans > 0:
        log.warning(f"{nans} NaN values in key columns; filling with median")
        for col in key_cols:
            combined[col] = combined[col].fillna(combined[col].median())

    # Reorder columns
    cols = ["team"] + key_cols + ["top3_att_mean", "squad_caps_total"]
    combined = combined[[c for c in cols if c in combined.columns]]

    # Save CSV
    csv_path = OUT / "wc2026_team_strength.csv"
    combined.to_csv(csv_path, index=False)
    log.info(f"Saved {csv_path}: {len(combined)} rows, {len(combined.columns)} cols")

    # Save to DB
    con = sqlite3.connect(DB_PATH)
    combined.to_sql("team_strength_features", con, if_exists="replace", index=False)
    con.close()
    log.info("Saved to DB table team_strength_features")

    # Top 10 by squad_overall
    top10 = combined.sort_values("squad_overall", ascending=False).head(10)
    log.info("Top 10 by squad_overall:")
    for _, r in top10.iterrows():
        log.info(f"  {r['team']:<15} squad={r['squad_overall']:.1f} "
                 f"gk={r['gk_overall']:.1f} def={r['def_overall']:.1f} "
                 f"mid={r['mid_overall']:.1f} att={r['att_overall']:.1f} "
                 f"top3_att={r['top3_att_mean']:.1f} caps={int(r['squad_caps_total'])}")

    # Ledger
    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"PLR-FEAT,2026-06-13,p1_player_features,team_strength,"
                f"sofascore_team_strength+player_career,{len(combined)},,,,,,"
                f"KEEP,top10={','.join(top10['team'].head(3).tolist())}\n")


if __name__ == "__main__":
    main()
