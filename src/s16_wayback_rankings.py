"""
s16 - FIFA rankings 2024-07 -> 2026 via the Wayback Machine.   (gap D-RANK)

fifa.com is Akamai-blocked from this host, but web.archive.org archived the
ranking JSON API (inside.fifa.com/api/ranking-overview) many times, including
monthly captures of the *current* table. Each payload carries the full 211-team
list + its own lastUpdateDate, so we harvest every capture in the window,
dedupe by release date, and:
  1. append new releases to the DB `fifa_rankings` table (proper as-of history)
  2. overwrite data_collection_pipeline .../fifa_rankings_updated.csv with the
     LATEST release (f1_build_features reads that file for the rank override)
Checkpointed via logs; idempotent (dedupe on date+team).
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime

import pandas as pd
import requests

from common import DB_PATH, ROOT, get_logger

log = get_logger("s16_wayback")
P2_CSV = (ROOT / "data_collection_pipeline" / "collected_data" / "processed"
          / "fifa_rankings_updated.csv")
CDX = "http://web.archive.org/cdx/search/cdx"
H = {"User-Agent": "Mozilla/5.0 (wc2026-research; rankings-backfill)"}
WINDOW_FROM = "20240701"


def cdx_captures() -> list[tuple[str, str]]:
    """(timestamp, original_url) for ranking-overview captures since 2024-07."""
    out = []
    for pattern, collapse in [
        ("inside.fifa.com/api/ranking-overview", "timestamp:6"),     # monthly currents
        ("inside.fifa.com/api/ranking-overview?*", "urlkey"),        # dateId variants
    ]:
        try:
            r = requests.get(CDX, params={
                "url": pattern, "from": WINDOW_FROM, "to": "20260612",
                "output": "json", "filter": "statuscode:200", "collapse": collapse,
                "limit": 200}, headers=H, timeout=60)
            rows = r.json()
            out += [(row[1], row[2]) for row in rows[1:]]
        except Exception as e:
            log.warning(f"cdx fail {pattern}: {str(e)[:100]}")
    # dedupe
    seen, res = set(), []
    for ts, u in out:
        if (ts, u) not in seen:
            seen.add((ts, u))
            res.append((ts, u))
    log.info(f"CDX captures to fetch: {len(res)}")
    return res


def parse_payload(j: dict) -> tuple[str | None, list[dict]]:
    rk = j.get("rankings") or []
    rows, rel_date = [], None
    for item in rk:
        ri = item.get("rankingItem", {})
        if rel_date is None:
            lu = item.get("lastUpdateDate")
            if lu:
                # epoch-ms or ISO
                try:
                    rel_date = (datetime.utcfromtimestamp(int(lu) / 1000).strftime("%Y-%m-%d")
                                if str(lu).isdigit() else str(lu)[:10])
                except Exception:
                    rel_date = str(lu)[:10]
        rows.append({"team": ri.get("name"), "ranking": ri.get("rank"),
                     "points": ri.get("totalPoints"),
                     "country_code": (ri.get("flag") or {}).get("src", "")[-3:],
                     "previous_rank": ri.get("previousRank")})
    return rel_date, rows


CACHE = ROOT / "fifa_wc_data" / "raw" / "fifa_rankings" / "wayback_releases.json"


def main():
    # resume from disk cache if a previous harvest already ran
    releases: dict[str, list[dict]] = {}
    if CACHE.exists():
        try:
            releases = json.loads(CACHE.read_text(encoding="utf-8"))
            log.info(f"cache: {len(releases)} releases already on disk")
        except Exception:
            releases = {}

    if not releases:
        captures = cdx_captures()
        # bare-endpoint monthly snapshots first (each = then-current full table)
        captures.sort(key=lambda c: ("?" in c[1], c[0]))
        sess = requests.Session()
        sess.headers.update(H)
        sess.headers["Connection"] = "close"      # wayback resets kept-alive bursts
        for ts, url in captures:
            wb = f"http://web.archive.org/web/{ts}/{url}"
            for attempt in range(3):
                try:
                    r = sess.get(wb, timeout=90)
                    if r.status_code != 200:
                        break
                    rel_date, rows = parse_payload(r.json())
                    if rel_date and len(rows) >= 150 and rel_date >= "2024-05-01" \
                            and rel_date not in releases:
                        releases[rel_date] = rows
                        log.info(f"  harvested release {rel_date}: {len(rows)} teams "
                                 f"(top: {rows[0]['team']})")
                        CACHE.parent.mkdir(parents=True, exist_ok=True)
                        CACHE.write_text(json.dumps(releases), encoding="utf-8")
                    break
                except Exception as e:
                    wait = 6 * (attempt + 1)
                    log.warning(f"  fetch fail {ts} (try {attempt+1}): {str(e)[:60]} "
                                f"-> sleep {wait}s")
                    time.sleep(wait)
            time.sleep(4.0)                        # polite pacing for wayback

    if not releases:
        log.error("no new releases harvested")
        return

    # ---- 1. append to DB fifa_rankings ----
    con = sqlite3.connect(DB_PATH)
    existing_dates = {r[0] for r in con.execute("SELECT DISTINCT date FROM fifa_rankings")}
    new_rows = []
    for d, rows in sorted(releases.items()):
        if d in existing_dates:
            continue
        for r in rows:
            if r.get("team") is None or r.get("ranking") is None:
                continue                            # malformed payload items
            new_rows.append({"date": d, "team": r["team"],
                             "ranking": float(r["ranking"]),
                             "points": float(r.get("points") or 0)})
    if new_rows:
        pd.DataFrame(new_rows).to_sql("fifa_rankings", con, if_exists="append", index=False)
        con.commit()
    n_after = con.execute("SELECT COUNT(*), MAX(date) FROM fifa_rankings").fetchone()
    con.close()
    log.info(f"DB fifa_rankings: +{len(new_rows)} rows -> {n_after[0]} total, "
             f"latest release {n_after[1]}")

    # ---- 2. refresh the f1 override file with the LATEST release ----
    # (s16b_validate_rankings re-writes this after scrubbing women's / foreign-
    #  locale releases; this is just a first pass so the file is never stale)
    latest = max(releases)
    rows = [r for r in releases[latest] if r.get("team") and r.get("ranking")]
    out = pd.DataFrame({
        "rank": [r["ranking"] for r in rows],
        "team": [r["team"] for r in rows],
        "country_code": [r.get("country_code") for r in rows],
        "points": [r.get("points") for r in rows],
        "previous_points": None, "confederation": None,
        "rank_date": latest, "source": "wayback:inside.fifa.com",
    })
    out.to_csv(P2_CSV, index=False, encoding="utf-8")
    log.info(f"override file refreshed -> release {latest} ({len(out)} teams); "
             f"releases harvested: {sorted(releases)}")


if __name__ == "__main__":
    main()
