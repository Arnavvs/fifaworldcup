# MASTER ML ROADMAP — FIFA World Cup 2026 Prediction System

*Written 2026-06-12 (day 2 of the tournament — group stage runs to June 27, final July 19).*
*Audience: any developer or LLM executing tasks from this document. Every task has exact
inputs, outputs, file paths, and acceptance criteria. Do tasks in order within a sprint;
sprints 2+ can be parallelized.*

---

## 0. How to use this document

- The system is built as **small, single-purpose Python modules** in `src/` (existing
  convention: `s##_*.py` = data stages, `r#_*.py` = research phases, `m#_*.py` = models).
- Two Python environments exist. Use the right one:
  - **System Python 3.13** (`python` on PATH): pandas 2.2.3, numpy 2.2.4, sklearn 1.7.2,
    requests, bs4. Use for ALL modelling and feature work.
  - **Conda env `minorproject`** (`C:\Users\HP\anaconda3\envs\minorproject\python.exe`,
    Py 3.11): has playwright + stealth helpers. Use ONLY for scraping
    (`data_collection_pipeline/`).
- Shared infra: `src/common.py` (paths, logging, `polite_get`, checkpoints). Import it.
- Every experiment gets a row in `research_ready_dataset/experiments.csv` (schema §12.3).
  Ideas are **kept or killed by test numbers, never by opinion**.
- Canonical class order everywhere: `["home_loss", "draw", "home_win"]` → indices 0/1/2.
- Time rule: **never train on data dated after what you predict.** All splits chronological.

### Current verified baselines (2026-06-12, `src/m0_baseline_sanity.py`, test = ~2010→2026, n=7,383)

| model | log-loss ↓ | Brier ↓ | accuracy |
|---|---|---|---|
| ELO-only logistic | 1.0397 | 0.6260 | 0.488 |
| Logistic (39 features) | 0.8838 | 0.5190 | 0.599 |
| HistGradientBoosting | 0.8823 | 0.5183 | 0.598 |
| **Blend (½LR+½GB)** | **0.8777** | 0.5155 | 0.600 |
| Blend + isotonic | 0.8811 | **0.5150** | 0.601 |

Notes: (a) every new model must beat **0.8777**; (b) isotonic *hurt* log-loss on the 7.4k-row
val set → prefer **temperature scaling** (§5.4); (c) uniform = 1.0986, so ELO-only is weak —
the engineered features carry real signal.

---

## 1. Asset inventory (what exists right now)

### 1.1 Database `fifa_wc_data/db/football.db` (27 tables)
Populated: `matches` 49,353 (1872→2026) · `team_match_features` 98,562 · `ml_match_features`
49,281×39 (leakage-safe) · `players` 18,127 (FIFA-game attrs) · `official_squads_2026` 1,246
(48 teams, caps+club) · `elo_ratings` 18,142 (year-end) · `fifa_rankings` 67,261 (1992→2024-04)
· `goalscorers` 47,601 · `odds_bank` 479,440 (closing 1X2, **2005–2015 only**) · `sb_matches`
128 + `starting_lineups` 2,816 + `sb_team_match_stats` 255 + `sb_player_match_stats` 1,757
(real StatsBomb xG, WC2018+2022) · `dim_team` 575 canonical teams · `venues` 16 (geocoded+altitude)
· `wc2026_fixtures` 104 · `wc_matches_history` 900 · `wc_tournaments` 21.
Empty (blocked sources): `injuries`, `odds`, `team_match_stats`, `player_match_stats`.

### 1.2 NOT yet integrated — `data_collection_pipeline/collected_data/` (second pipeline, June 2026)
| file | rows | content |
|---|---|---|
| `processed/travel_features.csv` | 752 | team×venue distance_km, timezone_delta, fatigue index, altitude_delta |
| `processed/weather_forecasts.csv` | 624 | venue×date temp/humidity (Open-Meteo) |
| `processed/squad_aggregates.csv` | 48 | mean/median age, caps, total goals per squad |
| `processed/manager_tenure.csv` | 48 | manager + tenure_years_at_wc |
| `processed/qualification_strength.csv` | 147 | qual position, pts, ppg |
| `processed/continental_form.csv` | 104 | confederation tournament form |
| `processed/fifa_rankings_updated.csv` | 210 | full table @2024-06-20 (freshest free) |
| `processed/shared_club_matrix.csv` / `cross_team_club_overlap.csv` | 48/1128 | squad club-chemistry |
| `raw/odds_international.csv` | 228 | **closing 1X2 for WC18/22, Euro20/24, Copa21** (OddsPortal via VPN) |
| `raw/odds_club_closing.csv` | 5,330 | club closing odds (calibration material) |
| `raw/understat_team_xg.csv` | 96 | club-season xG for context |

### 1.3 ML-ready exports `research_ready_dataset/`
`classification_dataset.csv` (49,281, target `home_win_draw_loss`, `split` col) ·
`regression_dataset.csv` (targets `home_goals`,`away_goals`) · `tournament_dataset.csv`
(104 fixtures w/ team strengths) · `feature_importance_precheck.csv` · `dim_team.csv` ·
`team_mapping.csv` · `baseline_metrics.json`.

### 1.4 Live feed
`https://fixturedownload.com/feed/json/fifa-world-cup-2026` — 104 fixtures, scores appear
post-match (verified lagging on day 2 → need fallback, see T4.2).

---

## 2. Target architecture

```
                        ┌─────────────────────────────────────────────┐
 DATA (db + csv) ─────► │ FEATURE BUILDER  src/f1_build_features.py   │──► features/match_features_v2.csv
                        └─────────────────────────────────────────────┘
                                            │
                 ┌──────────────────────────┼─────────────────────────┐
                 ▼                          ▼                         ▼
        MODEL ZOO (level 0)          GOALS MODELS               MARKET ANCHOR
        m1 elo_davidson              m4 dixon_coles             odds → implied probs
        m2 logreg                    m5 poisson_gbm             (where available)
        m3 gbm_classifier            (λ_home, λ_away)
                 │                          │                         │
                 └──────────────────────────┼─────────────────────────┘
                                            ▼
                        m6 STACKER (time-aware OOF) + m7 TEMPERATURE CALIBRATION
                                            │
              ┌─────────────────────────────┼──────────────────────────────┐
              ▼                             ▼                              ▼
   m8 TOURNAMENT SIMULATOR        m9 ENTROPY ENGINE              m10 SCORER MODEL
   (50k Monte-Carlo, 2026 rules)  (surprisal, chaos meter)       (Golden Boot)
              │                             │                              │
              └─────────────────────────────┼──────────────────────────────┘
                                            ▼
                          ARTIFACTS  artifacts/run_<ts>/ *.json
                                            │
                       ┌────────────────────┼────────────────────┐
                       ▼                    ▼                    ▼
              dashboard/ (HTML)      src/ask.py (CLI)     prediction_history.csv
                                     + CLAUDE.md          (live tracking)
                       ▲
                       └── m11 REALTIME LOOP src/live_update.py (per matchday:
                           ingest scores → update ELO/form → re-simulate → write artifacts)
```

---

## 3. WORKSTREAM A — Data preparation (Sprint 0)

### T0.1 Integrate second-pipeline features → feature store v2
**File:** `src/f1_build_features.py`. **Input:** `ml_match_features` + §1.2 files.
**Output:** `research_ready_dataset/match_features_v2.csv` (and DB table `match_features_v2`).
Steps:
1. Load `ml_match_features` (49,281 rows — keep all 39 existing features).
2. Join WC-2026-specific static features on canonical team (via `team_mapping.csv`):
   squad_aggregates (mean_age, mean_caps → `caps_diff`, `age_diff`),
   manager_tenure (`manager_tenure_diff`), qualification_strength (`qual_ppg_diff`),
   fifa_rankings_updated (override stale `fifa_rank_home/away` for matches after 2024-04;
   recompute `fifa_rank_diff`).
   These only exist for 2026 teams → for historical rows leave NaN (GBMs handle natively).
3. Travel/weather join keys for FUTURE fixtures only: `(team, venue_id)` → distance_km,
   tz_delta, altitude_delta; `(venue_id, date)` → temp_max_c, humidity. Add
   `travel_diff_km = home_travel − away_travel`.
4. Write CSV + table. **Acceptance:** row count == 49,281; new feature columns ≥ 10;
   re-run `m0_baseline_sanity.py` pointed at v2 → log-loss must NOT regress > 0.002.

### T0.2 Odds → implied probabilities table
**File:** `src/f2_odds_implied.py`. **Inputs:** `odds_bank` (2005-15),
`odds_international.csv` (228 recent). **Output:** table `odds_implied`
(`match_id, p_home_mkt, p_draw_mkt, p_away_mkt, overround, source`).
1. Devig two ways and store both: *proportional* p_i = (1/o_i)/Σ(1/o_j), and *Shin* (solve
   for insider proportion z by Newton iteration; see Shin 1993 — formula:
   p_i = (sqrt(z² + 4(1−z) (1/o_i)²/Σ(1/o_j)) − z) / (2(1−z)) normalised).
2. Join to `matches` by (date±1day, canonical home, canonical away) via `team_mapping.csv`.
   Expect ~60–70% join rate on the 2005-15 bank; log unmatched to `logs/odds_unjoined.csv`.
3. **Acceptance:** ≥ 25,000 matches with market probs; for joined rows, market log-loss
   computed against actual results must be < 1.00 (sanity that the join is correct —
   a *wrong* join gives ≈1.10).

### T0.3 Era weighting + final training protocol
Modern football ≠ 1930s. Add column `sample_weight = 0.5**(years_before_2026/10)`
(10-year half-life) to v2. All models accept it. Splits stay as-is (70/15/15 chrono).
**Final tournament models retrain on ALL labelled rows** with weights, after metrics
are locked on test.

### T0.4 Experiments ledger
Create `research_ready_dataset/experiments.csv` header:
`exp_id,date,module,model,features_desc,n_train,logloss_test,brier_test,rps_test,acc_test,ece_test,beats_baseline,decision,notes`
Every model run appends one row. Decision ∈ {KEEP, KILL, ITERATE}.

---

## 4. WORKSTREAM B — Model zoo (Sprint 0–1). Each = one file, one CLI, one ledger row.

Common interface (put in `src/model_base.py`):
```python
class MatchModel:
    name: str
    def fit(self, X: pd.DataFrame, y: np.ndarray, sample_weight=None): ...
    def predict_proba(self, X) -> np.ndarray  # (n,3) order [loss,draw,win]
    def predict_goals(self, X) -> tuple[np.ndarray, np.ndarray] | None  # (λh, λa) or None
    def save(self, path): ...  # joblib
    @classmethod
    def load(cls, path): ...
```

### m1 — ELO + Davidson draw (`src/m1_elo_davidson.py`)
First **rebuild per-match ELO** (we only have year-end): iterate `matches` chronologically,
R' = R + K·G·(W − W_e), W_e = 1/(1+10^(−ΔR_adj/400)), ΔR_adj = ΔR + 100·(home & !neutral),
K = 60 (WC), 50 (continental finals), 40 (qualifiers), 20 (friendlies);
G = 1 if margin ≤1, 1.5 if 2, (11+margin)/8 if ≥3. Start everyone at 1500, store
pre-match ELO per side → table `elo_match` (match_id, elo_home_pre, elo_away_pre).
Then Davidson (1970) draw model: with strength π_i = 10^(R_i/400) and draw parameter ν:
p_draw = ν·sqrt(π_h·π_a) / D, p_home = π_h/D, p_away = π_a/D, D = π_h + π_a + ν·sqrt(π_h π_a).
Fit ν (and a home multiplier γ on π_h) by max-likelihood on train (scipy.optimize.minimize).
**Kill criteria:** none — this is a permanent baseline + simulator engine.
**Acceptance:** test log-loss ≤ 1.00 (must beat the static-elo 1.0397 because per-match
ELO is fresher); `elo_match` covers ≥ 99% of matches.

### m2 — Regularised multinomial logistic (`src/m2_logreg.py`)
Exactly the sanity-run recipe (impute median → scale → LogisticRegression C grid
{0.1,0.3,0.5,1,3} chosen on val). Cheap, interpretable, stacker input. KEEP always.

### m3 — Gradient-boosted classifier (`src/m3_gbm.py`)
HistGradientBoostingClassifier now; `pip install lightgbm xgboost catboost` is task T1.0 —
then LightGBM `objective=multiclass num_class=3`, tune on val via 30-trial random search over
`learning_rate∈[0.02,0.1] num_leaves∈{31,63,127} min_child_samples∈{20,50,100}
feature_fraction∈[0.6,1.0] reg_lambda∈[0,5] n_estimators early-stopped`.
**Kill criteria:** any of the three GBM libs that doesn't beat HistGB val LL by >0.001 → KILL
(keep one winner + HistGB fallback).

### m4 — Dixon-Coles (`src/m4_dixon_coles.py`) — the football gold standard
Independent-Poisson with low-score correction τ and exponential time decay.
λ_home = exp(μ + α_h − β_a + γ_home·(1−neutral)), λ_away = exp(μ + α_a − β_h).
Likelihood per match: τ(x,y)·Pois(x;λ_h)·Pois(y;λ_a) where
τ = 1−λ_h λ_a ρ if (0,0); 1+λ_h ρ if (1,0); 1+λ_a ρ if (0,1); 1−ρ if (1,1); else 1.
Weight each match by φ(t) = exp(−ξ·days_before_now), ξ = 0.0019 (≈1-year half-life;
also try ξ ∈ {0.001, 0.003} on val). Fit α,β per team (only teams with ≥30 matches since 2000;
others map to confederation-mean dummy), μ, γ, ρ by L-BFGS. Outputs both probs (sum the
score matrix 0..10) and (λ_h, λ_a) → **this is the simulator's goal engine**.
**Acceptance:** test LL ≤ 0.92; λ calibration: mean predicted goals within 5% of actual on test.

### m5 — GBM Poisson goals (`src/m5_poisson_gbm.py`)
Two LightGBM `objective=poisson` regressors (home_goals, away_goals) on v2 features.
Derive W/D/L probs via independent-Poisson score matrix. Compare vs m4 on test:
keep both if each beats 0.95 LL (diversity helps the stack), else kill loser.

### m6 — Stacker (`src/m6_stack.py`)
1. Generate **out-of-fold** level-0 predictions with 5 expanding-window chronological folds
   (fold k trains on all data before its window, predicts the window — no leakage).
2. Meta-features per match: logit(p) of each model's 3 classes (drop one per model for
   collinearity), + stage_weight, neutral_flag, elo_diff, and `p_*_mkt` where present
   (NaN→median-impute; market column doubles as anchor when odds exist).
3. Meta-learner: multinomial LogisticRegression (C=1.0). Also try LightGBM-meta; keep winner.
**Acceptance:** test LL < min(level-0 LLs) − 0.005, and < 0.8777.

### m7 — Calibration (`src/m7_calibrate.py`)
**Temperature scaling** (single T>0 minimising val NLL on stacker logits) — preferred per
M0 evidence. Also fit vector scaling (per-class T). Report ECE (15 equal-mass bins) before/
after; produce `artifacts/calibration_plot_data.json` (bin centers, observed freq, n).
**Acceptance:** ECE_test ≤ 0.02; LL not worse than uncalibrated by > 0.001.

### Try-and-eliminate backlog (run AFTER m1–m7, one ledger row each)
ordered-logit on elo_diff (draws as middle category) · Skellam regression ·
Bradley-Terry-Davidson with recency · CatBoost w/ team_id categorical ·
kNN "historical analogue" (50 nearest in (elo_diff, form_diff) space) ·
bivariate Poisson (Karlis-Ntzoufras shared-λ3) · FT-Transformer (**expected KILL** at 50k rows
— run once for the ledger) · conformal prediction sets (keep as uncertainty layer, not predictor).

---

## 5. WORKSTREAM C — ENTROPY ENGINE (`src/m9_entropy.py`) — Sprint 2
*Formalising the user's core idea: "entropy = anything going not according to probability."*

### 5.1 Definitions (implement exactly)
For match m with pre-match distribution p = (p_L, p_D, p_W) from source s and realized
outcome y ∈ {L,D,W}:
- **Pre-match entropy (how uncertain the match was):** `H_s(m) = −Σ_i p_i ln p_i` ∈ [0, ln3≈1.0986].
- **Realized surprisal (how shocking the result was):** `I_s(m) = −ln p_s(y)`.
  This is the user's entropy: chalk result → I≈0.3–0.7; big upset → I≥2.
- **Excess surprisal (chaos beyond expectation):** `X_s(m) = I_s(m) − H_s(m)`.
  Key property: if probabilities are honest, E[X]=0. Positive sums ⇒ more chaos than the
  probabilities implied (or a miscalibrated source).
- **Scoreline surprisal (fine-grained):** `I_score(m) = −ln P_DC(scoreline)` from m4's score
  matrix (Brazil 1–7 Germany ≈ 9+ nats).
- **Epistemic disagreement:** Jensen-Shannon divergence between sources
  `JSD(p_elo, p_ens, p_mkt) = H(mean) − mean(H)`. High JSD = sources disagree = the
  interesting matches (model edge or model error).

### 5.2 Sources (compute all, store side-by-side)
`elo` (m1) · `ensemble` (m6+m7) · `market` (T0.2, where odds exist) · `dixon_coles` (m4).
Table `entropy_match`: `match_id, source, H, I, X, I_score, jsd_all_sources`.

### 5.3 Aggregations & products
1. **Historical chaos table** (`artifacts/chaos_history.json`): for every WC 1994→2022
   (rankings exist from '93), per tournament: ΣI, ΣH, ΣX, mean JSD, top-5 most shocking
   matches. *Deliverable: a ranking — was 2002 really the most chaotic WC? Now provable.*
2. **Group chaos forecast** (pre-play): for each 2026 group, expected ΣH over its 6 matches
   → "tightest group" ranking for the dashboard.
3. **Live chaos meter**: cumulative ΣI of played 2026 matches vs the simulator's expected-ΣI
   distribution (compute ΣI percentile across the 50k sims) → "WC2026 is running at the
   Pth percentile of chaos." Update each matchday.
4. **Team volatility feature** (feeds back into v3 features): rolling mean I over a team's
   last 20 matches (ensemble source) = "does this team systematically defy predictions?"
   Test as feature: KEEP iff stacker val LL improves ≥0.001.
5. **Upset radar**: matches where JSD(ensemble, market) > 0.02 → list with both probs
   (these are candidate value spots / model-error checks).

### 5.4 Calibration use
If backtest mean X > 0.01 → ensemble is overconfident → raise temperature T until mean X ≈ 0
on val. This ties the entropy engine into m7 — chaos accounting IS calibration auditing.

### 5.5 Simulation temperature (chaos-aware Monte-Carlo)
Fit the distribution of tournament-level mean-X across historical WCs (expect small spread,
fit Normal(μ_X, σ_X)). In each simulated tournament draw χ ~ that Normal and flatten every
match distribution: `p_i^(χ) ∝ p_i^(1/(1+χ))`. Effect: some simulated tournaments are
"chaotic editions". **Acceptance test:** simulator's upset-rate distribution (matches won by
the <35% side) must cover the historical per-WC upset rates within its 10–90 band.

---

## 6. WORKSTREAM D — Tournament simulator (`src/m8_simulate.py`) — Sprint 1

### 6.1 2026 format (hardcode exactly)
48 teams, 12 groups (A–L) of 4 → round robin (72 matches). Advance to R32: group winners (12)
+ runners-up (12) + **8 best third-placed**. Group ranking tiebreakers in order: points → GD
→ goals scored → head-to-head points among tied → h2h GD → h2h goals → fair-play points
(skip; use) → random draw. Third-place ranking: points → GD → goals → drawing of lots
(random in sim). Knockout: R32 (16) → R16 (8) → QF (4) → SF (2) → third-place + Final
(2026-07-19). Bracket mapping: parse from `wc2026_fixtures` RoundNumber + placeholder strings
("1A", "2B", "3C/D/F..."); the thirds-allocation table depends on which groups supply thirds —
v1 may allocate thirds to slots randomly subject to the feed's allowed-group constraints
(document as approximation; refine v2 with FIFA's official allocation table).

### 6.2 Per-match engine
Group + knockout 90': sample score from m4's Dixon-Coles matrix using λ from the **ensemble-
blended** strengths (λ scaled so the implied W/D/L matches m7 calibrated probs: solve scalar
s on λ_h,λ_a by bisection so P_matrix(win) = p_win_cal; clip s∈[0.5,2]).
Knockout if draw after 90': extra time = Poisson with λ/3 each side; still level → penalties:
p_home_win_pens = 0.5 + 0.03·sign(elo_diff) (v1; refine with historical shootout data from
`shootouts.csv` in kaggle raw — task backlog).
Apply chaos temperature χ per simulated tournament (§5.5).

### 6.3 Outputs (N = 50,000 sims, seed=2026, ~run as single process w/ numpy vectorised groups)
`artifacts/run_<UTCts>/sim_results.json`:
```json
{"meta": {"n_sims": 50000, "as_of": "...", "played_matches_locked": 5},
 "champion": {"Spain": 0.143, ...}, "reach_final": {...}, "reach_sf": {...},
 "reach_qf": {...}, "reach_r16": {...}, "reach_r32": {...},
 "group_tables_expected": {"A": [{"team": "Mexico", "exp_pts": 5.8, "p_win_group": 0.47,
                                  "p_advance": 0.83}, ...]},
 "match_probs": [{"match_number": 1, "home": "Mexico", "away": "South Africa",
                  "p": [0.18, 0.27, 0.55], "exp_goals": [1.6, 0.8]}],
 "chaos": {"expected_total_surprisal": 96.4, "p10": 88.1, "p90": 105.2}}
```
**Played matches are locked to their real result** in every sim (this is what makes
predictions update as the tournament runs).
**Acceptance:** champion probs sum to 1±0.001; every qualified team has P(advance)>0;
re-running with same seed reproduces identical output; runtime < 10 min.

### 6.4 Backtest the whole stack (T1.6 — the credibility test)
Freeze data before 2022-11-20, simulate WC2022 50k times → compare: champion probs
(Argentina should be top-4 likely), per-match LL vs the 228-row real odds file, and
realized-vs-expected chaos. Write `artifacts/backtest_wc2022.json` + a ledger row.
Repeat for 2018. **This is the report card that says the system works.**

---

## 7. WORKSTREAM E — Scorer / Golden Boot model (`src/m10_scorers.py`) — Sprint 4

Data: `official_squads_2026` (1,246 players, caps, goals, club, position) ·
`goalscorers` (47,601 intl goals w/ minute/penalty) · `sb_player_match_stats` (WC18/22 xG)
· `players` (FIFA attrs incl. `shooting`).
1. **Player goal share**: career intl goals/cap with empirical-Bayes shrinkage toward
   position prior (priors: FW 0.42 goals/match share-of-team, AM/W 0.25, CM 0.10, DF 0.04,
   GK 0.001 — recompute from goalscorers×squads history, don't trust these constants).
   Blend with FIFA `shooting` percentile (weight 0.3) for low-cap players.
2. **Penalty taker flag**: player's share of team's penalty goals in `goalscorers` ≥ 0.5
   → +0.08 share bonus.
3. **Expected minutes**: v1 heuristic — top-11 by FIFA `overall` per team start, decay
   bench by 0.35; refine with WC18/22 `starting_lineups` repetition rates.
4. **Simulation**: inside each m8 sim, each team's goals in each match are distributed
   multinomially over players by share×minutes. Aggregate 50k sims →
   `artifacts/run_<ts>/scorers.json`: P(golden boot), E[goals], P(≥1 goal in next fixture)
   per player (top 100).
5. **Backtest acceptance:** rerun on WC2022 frozen data — Mbappé/Messi must land in the
   model's pre-tournament top 10; report rank of actual top-5 scorers in the ledger.

---

## 8. WORKSTREAM F — Real-time engine (`src/live_update.py`) — Sprint 3 (URGENT: tournament is live)

Loop (manual run after each matchday, or Windows Task Scheduler every 6h:
`schtasks /create /tn WC26Update /tr "python C:\...\src\live_update.py" /sc hourly /mo 6`):
1. **Ingest**: poll fixturedownload feed; ALSO scrape Wikipedia
   "2026 FIFA World Cup Group A..L" result tables (`pd.read_html`, UA header) as fallback
   since the feed lags (verified 2026-06-12). New final scores → upsert into `matches` +
   `wc2026_fixtures`, set `status='played'`.
2. **Update state**: per-match ELO update (m1 K=60 rule) for the played match; recompute the
   two teams' rolling-form features; recompute group standings.
3. **Re-predict**: load frozen m1–m7 artifacts (NO retraining mid-tournament — fit is frozen,
   *features* move); regenerate match probs for all unplayed fixtures.
4. **Re-simulate**: m8 with played-matches locked → new `artifacts/run_<ts>/`.
5. **Track**: append every unplayed fixture's current probs + champion probs to
   `artifacts/prediction_history.csv`
   (`ts, match_number|CHAMPION, team/home, away, p_loss, p_draw, p_win | p_champion`) —
   this powers the dashboard's "probability trajectories" chart, the single coolest artifact.
6. **Entropy live**: compute realized I for the new results, update chaos meter (§5.3.3).
**Acceptance:** running it twice in a row without new results is a no-op (idempotent);
a simulated fake result (test fixture) flows through to changed champion probs.

---

## 9. WORKSTREAM G — Dashboard (`dashboard/`) — Sprint 5

Static site, **zero build step**: plain HTML + Chart.js CDN + `fetch('data/*.json')`.
Deploy = copy latest `artifacts/run_<ts>/*.json` → `dashboard/data/` (done by live_update
step 7) and push to GitHub Pages (`gh-pages` branch or `/docs`).
Pages and their data contracts:
- `index.html` — champion-odds bar chart (top 15) + chaos gauge + next-matchday cards.
  Reads `sim_results.json`, `chaos_live.json`.
- `groups.html` — 12 group tables: current real pts + P(win group)/P(advance) bars.
- `bracket.html` — knockout tree with per-slot most-likely team + prob (from
  `reach_*` fields).
- `matches.html` — every fixture: our p vs market p (where odds), exp goals, JSD badge,
  after-the-fact realized surprisal I.
- `scorers.html` — golden-boot table (from `scorers.json`).
- `entropy.html` — tournament chaos meter (percentile gauge), per-match surprisal log,
  group-chaos ranking, historical WC chaos ranking (`chaos_history.json`).
- `history.html` — line chart of P(champion) over time per team from
  `prediction_history.csv` (convert to JSON in live_update step 7).
- `model.html` — backtest metrics table (from `experiments.csv` → JSON), calibration plot.
**Acceptance:** opens from `file://` with no console errors; all numbers traceable to one
artifacts run id shown in the footer.

---

## 10. WORKSTREAM H — LLM / Claude interface — Sprint 6

### 10.1 `src/ask.py` — deterministic CLI any LLM can call
```
python ask.py predict <home> <away> [--stage group|r32|r16|qf|sf|final] [--neutral]
python ask.py cup-odds [--top 20]
python ask.py group <A..L>
python ask.py match <match_number>
python ask.py scorers [--top 20]
python ask.py chaos
python ask.py status            # data freshness, last run id, played count
```
All output **single-line JSON** to stdout (no prose), reading ONLY the latest
`artifacts/run_*/` (never retrains; team names resolved through `team_mapping.csv`,
fuzzy-match with `difflib.get_close_matches`, error JSON if ambiguous).
Example: `{"home":"Brazil","away":"Morocco","p":[0.14,0.22,0.64],"exp_goals":[1.9,0.8],
"H":0.89,"sources":{"elo":[...],"market":null},"run_id":"run_20260613T0400"}`

### 10.2 `CLAUDE.md` (repo root)
Contents (write it, don't defer): repo map, the two Python envs, "to answer prediction
questions run `python src/ask.py ...`", artifact schema summary, the class-order convention,
the never-train-on-future rule, where experiments.csv is, and "report numbers from artifacts;
never invent probabilities." This makes any Claude Code session instantly productive.

---

## 11. Group-stage extras (cheap wins, backlog)
Per-matchday picks file (most-likely scoreline per fixture) · P(group finishing order) exact
permutations (4!=24, computable from sims) · "team of the group stage" via player xG once
FBref unblocks · qualification scenarios ("X advances if...") — derivable by conditioning
sims on hypothetical results (filter the 50k sims, no new code).

---

## 12. Evaluation protocol (applies to every workstream)

### 12.1 Metrics (implement once in `src/metrics.py`)
log-loss · multiclass Brier · **RPS** `mean over matches of Σ_k (CDF_pred(k)−CDF_true(k))²/2`
(ordinal: loss<draw<win) · ECE (15 equal-mass bins, max-prob version) · accuracy.
Always on the chronological test split; report `2010+` subset too.

### 12.2 The bars
| bar | value | source |
|---|---|---|
| must beat | **0.8777 LL** | M0 blend |
| good | ≤ 0.86 | typical strong intl model |
| market-grade | ≈ 0.84–0.88 | compute exactly from T0.2 joined rows |
| ELO floor | 1.0397 | M0 |

### 12.3 Ledger discipline
One row per experiment in `experiments.csv` (schema §3/T0.4). An idea without a ledger row
doesn't exist. KILL is a success outcome — record why, so no idea is retried twice.

---

## 13. Sprint plan (each task ≈ one focused LLM session)

| sprint | tasks | deliverable | done-when |
|---|---|---|---|
| **0** (now) | T0.1–T0.4, T1.0 (pip install lightgbm xgboost catboost) | features v2 + odds joined + ledger | baselines re-run on v2, no regression |
| **1** | m1, m4, m3-tuned, m5, m6, m7, T1.6 backtests | calibrated ensemble + WC2022/18 backtest report | test LL < 0.87, backtest jsons exist |
| **2** | §5 entropy engine, chaos history, volatility feature test | `entropy_match` table + `chaos_history.json` | historical WC chaos ranking renders |
| **3** | m8 simulator + live_update.py | first real `artifacts/run_*` + champion odds | fake-result test passes; runs on schedule |
| **4** | m10 scorers + WC2022 scorer backtest | `scorers.json` | Mbappé/Messi top-10 check |
| **5** | dashboard 8 pages | GitHub Pages live | opens from file://, footer run-id |
| **6** | ask.py + CLAUDE.md + README refresh | LLM interface | `ask.py cup-odds` returns valid JSON |
| weekend (user) | data: FBref/TM via stealth+VPN, OddsPortal WC-qualifier odds backfill | richer v3 features | new ledger rows justify retrain |

Order matters for 0→1→3 (the live tournament needs the loop ASAP); 2/4/5/6 parallelise.

---

## 14. Honest limitations (so nobody oversells)
- No injuries/lineups for 2026 yet → player-availability blind. Scorer model uses heuristic
  minutes. Mitigation: weekend scraping + manual squad-news overrides file
  (`data/availability_overrides.csv`: player, status, weight).
- FIFA rankings frozen at 2024-06 → `fifa_rank_*` features are ~2 yrs stale for 2026 rows;
  the per-match ELO (m1) is our freshness engine. Don't double-trust rank features.
- Market probs exist for only a slice of history → market column is an anchor feature with
  high missingness, and the "market-grade" bar is computed on a biased (big-match) subset.
- Draw prediction is the hardest class (~23% base rate, all models under-predict it) —
  watch per-class recall in the ledger.
- 48-team format is NEW — no historical 12-group/best-thirds precedent; simulator's
  third-place allocation is an approximation until the official table is encoded.
```
END OF ROADMAP
```
