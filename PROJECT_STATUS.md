# PROJECT STATUS — Evidence-Based Audit

*Audit date: 2026-06-12 (tournament day 2). Every claim below was verified by running code
against the repo on this date — nothing assumed from the roadmap. Re-verification commands
included where useful.*

---

## 1. Repository structure (verified by `ls`/`find`)

### Exists
```
src/                              24 files: common.py, m0_baseline_sanity.py,
                                  r1,r2,r3,r4,r6,r_all, run_all, s01..s15 (no s—gaps: s13,s14,s15 present)
data_collection_pipeline/         run_collection.py + src/{common, s01..s11} + README,
                                  checkpoints.json (all 10 stages 'done'), pipeline.log
data_collection_pipeline/collected_data/   processed/ 9 csv + raw/ 4 csv (audited §5)
research_ready_dataset/           11 files (datasets + reports + baseline_metrics.json)
fifa_wc_data/                     raw/ + processed/ + db/football.db + logs/
root *.md                         7 docs incl. MASTER_ML_ROADMAP.md
```

### Missing (referenced by MASTER_ML_ROADMAP.md, do NOT exist yet)
| roadmap artifact | status |
|---|---|
| `dashboard/`, `artifacts/`, `features/` dirs | **missing** |
| `src/f1_build_features.py` (T0.1), `src/f2_odds_implied.py` (T0.2) | **missing** |
| `src/model_base.py`, `src/metrics.py` | **missing** |
| `src/m1_elo_davidson.py` … `src/m10_scorers.py`, `src/live_update.py`, `src/ask.py` | **missing** (only m0 exists) |
| `research_ready_dataset/experiments.csv` (T0.4 ledger) | **missing** |
| `CLAUDE.md` | **missing** |
| DB tables `elo_match`, `entropy_match`, `match_features_v2`, `odds_implied` | **missing** (verified via sqlite_master) |

**Conclusion: roadmap execution is at 0% (by design — it was written yesterday). The only
model artifact is `m0_baseline_sanity.py`, which works (§4).**
`data_collection_pipeline/src/s11_live_pipeline.py` is a **stub** ("No implementation yet —
this is the architecture contract") — do not count it as a live engine.

---

## 2. Database audit (`fifa_wc_data/db/football.db`, 27 tables — verified counts)

| table | rows | | table | rows |
|---|---|---|---|---|
| odds_bank | 479,440 | | players | 18,127 |
| team_match_features | 98,562 | | elo_ratings | 18,142 |
| fifa_rankings | 67,261 | | squads (FIFA-pool proxy) | 12,948 |
| matches / matches_norm | 49,353 | | starting_lineups | 2,816 |
| ml_match_features | 49,281 | | sb_player_match_stats | 1,757 |
| goalscorers | 47,601 | | official_squads_2026 | 1,246 |
| wc_matches_history | 900 | | dim_team | 575 |
| sb_team_match_stats | 255 | | sb_matches | 128 |
| wc2026_fixtures | 104 | | venues / wc2026_qualified_teams / wc_tournaments / market_values | 16 / 49 / 21 / 48 |
| **EMPTY:** injuries, odds, player_match_stats, player_tournament_stats, team_match_stats | 0 | | | |

### Schema verification (5 named tables) — all match SCHEMA.md
- `matches` 14 cols (match_id INT PK-like, date TEXT, scores REAL, referee/attendance TEXT **100% null**).
- `ml_match_features` 47 cols = 8 id/context + **39 features** — matches the roadmap's claim.
- `official_squads_2026` 8 cols (team, shirt_no, position, player, dob_age TEXT-mixed, caps, goals, club).
- `odds_bank` 19 cols (avg+max 1X2, top bookie, n quotes) — **2005–2015 only** (verified earlier).
- `wc2026_fixtures` 9 cols; HomeTeamScore/AwayTeamScore REAL all-null (no scores yet, see §8 risk #1).

---

## 3. Dataset audit (verified by load)

| check | classification_dataset.csv | regression_dataset.csv |
|---|---|---|
| rows × cols | 49,281 × 47 | 49,281 × 48 |
| split | train 34,497 / val 7,401 / test 7,383 | identical |
| target | home_win 24,149 (49%) / loss 13,928 (28.3%) / draw 11,204 (22.7%); **0 nulls in labelled splits** | home/away_goals 0 nulls; range 0–31 (31 = Australia 31-0 Am. Samoa 2001 — real, keep) |
| dates | 1872-11-30 → 2026-05-31 | identical |
| split boundaries | train ≤2011-01-17 < val ≤2018-10-11 < test ≤2026-05-31 — clean chronology | identical |

### ⚠ Material finding — feature missingness BY SPLIT
| feature | train | val | **test** |
|---|---|---|---|
| `elo_diff` (+9 elo-derived) | 75% | 82% | **83%** |
| `fifa_rank_diff` | 64% | 21% | 19% |
| `h2h_win_pct_diff` | 17% | 14% | 10% |
| form/rest/net_rating | ~1% | 0% | 0% |

**The ELO family — the strongest signal class in football models — is absent from 83% of the
test era.** Root cause (verified in `src/s02_elo.py`): year-end ELO rows carry 2-letter site
codes; only ~65 codes were mapped to team names, so the as-of join fails for every unmapped
team. The 0.8777 baseline was achieved with ELO essentially turned off. This is the
single biggest free accuracy lever in the project (→ §9).

---

## 4. Baseline reproducibility — ✅ EXACT

`python src/m0_baseline_sanity.py` re-run 2026-06-12 02:15: reproduces the roadmap table
to 4 decimals (elo_only 1.0397 · logreg 0.8838 · histgb 0.8823 · **blend 0.8777** ·
blend_cal 0.8811). `baseline_metrics.json` refreshed. Deterministic, no environment drift.

---

## 5. Data-collection-pipeline audit (13 files, all loaded; usability = can T0.1 join it TODAY)

| file | rows | null% | join key | T0.1-usable? |
|---|---|---|---|---|
| travel_features.csv | 752 | 0 | team + venue_id | ✅ (future fixtures only) |
| weather_forecasts.csv | 624 | 0 | venue_id + date (**covers 2026-06-11→07-19, 16 venues**) | ✅ (future fixtures only) |
| squad_aggregates.csv | 48 | 0 | team | ✅ |
| manager_tenure.csv | 48 | 9.6 | team | ✅ |
| shared_club_matrix.csv | 48 | 0 | team | ✅ |
| qualification_strength.csv | 147 | 0 | team | ✅ |
| continental_form.csv | 104 | 3 | team + tournament | ✅ (needs per-team latest-row dedup) |
| fifa_rankings_updated.csv | 210 | 0 | team (@2024-06-20) | ✅ (overrides stale ranks) |
| cross_team_club_overlap.csv | 1,128 | 0 | team_a + team_b (pairwise!) | ✅ (join on match pair) |
| odds_international.csv | 228 | 4.4 | home+away+date (**format "18 Dec 2022" — needs parsing**; already has imp_h/d/a devigged) | ✅ for T0.2 |
| odds_club_closing / odds_collected.csv | 5,330 | 0 | club teams — **no intl overlap** | calibration material only |
| understat_team_xg.csv | 96 | 0 | club teams | context only, not match-joinable |

All names need `team_mapping.csv` normalization on join (e.g. "Korea Republic"/"South Korea").
Checkpoints claim all 10 stages 'done' — outputs verified non-empty and sane above. ✅

---

## 6. Feature audit (roadmap §3/T0.1 vs reality)

- **Exist (39)**: everything in `ml_match_features` — verified identical to roadmap list.
- **Duplicated (3)**: `relative_strength` ≡ `elo_diff` (exact copy); `home_field` ≡ 1−`neutral_flag`;
  `upset_proxy` is a deterministic transform of `elo_expected_home`. Harmless for GBMs,
  drop for linear models.
- **Broken-but-present (10)**: the elo-derived family (83% test-missing, §3).
- **Missing but data-on-disk (≈12, effort ≈ ½ day = T0.1)**: caps_diff, age_diff,
  manager_tenure_diff, qual_ppg_diff, continental_form_diff, club_overlap, fresh fifa_rank
  override, travel_diff_km, tz_delta_diff, weather (temp/humidity/heat_flag), shared-club
  chemistry, squad value already exists via `market_values`.
- **Missing and needs new computation (effort 1 day = m1)**: per-match ELO (fixes the
  broken family at 100% coverage) + elo_diff recomputed from it.
- **Missing and needs new data (user's weekend)**: §10.

---

## 7. Model audit (every script in `src/`, run-status evidence-based)

| script | purpose | status | runnable? |
|---|---|---|---|
| `m0_baseline_sanity.py` | 4 baselines + metrics | **verified working today** | ✅ |
| `s01–s15` (15 data stages) | collection pipeline v1 | ran historically (outputs in DB); s06/s07 degrade when blocked | ✅ |
| `r1_audit, r2_dim_team, r3_feature_store, r4_feature_quality, r6_exports, r_all` | research phases | produced current artifacts | ✅ |
| `run_all.py` | v1 orchestrator | working | ✅ |
| pipeline2 `s01–s10` | feature collectors | all 'done' w/ valid outputs (§5) | ✅ (conda env) |
| pipeline2 `s11_live_pipeline.py` | live engine | **STUB — zero implementation** | ❌ |
| roadmap m1–m10, f1, f2, ask.py, live_update.py | the actual ML system | **do not exist** | — |

---

## 8. Risk register (ranked by threat to finishing before July 19)

### HIGH
1. **No live score ingestion + feed lags.** fixturedownload still shows 0 played on day 2
   (verified 02:15 today — opener was 14h ago). Without scores: no locked-sims, no live
   chaos meter, no prediction history. *Mitigation: Wikipedia group-page `read_html`
   fallback (T4.2) — build within Sprint 3, days not weeks.*
2. **Tournament clock.** Group stage ends June 27; the system must produce its first real
   artifacts before R32 (June 28) to be relevant. Sprints 0–3 must land in ~2 weeks.
3. **ELO features broken in test era (83% missing)** — silently caps every model trained
   today. Fix is fully in our control (m1).

### MEDIUM
4. **No current odds source for 2026 matches** — OddsPortal works only via VPN+stealth
   (proven once, brittle); The Odds API free tier untested here. Without it: no market
   anchor or value detection, though core predictions still work.
5. **No lineup/injury data for 2026** — scorer model and availability adjustments run on
   heuristics; wrong if a star is injured (mitigate with manual `availability_overrides.csv`).
6. **48-team format is unprecedented** — best-thirds bracket logic easy to get wrong;
   needs a unit test against FIFA's published allocation table.
7. **Single machine, OneDrive-synced repo** — DB corruption/sync conflict mid-tournament;
   mitigation: nightly copy of football.db outside OneDrive.

### LOW
8. Draw-class under-prediction (structural, all models). 9. `fifa_points` artifact column
still in team_match_features (excluded from datasets — fine). 10. Calibration val-set
overfit (already evidenced by isotonic, mitigated by temperature scaling). 11. OneDrive
path spaces/unicode (Curaçao mojibake seen in squads — cosmetic).

---

## 9. Recommendation — ONE next task: **m1 (per-match ELO rebuild + Davidson)**

**Not** T0.1, **not** T0.2. Evidence chain:
1. The single verified defect with the largest modelled-signal impact is the ELO family
   missing from **83% of the test split** (§3) — and from 100% of *future 2026 fixtures*
   (year-end 2026 ELO obviously doesn't exist yet). Every model in the zoo inherits this.
2. m1 fixes it **by construction**: ELO computed from our own complete `matches` table ⇒
   ~100% coverage, fresher than year-end snapshots, and updateable per-matchday — the live
   loop (Sprint 3) *requires* it anyway. T0.1's new features, by contrast, mostly attach to
   2026-only rows (48 teams) and cannot move historical train/test metrics much; T0.2's odds
   join only covers a 2005-15 slice + 228 recent matches.
3. m1 also unblocks the most downstream consumers: simulator match engine (§6 roadmap),
   entropy ELO-source, Davidson baseline, and corrected `elo_diff/elo_trend/strength_ratio`
   features for every other model.
4. Measurable success test exists today: after m1, re-run m0 with repaired elo features —
   expect blend LL **< 0.87** (if it doesn't improve, that's a finding worth a ledger row).

Order after m1: T0.1 (½ day, mechanical) → m4 Dixon-Coles → m6/m7 → m8 simulator.

---

## 10. Missing-data analysis — "what we could do wonders with" (for the user's collection days)

Ranked by (impact on prediction quality) × (proven feasibility on this setup):

| rank | dataset | why it's a wonder | feasibility evidence | unlocks |
|---|---|---|---|---|
| 1 | **Closing odds for ALL intl matches 2016→2026** (qualifiers, friendlies, Nations League — not just the 228 finals rows) | market probs are the strongest single feature + the only honest benchmark; with them the stacker gets an anchor on ~5k recent matches | OddsPortal works via **VPN + stealth** (proven 2026-06-08); same scraper, more tournament slugs | market-anchored ensemble, value detection, true market-grade bar, entropy market-source |
| 2 | **FBref team-match stats for intl matches 2015→2026** (xG, shots, possession per match) | rolling xG-for/against is the best form signal in football; replaces goals-based attack/defense ratings | NOT yet retried with stealth+VPN — next scrape target per pipeline2 notes; `soccerdata` lib as fallback | xG-Dixon-Coles (big LL gain), team_match_stats table fills, entropy I_score quality |
| 3 | **WC2026 live: lineups + injuries/suspensions** (daily during tournament) | star-player availability is the largest single-match swing factor a model can know pre-kickoff | API-Football free tier 100 req/day suffices for 104 matches; or FIFA match centre scrape | scorer model accuracy, availability-adjusted match probs, live loop credibility |
| 4 | **FIFA rankings 2024-07 → 2026-06 gap** | fifa_rank features are 2 yrs stale exactly where we predict | Wayback Machine snapshots of fifa.com ranking pages bypass Akamai (untested but standard); or inside-fifa JSON via stealth | repaired rank features for val/test/2026 rows |
| 5 | **Transfermarkt squad market values (time series) + injuries archive** | value_diff is a proven strength proxy independent of results; injury history enables availability backtests | TM blocked; needs stealth+VPN (same recipe as OddsPortal) | market_values time series, injuries table |
| 6 | **Historical WC squads w/ caps (1994→2022)** | enables scorer-model **backtesting** (the WC2022 Golden Boot test in roadmap §7.5) | Wikipedia squad pages, same parser as s14 (proven) | validated scorer model |
| 7 | **Penalty shootout archive** (have `shootouts.csv` in kaggle raw — just unintegrated!) | knockout sims currently use a 0.5+ε coin flip | **zero collection needed** — file exists on disk | better knockout resolution; 30-min task |
| 8 | **Referee per match** (matches.referee 100% null; sb_matches has 128) | referee card/penalty tendencies are a niche edge | FBref match pages once unblocked | card/penalty props, marginal W/D/L gain |

Items 1–2 are the difference between "good model" and "publishable model." Item 7 is free
and already on disk. If the user's data-days produce only #1 and #2, the ceiling moves more
than every architecture improvement in the roadmap combined.

---

### Bottom line
Repo is **healthy and exactly where the roadmap says Sprint 0 starts**: data layers verified,
datasets clean, baseline reproducible to 4 decimals, zero roadmap code written yet, and one
significant repairable defect found (ELO join). Build `m1` next.
