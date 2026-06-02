"""
Stage 08 - Player-attribute layer + WC-2026 squad linkage.

FBref/Transfermarkt are Cloudflare-blocked from this host, so the FIFA-game
player datasets (ratings 15-23) serve as the player-attribute proxy the brief
explicitly allows. We build:
  - players master (player_id, name, nationality, position, dob, club, attrs)
  - wc2026_player_pool: every FIFA-rated player whose nationality is a WC-2026
    qualified team  -> "the teams announced and their players"
  - market_values: per-team total / avg / median value_eur (TM proxy)
Outputs -> processed/players.csv, processed/wc2026_player_pool.csv,
           processed/market_values.csv
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from common import RAW, PROCESSED, get_logger, log_attempt, save_df

log = get_logger("s08_players")
KAGGLE = RAW / "kaggle"

# FIFA nationality_name -> WC2026 team label (align the two naming schemes)
NAT_ALIASES = {
    "Korea Republic": "Korea Republic", "South Korea": "Korea Republic",
    "United States": "USA", "USA": "USA",
    "Iran": "IR Iran", "IR Iran": "IR Iran",
    "Ivory Coast": "Côte d'Ivoire", "Côte d'Ivoire": "Côte d'Ivoire",
    "Czech Republic": "Czechia", "Czechia": "Czechia",
    "Turkey": "Türkiye", "Türkiye": "Türkiye",
    "Cape Verde Islands": "Cabo Verde", "Cabo Verde": "Cabo Verde",
    "DR Congo": "Congo DR", "Congo DR": "Congo DR",
    "Curacao": "Curaçao", "Curaçao": "Curaçao",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
}

ATTR_COLS = ["overall", "potential", "value_eur", "wage_eur", "age", "height_cm",
             "weight_kg", "international_reputation", "pace", "shooting", "passing",
             "dribbling", "defending", "physic"]


USECOLS = (["player_id", "short_name", "long_name", "player_positions",
            "nationality_name", "dob", "club_name", "fifa_version", "fifa_update"]
           + ATTR_COLS)


def load_latest_fifa() -> pd.DataFrame:
    """
    FIFA 23 male_players.csv is ~5.6 GB (every edition x every update snapshot).
    Read only the needed columns in chunks, keep the most recent fifa_version,
    then its latest fifa_update -> one current row per player.
    """
    p = KAGGLE / "fifa-23-complete-player-dataset" / "male_players.csv"
    if not p.exists():
        df = pd.read_csv(KAGGLE / "fifa-22-complete-player-dataset" / "players_22.csv",
                         low_memory=False)
        df["fifa_edition"] = "FIFA22"
        return df

    header = pd.read_csv(p, nrows=0).columns
    cols = [c for c in USECOLS if c in header]
    parts, max_ver = [], None
    for chunk in pd.read_csv(p, usecols=cols, chunksize=200_000, low_memory=False):
        v = chunk["fifa_version"].max()
        max_ver = v if max_ver is None else max(max_ver, v)
        parts.append(chunk[chunk["fifa_version"] == v])
    df = pd.concat(parts, ignore_index=True)
    df = df[df["fifa_version"] == max_ver]
    if "fifa_update" in df.columns:
        df = df[df["fifa_update"] == df["fifa_update"].max()]
    df = df.drop_duplicates(subset=["player_id"], keep="first").reset_index(drop=True)
    df["fifa_edition"] = f"FIFA{int(max_ver)}"
    log.info(f"loaded {len(df)} current players (FIFA v{int(max_ver)}) from {p.name}")
    log_attempt("players", str(p), "ok", len(df), "fifa ratings master (latest snapshot)")
    return df


def normalise_nat(s: str) -> str:
    return NAT_ALIASES.get(str(s).strip(), str(s).strip())


def main() -> None:
    df = load_latest_fifa()

    # ---- players master ----
    if "player_id" not in df.columns:
        df["player_id"] = np.arange(1, len(df) + 1)
    keep = ["player_id", "short_name", "long_name", "player_positions",
            "nationality_name", "dob", "club_name"] + ATTR_COLS
    keep = [c for c in keep if c in df.columns]
    players = df[keep].copy()
    players = players.rename(columns={
        "short_name": "name", "player_positions": "position",
        "nationality_name": "nationality", "club_name": "primary_club",
    })
    players["nationality_norm"] = players["nationality"].map(normalise_nat)
    save_df(players, PROCESSED / "players.csv")

    # ---- WC2026 player pool ----
    qpath = RAW / "worldcup" / "wc2026_qualified_teams.csv"
    if qpath.exists():
        q = pd.read_csv(qpath)
        teams = [t for t in q["team"].dropna().astype(str)
                 if t.lower() != "to be announced"]
        pool = players[players["nationality_norm"].isin(teams)].copy()
        pool = pool.merge(q[["team", "group"]], left_on="nationality_norm",
                          right_on="team", how="left").drop(columns=["team"])
        pool = pool.sort_values(["nationality_norm", "overall"],
                                ascending=[True, False])
        save_df(pool, PROCESSED / "wc2026_player_pool.csv")
        covered = sorted(pool["nationality_norm"].unique())
        missing = sorted(set(teams) - set(covered))
        log.info(f"WC2026 pool: {len(pool)} players across {len(covered)}/{len(teams)} teams")
        if missing:
            log.warning(f"no FIFA-rated players matched for: {missing}")

        # ---- market values per team (TM proxy via value_eur) ----
        if "value_eur" in pool.columns:
            mv = (pool.groupby("nationality_norm")["value_eur"]
                  .agg(total_value="sum", avg_value="mean", median_value="median",
                       n_players="count").reset_index()
                  .rename(columns={"nationality_norm": "team"}))
            mv["date"] = "2022-09-01"  # FIFA23 data snapshot
            mv = mv[["date", "team", "total_value", "avg_value", "median_value", "n_players"]]
            mv = mv.sort_values("total_value", ascending=False)
            save_df(mv, PROCESSED / "market_values.csv")
            log.info("top squads by FIFA value:\n" +
                     mv.head(5).to_string(index=False))
    else:
        log.warning("no WC2026 qualified-teams file; skipping pool/market values")

    log.info("stage 08 (players) complete")


if __name__ == "__main__":
    sys.exit(main())
