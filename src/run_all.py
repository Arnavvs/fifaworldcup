"""
Orchestrator - run the full FIFA WC 2026 dataset pipeline end to end.

Stages are independent and resumable (Kaggle/ELO/FBref checkpoint internally).
A failing stage is logged and the pipeline continues to the next one, so a
blocked scraper (FBref/Transfermarkt) never stops the build.

Usage:
    python run_all.py                # run every stage
    python run_all.py 8 9 10 11      # run only the listed stage numbers
    FBREF_SELENIUM=1 python run_all.py 6   # FBref via Selenium (if Chrome present)
"""
from __future__ import annotations

import importlib
import sys
import time

from common import get_logger

log = get_logger("run_all")

STAGES = [
    ("01", "s01_kaggle", "Kaggle datasets"),
    ("02", "s02_elo", "ELO ratings"),
    ("03", "s03_fifa_rankings", "FIFA rankings"),
    ("04", "s04_worldcup", "World Cup data + 2026 fixtures"),
    ("05", "s05_football_data", "football-data odds"),
    ("06", "s06_fbref", "FBref team/player stats"),
    ("07", "s07_transfermarkt", "Transfermarkt squads/values"),
    ("08", "s08_players", "Player attributes + WC2026 pool"),
    ("09", "s09_features", "Derived contextual features"),
    ("12", "s12_venues", "Venue geocoding + altitude"),
    ("10", "s10_build_db", "Build SQLite DB"),
    ("11", "s11_quality", "Data quality report"),
]


def main(argv: list[str]) -> int:
    want = set(argv)
    t0 = time.time()
    for num, mod_name, desc in STAGES:
        if want and num not in want:
            continue
        log.info(f"\n{'='*70}\nSTAGE {num}: {desc}\n{'='*70}")
        try:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            mod.main()
        except Exception as e:
            log.error(f"STAGE {num} ({mod_name}) crashed: {e!r} -- continuing")
    log.info(f"\nPIPELINE DONE in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
