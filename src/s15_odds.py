"""
Stage 15 - Historical betting odds (free Kaggle source, partial).

No free feed of *international* closing odds exists, so we ingest the
'beat-the-bookie-worldwide-football-dataset' (worldwide 1X2 closing odds) as a
starting odds bank, plus any odds columns shipped in club-match datasets.
This is a PARTIAL fill for objective #1 - WC/international coverage stays thin
until OddsPortal (Playwright) is wired. Output -> raw/odds/ + DB table odds_bank
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

from common import RAW, DB_PATH, get_logger, log_attempt, save_df

log = get_logger("s15_odds")
# Kaggle auth from env var or ~/.kaggle/access_token (never hard-code secrets).
if not os.environ.get("KAGGLE_API_TOKEN"):
    _tok = os.path.expanduser("~/.kaggle/access_token")
    if os.path.exists(_tok):
        with open(_tok, encoding="utf-8") as _f:
            os.environ["KAGGLE_API_TOKEN"] = _f.read().strip()
OUT = RAW / "odds"
DATASETS = ["austro/beat-the-bookie-worldwide-football-dataset"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi(); api.authenticate()

    frames = []
    for ref in DATASETS:
        dest = OUT / ref.split("/")[-1]
        dest.mkdir(parents=True, exist_ok=True)
        try:
            if not any(dest.iterdir()):
                api.dataset_download_files(ref, path=str(dest), unzip=True, quiet=True)
            # only the closing-odds + match-mapping files; skip giant intra-match series
            wanted = list(dest.glob("closing_odds*.csv*")) + list(dest.glob("*matches*.csv*"))
            log.info(f"{ref}: loading {[c.name for c in wanted]}")
            for c in wanted:
                try:
                    comp = "gzip" if c.name.endswith(".gz") else None
                    df = pd.read_csv(c, low_memory=False, compression=comp)
                    frames.append((c.name, df))
                except Exception as e:
                    log.warning(f"read {c.name}: {e}")
            log_attempt("odds", ref, "ok", sum(len(f) for _, f in frames))
        except Exception as e:
            log.warning(f"{ref} failed: {str(e).splitlines()[0]}")
            log_attempt("odds", ref, "fail", 0, str(e)[:150])

    if not frames:
        log.warning("no odds data obtained")
        return

    # surface the largest table as the odds bank
    name, big = max(frames, key=lambda kv: len(kv[1]))
    save_df(big, OUT / "odds_bank_raw.csv")
    con = sqlite3.connect(DB_PATH)
    big.to_sql("odds_bank", con, if_exists="replace", index=False)
    con.commit(); con.close()
    log.info(f"odds_bank: {len(big)} rows from {name}; cols={list(big.columns)[:12]}")


if __name__ == "__main__":
    sys.exit(main())
