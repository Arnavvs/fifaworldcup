"""
f2 / T0.2-lite - Market benchmark from real closing odds (228 intl matches:
WC2018/2022, Euro 2020/2024, Copa 2021). Computes the bookmaker log-loss --
the honest ceiling reference -- and stores table `odds_implied_recent`.
(Full odds_bank 2005-15 join is the remaining T0.2 work -> see TODO_FOR_OPUS.)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT, get_logger

log = get_logger("f2_market")
OUT = ROOT / "research_ready_dataset"
SRC = ROOT / "data_collection_pipeline" / "collected_data" / "raw" / "odds_international.csv"


def main():
    o = pd.read_csv(SRC)
    o["date"] = pd.to_datetime(o["date"], format="%d %b %Y", errors="coerce")
    o = o.dropna(subset=["date", "imp_h", "imp_d", "imp_a", "home_score", "away_score"])
    # normalise implied probs (devig safety)
    s = o[["imp_h", "imp_d", "imp_a"]].sum(axis=1)
    for c in ("imp_h", "imp_d", "imp_a"):
        o[c] = o[c] / s
    gd = o["home_score"] - o["away_score"]
    y = np.select([gd < 0, gd == 0], [0, 1], default=2)   # loss/draw/win
    p = o[["imp_a", "imp_d", "imp_h"]].values              # ordered [loss,draw,win]
    p = np.clip(p, 1e-12, 1)
    ll = float(-np.mean(np.log(p[np.arange(len(y)), y])))
    log.info(f"MARKET BENCHMARK: closing-odds log-loss {ll:.4f} on {len(o)} matches "
             f"({o['tournament'].nunique()} tournaments, {o['date'].min():%Y-%m}..{o['date'].max():%Y-%m})")

    con = sqlite3.connect(DB_PATH)
    o.to_sql("odds_implied_recent", con, if_exists="replace", index=False)
    con.commit(); con.close()

    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"market_closing,{datetime.utcnow():%Y-%m-%d},f2_market_benchmark,"
                f"bookmaker_closing,228 intl matches WC18/22 Euro20/24 Copa21,,"
                f"{ll:.4f},,,,,n/a,BENCHMARK,the honest ceiling on big tournaments\n")
    log.info("f2 complete; table odds_implied_recent written")


if __name__ == "__main__":
    main()
