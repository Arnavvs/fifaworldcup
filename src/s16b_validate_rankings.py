"""
s16b - Validate + scrub the Wayback-harvested FIFA ranking releases.

Drops releases that are (a) the women's ranking (USA-topped 204-team captures)
or (b) non-English locale captures ("Argentinien"), then rewrites the
f1 override CSV with the newest VALID men's release.
Checks per release date >= 2024-05-01:
  - top-1 team in a plausible men's set
  - >= 60% of names resolve through team_mapping (English canonical check)
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from common import DB_PATH, ROOT, get_logger

log = get_logger("s16b_validate")
P2_CSV = (ROOT / "data_collection_pipeline" / "collected_data" / "processed"
          / "fifa_rankings_updated.csv")
PLAUSIBLE_TOP = {"Argentina", "France", "Spain", "England", "Brazil", "Germany",
                 "Belgium", "Netherlands", "Portugal", "Italy"}


def main():
    tm = pd.read_csv(ROOT / "research_ready_dataset" / "team_mapping.csv")
    known = set(tm["raw_name"]) | set(tm["canonical_name"])

    con = sqlite3.connect(DB_PATH)
    new = pd.read_sql("SELECT date, team, ranking, points FROM fifa_rankings "
                      "WHERE date >= '2024-05-01'", con)
    kept, dropped = [], []
    for d, grp in new.groupby("date"):
        top1 = grp.sort_values("ranking").iloc[0]["team"]
        overlap = grp["team"].isin(known).mean()
        ok = (top1 in PLAUSIBLE_TOP) and overlap >= 0.6 and len(grp) >= 180
        (kept if ok else dropped).append((d, top1, len(grp), round(overlap, 2)))
        if not ok:
            con.execute("DELETE FROM fifa_rankings WHERE date = ?", (d,))
    con.commit()
    log.info(f"kept releases: {[k[0] for k in kept]}")
    if dropped:
        log.info(f"DROPPED (women's/foreign-locale/partial): {dropped}")

    if kept:
        latest = max(k[0] for k in kept)
        lat = pd.read_sql("SELECT team, ranking, points FROM fifa_rankings WHERE date=?",
                          con, params=(latest,))
        out = pd.DataFrame({
            "rank": lat["ranking"], "team": lat["team"], "country_code": None,
            "points": lat["points"], "previous_points": None, "confederation": None,
            "rank_date": latest, "source": "wayback:inside.fifa.com (validated)"})
        out.to_csv(P2_CSV, index=False, encoding="utf-8")
        log.info(f"override CSV -> validated release {latest} ({len(out)} teams); "
                 f"top-5: {lat.sort_values('ranking').head(5)['team'].tolist()}")
    n = con.execute("SELECT COUNT(*), MAX(date) FROM fifa_rankings").fetchone()
    con.close()
    log.info(f"fifa_rankings now {n[0]} rows, latest {n[1]}")


if __name__ == "__main__":
    main()
