"""
Data Collection Pipeline Orchestrator
Run all (or selected) collection stages in order with checkpointing.
Usage:
  python run_collection.py           # run all missing stages
  python run_collection.py 1 2 3     # run only stages 1,2,3
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from common import logger, load_checkpoints, save_checkpoint, PIPELINE_ROOT

STAGES = {
    1: ("s01_fifa_rankings", "src.s01_fifa_rankings", "update_fifa_rankings"),
    2: ("s02_weather", "src.s02_weather", "fetch_weather"),
    3: ("s03_travel_timezone", "src.s03_travel_timezone", "compute_travel_features"),
    4: ("s04_squad_aggregates", "src.s04_squad_aggregates", "compute_squad_aggregates"),
    5: ("s05_shared_club_matrix", "src.s05_shared_club_matrix", "build_shared_club_matrix"),
    6: ("s06_manager_tenure", "src.s06_manager_tenure", "collect_managers"),
    7: ("s07_qualification_strength", "src.s07_qualification_strength", "scrape_qualification_summary"),
    8: ("s08_continental_form", "src.s08_continental_form", "collect_continental_form"),
    9: ("s09_odds_scraper", "src.s09_odds_scraper", "collect_odds"),
    10: ("s10_understat_xg", "src.s10_understat_xg", "collect_understat"),
    11: ("s11_live_pipeline", "src.s11_live_pipeline", "main"),
}


def run_stage(num: int):
    name, module_path, func_name = STAGES[num]
    logger.info(f"\n{'='*50}\n>>> STAGE {num}: {name}\n{'='*50}")
    try:
        mod = __import__(module_path, fromlist=[func_name])
        getattr(mod, func_name)()
    except Exception as e:
        logger.exception(f"Stage {num} ({name}) FAILED: {e}")
        save_checkpoint(name, status="failed", meta={"error": str(e)})


def main():
    parser = argparse.ArgumentParser(description="WC 2026 Data Collection Pipeline")
    parser.add_argument(
        "stages",
        nargs="*",
        type=int,
        help="Stage numbers to run (default: all missing)",
    )
    args = parser.parse_args()

    if args.stages:
        to_run = [n for n in args.stages if n in STAGES]
    else:
        cp = load_checkpoints()
        to_run = [n for n, (name, _, _) in STAGES.items() if cp.get(name, {}).get("status") != "done"]

    if not to_run:
        logger.info("All stages are already complete (or none requested).")
        return

    logger.info(f"Pipeline root: {PIPELINE_ROOT}")
    logger.info(f"Will run stages: {to_run}")

    for num in to_run:
        run_stage(num)

    logger.info("\n>>> Pipeline run complete. Check checkpoints.json for status.")


if __name__ == "__main__":
    main()
