window.PROGRESS = {
 "updated": "2026-06-11 21:24 UTC",
 "run_id": "47c5620",
 "best_logloss": 0.8591,
 "elo_coverage": "100%",
 "wc_played": 0,
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
   "date": "2026-06-11",
   "module": "m0_baseline_sanity",
   "model": "histgb",
   "features_desc": "classification_dataset_v2.csv (44 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8645,
   "brier_test": 0.5074,
   "rps_test": "",
   "acc_test": 0.6046,
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "LOG",
   "notes": ""
  },
  {
   "exp_id": "m1_davidson",
   "date": "2026-06-11",
   "module": "m1_elo_davidson",
   "model": "elo_davidson",
   "features_desc": "per-match elo only",
   "n_train": 34497.0,
   "logloss_test": 0.8682,
   "brier_test": "",
   "rps_test": "",
   "acc_test": "",
   "ece_test": "",
   "beats_baseline": "yes",
   "decision": "KEEP",
   "notes": "nu=0.705 H=142 coverage=1.000"
  },
  {
   "exp_id": "m0_elo_only_v2",
   "date": "2026-06-11",
   "module": "m0_baseline_sanity",
   "model": "elo_only",
   "features_desc": "classification_dataset_v2.csv (44 feats)",
   "n_train": 34497.0,
   "logloss_test": 0.8812,
   "brier_test": 0.5175,
   "rps_test": "",
   "acc_test": 0.6026,
   "ece_test": "",
   "beats_baseline": "no",
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
   "status": "todo",
   "note": "also the simulator goal engine"
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
   "status": "todo",
   "note": ""
  },
  {
   "id": "m7",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Temperature calibration + ECE report",
   "status": "todo",
   "note": "isotonic proven to overfit val"
  },
  {
   "id": "BT22",
   "sprint": "Sprint 1 \u2014 Ensemble",
   "desc": "Backtest full stack on WC2022 + WC2018",
   "status": "todo",
   "note": "credibility gate"
  },
  {
   "id": "m8",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "48-team Monte-Carlo simulator (groups, best-thirds, bracket)",
   "status": "todo",
   "note": "lock played matches"
  },
  {
   "id": "PENS",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "Integrate shootouts.csv penalty model",
   "status": "todo",
   "note": "file already on disk"
  },
  {
   "id": "m9",
   "sprint": "Sprint 2 \u2014 Simulator",
   "desc": "Entropy engine: surprisal, chaos meter, WC chaos history",
   "status": "todo",
   "note": ""
  },
  {
   "id": "LIVE",
   "sprint": "Sprint 3 \u2014 Live loop",
   "desc": "live_update.py: ingest scores -> update ELO/form -> re-sim",
   "status": "todo",
   "note": "feed lags; Wikipedia fallback required"
  },
  {
   "id": "HIST",
   "sprint": "Sprint 3 \u2014 Live loop",
   "desc": "prediction_history.csv + champion-prob trajectories",
   "status": "todo",
   "note": ""
  },
  {
   "id": "m10",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "Golden Boot scorer model + WC2022 backtest",
   "status": "todo",
   "note": ""
  },
  {
   "id": "DASH",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "Public dashboard pages (groups/bracket/entropy/scorers)",
   "status": "todo",
   "note": "extend dashboard/"
  },
  {
   "id": "ASK",
   "sprint": "Sprint 4 \u2014 Products",
   "desc": "ask.py JSON CLI + CLAUDE.md for LLM access",
   "status": "todo",
   "note": ""
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
   "status": "todo",
   "note": "not yet retried with VPN"
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
   "status": "todo",
   "note": ""
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
   "fifa_rankings",
   67261
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
   49353
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
   128
  ],
  [
   "sb_player_match_stats",
   1757
  ],
  [
   "sb_team_match_stats",
   255
  ],
  [
   "squads",
   12948
  ],
  [
   "starting_lineups",
   2816
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
  }
 ]
};