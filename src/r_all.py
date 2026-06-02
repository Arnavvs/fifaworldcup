"""
Orchestrator for the research-grade feature-store pipeline (Phases 1-8).
Each phase is idempotent; run `python r_all.py` to rebuild everything.
"""
import importlib, sys
from common import get_logger

log = get_logger("r_all")
PHASES = [
    ("1", "r1_audit", "Data audit -> audit_report.md"),
    ("2", "r2_dim_team", "Team normalization -> dim_team, team_mapping.csv"),
    ("3+5", "r3_feature_store", "Feature store -> ml_match_features"),
    ("4", "r4_feature_quality", "Feature quality -> feature_importance_precheck.csv"),
    ("6", "r6_exports", "Model-ready exports"),
]
# Phases 7 & 8 are static markdown reports (already written).


def main():
    for num, mod, desc in PHASES:
        log.info(f"=== PHASE {num}: {desc} ===")
        try:
            m = importlib.import_module(mod); importlib.reload(m); m.main()
        except Exception as e:
            log.error(f"PHASE {num} failed: {e!r}")
    log.info("research feature-store pipeline complete")


if __name__ == "__main__":
    sys.exit(main())
