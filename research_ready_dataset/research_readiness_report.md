# PHASE 7 — Research Readiness Report

*Feature store: `ml_match_features` — **49,281 matches × 39 target-safe features**, time-split 70/15/15, normalized to 575 canonical teams (`dim_team`). All 48 WC-2026 qualified teams carry strength ratings.*

---

## 7.1 Current State (what is ready)

| Asset | Status |
|-------|--------|
| Canonical team keys (`dim_team`, `team_mapping.csv`) | ✅ 589 raw → 575 canonical, 100% resolved |
| Leakage-safe feature store (`ml_match_features`) | ✅ outcomes excluded by construction |
| Difference + interaction features | ✅ 39 features, top signals validated (net_rating_diff, h2h, form, fifa_rank) |
| Labelled history for training | ✅ 49,281 matches 1872→2026 |
| Classification / regression / tournament exports | ✅ time-based splits, no shuffling |
| Monte-Carlo inputs for all 48 teams | ✅ elo, fifa_rank, attack/defense ratings |

The dataset is **immediately sufficient to train and backtest match-outcome and goals models** and to run tournament simulations. It is *not yet* at professional betting grade (see gaps).

## 7.2 Remaining Data Gaps & Expected Impact

Impact = expected reduction in log-loss / gain in ranked-probability skill for WC prediction.

| Gap | Coverage now | Expected impact | Why |
|-----|--------------|:---------------:|-----|
| **Bookmaker closing odds** | MISSING | ★★★★★ | Market is the strongest single baseline; enables calibration & value detection |
| **xG / shot quality (team & player)** | MISSING | ★★★★★ | Outperforms raw goals as a stable strength signal; reduces variance |
| **Live FIFA rankings 2024→2026** | stale (ends 2024-04) | ★★★★☆ | Current `fifa_rank` is ~2 yr stale for the teams we must predict |
| **Per-match ELO** | annual only | ★★★★☆ | Removes within-year staleness; sharper `elo_diff` |
| **Official 26-man squads + caps + minutes** | national pools only | ★★★★☆ | Availability-aware strength; replaces all-nationals proxy |
| **Injuries / suspensions** | MISSING | ★★★★☆ | Key-player absence materially shifts outcomes |
| **Player club form / fatigue** | MISSING | ★★★☆☆ | Pre-tournament sharpness signal |
| **Lineups / formations** | MISSING | ★★★☆☆ | Lineup-conditional strength (advanced models) |
| **Travel / altitude / weather** | 2026 venues only | ★★★☆☆ | Context edges; altitude (Mexico City 2,287 m) matters |
| **Referee profiles** | MISSING | ★★☆☆☆ | Cards/penalty/home-bias tilt |

**Net:** the four highest-ROI, lowest-effort additions are **live rankings**, **per-match ELO**, **closing odds**, and **travel features** (the last computable from existing `venues`).

## 7.3 Model Readiness Scores (1–10)

Scored on: data shape fit, sample size, feature richness, and effort to reach a working model on *this* dataset.

| Model | Score | Rationale |
|-------|:----:|-----------|
| **XGBoost** | **9/10** | Tabular, 49k rows, 39 clean numeric features, robust to missing (`elo`/`rank` NaNs handled natively). Drop-in. |
| **LightGBM** | **9/10** | Same fit; fast, handles categoricals (team_id, continent, stage) and NaNs. Recommended primary. |
| **CatBoost** | **9/10** | Best native categorical handling (team_id, continent, tournament); strong default calibration. |
| **FT-Transformer** | **6/10** | Works on tabular but needs more features/data to beat GBMs; categorical embeddings useful (team_id). Worth it only after feature gaps close. |
| **TabTransformer** | **6/10** | Same as FT-T; benefits from high-cardinality categoricals (team_id ✓) but limited continuous richness now. |
| **LSTM** | **5/10** | Requires reshaping into per-team match sequences (data exists in `team_match_features` ordered by date), but engineered features are already aggregated → marginal gain. Needs sequence builder. |
| **Time-Series Transformer** | **5/10** | Same sequence-reshaping need; 49k matches give decent sequences per team but irregular spacing complicates positional encoding. |
| **Graph Neural Network** | **5/10** | Natural fit (teams=nodes, matches=edges via `team_id`), but needs graph construction + node features; payoff mainly with player/lineup graphs we don't yet have. |

**Recommendation:** start with **LightGBM/CatBoost + ELO/Poisson baselines**; defer deep tabular/sequence/graph models until xG, live rankings, lineups, and odds are added (they raise the deep-model ceiling from ~6 to ~8).

## 7.4 Is the dataset sufficient?

- **For a credible, backtestable WC-2026 model (GBM + Poisson + Monte-Carlo):** **Yes.**
- **For a deep-learning research portfolio (FT-T / GNN / TS-Transformer that beats GBMs):** **Partially** — add xG + lineups + more granular time series first.
- **For professional betting-grade edge:** **No** — requires closing odds (calibration/CLV), lineup-conditional strength, and live availability.
