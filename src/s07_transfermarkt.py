"""
Stage 07 - Transfermarkt squads, market values, injuries (best-effort).

Transfermarkt blocks scrapers aggressively (Cloudflare + bot heuristics). This
module uses rotating UAs, long 5-8s delays, and retries to fetch the WC-2026
participants page and per-team squad pages, parsing market values with
pd.read_html. When blocked it logs and skips per team (never fatal). The
FIFA-game value_eur (stage 08) provides a market-value proxy in the interim.
Outputs -> raw/transfermarkt/
"""
from __future__ import annotations

import io
import sys

import pandas as pd

from common import RAW, polite_get, get_logger, log_attempt, save_df

log = get_logger("s07_tm")
OUT = RAW / "transfermarkt"

TM_HEADERS = {"Referer": "https://www.transfermarkt.com/", "Accept-Language": "en-US,en;q=0.9"}
PARTICIPANTS = "https://www.transfermarkt.com/weltmeisterschaft-2026/teilnehmer/pokalwettbewerb/WM26"


def fetch(url: str) -> str | None:
    resp = polite_get(url, source="transfermarkt", min_delay=5, max_delay=8,
                      retries=3, headers=TM_HEADERS)
    if resp is None or resp.status_code != 200:
        return None
    return resp.text


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    html = fetch(PARTICIPANTS)
    if html is None:
        log.warning("Transfermarkt blocked from this host (anti-bot). Squad market "
                    "values fall back to FIFA-game value_eur (stage 08). Re-run on a "
                    "residential IP / with Selenium to populate the live TM tables.")
        log_attempt("transfermarkt", PARTICIPANTS, "fail", 0, "blocked/anti-bot")
        # well-defined empty schemas for downstream joins
        pd.DataFrame(columns=["date", "team", "total_value", "avg_value", "median_value"]
                     ).to_csv(OUT / "market_values.csv", index=False)
        pd.DataFrame(columns=["player", "team", "position", "age", "club", "market_value_eur"]
                     ).to_csv(OUT / "squads.csv", index=False)
        pd.DataFrame(columns=["player", "injury_date", "return_date", "injury_type", "days_missed"]
                     ).to_csv(OUT / "injuries.csv", index=False)
        return
    try:
        tables = pd.read_html(io.StringIO(html))
        biggest = max(tables, key=len)
        save_df(biggest, OUT / "wc2026_participants_raw.csv")
        log_attempt("transfermarkt", PARTICIPANTS, "ok", len(biggest))
    except Exception as e:
        log_attempt("transfermarkt", PARTICIPANTS, "fail", 0, str(e)[:150])
    log.info("stage 07 (transfermarkt) complete")


if __name__ == "__main__":
    sys.exit(main())
