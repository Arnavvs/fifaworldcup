"""
Stage 11 — WC 2026 Live Pipeline Stub
This module is a placeholder / scaffolding for when the tournament starts.
It will need:
  - Live lineup feeds (API-Football free tier / WhoScored / official FIFA)
  - Live odds feeds (Pinnacle / Betfair Exchange if API access is available)
  - Live weather updates (Open-Meteo forecast refresh)
  - Injury / availability alerts (Transfermarkt / Twitter/X RSS / news APIs)

Design decisions for live mode:
  1. Run on a schedule (cron every 15 minutes during tournament days).
  2. Fetch only changed data (lineups, weather, latest odds).
  3. Recompute features incrementally and write to Redis / SQLite.
  4. Trigger model inference if lineups change or odds move materially.

No implementation yet — this is the architecture contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import logger, save_checkpoint

LIVE_SOURCES = {
    "lineups": {
        "description": "Official FIFA starting XIs (usually released ~60 min pre-kickoff)",
        "free_options": [
            "API-Football free tier (100 requests/day)",
            "WhoScored lineup pages (scrape with Playwright)",
            "FIFA.com match centre (unofficial scrape)",
        ],
        "notes": "Must handle uncertainty before official release (projected XI model).",
    },
    "odds": {
        "description": "Real-time 1X2, Asian Handicap, O/U from sharp books",
        "free_options": [
            "Pinnacle API (needs active account, free REST polling)",
            "Betfair Exchange API (free, needs account)",
            "OddsChecker / OddsPortal (scrape, anti-bot)",
        ],
        "notes": "Shin overround removal must run on every poll.",
    },
    "weather": {
        "description": "Kickoff-time weather refresh",
        "free_options": [
            "Open-Meteo forecast API (free, no key)",
        ],
        "notes": "Only meaningful if forecast changed materially (rain added, heat spike).",
    },
    "injuries": {
        "description": "Late withdrawals / fitness doubts",
        "free_options": [
            "Transfermarkt news (Playwright scrape)",
            "Twitter/X sports journalist feeds (RSS / Nitter)",
            "FIFA medical bulletins (official site)",
        ],
        "notes": "Highest-value last-minute signal. Manual curation may be required.",
    },
    "match_events": {
        "description": "In-play events (goals, cards, subs, xG) for live trading",
        "free_options": [
            "StatsBomb open-data API (free for some competitions, not live WC)",
            "Sofascore / FotMob unofficial APIs ( brittle )",
        ],
        "notes": "Premium required for reliable sub-second event feeds (Opta / StatsBomb 360).",
    },
}


def print_live_architecture():
    logger.info("=" * 60)
    logger.info("WC 2026 LIVE PIPELINE — ARCHITECTURE CONTRACT")
    logger.info("=" * 60)
    for name, info in LIVE_SOURCES.items():
        logger.info(f"\n[{name.upper()}]")
        logger.info(f"  Purpose: {info['description']}")
        logger.info(f"  Free sources:")
        for opt in info['free_options']:
            logger.info(f"    - {opt}")
        logger.info(f"  Notes: {info['notes']}")
    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDED IMPLEMENTATION ORDER:")
    logger.info("  1. Weather refresh (Open-Meteo) — easiest, runs every 6 hours.")
    logger.info("  2. Lineup scraper (Playwright on WhoScored / FIFA) — runs every 15 min on matchdays.")
    logger.info("  3. Odds poller (Pinnacle REST API if account available) — runs every 5 min.")
    logger.info("  4. Injury news aggregator (RSS + manual curation) — runs every 30 min.")
    logger.info("  5. In-play event bridge (if premium data is acquired later).")
    logger.info("=" * 60)


def main():
    # Nothing to run yet; just document the plan
    print_live_architecture()
    save_checkpoint("s11_live_pipeline", status="stub", meta={"live_sources": list(LIVE_SOURCES.keys())})


if __name__ == "__main__":
    main()
