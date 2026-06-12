# AGENTS.md — Repo Guide for LLM Agents

## Quick start
This is a FIFA World Cup 2026 prediction system. To answer prediction questions, run:

```bash
python src/ask.py predict Brazil Morocco
python src/ask.py cup-odds --top 5
python src/ask.py group A
python src/ask.py status
```

All output is one-line JSON. Never invent probabilities — read artifacts.

## Environments
- **System Python 3.13** (PATH): pandas, numpy, sklearn, scipy, joblib. Use for ALL ML/model work.
- **Conda `minorproject`** (`C:\Users\HP\anaconda3\envs\minorproject\python.exe`): Playwright only. Use ONLY for scraping.

## Key conventions
- **Class order**: ALWAYS `[home_loss, draw, home_win]` = indices `[0, 1, 2]` in every probability array.
- **Chronological splits**: train ≤ 2011-01-17 < val ≤ 2018-10-11 < test. Never random splits.
- **Team names**: always map through `research_ready_dataset/team_mapping.csv` (raw → canonical).
- **Never use as features**: gf, ga, result, points, home_score, away_score, attendance, outcome.
- **Experiments**: every model run appends a row to `research_ready_dataset/experiments.csv`.

## Artifact contracts
- Latest sim: `dashboard/data/sim_results.json` (or `window.SIM` in `dashboard/sim_data.js`)
- Champion history: `dashboard/data/history_data.js` (`window.HISTORY`)
- Entropy: `dashboard/data/entropy_data.js` (`window.ENTROPY`)
- Chaos history: `artifacts/chaos_history.json`
- Backtest: `artifacts/backtest_wc2022.json`
- ELO params: `research_ready_dataset/davidson_params.json`
- Penalty model: `research_ready_dataset/penalty_model.json`

## Live loop
```bash
python src/live_update.py   # ingest scores, update ELO, re-sim
```

## Dashboard
Open `dashboard/index.html` in a browser (works from `file://`). Pages:
- `index.html` — champion odds, trajectory chart, group forecasts, match probs
- `bracket.html` — R32 slot grid
- `entropy.html` — WC chaos ranking, group chaos forecast, realized surprisal
- `progress.html` — engineering tracker

## Model files
- `src/m1_elo_davidson.py` — per-match ELO + Davidson baseline
- `src/m4_dixon_coles.py` — goals model (simulator engine)
- `src/m6_stack.py` — stacking ensemble
- `src/m8_simulate.py` — 50k Monte-Carlo tournament sim
- `src/m9_entropy.py` — surprisal/chaos engine
- `src/live_update.py` — live score ingestion loop
- `src/ask.py` — JSON CLI for external queries

## Database
`fifa_wc_data/db/football.db` — 27 tables. Key: `matches` (49k), `elo_match` (49k), `wc2026_fixtures` (104).

## Git branch
Work on `opencode/sprint34`. One commit per completed task. Do not merge to main — reviewer verifies.

## Rule: never train on future data
All models use chronological expanding-window folds. The `split` column in datasets is the source of truth.

## Current best model
Test log-loss: **0.8574** (stacker: davidson + dixon + logreg + histgb, temperature calibrated, T=1.099)
