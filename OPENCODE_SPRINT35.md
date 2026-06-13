# PROMPT FOR OPENCODE — Sprint 35 (player-data models, ELO fix, live scorecard, cleanup)

---

You are an autonomous coding agent on a **live** FIFA World Cup 2026 prediction system at
`C:\Users\HP\OneDrive\Desktop\worldCup`. Group stage is in progress. Ship working increments.

## STEP 0 — Required reading (before any code)
1. `CLAUDE.md` (root) — conventions, env split, artifact contracts. **Authoritative.**
2. `OPENCODE_PROMPT.md` — the previous sprint's HARD RULES still apply verbatim.
3. `MASTER_ML_ROADMAP.md` — model specs ("roadmap §N" below).
4. Run `python src/track.py update`, open `dashboard/progress.html`, read
   `research_ready_dataset/experiments.csv` (the ledger) to see current state.
5. Read `scrapers/sofascore_players_integrate.py` — it already built the player-rating
   DB tables you will consume. Do **not** re-scrape (that needs the Playwright conda env;
   a human runs it). The data is already in the DB.

## HARD RULES (unchanged — violating any makes results worthless)
- Class order is ALWAYS `[home_loss, draw, home_win]` = indices [0,1,2] in every proba array.
- Chronological splits only: train ≤ 2011-01-17 < val ≤ 2018-10-11 < test. Existing `split`
  column is the source of truth. **NEVER** random splits. **NEVER** train on data dated after
  what you predict.
- Team names: always map through `research_ready_dataset/team_mapping.csv` (raw → canonical).
  SofaScore names differ ("Korea Republic" vs "South Korea", "Türkiye" vs "Turkey", "USA" vs
  "United States") — extend `team_mapping.csv` with any new aliases you hit; never hardcode.
- Never use as features: gf, ga, result, points, home_score, away_score, attendance, outcome.
- Every model run appends a row to `research_ready_dataset/experiments.csv` and calls
  `python src/track.py done <TASK_ID> "<result>"` (or `track.py log "..."`).
- System `python` (3.13: pandas/numpy/sklearn/scipy/joblib) for ALL ML. The conda env is
  ONLY for Playwright — you should not need it.
- Git: branch `opencode/sprint35` (create from `opencode/sprint34`). One commit per completed
  task; message = `<TASK_ID>: <result numbers>`. NEVER commit: files >5 MB, `models/`,
  `artifacts/`, `fifa_wc_data/raw|db|processed`, secrets, the ~40MB raw scrape under
  `scrapers/sofascore_*/` (already gitignored).
- Do NOT overwrite `models/ensemble_v1.pkl` or `m4_*.pkl` — create new versioned files.
- If blocked >30 min, write the blocker into `HANDBACK_REPORT.md` and move on.

## ⚠️ THE ONE NEW RULE THAT MATTERS MOST — player-rating leakage
SofaScore `attribute-overviews` ratings reflect a player's quality **today**. Their history
only goes back `yearShift` 0–3 years. Therefore:
- **You may NOT** add player-rating features to the historical ensemble (`m6_stack`) and
  report a 2011/2018-split backtest — that is leakage (2026 ratings predicting 2015 matches).
  The 0.857 historical backtest must stay clean and comparable.
- Player ratings are valid ONLY for **contemporaneous** matches. So the player-data model is a
  **WC2026 / recent-form** model, validated on recent internationals (≥ 2024-01-01) and on the
  live WC2026 results as they arrive — NOT on the 2011/2018 split.
- Keep two clearly separated tracks (see TASK 3). Never mix their evaluation numbers.

---

## TASKS — do in this order

### TASK 1 (id: ELO-HOST) — fix the host/underrating problem
**Why:** On the 4 played matches the model went 2/4 (mean outcome log-loss 0.934 vs its 0.857
standard). The misses were both CONCACAF hosts: **USA 4-1 Paraguay** (model had USA at 34% with
1.22 xG) and **Canada 1-1 Bosnia** (model had Canada 62%). Host advantage *is* applied in
`m8_simulate.py` (`HOSTS={"USA","Mexico","Canada"}`, neutral=0), but USA's **base ELO is too
low** for a host, and a single regular-home boost (`home_adv` H≈80–100) under-credits a World
Cup host nation playing at home in front of a massive crowd.

Do, in `src/m1_elo_davidson.py` + `src/m8_simulate.py` (and a new `src/m1b_host_calib.py`):
1. **Quantify host overperformance empirically.** From `matches`, build the set of historical
   World Cup **host** matches (host nation playing at home in its own WC: 1990–2022; the host
   per tournament is known — hardcode the 8–9 hosts with their years, it's a tiny fixed list).
   Fit the extra ELO points a host earns *beyond* the normal `home_adv` by maximising Davidson
   likelihood on those matches only. Call it `host_bonus` (expect +40 to +120 ELO; report it).
2. In the simulator's `lambdas()` / Davidson call, when `home in HOSTS` use
   `dr = elo_diff + home_adv + host_bonus` (not just `home_adv`). Keep non-hosts neutral.
3. **Recency / form correction for stale base ELO.** Add an optional `elo_form` adjustment:
   for each WC2026 team, blend their stored `elo_current` 85% with a recent-form ELO computed
   from their last 10 internationals (2024–2026, already in `matches` after live updates),
   15% weight. Document the blend; make the weight a top-of-file constant.
4. Re-fit Davidson (`nu`, `home_adv`) unchanged on the historical split (do NOT let host_bonus
   leak into the global fit — it is an additive term applied only to host rows).
5. Re-run `python src/m8_simulate.py`. Report the BEFORE/AFTER champion top-5 and the
   before/after model probability for USA-Paraguay and Canada-Bosnia (retrodict with the
   pre-tournament ELO snapshot if available, else just report the new group odds).
**ACCEPTANCE:** ledger row with `host_bonus` value; simulator runs; USA's group-win and
champion probability strictly increase; write the before/after numbers into the ledger note.
Do **not** tune host_bonus to fit the 4 results — fit it on history, then report honestly.

### TASK 2 (id: PLR-FEAT) — squad-strength feature store from player ratings
Build `src/p1_player_features.py` that turns the scraped ratings into team-level features.
- Source tables (already populated): `sofascore_player_attributes` (year_shift=0 = current),
  `sofascore_team_strength` (squad avg by position group, GK-aware overall),
  `sofascore_player_career`.
- For each of the 48 WC2026 teams compute a feature vector:
  `gk_overall, def_overall, mid_overall, att_overall, squad_overall` (n-weighted),
  plus `att_attacking, def_defending, mid_creativity, top3_att_mean` (mean overall of the
  team's 3 best ATT players), and `squad_caps_total` (sum of national-team appearances —
  experience proxy) from `sofascore_player_career`.
- Map SofaScore team names → canonical via `team_mapping.csv` (extend it as needed).
- Write `research_ready_dataset/wc2026_team_strength.csv` (one row per canonical team) AND a
  DB table `team_strength_features`.
**ACCEPTANCE:** 48 rows, no NaNs in the 4 group overalls; print the top-10 teams by
`squad_overall` (sanity: Spain/France/England/Brazil/Argentina should be near the top).

### TASK 3 (id: PLR-MODEL) — player-data match model + WC2026 ensemble
**Two separated tracks. Read the leakage rule above first.**

**(a) Player-strength → outcome model (recent-era only).**
`src/p2_player_model.py`:
- Build a training frame of **international matches dated ≥ 2024-01-01** (where current
  SofaScore ratings approximate the squads' quality — acknowledge this is an approximation in
  the ledger note). Features = the *difference* of the TASK-2 team vectors (home − away) plus
  the existing `elo_diff` and `neutral` flag. Target = `[home_loss, draw, home_win]`.
- Fit a multinomial logistic regression (and, if `lightgbm` available, an LGBM classifier —
  keep whichever has lower log-loss on a time-ordered 80/20 split of the 2024–2026 window).
- Calibrate (temperature) on the holdout. Save `models/player_model_v1.pkl`.
**ACCEPTANCE:** log-loss on the 2024–2026 holdout beats the Davidson-only baseline on the
same rows; ledger row with both numbers.

**(b) WC2026 live blend (the model that actually predicts the tournament).**
`src/p3_wc2026_blend.py`:
- For each WC2026 fixture, produce probabilities from THREE sources: (i) the host-fixed
  Davidson/ELO from TASK 1, (ii) the player-strength model from 3(a), (iii) the SofaScore
  power-ranking implied probability (build a simple Davidson-style map from
  `sofascore_power_rankings.points` differences — calibrate the scale on the same 2024–2026
  window).
- Blend with weights fitted on the 2024–2026 window (constrained, sum to 1) — start from
  equal weights, optimise log-loss, report the learned weights.
- This blend feeds a NEW simulator entry point or a thin wrapper that swaps the per-match
  probability function. Write `artifacts/run_<ts>/wc2026_blend_probs.json` and have
  `m8_simulate` optionally consume it (flag `--probs blend`). Keep the pure-ELO path as default
  so the historical backtest is untouched.
**SHIP-AS-PARALLEL-TRACK (user decision):** Do **NOT** gate or kill the player-blend on the
small live sample. Always ship it as a **parallel track** shown alongside pure-ELO on the
scorecard (TASK 4) and let the live numbers decide over the full tournament. Report its mean
log-loss on the **played** WC2026 matches (recomputed each run from `sofascore_events`) in the
ledger, next to pure-ELO's, but never auto-remove it. The disagreement between the two models
is itself a feature (surfaced in TASK 6).
**ACCEPTANCE:** `wc2026_blend_probs.json` produced; ledger row reports blend vs pure-ELO
log-loss on played matches (no kill decision); both models appear on the scorecard.

### TASK 4 (id: SCORECARD) — live model success-rate tracker (for LinkedIn) ⭐
This is the headline deliverable for publishing. Build `src/scorecard.py`.
- Ingest every played WC2026 match (from `sofascore_events` where score is final; map names
  to canonical). For EACH model variant we want to showcase — `elo_davidson` (pre-TASK-1),
  `elo_host` (post-TASK-1), `player_blend` (TASK 3b), and `market` (SofaScore featured odds
  where captured) — record the probability it gave the **actual** outcome.
- Append to `artifacts/model_scorecard.csv` (idempotent on match_number+model):
  `match_number, date, home, away, score, outcome, model, p_home, p_draw, p_away,
   p_outcome, correct(argmax==actual), logloss, brier`.
- Compute running aggregates per model into `dashboard/data/scorecard_data.js`
  (`window.SCORECARD`): n_matches, hit_rate (argmax accuracy), mean_logloss,
  vs_coinflip (1.0986 − logloss), mean_brier, a 5-bin reliability/calibration array, and the
  per-match detail list. Include `generated_at`.
- Wire it into `src/live_update.py` so it runs after every ingest, and into
  `src/track.py update`.
All four variants (`elo_davidson`, `elo_host`, `player_blend`, `market`) are tracked as
**parallel tracks** — the scorecard compares them, it does not pick a winner or drop any.
A starter `src/scorecard.py` already exists tracking `elo_dixon`; extend it (don't rewrite from
scratch) to emit one summary block per model variant.
**ACCEPTANCE:** with the current 4 results, `scorecard_data.js` shows, per model, hit_rate and
mean_logloss; numbers reconcile with a hand check of the 4 matches. Re-running is a no-op.

### TASK 5 (id: DASH-ACC) — accuracy/scorecard dashboard page (publish-ready)
New `dashboard/accuracy.html` (match the existing dark theme + nav; copy header/nav from
`players.html`). Render from `dashboard/data/scorecard_data.js` only (NEVER fetch() local
JSON — CORS-blocked from file://). Sections:
1. **Headline cards** per model: big hit-rate %, mean log-loss, "beats coin-flip by X", n
   matches. Highlight the best model.
2. **Model comparison bar** — log-loss of each model vs the coin-flip and market baselines.
3. **Per-match table** — date, fixture, actual score, each model's P(actual) and a ✓/✗ for
   argmax; colour ✓ green / ✗ red.
4. **Calibration plot** — predicted-prob bins vs realized frequency (plain SVG).
5. A short, honest methodology blurb (good for LinkedIn screenshots): splits, no-leakage,
   sample size caveat.
Add `accuracy.html` to the nav on ALL dashboard pages (index, bracket, entropy, scorelines,
players, progress). Add a `player` ratings + `accuracy` link row.
**ACCEPTANCE:** opens from file:// with no console errors; updates when
`scorecard_data.js` regenerates.

### TASK 6 (id: DASH-PLR) — surface player-strength on the dashboard
- On `dashboard/index.html`, under the existing group forecasts, add a compact
  "squad strength vs ELO" note per group OR a small table from
  `research_ready_dataset/wc2026_team_strength.csv` (export it to a JS file via track.py).
- Optionally add a "biggest model disagreements" widget: matches where the player_blend and
  pure-ELO disagree most (great LinkedIn content — shows the models reasoning differently).
**ACCEPTANCE:** renders from file://; no console errors.

### TASK 7 (id: CLEANUP) — delete/triage repo cruft (do LAST, in its own commit)
Be conservative. Do exactly this:
- **Delete (safe):**
  - `UsersHPOneDriveDesktopworldCupscraperssofascore_scraper/` — empty path-artifact junk dir.
  - `src/__pycache__/`, any stray `*.pyc`.
  - `scrapers/sofascore_scraper/` — the cloned third-party repo (tunjayoff/sofascore_scraper);
    it does NOT work (Cloudflare-blocked) and is superseded by our Playwright scraper. Confirm
    nothing in `src/` imports it (grep) before removing; it is already gitignored.
- **Gitignore + delete from worktree (dead data):** the `data_collection_pipeline/collected_data/raw/statsapi_*`
  files — the StatsAPI key is REVOKED, this data is unusable. Add a gitignore rule and remove.
- **Archive (do NOT delete — move to `docs/archive/`):** superseded one-off reports
  `API_CAPABILITY_REPORT.md`, `ODDS_GAP_REPORT.md`, `STATSAPI_INTEGRATION_PLAN.md`,
  `BRUTAL_GAP_ANALYSIS.md`, `AI_PLANNING_DOCUMENT.md`, `INVENTORY_REPORT.md`,
  `DATA_BANK_UPDATE.md`, `DATA_SOURCE_RANKING.md`. Keep at root: `CLAUDE.md`, `README.md`,
  `MASTER_ML_ROADMAP.md`, `OPENCODE_PROMPT.md`, this file, `PROJECT_STATUS.md`, `SCHEMA.md`,
  `TODO_FOR_OPUS.md`, `AGENTS.md`, `HANDBACK_REPORT.md`.
- Update `README.md` so its file list matches reality after the move.
**ACCEPTANCE:** `git status` clean except intended changes; `python src/ask.py status` and
`python src/m8_simulate.py` still run (nothing essential deleted); one commit titled
`CLEANUP: archive stale reports, drop dead statsapi data + junk dir`.

---

## SEQUENCING & DEPENDENCIES
1 → 2 → 3 → 4 → 5 → (6) → 7.  TASK 4/5 depend on 1 and 3 producing probabilities.
TASK 7 last so deletions can't break earlier verification.

## DEFINITION OF DONE (whole sprint)
- `experiments.csv` has new rows for ELO-HOST, PLR-MODEL(a+b); each with honest numbers.
- `dashboard/accuracy.html` renders a live model scorecard from `scorecard_data.js`.
- `src/scorecard.py` runs inside `live_update.py`; re-running is idempotent.
- Pure-ELO historical backtest (0.857) is UNCHANGED (you didn't pollute it with player data).
- Repo cleaned per TASK 7; nothing essential removed.
- `HANDBACK_REPORT.md` updated: per-task status, numbers, files touched, deviations, verify
  commands. `python src/track.py update`. Commit + push `opencode/sprint35`. Do NOT merge to
  main — a reviewer verifies.

## QUICK VERIFY COMMANDS
```
python src/m1b_host_calib.py            # prints host_bonus
python src/m8_simulate.py               # re-sim with host fix
python src/p1_player_features.py        # 48-team strength csv
python src/p2_player_model.py           # recent-era player model LL
python src/p3_wc2026_blend.py           # blend probs + weights
python src/scorecard.py                 # rebuild scorecard_data.js
python src/track.py update              # refresh dashboards
# open dashboard/accuracy.html in a browser (file://)
```

## NOTES / TRAPS
- SofaScore↔canonical name mismatches WILL bite you (Korea Republic, Türkiye, USA, Czechia,
  Bosnia & Herzegovina, Côte d'Ivoire, Cabo Verde, DR Congo). Fix in `team_mapping.csv`.
- `sofascore_events` is the live results source; it is refreshed by a human running
  `scrapers/sofascore_test.py` + `scrapers/sofascore_integrate.py`. Read it; don't scrape it.
- GK ratings live on a different scale (saves/anticipation/ball_distribution/aerial/tactical) —
  the GK-aware "overall" is already computed in `sofascore_team_strength.avg_overall`; use that,
  do not average GK with outfield raw attributes.
- Keep the player-data evaluation window (≥2024) completely separate from the 2011/2018 split.
- Don't tune anything to the 4 played results. Fit on history/recent windows, then REPORT.
