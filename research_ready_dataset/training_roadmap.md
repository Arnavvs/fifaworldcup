# PHASE 8 — Training Roadmap

*Target datasets: `classification_dataset.csv` (W/D/L), `regression_dataset.csv` (home/away goals), `tournament_dataset.csv` (Monte-Carlo). All splits are **time-based** — never shuffle.*

---

## Golden rules
1. **Time-based splits only.** Use the provided `split` column (train ≤ p70 date, val p70–p85, test > p85). For final WC-2026 inference, train on *all* labelled data.
2. **No leakage.** Train only on the 39 `ml_match_features` columns; never feed `home_goals/away_goals/result`.
3. **Calibrate probabilities** before simulating — Brier/log-loss matter more than accuracy for tournaments.
4. **Evaluate with proper scoring**: multiclass log-loss + Ranked Probability Score (RPS); for goals use Poisson deviance.

---

## Stage 1 — Baselines (establish the bar)

| Model | Setup | Output |
|-------|-------|--------|
| **ELO baseline** | `elo_expected_home` → P(win); draw via fixed draw-rate split | reference log-loss |
| **Logistic Regression** | features → softmax W/D/L; standardize, impute NaN; class weights | linear baseline |
| **Poisson** | independent Poisson on `home_goals`,`away_goals` using attack/defense diffs | goals baseline |
| **Dixon-Coles** | bivariate Poisson + low-score correlation + time-decay weighting | gold-standard football baseline |

*Goal:* any ML model must beat Dixon-Coles RPS on the test split, else it is not earning its complexity.

## Stage 2 — Intermediate (gradient boosting — the workhorses)

| Model | Notes |
|-------|-------|
| **LightGBM** | primary; native NaN + categorical (`team_id`,`continent`,`stage`); fast HPO |
| **XGBoost** | cross-check; `multi:softprob` for W/D/L, `count:poisson` for goals |
| **CatBoost** | best for high-cardinality `team_id`; strong out-of-box calibration |

- Two heads: (a) **classifier** → W/D/L probabilities; (b) **two Poisson regressors** → expected goals (feeds simulation).
- HPO with **time-series CV** (expanding window), not k-fold random.
- Track feature importance against `feature_importance_precheck.csv` to catch drift/leakage.

## Stage 3 — Advanced (only after data gaps close)

| Model | Prerequisite |
|-------|--------------|
| **FT-Transformer** | embed `team_id`; needs xG + richer continuous features to beat GBMs |
| **Time-Series Transformer** | reshape `team_match_features` into per-team ordered sequences (sequence builder) |
| *(stretch)* **GNN** | team-graph with player/lineup node features |

## Stage 4 — Ensemble & Calibration

1. **Stacking:** out-of-fold (time-aware) predictions from {Dixon-Coles, LightGBM, CatBoost, FT-T} → meta-learner (logistic / shallow GBM).
2. **Calibration layer:** isotonic or temperature scaling on the **val** split; verify reliability curves on **test**.
3. **Blend** match-model goal expectations with the ELO prior for low-data matchups.

## Stage 5 — Tournament Simulation (Monte-Carlo)

- Feed calibrated goal expectations into `tournament_dataset.csv` (all 48 teams have ratings).
- Simulate group stage → knockout **N≥50,000** times; resolve draws in knockouts via extra-time/penalty model (use historical WC draw/penalty rates).
- Output per-team: P(advance group), P(reach SF/F), **P(win World Cup)**.

## Stage 6 — Backtesting & Validation

- **Walk-forward** over past tournaments (2010, 2014, 2018, 2022): train on all matches before the tournament, predict it, score with RPS + log-loss vs the ELO/market baseline.
- **Calibration tracking:** reliability diagrams per split; expected vs actual progression rates.
- **No random splits, ever** — every evaluation respects chronology.
- If odds are later added: track **closing-line value (CLV)** and Brier vs the implied market probabilities.

---

### Suggested first sprint (1 week, data as-is)
LightGBM + CatBoost classifiers → calibrate → Dixon-Coles goals model → 50k-run Monte-Carlo → WC-2026 win probabilities, benchmarked against the ELO baseline via walk-forward on 2018 & 2022.
