# TODO FOR OPUS — Session Handoff (2026-06-12)

*Read this + `MASTER_ML_ROADMAP.md` (the full specs) + `PROJECT_STATUS.md` (the audit).
This file = what is DONE with evidence, what is NEXT with exact instructions, and the traps.*

---

## A. STATE: what is done and verified (this session)

| item | evidence | numbers |
|---|---|---|
| Evidence audit | `PROJECT_STATUS.md` | found ELO 83% missing in test era |
| **m1: per-match ELO + Davidson** | `src/m1_elo_davidson.py`; DB tables `elo_match` (49,353, **100% coverage**), `elo_current` (575 teams) | Davidson alone: **test LL 0.8682** (ν=0.705, home adv=142, params in `research_ready_dataset/davidson_params.json`) |
| **T0.1: feature store v2** | `src/f1_build_features.py`; DB `match_features_v2`; `classification_dataset_v2.csv` (49,281×55) + `regression_dataset_v2.csv` | repaired ELO family + mean_age/caps/club_quality/mgr_tenure/qual_ppg diffs (2025-06+ rows only) + fifa-rank override post-2024-04 + `sample_weight` |
| **Baselines on v2** | `src/m0_baseline_sanity.py classification_dataset_v2.csv`; `baseline_metrics_v2.json` | elo_only 0.8812 · logreg 0.8625 · histgb 0.8645 · **blend 0.8591** (v1 was 0.8777) |
| **T0.2-lite: market benchmark** | `src/f2_market_benchmark.py`; DB `odds_implied_recent` | **bookmaker closing LL 0.8219** on 97 complete rows (of 228 scraped) |
| **T0.4: experiments ledger** | `research_ready_dataset/experiments.csv` — auto-appended by m0/m1/f2 | 12 rows so far |
| **Progress tracker** | `dashboard/progress.html` + `progress_data.js` + `tasks.json` + `src/track.py` | open progress.html in a browser; auto-refreshes 60s |

### Current leaderboard (test = 2018-10-12 → 2026-05-31, n=7,383)
```
0.8219  bookmaker closing odds   <- ceiling (biased sample: big tournaments only)
0.8591  blend(logreg+histgb) on v2   <- OUR BEST
0.8625  logreg v2
0.8682  Davidson(per-match ELO only)
0.8777  old v1 blend                 <- old bar, beaten
1.0397  year-end-ELO logistic        <- where we started yesterday
```

---

## B. CONVENTIONS — violate these and results are garbage

1. **Class order is ALWAYS `[home_loss, draw, home_win]` = [0,1,2].** Every proba array.
2. **Chronological splits only.** Boundaries: train ≤ 2011-01-17 < val ≤ 2018-10-11 < test.
   Reuse the `split` column; never re-randomise.
3. **Never train on data dated after the prediction date.** OOF folds = expanding window.
4. **Team names**: always map through `research_ready_dataset/team_mapping.csv`
   (raw → canonical → team_id). ELO tables use canonical names already.
5. **Leakage columns** (never features): gf, ga, result, points, home_score, away_score,
   *_score, attendance, outcome, winning_team.
6. **Every experiment appends a row** to `research_ready_dataset/experiments.csv` and runs
   `python src/track.py update` (or `track.py done <task_id> "note"`). The tracker is the
   user's window into progress — keep it honest.
7. Environments: **system `python`** (3.13) for all ML; conda
   `C:\Users\HP\anaconda3\envs\minorproject\python.exe` ONLY for Playwright scraping.
8. Use `src/common.py` for paths/logging. v2 CSVs are gitignored (only docs/structure pushed).

---

## C. NEXT TASKS in order (each ≈ one focused session; full specs in roadmap §)

### C1. m4 Dixon-Coles (roadmap §4-m4) — HIGHEST priority model
- File `src/m4_dixon_coles.py`. Fit on matches since 2000 w/ time-decay ξ=0.0019
  (try {0.001,0.0019,0.003} on val); teams <30 matches → confederation pooled dummy.
- Outputs: probs + (λ_home, λ_away) per match; save params via joblib to `models/m4.pkl`;
  ledger row; **acceptance: test LL ≤ 0.92** standalone, and λ within 5% of actual mean goals.
- This is the **simulator's goal engine** — m8 is blocked without it.

### C2. m3 tuned GBM (roadmap §4-m3)
- `pip install lightgbm` (if it fails on this machine, HistGB stays the workhorse — fine).
- 30-trial random search on val, train on v2 WITH `sample_weight`. Ledger + `models/m3.pkl`.

### C3. m6 stacker + m7 temperature calibration (roadmap §4-m6/m7)
- OOF via 5 expanding-window folds over train+val; meta = multinomial LR on logit probs of
  {davidson, m3, m4, m5-if-built} + stage_weight, neutral_flag.
- Calibrate with **temperature scaling** (isotonic PROVEN to overfit here — see ledger).
- **Acceptance: test LL < 0.855** (must beat 0.8591) → freeze `models/ensemble_v1.pkl`.

### C4. m8 simulator (roadmap §6 — exact 2026 rules are written there)
- Needs m4 λs + m6 probs. Lock played matches from `wc2026_fixtures` scores.
- Integrate `fifa_wc_data/raw/kaggle/international-football-results-from-1872-to-2017/shootouts.csv`
  for penalty priors (free win, file already on disk).
- Output `artifacts/run_<ts>/sim_results.json` (schema in roadmap §6.3) + copy to
  `dashboard/data/`. 50k sims, seed 2026.

### C5. live_update.py (roadmap §8) — URGENT, tournament is running
- **fixturedownload feed STILL showed 0 played matches on day 2** (verified 02:15 today).
  Primary ingestion must be Wikipedia: `pd.read_html` on the group pages
  (`2026_FIFA_World_Cup_Group_A`…`_L`) with a browser UA — same technique as
  `src/s14_wc2026_squads.py`. Upsert scores into `matches` + `wc2026_fixtures`,
  run ELO update (reuse m1's k/G functions), refresh form, re-sim, append
  `artifacts/prediction_history.csv`, run `track.py update`.
- Schedule: `schtasks /create /tn WC26Update /tr "python <abs path>\src\live_update.py" /sc daily /st 23:30` (or every 6h).

### C6. m9 entropy engine (roadmap §5 — formulas are exact, implement as written)
Then: m10 scorers (§7), dashboard pages (§9), ask.py + CLAUDE.md (§10).

---

## D. KNOWN TRAPS (cost this session real time)

1. `odds_international.csv` dates are `"18 Dec 2022"` → `pd.to_datetime(format="%d %b %Y")`.
   **131/228 rows lack scores or implied probs** — the scrape is partial; benchmark used 97.
2. Wikipedia needs a browser `User-Agent` header or returns 403 (use `polite_get`).
3. The 5.6 GB `male_players.csv` will OOM naive `read_csv` — always chunk (see s08).
4. Isotonic calibration overfits the 7.4k val set (worsened LL by 0.003) — temperature only.
5. `fifa_points` in old tables is a junk join artifact — never use.
6. OneDrive path: occasional file-lock weirdness on rapid rewrites; retry once.
7. `track.py` excludes `decision==BENCHMARK` rows from "best LL" — keep using that decision
   tag for non-model reference rows.
8. Davidson home_adv≈142 already includes what `home_field` encodes — don't double-count
   home advantage when blending Davidson with feature models (stacker handles it).

## E. DATA GAPS the user will collect (don't block on these; integrate when they land)
Ranked list + how-to in `PROJECT_STATUS.md` §10: (1) OddsPortal 2016-26 intl closing odds
[VPN+stealth recipe proven], (2) FBref intl xG 2015-26, (3) WC2026 lineups/injuries
[API-Football free tier], (4) FIFA rankings 2024-07→2026 [Wayback], (5) TM values/injuries.
When #1 lands → redo f2 benchmark on the full sample + add market feature to the stacker.

## F. COMPUTE — none of this needs heavy hardware
49k rows × ≤60 features: GBMs train in seconds–minutes on this laptop's CPU; Dixon-Coles
L-BFGS ≈ <1 min; 50k tournament sims vectorised ≈ minutes. GPU is only relevant for the
FT-Transformer experiment (expected KILL) — use free Colab if ever needed. Do NOT load the
5.6 GB FIFA file outside chunked mode. Disk and 8 GB RAM are sufficient.
