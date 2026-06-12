# Codex Suggestions: Feature Engineering to Model Engineering

Date: 2026-06-12
Scope: suggestions only, based on the current repo artifacts, source files, reports, and experiment ledger.

## Current State I Observed

This project is no longer at the original roadmap starting point. A lot of the core Claude/OpenCode work is already present.

Already shipped:

- Per-match ELO rebuild plus Davidson baseline in `src/m1_elo_davidson.py`.
- Feature store v2 in `src/f1_build_features.py`.
- Market benchmark lite in `src/f2_market_benchmark.py`.
- Dixon-Coles goals model in `src/m4_dixon_coles.py`.
- Stacker plus temperature calibration in `src/m6_stack.py`.
- Monte Carlo tournament simulator in `src/m8_simulate.py`.
- Entropy engine in `src/m9_entropy.py`.
- Penalty model integrated into simulator.
- Golden Boot heuristic in `src/m10_scorers.py`.
- Live update loop in `src/live_update.py`.
- JSON CLI in `src/ask.py`.
- Dashboard data artifacts under `dashboard/data/`.

Current evidence from artifacts and ledger:

| Area | Current evidence |
|---|---|
| Old v1 baseline | blend raw log-loss 0.8777 |
| Repaired v2 baseline | blend raw log-loss 0.8582, blend calibrated 0.8589 |
| Current best model | stacker log-loss 0.8569 to 0.8574 depending ledger row |
| Davidson only | test log-loss 0.8682, ELO coverage 1.0 |
| Dixon-Coles | test log-loss 0.9143, goal calibration home x0.961, away x1.017 |
| Market benchmark | closing odds log-loss 0.8219 on the limited recent tournament sample |
| Penalty model | 572 joined shootouts, higher-ELO side won 54.9 percent |
| Simulator | 50,000 sims, 2 locked matches in latest `sim_results.json` |
| Known data gaps | broad 2016-2026 international odds, live injuries/lineups, full FBref/API xG, scorer backtest squads |

The main opportunity is not another generic model. The project needs a tighter feature pipeline, exact tournament mechanics, stronger time-frozen validation, and then richer level-0 models feeding the stacker.

## Priority 0: Correctness and Product Gaps

These are not glamorous, but they protect every probability shown to the user.

### 1. Fix `ask.py scorers`

`src/m10_scorers.py` writes `dashboard/data/scorers_data.js`, but `python src/ask.py scorers --top 5` currently returns:

```json
{"error": "scorers model not yet built", "top": 5}
```

Suggestion:

- Make `ask.py scorers` read `dashboard/data/scorers_data.js` or the latest `artifacts/run_*/scorers.json`.
- Preserve the one-line JSON contract.
- Return top N with player, team, expected_goals, and run_id.

Why it matters:

- The CLI is the main external query layer. It currently hides an existing model artifact.

### 2. Make the simulator bracket and advancement math exact

`src/m8_simulate.py` explicitly labels these approximations:

- R16+ pairing uses sequential winner pairing.
- Third-place slot assignment is greedy.
- Group tiebreak skips head-to-head.

There is also a likely output issue in group tables: `p_top2` is computed only from top-two ranks, while third-place advancement is not added to a separate `p_advance` field.

Suggestion:

- Split group output into `p_top2`, `p_best_third`, and `p_advance`.
- Add FIFA 2026 third-place allocation table as a data file, not hard-coded guessing.
- Add unit tests with synthetic standings for all 12 groups.
- Implement FIFA tiebreak order as far as possible: points, goal difference, goals scored, then head-to-head mini-table, then fallback random/fair-play if missing.
- Replace sequential knockout pairing with the exact bracket slots from `wc2026_fixtures`.

Why it matters:

- Champion and reach probabilities are very sensitive to bracket routing in a 48-team format.
- Bad bracket logic can dominate small model improvements.

### 3. Fix the WC2022 backtest freeze

`HANDBACK_REPORT.md` already flags that the WC2022 backtest is not fully frozen. Reading `src/bt_backtest.py` shows a bigger risk: WC2022 rows are not merged with pre-match ELO before Davidson prediction, so `r.get("elo_home_pre", 1500)` and `r.get("elo_away_pre", 1500)` can silently fall back to 1500.

Suggestion:

- Rebuild an ELO table only up to each backtest cutoff date.
- Join pre-match ELO into WC2022 fixtures before prediction.
- Run complete frozen tournament backtests for 2014, 2018, 2022.
- Store each result in `artifacts/backtest_wcYYYY.json`.

Acceptance:

- No feature or rating in a backtest may use matches after opening day.
- Backtest output should report per-match log-loss, champion rank of the winner, and top-5 hit/miss.

Why it matters:

- The current model looks promising, but the credibility test needs strict historical freezing.

### 4. Add an environment sanity check

The repo guide says system Python has pandas, but the active shell Python here did not. That is a reproducibility risk.

Suggestion:

- Add `src/env_check.py`.
- Check Python version, pandas, numpy, sklearn, scipy, joblib, sqlite DB path, required artifact paths.
- Print one-line JSON so it follows the rest of the project style.

## Feature Engineering Suggestions

### 1. Finish the v2 feature integration that data already supports

`src/f1_build_features.py` repairs ELO and joins squad, manager, qualification, updated rankings, and tournament xG. The data pipeline already has more usable files that are not fully integrated:

- `processed/travel_features.csv`
- `processed/weather_forecasts.csv`
- `processed/shared_club_matrix.csv`
- `processed/cross_team_club_overlap.csv`
- `processed/continental_form.csv`

Suggested features:

| Feature | Source | Notes |
|---|---|---|
| `travel_diff_km` | travel features | For 2026 fixtures and future live sim |
| `timezone_delta_diff` | travel features | Fatigue proxy |
| `altitude_delta_diff` | travel features | Venue/team adaptation proxy |
| `heat_flag`, `humidity_diff` | weather forecasts | Only pre-match forecast data, no post-match leakage |
| `shared_club_diff` | shared club matrix | Squad chemistry proxy |
| `pair_club_overlap` | cross-team club overlap | Pairwise match feature |
| `continental_form_diff` | continental form | Use latest row per team, pre-match only |

Implementation notes:

- Keep historical rows as NaN where the feature truly does not exist.
- Add missingness flags for deployment-only features, for example `has_travel_features`.
- Do not backfill future-only data into old test rows.

### 2. Create a feature registry and leakage guard

The project already has strong leakage rules in `AGENTS.md`, but those rules are not enforced in code.

Suggestion:

- Add `research_ready_dataset/feature_registry.csv`.
- Columns: `feature`, `source`, `available_from`, `available_to`, `is_pre_match`, `allowed_for_training`, `notes`.
- Add a check in the feature builder that fails if forbidden columns are present in model features.

Forbidden patterns should include:

- `gf`, `ga`, `result`, `points`, `home_score`, `away_score`, `attendance`, `outcome`, `winning_team`, `*_score`.

Why it matters:

- As new API data lands, leakage will become the easiest way to accidentally improve log-loss.

### 3. Build rolling xG and opponent-adjusted form features

Current xG features are static team aggregates from covered tournaments. That helps 2026 inference but does not fully exploit match chronology.

Suggestion:

- For teams with StatsBomb/API xG: maintain rolling pre-match features.
- Use windows of 3, 5, and 10 matches.
- Weight by recency and opponent strength.
- Add fallback confederation means for teams with no xG.

Candidate columns:

- `xg_for_roll5_diff`
- `xg_against_roll5_diff`
- `xg_net_roll5_diff`
- `xg_for_opp_adj_diff`
- `xg_against_opp_adj_diff`
- `finishing_over_xg_roll10_diff`
- `keeper_goals_prevented_roll10_diff` if post-shot data appears later

Important:

- Each row must use only matches before that row's date.

### 4. Improve current squad strength features

The current `m10_scorers.py` and `f1_build_features.py` use caps, goals, age, club quality, and FIFA overall proxies. This can be made much stronger without changing the main model architecture.

Suggested team-level features:

- Top-11 average FIFA overall.
- Top-16 average FIFA overall.
- Position-bucket strength: GK, DEF, MID, FWD.
- Squad age balance: share under 23, share over 32.
- Caps concentration: top-5 players share of total caps.
- Goal concentration: top-3 forwards share of squad goals.
- Club league quality weighted by likely minutes.
- Same-club links in likely XI, not just full squad.

Suggested pairwise features:

- Home forward strength minus away defensive strength.
- Home midfield strength minus away midfield strength.
- Away forward strength minus home defensive strength.
- Club-overlap familiarity between opponents.

### 5. Add host, venue, and schedule features into simulation

The simulator currently applies host home advantage based on USA/Mexico/Canada as home side. That is a start, but the 2026 tournament is spread across long distances.

Suggested sim-only features:

- Team travel distance accumulated across simulated path.
- Rest days before match.
- Venue altitude difference.
- Timezone shift since last match.
- Heat/humidity penalty by venue and kickoff date.
- Host region advantage, not only home-team flag.

Practical approach:

- Start with group-stage actual fixture travel.
- For knockout paths, accumulate travel from the previous simulated venue.
- Keep the first version deterministic and inspectable.

### 6. Add market features when odds arrive

The market benchmark is the single strongest signal observed, but coverage is limited.

When broader odds are collected, add:

- `p_home_mkt`, `p_draw_mkt`, `p_away_mkt`
- `market_entropy`
- `bookmaker_disagreement`
- `open_to_close_home_delta`
- `sharp_vs_average_home_delta`
- `overround`
- `has_market`

Modeling rule:

- Train one stacker with market features and one without.
- Use market-aware model only when market coverage exists.
- Always report model-vs-market log-loss separately.

## Model Engineering Suggestions

### 1. Rebuild the stacker with true expanding-window OOF

`src/m6_stack.py` currently uses a holdout-style stack:

- level-0 train -> val predictions
- level-0 train+val -> test predictions
- meta trained on part of validation
- temperature fitted on remaining validation

This is time-honest, but it wastes data and gives the meta-model a narrow view.

Suggestion:

- Implement 5 expanding-window folds over train+val.
- Generate OOF predictions from Davidson, Dixon-Coles, logreg, HistGB, and any new models.
- Train meta-model on all OOF predictions.
- Fit temperature on a final chronological calibration slice.
- Evaluate once on test.

Acceptance:

- Test log-loss must beat current best 0.8569 by at least 0.002 before replacing `ensemble_v1.pkl`.

### 2. Add tuned LightGBM or CatBoost as `m3`

The current stack uses sklearn HistGradientBoosting. It is solid, but LightGBM/CatBoost usually handle tabular missingness, nonlinear interactions, and monotonic-ish effects better.

Suggestion:

- Add `src/m3_gbm.py`.
- Try LightGBM first if installation is clean.
- Use chronological validation only.
- Respect `sample_weight`.
- Log every run to `experiments.csv`.

Search space:

- learning rate: 0.02 to 0.08
- leaves/depth: small to medium
- min child samples: 20, 50, 100
- feature fraction: 0.6 to 1.0
- L2 regularization: 0 to 10
- early stopping on validation log-loss

Kill rule:

- If it does not beat HistGB v2 by at least 0.001 on test or improve the stacker, keep HistGB and document the kill.

### 3. Add Poisson GBM goals model as `m5`

Dixon-Coles is useful because it gives a score matrix, but it only uses team attack/defense and time decay. A feature-based Poisson model can use squad, ELO, xG, travel, venue, and market features.

Suggestion:

- Add `src/m5_poisson_gbm.py`.
- Train two Poisson regressors: home goals and away goals.
- Convert lambdas to W/D/L probabilities via score matrix.
- Feed both lambdas and W/D/L probabilities into the stacker.

Acceptance:

- Standalone log-loss under 0.95.
- Goal calibration within 5 percent on test.
- Keep in stacker only if it improves ensemble log-loss.

### 4. Tilt Dixon-Coles score matrices to match ensemble W/D/L

The simulator currently uses Dixon-Coles deploy as the match engine. But the best W/D/L model is the stacker, not Dixon-Coles.

Suggestion:

- Use Dixon-Coles for scoreline shape.
- Use ensemble probabilities for W/D/L marginals.
- Rescale the three regions of the score matrix:
  - home loss cells
  - draw diagonal
  - home win cells
- Renormalize the matrix.

Why it matters:

- The simulator keeps realistic scorelines while using the best calibrated match probabilities.
- This should improve champion odds without needing a full scoreline ensemble.

### 5. Improve Dixon-Coles with dynamic and hierarchical structure

Current Dixon-Coles pools low-sample teams by continent and uses one global decay.

Possible improvements:

- Tune decay `xi` on validation, not only use 0.0019.
- Use separate attack and defense shrinkage toward confederation means.
- Allow home advantage to differ for host, neutral, and non-neutral non-host games.
- Add simple covariates to lambdas: ELO diff, squad strength diff, xG diff, rest/travel.
- Try bivariate Poisson or Skellam as a ledger experiment.

Keep this incremental:

- Do not replace the working `m4_deploy.pkl` unless test and backtest improve.

### 6. Make calibration a first-class artifact

Current temperature scaling helps the stacker, but calibration should be monitored by segment.

Suggestion:

- Add `src/m7_calibrate.py`.
- Write `artifacts/calibration_plot_data.json`.
- Report ECE, classwise ECE, RPS, and log-loss.
- Segment by:
  - group vs knockout
  - favorite probability bucket
  - neutral vs host
  - confederation matchup
  - teams with xG coverage vs without
  - market coverage vs without

Acceptance:

- ECE under 0.02 overall.
- No segment with obvious severe overconfidence unless documented.

### 7. Upgrade scorer model from heuristic to path-aware model

Current `m10_scorers.py` estimates team goals as `exp_pts * 0.6`, which is too indirect.

Suggestion:

- Use simulator path output to estimate team expected matches and expected goals.
- Allocate goals using player-level rates and minutes probabilities.
- Add player xG/xA where StatsBomb/API coverage exists.
- Add penalty taker and set-piece taker flags.
- Backtest on WC2022 once historical squads are integrated.

Minimum fix:

- Sum expected team goals from simulated match scorelines instead of deriving from expected points.

Acceptance:

- WC2022 backtest has Mbappe and Messi in top 10 pre-tournament.
- The CLI returns scorer results through `ask.py`.

### 8. Add model uncertainty and disagreement outputs

The entropy engine already uses uncertainty concepts. Expose model disagreement as a practical warning layer.

Suggested fields per match:

- `p_ensemble`
- `p_davidson`
- `p_dixon`
- `p_logreg`
- `p_histgb`
- `jsd_sources`
- `confidence_bucket`
- `market_edge` when odds exist

Why it matters:

- High-disagreement matches are where the model is least trustworthy or most interesting.
- It helps dashboard users understand risk without inventing certainty.

## Data Engineering Suggestions

### 1. Normalize future API exports separately from collection

The StatsAPI collector is already scaffolded but local socket access was blocked. When real rows arrive, do not mix raw collection and model integration.

Suggested files:

- `src/f3_normalize_statsapi.py`
- `src/f4_join_odds.py`
- `src/f5_build_player_availability.py`

Rules:

- Raw files stay untouched.
- Normalized files go to `research_ready_dataset/`.
- All team names pass through `team_mapping.csv`.
- Every join writes an unmatched report.

### 2. Add data quality reports for every high-value table

For each normalized source, output:

- row count
- date range
- competition coverage
- team coverage
- null percentages
- join rate to `matches`
- join rate to `wc2026_fixtures`

Suggested output:

- `artifacts/data_quality/latest_statsapi_quality.json`
- `artifacts/data_quality/latest_odds_quality.json`

### 3. Build an availability override file

Until a reliable live injury feed exists, support manual overrides.

Suggested file:

- `research_ready_dataset/availability_overrides.csv`

Columns:

- `date`
- `team`
- `player`
- `status`
- `impact`
- `source_note`

Usage:

- Scorer model reduces player minutes.
- Match model gets team-level unavailable-impact diff.
- Live update reads it before re-simulating.

## Evaluation and Experiment Discipline

### 1. Expand metrics beyond log-loss

Keep log-loss as the main metric, but also record:

- Brier score
- Ranked probability score
- ECE
- accuracy
- calibration slope
- draw-class log-loss
- favorite upset log-loss

### 2. Use backtest tournaments as release gates

Before replacing production artifacts:

- Run 2014, 2018, 2022 frozen backtests.
- Compare champion winner rank and probability.
- Compare per-match log-loss vs market where odds exist.
- Compare knockout progression calibration.

### 3. Keep a champion-odds diff report

Every model change should write:

- top 20 champion odds before/after
- largest absolute probability shifts
- explanation of which model/data source changed

Suggested output:

- `artifacts/model_diff/run_<ts>_champion_diff.json`

Why it matters:

- A tiny log-loss improvement can produce a big tournament probability movement. That needs inspection.

## Recommended Next Work Order

1. Fix `ask.py scorers` and simulator group advancement outputs.
2. Make WC2022 backtest truly frozen and add 2018/2014 tournament backtests.
3. Integrate unused existing feature files: travel, weather, club overlap, continental form.
4. Add feature registry plus leakage guard.
5. Rebuild stacker with expanding-window OOF.
6. Add matrix tilting so simulator uses ensemble W/D/L plus Dixon-Coles score shape.
7. Add `m3_gbm.py` and `m5_poisson_gbm.py`; keep only if they improve the stacker.
8. Upgrade scorer model to use simulated team goals and historical backtest squads.
9. Integrate broad odds/API data only after raw exports are non-empty and quality reports pass.

## High-Level Judgment

The best current project upgrade is not to chase a deep model first. The project already has a useful ensemble. The biggest gains should come from:

1. Exact tournament mechanics.
2. Strict frozen backtests.
3. Integrating unused existing features.
4. Using ensemble probabilities inside the simulator.
5. Market-aware modeling once broad odds coverage lands.

After those are solid, LightGBM/CatBoost and Poisson GBM are worth running as controlled ledger experiments.
