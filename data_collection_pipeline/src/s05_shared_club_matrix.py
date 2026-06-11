"""
Stage 05 — Build Shared Club Teammates Matrix from official_squads_2026.
For each national team, compute how many XI pairs play at the same club.
Also outputs a pairwise CSV for all 48 qualified teams.
"""
import sys
from pathlib import Path
import pandas as pd
import itertools

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, save_csv, PROCESSED_DIR,
    should_run, save_checkpoint,
)


def build_shared_club_matrix():
    if not should_run("s05_shared_club_matrix"):
        logger.info("[s05] Already done. Skipping.")
        return

    logger.info("[s05] Building shared-club teammate matrix...")
    conn = db_conn()
    df = pd.read_sql_query("SELECT team, player, club FROM official_squads_2026", conn)
    conn.close()

    if df.empty:
        logger.error("[s05] official_squads_2026 empty.")
        return

    # Normalize club names (basic strip + lower)
    df["club_norm"] = df["club"].astype(str).str.strip().str.lower()

    records = []
    for team in sorted(df["team"].unique()):
        squad = df[df["team"] == team]
        clubs = squad["club_norm"].value_counts()
        # For each club with >=2 players, count pairs = nC2
        shared_pairs = 0
        max_clique_size = 1
        for club, count in clubs.items():
            if count >= 2:
                shared_pairs += (count * (count - 1)) // 2
                if count > max_clique_size:
                    max_clique_size = count
        # % of possible pairs that are shared
        n = len(squad)
        total_possible_pairs = (n * (n - 1)) // 2 if n > 1 else 1
        shared_ratio = shared_pairs / total_possible_pairs

        records.append({
            "team": team,
            "squad_size": n,
            "shared_club_pairs": shared_pairs,
            "max_players_from_same_club": max_clique_size,
            "shared_pair_ratio": round(shared_ratio, 3),
        })

    agg = pd.DataFrame(records)
    out = PROCESSED_DIR / "shared_club_matrix.csv"
    save_csv(agg, out)
    save_checkpoint("s05_shared_club_matrix", meta={"teams": len(agg)})
    logger.info(f"[s05] Done. {len(agg)} team shared-club records.")

    # Also build pairwise team-vs-team shared-club overlap for H2H chemistry
    # (For national teams A and B, how many clubs appear in both squads?)
    logger.info("[s05] Building cross-team club overlap...")
    teams = sorted(df["team"].unique())
    overlap_rows = []
    for t_a, t_b in itertools.combinations(teams, 2):
        clubs_a = set(df[df["team"] == t_a]["club_norm"].unique())
        clubs_b = set(df[df["team"] == t_b]["club_norm"].unique())
        shared_clubs = clubs_a & clubs_b
        # Count total players from shared clubs in each squad
        players_a_shared = len(df[(df["team"] == t_a) & (df["club_norm"].isin(shared_clubs))])
        players_b_shared = len(df[(df["team"] == t_b) & (df["club_norm"].isin(shared_clubs))])
        overlap_rows.append({
            "team_a": t_a,
            "team_b": t_b,
            "shared_clubs": len(shared_clubs),
            "players_a_from_shared_clubs": players_a_shared,
            "players_b_from_shared_clubs": players_b_shared,
        })
    overlap = pd.DataFrame(overlap_rows)
    out2 = PROCESSED_DIR / "cross_team_club_overlap.csv"
    save_csv(overlap, out2)
    logger.info(f"[s05] Cross-team overlap done: {len(overlap)} pairs.")


if __name__ == "__main__":
    build_shared_club_matrix()
