"""
Stage 03 - FIFA world rankings (1992 -> present).

The full release-by-release ranking history is not on a single Wikipedia page,
so we use the maintained Kaggle dataset `cashncarry/fifaworldranking`
(date, rank, team, points for every official release) as the primary source,
and scrape the Wikipedia "FIFA World Rankings" leaders/top-table as a
supplementary cross-check. Output -> raw/fifa_rankings/fifa_rankings.csv
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from common import RAW, get_logger, log_attempt, save_df

log = get_logger("s03_fifa")
# Kaggle auth from env var or ~/.kaggle/access_token (never hard-code secrets).
if not os.environ.get("KAGGLE_API_TOKEN"):
    _tok = os.path.expanduser("~/.kaggle/access_token")
    if os.path.exists(_tok):
        with open(_tok, encoding="utf-8") as _f:
            os.environ["KAGGLE_API_TOKEN"] = _f.read().strip()

OUT = RAW / "fifa_rankings"


def from_kaggle() -> pd.DataFrame | None:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi(); api.authenticate()
        dest = OUT / "kaggle"
        dest.mkdir(parents=True, exist_ok=True)
        api.dataset_download_files("cashncarry/fifaworldranking", path=str(dest), unzip=True, quiet=True)
        csvs = list(dest.glob("*.csv"))
        if not csvs:
            return None
        df = pd.read_csv(max(csvs, key=lambda p: p.stat().st_size))
        # normalise common column names
        ren = {
            "rank_date": "date", "country_full": "team", "total_points": "points",
            "rank": "ranking",
        }
        df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
        keep = [c for c in ["date", "team", "ranking", "points"] if c in df.columns]
        df = df[keep].dropna(subset=["date", "team"])
        log_attempt("fifa_rankings", "kaggle:cashncarry/fifaworldranking", "ok", len(df))
        return df
    except Exception as e:
        log.warning(f"kaggle fifa ranking failed: {str(e).splitlines()[0]}")
        log_attempt("fifa_rankings", "kaggle:cashncarry/fifaworldranking", "fail", 0, str(e)[:200])
        return None


def from_wikipedia() -> pd.DataFrame | None:
    url = "https://en.wikipedia.org/wiki/FIFA_World_Rankings"
    try:
        tables = pd.read_html(url)
        # find a table that looks like a ranking (has Rank & Team & Points-ish cols)
        for t in tables:
            cols = [str(c).lower() for c in t.columns]
            if any("team" in c for c in cols) and any("point" in c for c in cols):
                log_attempt("fifa_rankings", url, "ok", len(t), "wikipedia leaders table")
                return t
        log_attempt("fifa_rankings", url, "empty", 0, "no ranking table found")
    except Exception as e:
        log.warning(f"wikipedia fifa ranking failed: {e}")
        log_attempt("fifa_rankings", url, "fail", 0, str(e)[:200])
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = from_kaggle()
    if df is not None and len(df):
        df = df.sort_values(["date", "ranking"] if "ranking" in df.columns else ["date"])
        save_df(df, OUT / "fifa_rankings.csv")
        log.info(f"fifa rankings: {len(df)} rows, {df['team'].nunique()} teams, "
                 f"{df['date'].min()}..{df['date'].max()}")
    else:
        log.warning("primary fifa ranking source empty")

    wiki = from_wikipedia()
    if wiki is not None:
        save_df(wiki, OUT / "fifa_rankings_wikipedia_current.csv")
    log.info("stage 03 (fifa rankings) complete")


if __name__ == "__main__":
    sys.exit(main())
