# PROMPT FOR OPENCODE (copy everything below the line into opencode)

---

You are an autonomous coding agent working on a FIFA World Cup 2026 prediction system at
`C:\Users\HP\OneDrive\Desktop\worldCup`. The tournament is LIVE (group stage until June 27,
final July 19) so ship working increments, not perfection.

## STEP 0 — Required reading (do this before any code)
1. `TODO_FOR_OPUS.md` — state of the repo, conventions, traps (section D is critical).
2. `MASTER_ML_ROADMAP.md` — full specs; referenced below as "roadmap §N".
3. `PROJECT_STATUS.md` §10 — data gaps (do NOT attempt the scraping tasks; a human does those).
4. Run `python src/track.py update` and open `dashboard/progress.html` to see live state.

## HARD RULES — violating any of these makes results worthless
- Class order is ALWAYS `[home_loss, draw, home_win]` = indices [0,1,2] in every proba array.
- Chronological splits only: train ≤ 2011-01-17 < val ≤ 2018-10-11 < test. Use the existing
  `split` column. NEVER random splits. NEVER train on data dated after what you predict.
- Team names: always map through `research_ready_dataset/team_mapping.csv` (raw → canonical).
- Never use as features: gf, ga, result, points, home_score, away_score, attendance, outcome.
- Every model run appends a row to `research_ready_dataset/experiments.csv` (see header) and
  calls `python src/track.py done <TASK_ID> "<one-line result>"` (or `track.py log "..."`).
- Use system `python` (3.13: pandas/numpy/sklearn/scipy/joblib present). The conda env
  `C:\Users\HP\anaconda3\envs\minorproject\python.exe` is ONLY for Playwright scraping — you
  should not need it.
- Git: work on branch `opencode/sprint34` (create from main). One commit per completed task,
  message = task id + result numbers. Push the branch. NEVER commit: files >5 MB, `models/`,
  `artifacts/`, `fifa_wc_data/raw|db|processed` (gitignored anyway), secrets/tokens.
- Do not modify: existing rows of experiments.csv, the split boundaries, `m4_*.pkl` /
  `ensemble_v1.pkl` (create new versions instead), or any file under `fifa_wc_data/raw/`.
- numpy 2.x: `np.math` does not exist (use `import math`). Windows paths: use `pathlib`
  via `src/common.py` (ROOT, DB_PATH, get_logger). Wikipedia requires a browser User-Agent
  (use `common.polite_get`, see `src/s14_wc2026_squads.py` for the pattern).
- If blocked on a task for >30 minutes, write the blocker into `HANDBACK_REPORT.md` and move
  to the next task. A documented skip beats a broken hack.

## TASKS — do in this order

### TASK 1 (id: LIVE) — `src/live_update.py`  [URGENT]
Per-matchday update loop. Roadmap §8.
1. Fetch scores: primary `https://fixturedownload.com/feed/json/fifa-world-cup-2026`;
   it LAGS (verified), so also parse Wikipedia pages `2026_FIFA_World_Cup_Group_A` … `_L`
   (pd.read_html on `common.polite_get(...).text`) and take whichever source has more
   final scores per match.
2. Upsert scores into `wc2026_fixtures` (HomeTeamScore/AwayTeamScore) and into `matches`
   (match rows for WC2026 group games already exist with NULL scores — match them on
   date + canonical home/away; update home_score/away_score).
3. For each NEWLY ingested result, update the `elo_current` table using `k_factor` and
   `goal_mult` imported from `src/m1_elo_davidson.py` (K=60, home adv only for USA/Mexico/
   Canada as home team).
4. Re-run the simulator: `from m8_simulate import main as sim; sim()` (it locks played
   matches and appends `artifacts/prediction_history.csv` automatically).
5. Compute realized surprisal for played matches: I = −ln p(observed) using the
   `match_probs` of the PREVIOUS run (artifacts dir is timestamped — use the latest run
   before this one). Append rows to `artifacts/realized_surprisal.csv`
   (ts, match_number, home, away, outcome, p_outcome, surprisal).
6. `python src/track.py log "live update: N new results, champion now X%"`.
ACCEPTANCE: running it twice in a row is a no-op (no duplicate ELO updates — track ingested
match_numbers in a state file `artifacts/ingested.json`). Test with a fake injected score
(then revert): champion probs must change.

### TASK 2 (id: PENS) — penalty model from real data
`fifa_wc_data/raw/kaggle/international-football-results-from-1872-to-2017/shootouts.csv`
exists on disk. Compute empirical shootout win rate for the higher-ELO team (join shootouts
to elo_match via date+teams+match). Replace the hardcoded `0.5 + 0.03*sign(elo_diff)` in
`src/m8_simulate.py` with the fitted relationship (e.g. logistic on elo_diff, or binned
constant — whichever the data supports; document in ledger note). Rerun m8.
ACCEPTANCE: ledger row with the fitted numbers; top-5 champion probs shift < 2pp (sanity).

### TASK 3 (id: m9) — `src/m9_entropy.py` entropy engine
Implement roadmap §5 EXACTLY (formulas are written there). Minimum scope:
- Table `entropy_match` (match_id, source, H, I, X) for sources: `davidson` (from
  `elo_match` + `davidson_params.json`, all matches since 1994) and `dixon`
  (from `research_ready_dataset/m4_probs.csv`, val+test era).
- `artifacts/chaos_history.json`: per World Cup 1994–2022 (filter matches.competition
  contains 'FIFA World Cup', not qualifiers): ΣI, ΣH, ΣX, top-5 highest-surprisal matches
  (davidson source). This is the "which WC was most chaotic" ranking.
- 2026 group chaos forecast: expected ΣH per group from the latest sim run's match_probs.
- Write `dashboard/entropy_data.js` (`window.ENTROPY = {...}`) and add an entropy section
  or page to the dashboard rendering: WC chaos ranking + 2026 group chaos + realized
  surprisal log (from artifacts/realized_surprisal.csv when present).
ACCEPTANCE: chaos_history.json has ≥ 7 tournaments; dashboard renders from file://.

### TASK 4 (id: BT22) — `src/bt_backtest.py` credibility backtest
Freeze data before 2022-11-20, predict WC2022:
- Refit Dixon-Coles with cutoff (reuse `fit_dc` from m4 with a filtered dataframe,
  ref_date=2022-11-20) and refit Davidson (ν, H) on the same window.
- Per-match: blend 0.5*DC + 0.5*Davidson probs for the 64 actual WC2022 matches
  (real fixtures/results are in `sb_matches` table, tournament='WC2022').
- Report log-loss vs the real closing odds (table `odds_implied_recent`,
  tournament='World Cup 2022', ~50 rows) on the overlapping matches.
- Simulate the actual tournament 20,000× (reuse m8 machinery if practical, else group-only
  + simple bracket) → champion probs. Write `artifacts/backtest_wc2022.json` with: our LL,
  market LL, champion top-10, P(Argentina champion), rank of Argentina.
ACCEPTANCE: ledger row; Argentina in top-5 of pre-tournament champion probs (if not,
report honestly — do not tune until it passes).

### TASK 5 (id: HIST + DASH) — dashboard extensions
- `track.py update` should additionally convert `artifacts/prediction_history.csv` into
  `dashboard/history_data.js` (window.HISTORY).
- Add to `dashboard/index.html`: champion-probability trajectory chart (one line per top-8
  team over run timestamps; plain SVG or CSS, no external libs) + realized-chaos marker on
  the existing gauge (cumulative ΣI from realized_surprisal.csv vs the p10–p90 band).
- New `dashboard/bracket.html`: R32 slot grid (from sim reach_r32 + the slot codes in
  wc2026_fixtures rounds 4) showing most-likely qualifier per slot with probability.
ACCEPTANCE: all pages render from file:// with no console errors (data via *.js files only,
NEVER fetch() of local json — CORS-blocked).

### TASK 6 (id: m10) — `src/m10_scorers.py` Golden Boot model
Roadmap §7. Data: `official_squads_2026` (1,246 players, caps, goals, position, club),
`goalscorers` (47k intl goals), `players` (FIFA attrs incl 'shooting'), latest sim run
(expected team goals). Steps: per-player share of team goals = empirical-Bayes-shrunk
career rate (goals/caps) toward position priors COMPUTED from goalscorers×squads history;
penalty-taker bonus from goalscorers.penalty; expected-minutes heuristic (top-11 by FIFA
overall start, bench ×0.35). Allocate each team's simulated tournament goals multinomially.
Output `artifacts/run_<ts>/scorers.json` (P(golden boot), E[goals], top 100) +
`dashboard/scorers_data.js` + a scorers section/page.
ACCEPTANCE: backtest on WC2022 (squads in `squads`/kaggle raw; team goals from sb_matches):
Mbappé and Messi must appear in the model's top-10 — report their exact ranks in the ledger.

### TASK 7 (id: ASK) — `src/ask.py` + `CLAUDE.md`
Roadmap §10. `ask.py` subcommands: predict <home> <away> [--stage --neutral], cup-odds
[--top N], group <A-L>, match <n>, scorers [--top N], chaos, status. ALL output = one-line
JSON to stdout, no prose. Reads ONLY latest `artifacts/run_*` + models/ (never retrains).
Resolve team names via team_mapping + difflib fuzzy match (error JSON if ambiguous).
`CLAUDE.md` at repo root: repo map, env rules, conventions (class order, splits, leakage),
artifact contracts, ask.py usage examples, "never invent probabilities — read artifacts".
ACCEPTANCE: `python src/ask.py cup-odds --top 5` and `predict Brazil Morocco` return valid
JSON (test with json.loads).

### TASK 8 (id: m3 + m5) — gradient-boosting upgrades (only after 1–7)
`pip install lightgbm`. m3: LGBMClassifier, 30-trial random search on val (param space in
roadmap §4-m3), sample_weight from v2. m5: two LGBM Poisson regressors (home/away goals) →
W/D/L via score matrix. Add both as level-0 inputs to a NEW stack `models/ensemble_v2.pkl`
(copy m6_stack.py → m6b; do not overwrite v1). KEEP v2 only if test LL ≤ 0.8543
(current 0.8563 − 0.002). Ledger rows for everything, including KILLs.

### TASK 9 (id: T0.2full) — odds_bank historical join (lowest priority)
Join `odds_bank` (479k rows, 2005-15) to `matches` on date±1 + canonical names; build table
`odds_implied` (proportional devig from avg_odds_*); report join rate + market LL on joined
rows (expect ~0.95–1.00; if >1.05 the join is wrong). Add p_*_mkt as meta-features with a
missing-indicator to the m6b stack; keep iff test LL improves ≥0.001.

## HANDBACK PROTOCOL (mandatory, last step)
Write `HANDBACK_REPORT.md` at repo root: for EVERY task — status (done/partial/skipped),
key numbers, files created/modified, deviations from spec + why, known issues, and the
exact commands to verify. Run `python src/track.py update`. Commit + push branch
`opencode/sprint34`. Do not merge to main — a reviewer (Claude) will verify, fix, and merge.
