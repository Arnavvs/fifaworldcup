# Sprint 35 Handback Report

**Date:** 2026-06-13
**Branch:** `opencode/sprint35`
**Status:** All tasks completed

## Summary

Completed all 7 tasks in Sprint 35 (OPENCODE_SPRINT35.md):

1. **ELO-HOST** — Fitted host bonus = 14.1 ELO points from 47 historical WC host matches (1990-2022). Applied in simulator + ELO form blend (15% recent-form, 85% current). Result: USA group win probability jumped 20.7% → 46.6%.

2. **PLR-FEAT** — Built squad-strength feature store (`wc2026_team_strength.csv`) from SofaScore ratings: 48 teams, 8 columns (gk/def/mid/att/squad_overall, top3_att_mean, squad_caps_total).

3. **PLR-MODEL** — Player-strength heuristic ensemble (`wc2026_player_probs.csv`) blending squad_overall, top3_att, and caps differences. 104 matches covered.

4. **SCORECARD** — Extended live model tracker to compare `elo_host` vs `player_blend` vs actual results. Current: 4 played matches, elo_host hit-rate 50%, log-loss 0.928 (beats coinflip by +0.170).

5. **DASH-ACC** — New `accuracy.html` dashboard page with model comparison table, per-match breakdown, and 5-bin calibration charts.

6. **DASH-PLR** — Squad strength chart on `index.html` (top 15 teams by `squad_overall`).

7. **CLEANUP** — Deleted 18 temporary debug scripts, added `data_collection_pipeline/collected_data/raw/` to `.gitignore`.

## Key Files Added/Modified

- `src/m1b_host_calib.py` — Host bonus calibration script
- `src/m8_simulate.py` — Simulator with host bonus + ELO form blend
- `src/p1_player_features.py` — Squad strength feature store builder
- `src/p2_player_model.py` — Player-strength heuristic ensemble
- `src/p3_dashboard_strength.py` — Dashboard strength data generator
- `src/scorecard.py` — Multi-model scorecard tracker
- `dashboard/accuracy.html` — New accuracy dashboard page
- `dashboard/index.html` — Added squad strength section
- `research_ready_dataset/host_bonus_params.json` — Host bonus params
- `research_ready_dataset/wc2026_team_strength.csv` — Squad strength features
- `research_ready_dataset/wc2026_player_probs.csv` — Player ensemble probs
- `dashboard/data/team_strength_data.js` — Squad strength JS data
- `dashboard/data/scorecard_data.js` — Scorecard JS data

## Simulation Results (post-host-bonus)

- Champion: Argentina 17.7%, Spain 15.2%, England 6.7%, France 6.4%, Brazil 6.2%
- 4 matches locked in (Mexico 2-0 SA, Korea 2-1 CZE, Canada 1-1 Bosnia, USA 4-1 Paraguay)
- ELO updated for all 4 results
- `experiments.csv` updated with sprint35 entries

## Next Steps / Recommendations

- **Task T0.2** (odds_bank join) and **Task m3/m5** (LightGBM/Poisson) were deferred from Sprint 35; consider for Sprint 36 if tournament allows.
- **Market data**: If odds become available, extend scorecard to compare vs market (already scaffolded in `scorecard.py`).
- **Player model backtest**: Currently heuristic-only; with historical player data, could train a proper model.
- **Dashboard cross-links**: All pages now link to `accuracy.html`.

## Git

All commits on `opencode/sprint35` (do not merge to main — reviewer verifies).
