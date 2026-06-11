# Football Intelligence Platform — Comprehensive AI Planning Document

**Project:** FIFA World Cup 2026 Machine Learning Platform  
**Location:** `C:\Users\HP\OneDrive\Desktop\worldCup`  
**Snapshot Date:** 2026-06-02  
**Document Purpose:** Machine-readable planning artifact for AI-assisted implementation, code generation, and project management.  
**Status:** MVP-ready dataset assembled; research-grade and betting-grade architectures planned.

---

## 1. Executive Summary

This project is a modular, resumable data pipeline that aggregates free football data into an analysis-ready SQLite + CSV dataset for WC-2026 prediction and betting research.

- **Total rows:** ~626,248 across 27 tables
- **Time span:** 1872 → 2026-06-27
- **Model-ready samples:** 49,281 matches × 39 leakage-safe features
- **Qualified teams:** 48/48 + 1 TBD playoff slot
- **Fixtures:** 104 (group stage through final)

The project is **immediately sufficient** to train and backtest match-outcome + goals models and run tournament simulations. It is **not yet** at professional betting grade.

---

## 2. Existing Project Structure

```
C:\Users\HP\OneDrive\Desktop\worldCup\
├── fifa_wc_data/
│   ├── raw/
│   │   ├── kaggle/                    # Intl results, goalscorers, WC datasets, FIFA ratings 15–22
│   │   ├── elo/
│   │   │   └── elo_ratings.csv        # 18,142 rows; year-end ELO 1901→2026
│   │   ├── fifa_rankings/
│   │   │   ├── fifa_rankings.csv      # 67,261 rows; 1992→2024-04 (STALE)
│   │   │   └── kaggle/                # Additional Kaggle ranking snapshots
│   │   ├── worldcup/
│   │   │   ├── wc_matches_history.csv # 900 rows; 1930→2018
│   │   │   ├── wc_tournaments.csv     # 21 rows; tournament meta
│   │   │   ├── wc2026_fixtures.csv    # 104 rows; future fixtures
│   │   │   ├── wc2026_qualified_teams.csv # 49 rows (48 + TBD)
│   │   │   └── squad_players_*.csv    # Historical WC squads (FIFA game data)
│   │   ├── statsbomb/
│   │   │   ├── sb_matches.csv         # 128 rows; WC 2018+2022
│   │   │   ├── sb_team_match_stats.csv   # 255 rows; xG, shots, goals
│   │   │   ├── sb_player_match_stats.csv  # 1,757 rows; player xG
│   │   │   └── starting_lineups.csv      # 2,816 rows; WC 2018+2022 XIs
│   │   ├── transfermarkt/
│   │   │   ├── squads.csv             # Blocked/empty proxy
│   │   │   ├── market_values.csv      # Blocked/empty proxy
│   │   │   └── injuries.csv           # Blocked/empty proxy
│   │   ├── football_data/
│   │   │   └── odds.csv               # Empty (no intl feed)
│   │   └── odds/
│   │       └── odds_bank_raw.csv      # 479,440 rows; 2005→2015 only
│   ├── processed/
│   │   ├── matches.csv                # 49,353 rows; canonical match table
│   │   ├── team_match_features.csv    # 98,562 rows; 30 features per team-match
│   │   ├── players.csv                # 18,127 rows; FIFA game ratings
│   │   ├── market_values.csv          # 48 rows; squad aggregates (2022 snapshot)
│   │   └── venues.csv                 # 16 rows; WC2026 geocodes + altitude
│   ├── db/
│   │   └── football.db                # SQLite; 27 tables (see schema below)
│   └── logs/
│       ├── pipeline.log
│       ├── scrape_attempts.csv
│       ├── checkpoints.json
│       ├── source_summary.csv
│       ├── table_summary.csv
│       └── data_quality_report.csv
├── research_ready_dataset/
│   ├── ml_match_features.csv          # 49,281 rows × 47 cols (DIFF + INTERACTION features)
│   ├── classification_dataset.csv
│   ├── regression_dataset.csv
│   ├── tournament_dataset.csv
│   ├── dim_team.csv                   # 575 canonical team IDs
│   ├── team_mapping.csv
│   ├── feature_importance_precheck.csv
│   ├── audit_report.md
│   ├── research_readiness_report.md
│   └── training_roadmap.md
├── src/
│   ├── common.py
│   ├── run_all.py                     # Pipeline orchestrator
│   ├── s01_kaggle.py                  # Stage 1: Kaggle CLI ingestion
│   ├── s02_elo.py                     # Stage 2: ELO ratings
│   ├── s03_fifa_rankings.py           # Stage 3: FIFA rankings
│   ├── s04_worldcup.py                # Stage 4: WC history + fixtures
│   ├── s05_football_data.py           # Stage 5: Odds (empty, documented)
│   ├── s06_fbref.py                   # Stage 6: FBref (Cloudflare blocked)
│   ├── s07_transfermarkt.py           # Stage 7: Transfermarkt (anti-bot blocked)
│   ├── s08_players.py                 # Stage 8: FIFA-game player master
│   ├── s09_features.py                # Stage 9: Feature engineering
│   ├── s10_build_db.py                # Stage 10: SQLite assembly
│   ├── s11_quality.py               # Stage 11: Quality reports
│   ├── s12_venues.py                # Stage 12: Venue geocoding
│   ├── s13_statsbomb.py             # Stage 13: StatsBomb open data
│   ├── s14_wc2026_squads.py         # Stage 14: Official 26-man squads
│   ├── s15_odds.py                  # Stage 15: Odds bank ingestion
│   ├── r1_audit.py                  # Research Phase 1: Audit
│   ├── r2_dim_team.py             # Research Phase 2: Team normalization
│   ├── r3_feature_store.py        # Research Phase 3: Feature store
│   ├── r4_feature_quality.py      # Research Phase 4: Quality checks
│   ├── r6_exports.py              # Research Phase 6: ML exports
│   └── r_all.py                   # Research orchestrator
├── README.md
├── SCHEMA.md
├── INVENTORY_REPORT.md
├── DATA_BANK_UPDATE.md
└── DATA_PORTFOLIO_REPORT.html
```

---

## 3. SQLite Database Schema (27 Tables)

The canonical data lives in `fifa_wc_data/db/football.db`.

### Populated Tables

| Table | Rows | Cols | PK | Notes |
|---|---|---|---|---|
| `matches` | 49,353 | 14 | `match_id` | Canonical results 1872→2026 |
| `matches_norm` | 49,353 | 16 | `match_id` | Normalized with `team_id` FKs |
| `team_match_features` | 98,562 | 30 | `(match_id, team)` | 30 features per team-match |
| `ml_match_features` | 49,281 | 47 | — | Research-ready diff + interaction features |
| `players` | 18,127 | 22 | `player_id` | FIFA game ratings proxy |
| `squads` | 12,948 | 6 | `(tournament, team, player_id)` | National pools (NOT official 26-man) |
| `official_squads_2026` | 1,246 | 8 | — | Real 26-man lists with caps, club, position |
| `elo_ratings` | 18,142 | 4 | `(date, team)` | Year-end ELO only |
| `fifa_rankings` | 67,261 | 4 | `(date, team)` | Stale: ends 2024-04 |
| `goalscorers` | 47,601 | 8 | — | Event-level goal data |
| `market_values` | 48 | 6 | `team` | Single 2022 snapshot |
| `venues` | 16 | 7 | `venue_id` | WC2026 geocodes; 1 geocode fail (Guadalajara) |
| `wc2026_fixtures` | 104 | 9 | `MatchNumber` | Future scores are null |
| `wc2026_qualified_teams` | 49 | 3 | — | 48 teams + TBD |
| `wc_matches_history` | 900 | 15 | — | 1930→2018 WC results |
| `wc_tournaments` | 21 | 10 | — | Tournament meta |
| `odds_bank` | 479,440 | 19 | — | Historical closing odds 2005→2015 |
| `sb_matches` | 128 | 10 | — | StatsBomb WC 2018+2022 |
| `sb_team_match_stats` | 255 | 6 | — | Team xG for WC 18/22 |
| `sb_player_match_stats` | 1,757 | 7 | — | Player xG for WC 18/22 |
| `starting_lineups` | 2,816 | 7 | — | Real XIs for WC 18/22 |
| `dim_team` | 575 | 5 | `team_id` | Canonical normalization table |

### Empty / Schema-Only Tables

| Table | Cols | Reason |
|---|---|---|
| `team_match_stats` | 13 | FBref Cloudflare blocked (xG, SCA, possession…) |
| `player_match_stats` | 12 | FBref Cloudflare blocked |
| `player_tournament_stats` | 8 | Depends on FBref |
| `injuries` | 5 | Transfermarkt anti-bot blocked |
| `odds` | 9 | football-data.co.uk has no intl odds feed |

---

## 4. Data Requirements Matrix (For AI Feature Engineering)

| Category | Feature Examples | Required Raw Data | Source | Cost | Difficulty | Current Status | Gap Severity |
|---|---|---|---|---|---|---|---|
| **Team Strength** | ELO diff, FIFA rank diff, Bayesian α/β | Match results, rankings | eloratings, FIFA, Football-data | Free | Easy | Partial (ELO year-end, rankings stale) | Medium |
| **Team Form** | Rolling win%, xGD, goals for/against | Match scoreboards | Football-data, Kaggle | Free | Easy | **Complete** | Low |
| **Player Quality** | OBV, xT, xP, GSAA | Spatiotemporal events, lineups | StatsBomb 360, Opta | Premium | Hard | Partial (FIFA proxy only) | High |
| **Squad Depth** | Entropy, elasticity, rotation Gini | Market values, minutes, lineups | Transfermarkt | Free-Premium | Medium | Partial (values exist, minutes missing) | Medium |
| **Injuries** | ZINB hazard, XGBSE, severity weight | Injury logs, recovery, GPS | Transfermarkt, physioroom | Free-Premium | Hard | **Missing** (table empty) | High |
| **Team Chemistry** | SNA networks, shared minutes | Career pass events, joint minutes | StatsBomb, Transfermarkt | Premium | Hard | **Missing** | Medium |
| **Tactical** | PPDA, Field Tilt, xD, LBP | Event coordinates (passes, tackles) | StatsBomb, Opta, Wyscout | Premium | Hard | Partial (derivable from public data) | Medium |
| **Formation** | Delaunay clusters, shape entropy | Lineup positions, tracking | Wyscout, Opta | Premium | Hard | Partial (lineups only WC 18/22) | Medium |
| **Matchup** | Gower distance, spectral clustering | Playstyle vectors, H2H | Wyscout, StatsBomb | Premium | Medium | Partial (H2H exists, embeddings missing) | Medium |
| **Scheduling** | RRD, congestion | Fixture calendars | Football-data, FIFA | Free | Easy | Mostly complete | Low |
| **Travel** | TDF, timezone delta | Venue geocodes, team bases | Geopy, public APIs | Free | Easy | Partial (geocodes exist, distances not computed) | Low |
| **Environmental** | Heat index, altitude | Weather forecasts, elevation | OpenWeather, elevation APIs | Free | Easy | Partial (altitude exists, weather missing) | Low |
| **Tournament** | Dynamic Elo, suspension risk | Brackets, rules, cards | FIFA, Opta | Free-Premium | Medium | Partial (fixtures exist, dynamic Elo missing) | Medium |
| **Psychological** | Momentum flow, resilience | In-play sequences, half-time events | StatsBomb, broadcast | Premium | Hard | **Missing** | Medium |
| **Betting Market** | CLV, Shin probs, sentiment | Real-time & historical odds | Pinnacle, OddsPortal | Free-Premium | Medium | **Missing** (only 2005-2015 odds) | **Critical** |
| **Transfer Market** | Gini, expenditure, ROI | Transfer records, valuations | Transfermarkt | Free-Premium | Medium | Partial (single snapshot) | Medium |
| **Referee** | Card bias, penalty ratio | Referee histories, assignments | Football-data, Opta | Free-Premium | Medium | **Missing** (100% null) | Medium |
| **Fan/Crowd** | Occupancy density | Attendance, capacity | Transfermarkt, public | Free | Easy | **Missing** | Low |

---

## 5. Feature Inventory (Tiered)

### Tier 1 — Core Predictive Engine (Build First)

These 20 features provide the highest log-loss reduction and are buildable from existing + near-term data.

| # | Feature | Taxonomy | Formula | Raw Data | Status |
|---|---|---|---|---|---|
| 1 | Elo Rating Delta | Team Strength | `Elo_team - Elo_opponent` | Historical results | Done |
| 2 | FIFA Rank Diff | Team Strength | `Rank_team - Rank_opponent` | Ranking tables | Needs refresh |
| 3 | Decay-Weighted GD (N=10) | Team Form | `Σ e^(-ξ(t-tk)) · GD_k` | Match histories | Done |
| 4 | Win % Form (L5/10/20) | Team Form | Rolling win % | Match results | Done |
| 5 | Goals For/Against Avg (L5/10/20) | Team Form | Rolling averages | Match results | Done |
| 6 | H2H Win % (L10) | Matchup | Win rate last 10 meetings | Match results | Done |
| 7 | H2H Goal Diff (L10) | Matchup | Avg goal diff last 10 | Match results | Done |
| 8 | Days Rest Diff (RRD) | Scheduling | `Rest_team - Rest_opponent` | Fixture calendars | Done |
| 9 | Home Field / Neutral Flag | Context | `Is_home × (1 - neutral)` | Match metadata | Done |
| 10 | WC Experience Diff | Tournament | Prior WC appearances delta | WC history | Done |
| 11 | Stage Weight | Tournament | Group=1 → Final=5 | Fixture metadata | Done |
| 12 | Result Streak Diff | Team Form | Current streak delta | Match results | Done |
| 13 | Rivalry Flag | Context | Historical rivalry indicator | Match results | Done |
| 14 | Travel Distance Fatigue (TDF) | Travel | `log(Dist_km + 1) × ΔTimezones` | Venue geocodes | 2-3 hrs |
| 15 | Altitude Penalty | Environmental | `Elevation × I(Elevation ≥ 1000)` | Venue elevation | Done |
| 16 | Closing Line Value (CLV) | Betting Market | `Odds_open / (Odds_close × (1-Margin))` | Odds time-series | Needs collection |
| 17 | Shin Implied Probability | Betting Market | Iterative overround removal | Bookmaker odds | Needs collection |
| 18 | Lineup Overall Rating | Player Quality | Mean FIFA overall of XI | Players + lineups | 1 day |
| 19 | Squad Age Centroid | Squad Depth | Mean age of XI | Player DOBs + lineups | 1 day |
| 20 | Team Value Multiplier | Transfer Market | `log(ΣValue_opp / ΣValue_team)` | Market values | Done |

### Tier 2 — Contextual & Tactical Stabilizers (Important)

| # | Feature | Taxonomy | Description | Data Needed | Effort |
|---|---|---|---|---|---|
| 21 | Venue-Adjusted Rolling xGD (10) | Team Strength | xG-generated - xG-conceded - HA_adj | Shot coordinates + pressure | Medium |
| 22 | Expected Threat (xT) Attacking Diff | Tactical | `xT_team - xT_opp` (Markov iteration) | Pass/carries coordinates | Medium |
| 23 | PPDA (Pressing Intensity) | Tactical | Opponent passes in F60% / defensive actions | Interceptions, tackles, passes | Medium |
| 24 | Field Tilt Share | Tactical | Team F3 passes / total F3 passes | Spatial pass coordinates | Medium |
| 25 | Expected Disruption (xD) | Tactical | Opponent expected passes / completed passes | Defensive events + xP model | Hard |
| 26 | Lineup Cohesion Index | Team Chemistry | `Σ_{i<j} MinPlayedTogether_{i,j}` | Historical lineups + minutes | Medium |
| 27 | Lineup Net OBV | Player Quality | `Σ_{p=1}^{11} OBV_p` | StatsBomb 360 events + lineups | Hard |
| 28 | GK GSAA | Player Quality | `PSxG_faced - Conceded` | GK shot events + xG | Medium |
| 29 | Squad Depth Elasticity | Squad Depth | `Value(StartingXI) / Value(Squad)` | Valuations + projected lineups | Medium |
| 30 | Minutes Rotation Entropy | Squad Depth | `-Σ p(mi) log p(mi)` | Player minutes distributions | Medium |
| 31 | Dynamic Injury Severity Weight | Injuries | `Σ_{p∈Injured} OBV_net,p × Severity_days` | Injury logs + recovery + values | Hard |
| 32 | Roster Injury Density | Injuries | `Σ_{p∈injured} Value_p` | Injury logs + valuations | Medium |
| 33 | Gower Playstyle Distance | Matchup | Weighted distance over playstyle centroids | Multi-dimensional vectors | Hard |
| 34 | Tactical Matchup Cosine | Matchup | `1 - cos(θ_team, θ_opp)` | Playstyle embeddings | Hard |
| 35 | Deep Completion Volume | Tactical | Passes completed within 20m of goal | Spatial pass coordinates | Medium |
| 36 | Set-Piece Attacking xG | Tactical | `Σ xG_set-piece shots` | Set-piece shot events | Medium |
| 37 | Weather Heat Index | Environmental | `Temp_C + 0.55 × (1 - Humidity%)` | Weather forecasts | Easy |
| 38 | Referee Card Bias | Referee | `Mean(Yellows + 2×Reds)` per referee | Referee histories | Medium |
| 39 | Referee Penalty Ratio | Referee | Penalties awarded / matches | Referee assignments + penalties | Medium |
| 40 | Stadium Occupancy Density | Fan/Crowd | `Attendance / Capacity` | Attendance + capacity | Easy |

### Tier 3 — Experimental / Research-Grade

| # | Feature | Taxonomy | Description | Data Needed | Effort |
|---|---|---|---|---|---|
| 41 | HIGFormer Player Embedding | Player Quality | Latent node representation from interaction graph | StatsBomb 360 + career networks | Very Hard |
| 42 | HIGFormer Team Interaction | Matchup | Team convolution from macro-level competitive graph | Historical results + player graphs | Very Hard |
| 43 | Edge-Conditioned GNN Logits | Team Chemistry | Passer star-graph topology receiver prediction | Spatiotemporal passing events | Very Hard |
| 44 | TacticGen Classifier Guidance | Tactical | `∇_x log p(Objective | x)` alignment | 25 Hz tracking + generative model | Very Hard |
| 45 | Pitch Control Area Share | Tactical | `∬ P(x,y) ≥ 0.5 dxdy` (Voronoi) | 25 Hz tracking (all 22 players) | Very Hard |
| 46 | Time to Control (TTC) Delta | Tactical | `TTC_XI - TTC_opp_XI` physics-based | Player velocities, acceleration | Very Hard |
| 47 | Off-the-Ball Sprint Density | Physical Load | `Σ sprints_off-ball` | SkillCorner / tracking | Hard |
| 48 | XGBSE Workload Survival Hazard | Injuries | Tree-based survival embedding for injury risk | GPS training loads | Hard |
| 49 | ZINB Re-Injury Recurrence | Injuries | Zero-Inflated Negative Binomial for time-loss | Injury history + biomechanics | Hard |
| 50 | HT Post-Hit Counterfactual Momentum | Psychology | `I(Goal_HT) - I(PostHit_HT)` | In-play shot metadata | Medium |
| 51 | In-Play Momentum Flow Velocity | Psychology | Mean shot velocity over 5-min windows | Live in-play shot feeds | Medium |
| 52 | Cognitive Panic Metric | Psychology | Voronoi area expansion after conceding | 25 Hz tracking | Very Hard |
| 53 | Delaunay Adjacency Shape Shift | Formation | g-segmentation over Delaunay matrices | Player positional tracking | Hard |
| 54 | Manager-Player Exposure Days | Team Chemistry | `Σ DaysActiveUnderManager_{p,m}` | Career manager-player logs | Medium |
| 55 | Language Barrier Misunderstanding Index | Referee | `1 - I(Lang_team = Lang_ref)` | Nationality language maps | Low |
| 56 | Agent-Based Simulation Output | Research | RoboCup / Google Football emergent tactics | Custom multi-agent env | Very Hard |

---

## 6. Model Architecture Recommendations

### Baseline Models (Always Required)

| Model | Role | Inputs | Pros | Cons | When to Use |
|---|---|---|---|---|---|
| **Elo Rating** | Reference baseline | Match results (W/D/L), K-factor, venue adj | Trivial, self-correcting, robust | Single scalar; ignores tactics, injuries, form | Tournament bracket simulation; as a covariate in ensembles |
| **Independent Poisson** | Legacy reference | Historical goals by venue | Intuitive, easy GLM fit | Assumes goal independence; overestimates 0-0 | **Obsolete** — use only for pedagogy |
| **Dixon-Coles** | Gold-standard scoreline | Venue-adjusted xG (or goals), ρ, ξ decay | Corrects low-scoring correlation; calibrates correct score / O/U | No player/tracking data; static params | Primary simulation engine for goal markets and tournament Monte Carlo |

### Machine Learning Models

| Model | Best For | Why | Status |
|---|---|---|---|
| **LightGBM** | Continuous event features (PPDA, Field Tilt, xD) | Leaf-wise best-first growth; millions of events fast; native NaN handling | **Primary workhorse** — build first |
| **CatBoost** | High-cardinality categoricals (Referee_ID, Manager_ID, Formation_ID, Weather) | Native categorical encoding; no one-hot explosion; strong calibration | **Co-primary** — build alongside LightGBM |
| **XGBoost** | Deep tabular ensembles | Depth-wise growth; robust regression; `multi:softprob` / `count:poisson` | **Cross-check** — validate against LightGBM/CatBoost |
| **HIGFormer GNN** | Player interaction graphs, passing synergy | Models team as dynamic graph; captures chemistry | **Defer** until xG + lineup data is rich |
| **Temporal Transformer** | Ordered event sequences | Self-attention over build-up actions; long-term credit assignment | **Defer** until large event corpus available |
| **Bayesian Hierarchical Poisson** | Sparse national team data | Shares info across teams via random effects; robust for small samples | **Use for tournament priors** |

### Calibration (Mandatory for Betting)

| Technique | Best For | Implementation |
|---|---|---|
| **Isotonic Regression** | Large continuous datasets | `sklearn.isotonic.IsotonicRegression` on validation margins |
| **Platt Scaling** | Small datasets / normal margins | Logistic regression on raw model scores |

### Ensemble Architecture

```
Level-0 (Base Models):
  ├── CatBoost           → P_home, P_draw, P_away
  ├── LightGBM           → P_home, P_draw, P_away
  ├── XGBoost            → P_home, P_draw, P_away
  ├── Dixon-Coles        → Scoreline matrix → marginal 1X2 probs
  └── HIGFormer (future) → P_home, P_draw, P_away

Level-1 (Meta-Learner):
  └── Calibrated Ridge / Shallow NN / Logistic Regression
      Inputs: All Level-0 probs + Shin-derived market probs
      Output: Final calibrated P_home, P_draw, P_away
```

---

## 7. Implementation Roadmap (AI-Actionable)

### Phase 1: Data Collection & Harmonization (Weeks 1–4)

| Week | Task | Deliverable | Blocker Mitigation |
|---|---|---|---|
| W1 | Refresh FIFA rankings 2024→2026 | Updated `fifa_rankings` table | Scrape monthly FIFA PDFs/tables |
| W1 | Compute per-match ELO or source full series | Sub-annual ELO table | Use eloratings.net full history or self-compute from results |
| W1–2 | Scrape recent odds 2016→2026 (OddsPortal + Playwright) | Populated `odds` table | Run from residential IP; rate-limit; cache aggressively |
| W2 | Compute travel distances + timezone shifts | `TDF` feature | Use existing venue geocodes + Haversine |
| W2–3 | Integrate official squads into aggregates | Squad strength features | Compute mean caps, age, club-quality proxy per team |
| W3–4 | Attempt FBref/Transfermarkt unblocking | `team_match_stats`, `injuries` tables | Playwright/Selenium on cloud VM or residential IP |
| W3–4 | Expand `dim_team` + build player ID crosswalk | Canonical IDs linking all sources | Manual alias mapping for edge cases |

### Phase 2: Feature Engineering & Store (Weeks 3–6)

| Week | Task | Deliverable |
|---|---|---|
| W3–4 | Build expanding-window engine | Python/Polars or Spark job for rolling features |
| W4–5 | Implement Tier 1 feature set | Feature vectors for all 49k matches |
| W5–6 | Deploy Feast Feature Store | Offline: S3 Parquet; Online: Redis |
| W5–6 | Leakage audit pipeline | Automated tests: temporal boundary, lineup boundary, target boundary |
| W6 | Feature interactions | `Elo × xGD`, `Cohesion × Gower`, `TDF × RRD` terms |

### Phase 3: Baseline Models (Weeks 5–7)

| Week | Task | Success Criteria |
|---|---|---|
| W5 | Elo baseline | Reference log-loss computed |
| W6 | Dixon-Coles with xG-derived rates (or goal-derived if xG missing) | Scoreline matrices; RPS benchmark |
| W6–7 | Poisson baseline (independent, for comparison) | Document that DC outperforms |
| W7 | Walk-forward validation on 2018 & 2022 WCs | Backtest report: log-loss, RPS, Brier |

### Phase 4: GBDT Models (Weeks 7–10)

| Week | Task |
|---|---|
| W7–8 | LightGBM classifier (W/D/L) on Tier 1 features |
| W8 | CatBoost classifier (high-cardinality categoricals) |
| W8–9 | XGBoost regression (home/away goals) |
| W9 | Time-series CV (expanding window, NEVER shuffle) |
| W9–10 | HPO with Optuna / Ray Tune |
| W10 | **Go/No-Go:** Model must beat Elo log-loss by >5% to proceed to ensemble |

### Phase 5: Ensemble & Calibration (Weeks 10–12)

| Week | Task | Deliverable |
|---|---|---|
| W10 | Generate Level-0 OOF predictions (time-aware) | OOF matrix |
| W10–11 | Train Level-1 meta-learner | Stacked ensemble |
| W11 | Fit Isotonic + Platt calibration layers | Calibrated probs |
| W11 | Reliability diagrams + Brier validation | Calibration report |
| W12 | Feature importance drift check vs. `feature_importance_precheck.csv` | Drift report |

### Phase 6: Tournament Simulation (Weeks 11–13)

| Week | Task | Deliverable |
|---|---|---|
| W11 | Bivariate Dixon-Coles scoreline generator | Match-level P(scoreline) function |
| W12 | Dynamic Elo update within sim runs | Momentum-capturing ratings |
| W12 | Monte Carlo engine (Celery, N≥50,000) | Distributed sim framework |
| W13 | WC 2026 bracket simulation | Per-team P(advance), P(win), tail-risk |
| W13 | Historical backtest (2010, 2014, 2018, 2022) | Walk-forward tournament validation |

### Phase 7: Advanced Research (Weeks 12–20+)

| Week | Task | Risk |
|---|---|---|
| W12–14 | Build SNA passing networks | Data availability |
| W14–16 | HIGFormer GNN prototype | Compute cost; marginal gain uncertain |
| W16–18 | Temporal Transformer on event sequences | Requires large corpus |
| W18–20 | Tactical embeddings (Gower + spectral) | Medium |
| W20+ | Manager-player familiarity indices | Low |
| W20+ | Psychological momentum flows | High noise |
| W20+ | Agent-based simulations | Research-only |

---

## 8. Dependency Graphs (Text/ASCII)

### 8.1 Full Data Flow

```
RAW DATA
├── Match Results (Kaggle, Football-data) ──> Canonical Matches Table
├── ELO Ratings (eloratings.net) ──────────> Year-end ELO Table
├── FIFA Rankings (FIFA / Kaggle) ─────────> Rankings Table (STALE)
├── StatsBomb Open (GitHub) ───────────────> WC 2018/22 xG + Lineups
├── Odds Bank (football-data, OddsPortal) ──> Historical Odds (2005-2015)
├── Transfermarkt (squads, values, injuries) -> BLOCKED / EMPTY
├── FBref (xG, player stats) ──────────────> BLOCKED / EMPTY
└── Weather / Elevation (public APIs) ───────> NOT COLLECTED

HARMONIZATION
├── SPADL Schema Normalization
├── dim_team Canonical Mapping (575 IDs)
├── Player ID Crosswalk (FIFA ↔ StatsBomb ↔ Transfermarkt)
└── Temporal Boundary Enforcement (t < T strict)

FEATURE ENGINEERING (18 Taxonomies)
├── Team Strength ──────> ELO diff, xGD, Bayesian intercepts
├── Team Form ──────────> Decay-weighted rolling windows (N∈{3,5,10,15,30})
├── Player Quality ─────> OBV, xT, xP (premium data required)
├── Squad Depth ────────> Entropy, elasticity, rotation Gini
├── Injuries ───────────> ZINB hazard, XGBSE (data missing)
├── Team Chemistry ─────> SNA networks, shared minutes (data missing)
├── Tactical ───────────> PPDA, Field Tilt, xD (partially derivable)
├── Formation ──────────> Delaunay clusters (data missing)
├── Matchup ────────────> Gower distance, spectral (data missing)
├── Scheduling ─────────> RRD, congestion (mostly done)
├── Travel ─────────────> TDF, timezone (geocodes done; compute distances)
├── Environmental ──────> Heat index, altitude (altitude done; weather missing)
├── Tournament ─────────> Dynamic Elo, suspension risk (partial)
├── Psychological ──────> Momentum, resilience (missing)
├── Betting Market ─────> CLV, Shin, sentiment (missing)
├── Transfer Market ────> Gini, expenditure (partial snapshot)
├── Referee ────────────> Card bias, penalties (100% null)
└── Fan/Crowd ──────────> Occupancy density (missing)

FEATURE STORE (Feast)
├── Offline: S3 Parquet Lake (training, backtesting, time-travel)
└── Online: Redis Cache (sub-millisecond pre-match / in-play serving)

MODELS
├── Baselines: Elo, Dixon-Coles, Poisson
├── GBDTs: LightGBM, CatBoost, XGBoost
├── Deep Learning: HIGFormer GNN, Temporal Transformer (deferred)
└── Bayesian: Hierarchical Poisson (tournament priors)

ENSEMBLE
├── Level-0: CatBoost + LightGBM + XGBoost + Dixon-Coles
└── Level-1: Calibrated Ridge / Shallow NN + market odds

SIMULATION
├── Bayesian Hierarchical Skill Model
├── Bivariate Dixon-Coles Scoreline Generator
├── Dynamic Elo Updates (momentum)
└── Monte Carlo Engine (N≥50,000)

BETTING LAYER
├── Shin Overround Removal (true market probs)
├── EV Engine: EV = (TrueProb × Odds) - 1
├── Kelly Criterion: f* = (bp - q) / b; fractional f*/4
└── Automated Execution (REST API)
```

### 8.2 Betting Execution Architecture

```
Pinnacle Odds Feed (WebSocket)
    │
    ▼
Shin Overround Removal Engine
    │──> True Market Probability P_market
    │
    ▼
Feature Store (Redis) ──> Pre-match Features
    │
    ▼
Level-0 Ensemble:
    ├── CatBoost ────────┐
    ├── LightGBM ────────┼──> Level-1 Meta-Learner
    ├── XGBoost ─────────┤    (Ridge / Shallow NN)
    └── Dixon-Coles ─────┘
    │
    ▼
Calibrated Model Probability P_model
    │
    ▼
EV Engine:
    IF EV > threshold AND P_model > P_market × margin:
        Kelly Stake = f* / 4
        Execute Bet via REST API
    ELSE:
        No Action
```

### 8.3 Tournament Simulation Architecture

```
Bayesian Hierarchical Skill Model:
    goals_k ~ Poisson(μ_k)
    ln(μ_k) = home·I(k∈Home) + α_team(k) - β_opp(k)
    α_i ~ N(μ_att, σ²_att)
    β_i ~ N(μ_def, σ²_def)
    │
    ▼
Celery Distributed Worker Pool (N ≥ 50,000 iterations)
    Per iteration:
        1. Draw group stage from bivariate Dixon-Coles
        2. Update dynamic Elo (momentum)
        3. Resolve tiebreakers (GD, GF, H2H)
        4. Populate knockout bracket
        5. Resolve knockouts (ET / penalties)
        6. Record champion + paths
    │
    ▼
Aggregation & Reporting:
    - P(advance from group) per team
    - P(reach R16 / QF / SF / Final)
    - P(win World Cup)
    - Tail-risk curves (EVT)
```

---

## 9. Gap Analysis & Risk Register

### What Is Missing (Critical)

| Gap | Impact | How to Close | Effort |
|---|---|---|---|
| FIFA rankings stale (ends 2024-04) | Strength mis-rating for 2026 teams | Scrape monthly ranking tables/PDFs | 2–4 hrs |
| Year-end ELO only | Within-year rating shifts ignored | Source per-match ELO or self-compute | 1 day |
| No recent odds (2016→2026) | Cannot calibrate or detect +EV | OddsPortal + Playwright scrape | 1–2 days |
| xG only for WC 18/22 | No qualifier/friendly strength signal | Understat scrape or StatsBomb 360 subscription | 2–3 days |
| Injuries table empty | Key-player absence unmodeled | Playwright on Transfermarkt injury pages | 2–3 days |
| No real-time infrastructure | Cannot do live betting or in-play | Feast + Redis + streaming (Phase 4+) | 2–4 weeks |

### Biggest Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Data leakage (temporal boundary)** | Critical | Automated tests: for match at time T, reject any feature with timestamp ≥ T |
| **Anti-bot blocking (FBref/Transfermarkt)** | High | Playwright/Selenium on residential IP or cloud VM; cache aggressively; respect robots.txt |
| **Overfitting to small tournament samples** | High | Validate on multiple tournaments + leagues; use hierarchical Bayesian priors for sparse teams |
| **Lineup uncertainty pre-kickoff** | Medium | Use projected lineup probability distributions until official sheets drop (~60 min pre-match) |
| **Premature deep learning investment** | Medium | Gate: GNN/Transformer must beat GBDT by >2% log-loss on held-out data before production |
| **Calibrated probs without market benchmark** | Medium | Always compare model probs to Shin-derived market probs; positive CLV is the only valid success metric |

---

## 10. File Paths for AI Code Generation

When writing code for this project, use these exact paths:

- **Project root:** `C:\Users\HP\OneDrive\Desktop\worldCup`
- **Raw data:** `fifa_wc_data/raw/`
- **Processed data:** `fifa_wc_data/processed/`
- **Database:** `fifa_wc_data/db/football.db`
- **Logs:** `fifa_wc_data/logs/`
- **Research exports:** `research_ready_dataset/`
- **Pipeline code:** `src/`
- **Orchestrator:** `src/run_all.py`
- **Research orchestrator:** `src/r_all.py`

### Key CSV Schemas (for parsing)

**`fifa_wc_data/processed/matches.csv`** (header row 1):
```
date,home_team,away_team,home_score,away_score,tournament,city,country,neutral,match_id,stage,stage_weight,rivalry
```

**`fifa_wc_data/processed/team_match_features.csv`** (header row 1):
```
match_id,date,team,opponent,is_home,tournament,stage,stage_weight,rivalry,neutral,gf,ga,result,days_rest,result_streak_in,wc_appearances_before,h2h_win_pct_l10,h2h_gf_avg_l10,win_pct_l5,win_pct_l10,win_pct_l20,gf_avg_l5,gf_avg_l10,gf_avg_l20,ga_avg_l5,ga_avg_l10,ga_avg_l20,elo,fifa_rank,fifa_points
```

**`research_ready_dataset/ml_match_features.csv`** (header row 1):
```
match_id,date,team_id_home,team_id_away,team_home,team_away,tournament,stage,elo_diff,fifa_rank_diff,fifa_rank_ratio,form_diff_last_5,form_diff_last_10,form_diff_last_20,goals_for_diff,goals_against_diff,h2h_win_pct_diff,h2h_goal_diff,days_rest_diff,wc_experience_diff,streak_diff,neutral_flag,stage_weight,rivalry_flag,home_field,elo_trend_diff,rank_trend_diff,goal_trend_diff,attack_rating_diff,defense_rating_diff,net_rating_diff,pedigree_diff,strength_ratio,relative_strength,elo_expected_home,upset_proxy,elo_diff_x_stage,elo_diff_x_homefield,formdiff10_x_elodiff,rankratio_x_formdiff10,restdiff_x_stage,netrating_x_homefield,pedigree_x_stage,elo_home,elo_away,fifa_rank_home,fifa_rank_away
```

**`research_ready_dataset/feature_importance_precheck.csv`** (header row 1):
```
rank,feature,corr_goaldiff,mutual_info,missing_pct,variance,leakage_risk,signal_score
```

**`fifa_wc_data/raw/elo/elo_ratings.csv`** (header row 1):
```
date,code,team,elo,elo_change
```

**`fifa_wc_data/raw/fifa_rankings/fifa_rankings.csv`** (header row 1):
```
date,team,ranking,points
```

**`fifa_wc_data/raw/odds/odds_bank_raw.csv`** (header row 1):
```
match_id,league,match_date,home_team,home_score,away_team,away_score,avg_odds_home_win,avg_odds_draw,avg_odds_away_win,max_odds_home_win,max_odds_draw,max_odds_away_win,top_bookie_home_win,top_bookie_draw,top_bookie_away_win,n_odds_home_win,n_odds_draw,n_odds_away_win
```

---

## 11. Highest ROI Actions (Prioritized for AI Sprint Planning)

| Rank | Action | Expected Impact | Effort | Pre-train Required? |
|---|---|---|---|---|
| 1 | **Refresh FIFA rankings 2024→2026** | Eliminates 2-year staleness in all models | 2–4 hrs | **Yes** |
| 2 | **Fix team-name normalization (`dim_team` pass)** | Prevents silent join failures across ELO, odds, rankings | 2–3 hrs | **Yes** |
| 3 | **Harvest recent odds 2016→2026** | Enables market calibration & value detection | 1–2 days | **Yes** |
| 4 | **Compute per-match ELO or source full series** | Sharpens strength signal; removes year-end bluntness | 1 day | **Yes** |
| 5 | **Compute travel distances + timezone shifts** | Real physiological context; computable from existing data | 2–3 hrs | No |
| 6 | **Integrate official squads (caps, age, club quality)** | Lineup-aware strength replaces squad averages | 1 day | **Yes** |
| 7 | **Add weather forecasts (OpenWeather API)** | Easy environmental context for all 2026 fixtures | 2–3 hrs | No |
| 8 | **Scrape Understat xG for all matches** | High research value; stable strength signal | 2–3 days | **Yes** |
| 9 | **Build referee history DB** | Medium lift; real impact on cards/corners | 1 day | No |
| 10 | **Unblock FBref/Transfermarkt (Playwright)** | Richest data layer (xG, injuries, club form) | 2–3 days | **Yes** |

---

## 12. Validation Gates (Go/No-Go Criteria)

### MVP Gate (End of Week 2)
- [ ] FIFA rankings refreshed to 2026
- [ ] Travel distances computed
- [ ] LightGBM + CatBoost trained on Tier 1 features
- [ ] Model beats Elo baseline on walk-forward test (2018 & 2022 WCs)
- [ ] Dixon-Coles generates plausible scoreline distributions
- [ ] Monte-Carlo simulation outputs WC 2026 win probabilities

### Research Gate (End of Week 12)
- [ ] Tier 2 features implemented (xG, PPDA, Field Tilt, cohesion, weather)
- [ ] HIGFormer or Transformer prototype trained
- [ ] GNN/Transformer demonstrates ≥2% log-loss improvement over GBDT baseline
- [ ] Feast feature store deployed (offline + online)
- [ ] Calibration layer (Isotonic) fitted and validated
- [ ] Tournament simulation backtested on 2010, 2014, 2018, 2022

### Betting Gate (End of Week 24)
- [ ] Pinnacle / sharp bookmaker odds feed ingested in real-time
- [ ] Shin overround removal engine operational
- [ ] EV engine calculates positive expected value bets
- [ ] Paper-trading demonstrates positive CLV over ≥500 bets
- [ ] Kelly criterion staking implemented with drawdown circuit breakers
- [ ] Automated execution pipeline places orders via REST API

---

## 13. Core Principles for AI Implementation

1. **Data > Architecture.** A LightGBM with live rankings and recent odds beats a HIGFormer with stale features.
2. **Time-based splits only.** Never shuffle. Use expanding windows. Chronology is causality.
3. **Leakage is the silent killer.** Automate temporal, lineup, and target boundary checks in CI.
4. **The market is the benchmark.** Any model without odds comparison is a research toy, not a betting system.
5. **Ship the baseline first.** Generate WC 2026 win probabilities with Elo + LightGBM + Monte Carlo before adding deep learning.
6. **Positive CLV is the only metric that matters.** Accuracy, log-loss, and RPS are intermediate diagnostics. EV and CLV are the final exam.

---

*End of Document.*

**Generated for:** AI-assisted planning and code generation.  
**Source material:** Existing worldCup project files (`README.md`, `SCHEMA.md`, `INVENTORY_REPORT.md`, `DATA_BANK_UPDATE.md`, audit reports, CSV samples) + research corpus (`research1.txt`, `research2.txt`).  
**Next step for AI:** Use this document as the system prompt context for generating implementation code, data pipelines, or model training scripts.
