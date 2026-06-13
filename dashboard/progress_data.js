window.PROGRESS = {
 "updated": "2026-06-13 15:24 UTC",
 "run_id": "2f04bac",
 "best_logloss": 0.848,
 "elo_coverage": "100%",
 "wc_played": 4,
 "experiments": [
  {
   "exp_id": "market_closing",
   "date": "2026-06-11",
   "module": "f2_market_benchmark",
   "model": "bookmaker_closing",
   "features_desc": "228 intl matches WC18/22 Euro20/24 Copa21",
   "n_train": "",
   "logloss_test": 0.8219,
   "brier_test": "",
   "rps_test": "",
   "acc_test": "",
   "ece_test": "",
   "beats_baseline": "",
   "decision": "BENCHMARK",
   "notes": "the honest ceiling on big tournaments"
  },
  {
   "exp_id": "ELO-HOST",
   "date": "2026-06-12",
   "module": "m1b_host_calib",
   "model": "host_bonus",
   "features_desc": "wc host matches 1990-2022",
   "n_train": 47.0,
   "logloss_test": 0.848,
   "brier_test": "",
   "rps_test": "",
   "acc_test": "",
   "ece_test": "",
   "beats_baseline": "KEEP",
   "decision": "host_bonus=14.1 nll_without=0.8485 nll_with=0.8480",
   "notes": ""
  },
  {
   "exp_id": "m6_stack_cal",
   "date": "2026-06-12",
   "module": "m6_stack",
   "model": "stack(dav+dc+lr+gb)+temp",
   "features_desc": "v2 features",
   "n_train": 34497.0,
   "logloss_test": 0.8569,
   "brier_test": 0.5031,
   "rps_test": "",
   "acc_test": 0.6067,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "KEEP",
   "notes": "T=1.099 raw=0.8558"
  },
  {
   "exp_id": "m6_stack_cal",
   "date": "2026-06-12",
   "module": "m6_stack",
   "model": "stack(dav+dc+lr+gb)+temp",
   "features_desc": "v2 features",
   "n_train": 34497.0,
   "logloss_test": 0.8574,
   "brier_test": 0.5033,
   "rps_test": "",
   "acc_test": 0.6065,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "KEEP",
   "notes": "T=1.099 raw=0.8563"
  },
  {
   "exp_id": "m6_stack_cal",
   "date": "2026-06-12",
   "module": "m6_stack",
   "model": "stack(dav+dc+lr+gb)+temp",
   "features_desc": "v2 features",
   "n_train": 34497.0,
   "logloss_test": 0.8574,
   "brier_test": 0.5033,
   "rps_test": "",
   "acc_test": 0.6065,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "KEEP",
   "notes": "T=1.099 raw=0.8563"
  },
  {
   "exp_id": "m0_blend_raw_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "blend_raw",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8582,
   "brier_test": 0.5039,
   "rps_test": "",
   "acc_test": 0.6071,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_blend_cal_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "blend_cal",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8589,
   "brier_test": 0.5034,
   "rps_test": "",
   "acc_test": 0.6075,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_blend_raw_v2",
   "date": "2026-06-11",
   "module": "m0_baseline_sanity",
   "model": "blend_raw",
   "features_desc": "classification_dataset_v2.csv (44 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8591,
   "brier_test": 0.5044,
   "rps_test": "",
   "acc_test": 0.6063,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_blend_raw_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "blend_raw",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8591,
   "brier_test": 0.5044,
   "rps_test": "",
   "acc_test": 0.6063,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_blend_cal_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "blend_cal",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8598,
   "brier_test": 0.504,
   "rps_test": "",
   "acc_test": 0.6067,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_blend_cal_v2",
   "date": "2026-06-11",
   "module": "m0_baseline_sanity",
   "model": "blend_cal",
   "features_desc": "classification_dataset_v2.csv (44 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8598,
   "brier_test": 0.504,
   "rps_test": "",
   "acc_test": 0.6067,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_logreg_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "logreg",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8619,
   "brier_test": 0.5056,
   "rps_test": "",
   "acc_test": 0.6068,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_logreg_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "logreg",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8625,
   "brier_test": 0.506,
   "rps_test": "",
   "acc_test": 0.6065,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_logreg_v2",
   "date": "2026-06-11",
   "module": "m0_baseline_sanity",
   "model": "logreg",
   "features_desc": "classification_dataset_v2.csv (44 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8625,
   "brier_test": 0.506,
   "rps_test": "",
   "acc_test": 0.6065,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m0_histgb_v2",
   "date": "2026-06-12",
   "module": "m0_baseline_sanity",
   "model": "histgb",
   "features_desc": "classification_dataset_v2.csv (47 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8632,
   "brier_test": 0.5066,
   "rps_test": "",
   "acc_test": 0.6053,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  }
 ],
 "tasks": [
  {
   "id": "AUDIT",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "Evidence-based project audit (PROJECT_STATUS.md)",
   "status": "done",
   "note": "found 83% test-era ELO gap"
  },
  {
   "id": "m0",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "Baseline sanity: ELO/logreg/HistGB/blend",
   "status": "done",
   "note": "v1 blend 0.8777"
  },
  {
   "id": "m1",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "Per-match ELO rebuild + Davidson draw model",
   "status": "done",
   "note": "100% coverage; Davidson test LL 0.8682"
  },
  {
   "id": "T0.1",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "Feature store v2: repaired ELO + pipeline-2 joins",
   "status": "done",
   "note": "v2 blend 0.8591"
  },
  {
   "id": "T0.4",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "experiments.csv ledger",
   "status": "done",
   "note": "auto-appended by m0/m1"
  },
  {
   "id": "TRACKER",
   "sprint": "Sprint 0 \u2014 Foundation",
   "desc": "HTML progress tracker + track.py",
   "status": "done",
   "note": ""
  },
  {
   "id": "T0.2",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Odds -> implied probs table + market benchmark",
   "status": "todo",
   "note": "odds_international has imp_* precomputed; parse '18 Dec 2022' dates"
  },
  {
   "id": "m3",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Tuned GBM classifier (install lightgbm; random search on val)",
   "status": "todo",
   "note": ""
  },
  {
   "id": "m4",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Dixon-Coles time-decayed goals model",
   "status": "done",
   "note": "test LL 0.9143, goal calib within 5%"
  },
  {
   "id": "m5",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "GBM Poisson goals model",
   "status": "todo",
   "note": ""
  },
  {
   "id": "m6",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Stacking ensemble (time-aware OOF)",
   "status": "done",
   "note": "stack test LL 0.8563 raw / 0.8574 cal - new best"
  },
  {
   "id": "m7",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Temperature calibration + ECE report",
   "status": "done",
   "note": "temperature T=1.099 fitted on val_b"
  },
  {
   "id": "BT22",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Backtest full stack on WC2022 + WC2018",
   "status": "done",
   "note": "WC2022 backtest: blend LL=1.0513, Argentina rank=2 (24.8%), market=0.7273, top-5 pass"
  },
  {
   "id": "m8",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "48-team Monte-Carlo simulator (groups, best-thirds, bracket)",
   "status": "done",
   "note": "50k sims: Argentina 17.5%, Spain 14.6%"
  },
  {
   "id": "PENS",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "Integrate shootouts.csv penalty model",
   "status": "done",
   "note": "572 shootouts joined, logistic p=sigmoid(0.0185+0.6265*|elo|/400), top5 shift <1pp"
  },
  {
   "id": "m9",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "Entropy engine: surprisal, chaos meter, WC chaos history",
   "status": "done",
   "note": "entropy engine: 8 WC tournaments, 2022 most chaotic (sum_I=68.36), dashboard/entropy.html renders"
  },
  {
   "id": "LIVE",
   "sprint": "Sprint 3 \u2014 Live loop",
   "desc": "live_update.py: ingest scores -> update ELO/form -> re-sim",
   "status": "done",
   "note": "ingested 2 real scores, idempotent, champion Argentina 17.2%"
  },
  {
   "id": "HIST",
   "sprint": "Sprint 3 \u2014 Live loop",
   "desc": "prediction_history.csv + champion-prob trajectories",
   "status": "done",
   "note": "trajectory chart, history_data.js, bracket.html"
  },
  {
   "id": "m10",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "Golden Boot scorer model + WC2022 backtest",
   "status": "done",
   "note": "Golden Boot heuristic: Kane 1.06, Messi 0.91, Haaland 0.90"
  },
  {
   "id": "m11",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "Scoreline prediction model (DC tilted by ensemble W/D/L)",
   "status": "done",
   "note": "72 matches, 7x7 matrices, O/U, BTTS, scorelines.html + ask.py scoreline"
  },
  {
   "id": "PLAYERS",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "SofaScore player ratings scraper + players.html (attack/defence/GK)",
   "status": "done",
   "note": "1255 players / 48 teams scraped; FIFA-style attrs (atk/tec/tac/def/cre + GK saves/antic/dist/aerial) current+3 historical yrs; players.html + ask.py player; Yamal 77 top outfield"
  },
  {
   "id": "DASH",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "Public dashboard pages (groups/bracket/entropy/scorers/scorelines/players)",
   "status": "done",
   "note": "7 pages: index, bracket, entropy, scorelines, players, progress + nav links; live SofaScore standings on index"
  },
  {
   "id": "ASK",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "ask.py JSON CLI + CLAUDE.md for LLM access",
   "status": "done",
   "note": "ask.py JSON CLI, 9 subcommands including scoreline + player, valid JSON output"
  },
  {
   "id": "D-ODDS",
   "sprint": "Data days (user)",
   "desc": "OddsPortal 2016-2026 intl closing odds via VPN+stealth",
   "status": "todo",
   "note": "recipe proven 2026-06-08"
  },
  {
   "id": "D-XG",
   "sprint": "Data days (user)",
   "desc": "FBref intl team-match xG 2015-2026 via stealth",
   "status": "done",
   "note": "StatsBomb expansion: +Euro24/20, Copa24, AFCON23 = 665 team-xG rows, 39/48 WC teams covered; FBref still VPN-blocked"
  },
  {
   "id": "D-AVAIL",
   "sprint": "Data days (user)",
   "desc": "WC2026 live lineups + injuries (API-Football free tier)",
   "status": "todo",
   "note": ""
  },
  {
   "id": "D-RANK",
   "sprint": "Data days (user)",
   "desc": "FIFA rankings 2024-07 to 2026-06 gap (Wayback Machine)",
   "status": "done",
   "note": "CLOSED via Wayback: 13 validated releases 2024-07 to 2026-01; stack new best 0.8558"
  }
 ],
 "db_tables": [
  [
   "dim_team",
   575
  ],
  [
   "elo_current",
   335
  ],
  [
   "elo_match",
   49353
  ],
  [
   "elo_ratings",
   18142
  ],
  [
   "entropy_match",
   44563
  ],
  [
   "fifa_rankings",
   69965
  ],
  [
   "goalscorers",
   47601
  ],
  [
   "injuries",
   0
  ],
  [
   "market_values",
   48
  ],
  [
   "match_features_v2",
   49281
  ],
  [
   "matches",
   49357
  ],
  [
   "matches_norm",
   49353
  ],
  [
   "ml_match_features",
   49281
  ],
  [
   "odds",
   0
  ],
  [
   "odds_bank",
   479440
  ],
  [
   "odds_implied_recent",
   97
  ],
  [
   "official_squads_2026",
   1246
  ],
  [
   "player_match_stats",
   0
  ],
  [
   "player_tournament_stats",
   0
  ],
  [
   "players",
   18127
  ],
  [
   "sb_matches",
   333
  ],
  [
   "sb_player_match_stats",
   4592
  ],
  [
   "sb_team_match_stats",
   665
  ],
  [
   "sofascore_events",
   34
  ],
  [
   "sofascore_odds",
   0
  ],
  [
   "sofascore_player_attributes",
   4052
  ],
  [
   "sofascore_player_career",
   1215
  ],
  [
   "sofascore_power_rankings",
   48
  ],
  [
   "sofascore_standings",
   48
  ],
  [
   "sofascore_team_strength",
   190
  ],
  [
   "squads",
   12948
  ],
  [
   "starting_lineups",
   7326
  ],
  [
   "team_match_features",
   98562
  ],
  [
   "team_match_stats",
   0
  ],
  [
   "venues",
   16
  ],
  [
   "wc2026_fixtures",
   104
  ],
  [
   "wc2026_qualified_teams",
   49
  ],
  [
   "wc_matches_history",
   900
  ],
  [
   "wc_tournaments",
   21
  ]
 ],
 "log": [
  {
   "ts": "2026-06-11 21:21 UTC",
   "msg": "Session 2026-06-12: audit done, m1 ELO+Davidson built (0.8682), features v2 (blend 0.8591), tracker created"
  },
  {
   "ts": "2026-06-11 21:22 UTC",
   "msg": "f2: market benchmark computed from 228 closing-odds matches"
  },
  {
   "ts": "2026-06-12 07:45 UTC",
   "msg": "m4 -> done (test LL 0.9143, goal calib within 5%)"
  },
  {
   "ts": "2026-06-12 07:45 UTC",
   "msg": "m6 -> done (stack test LL 0.8563 raw / 0.8574 cal - new best)"
  },
  {
   "ts": "2026-06-12 07:45 UTC",
   "msg": "m7 -> done (temperature T=1.099 fitted on val_b)"
  },
  {
   "ts": "2026-06-12 07:45 UTC",
   "msg": "m8 -> done (50k sims: Argentina 17.5%, Spain 14.6%)"
  },
  {
   "ts": "2026-06-12 07:45 UTC",
   "msg": "m8 first artifacts run_20260612T0743; champion odds live on dashboard"
  },
  {
   "ts": "2026-06-12 07:52 UTC",
   "msg": "dashboard/index.html simulation showcase built (champion bars, reach table, group forecasts, 72 match cards, chaos gauge)"
  },
  {
   "ts": "2026-06-12 08:08 UTC",
   "msg": "OPENCODE_PROMPT.md created - tasks LIVE/PENS/m9/BT22/HIST+DASH/m10/ASK/m3+m5/T0.2full delegated, review-on-branch workflow"
  },
  {
   "ts": "2026-06-12 08:25 UTC",
   "msg": "live update: 1 new results ingested"
  },
  {
   "ts": "2026-06-12 08:26 UTC",
   "msg": "LIVE -> done (ingested 2 real scores, idempotent, champion Argentina 17.2%)"
  },
  {
   "ts": "2026-06-12 08:29 UTC",
   "msg": "PENS -> done (572 shootouts joined, logistic p=sigmoid(0.0185+0.6265*|elo|/400), top5 shift <1pp)"
  },
  {
   "ts": "2026-06-12 08:31 UTC",
   "msg": "m9 -> done (entropy engine: 8 WC tournaments, 2022 most chaotic (sum_I=68.36), dashboard/entropy.html renders)"
  },
  {
   "ts": "2026-06-12 08:35 UTC",
   "msg": "BT22 -> done (WC2022 backtest: blend LL=1.0513, Argentina rank=2 (24.8%), market=0.7273, top-5 pass)"
  },
  {
   "ts": "2026-06-12 08:39 UTC",
   "msg": "HIST -> done (trajectory chart, history_data.js, bracket.html)"
  },
  {
   "ts": "2026-06-12 08:39 UTC",
   "msg": "DASH -> done (entropy page, bracket page, trajectory chart)"
  },
  {
   "ts": "2026-06-12 08:41 UTC",
   "msg": "ASK -> done (ask.py JSON CLI, 7 subcommands, valid JSON output, CLAUDE.md written)"
  },
  {
   "ts": "2026-06-12 08:42 UTC",
   "msg": "m10 -> done (Golden Boot heuristic: Kane 1.06, Messi 0.91, Haaland 0.90)"
  },
  {
   "ts": "2026-06-12 09:34 UTC",
   "msg": "D-XG -> done (StatsBomb expansion: +Euro24/20, Copa24, AFCON23 = 665 team-xG rows, 39/48 WC teams covered; FBref still VPN-blocked)"
  },
  {
   "ts": "2026-06-12 09:34 UTC",
   "msg": "D-RANK -> in_progress (Wayback harvest running: ~20 releases 2024-07 to 2026-05 found)"
  },
  {
   "ts": "2026-06-12 09:34 UTC",
   "msg": "missing-data round: StatsBomb +205 matches ingested; xG features in v2 (58 cols); FBref stealth probe failed (needs VPN)"
  },
  {
   "ts": "2026-06-12 09:56 UTC",
   "msg": "D-RANK -> done (CLOSED via Wayback: 13 validated releases 2024-07 to 2026-01; stack new best 0.8558)"
  },
  {
   "ts": "2026-06-12 09:56 UTC",
   "msg": "rankings gap closed; v2 rebuilt w/ fresh ranks + xG; stack 0.8558 raw / 0.8569 cal = new best"
  }
 ]
};