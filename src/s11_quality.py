"""
Stage 11 - Data-quality report.

Summarises the SQLite database: per-table row counts, column count, per-column
null %, and date range where a date column exists. Also rolls up the scrape
attempt ledger (success/fail/skip per source). Outputs:
  logs/data_quality_report.csv   (per-table x per-column null %)
  logs/table_summary.csv         (per-table rows / cols / date range)
  logs/source_summary.csv        (per-source attempt outcomes)
"""
from __future__ import annotations

import sqlite3
import sys

import pandas as pd

from common import DB_PATH, LOGS, get_logger

log = get_logger("s11_quality")


def main() -> None:
    if not DB_PATH.exists():
        log.error("no database; run stage 10 first")
        return
    con = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

    col_rows, tbl_rows = [], []
    for t in tables:
        df = pd.read_sql(f"SELECT * FROM '{t}'", con)
        n = len(df)
        date_col = next((c for c in df.columns if c.lower() in ("date", "rank_date")), None)
        dmin = dmax = None
        if date_col and n:
            d = pd.to_datetime(df[date_col], errors="coerce")
            dmin, dmax = (str(d.min().date()) if d.notna().any() else None,
                          str(d.max().date()) if d.notna().any() else None)
        tbl_rows.append({"table": t, "rows": n, "cols": df.shape[1],
                         "date_col": date_col, "date_min": dmin, "date_max": dmax})
        for c in df.columns:
            null_pct = round(df[c].isna().mean() * 100, 2) if n else 100.0
            col_rows.append({"table": t, "column": c, "null_pct": null_pct,
                             "n_unique": int(df[c].nunique(dropna=True)) if n else 0})
    con.close()

    tbl = pd.DataFrame(tbl_rows)
    col = pd.DataFrame(col_rows)
    tbl.to_csv(LOGS / "table_summary.csv", index=False)
    col.to_csv(LOGS / "data_quality_report.csv", index=False)

    # source attempt rollup
    att_path = LOGS / "scrape_attempts.csv"
    if att_path.exists():
        att = pd.read_csv(att_path)
        src = (att.groupby(["source", "status"]).size().unstack(fill_value=0))
        src["total_rows"] = att.groupby("source")["rows"].sum()
        src.to_csv(LOGS / "source_summary.csv")

    log.info("=" * 64)
    log.info("DATA QUALITY SUMMARY")
    log.info("=" * 64)
    for _, r in tbl.iterrows():
        rng = f" [{r['date_min']}..{r['date_max']}]" if r["date_min"] else ""
        log.info(f"  {r['table']:<26} {r['rows']:>8} rows x {r['cols']:>2} cols{rng}")
    empty = tbl[tbl["rows"] == 0]["table"].tolist()
    if empty:
        log.info(f"  empty tables (blocked/unavailable sources): {empty}")
    log.info("=" * 64)
    log.info(f"reports -> {LOGS/'table_summary.csv'} , {LOGS/'data_quality_report.csv'}")


if __name__ == "__main__":
    sys.exit(main())
