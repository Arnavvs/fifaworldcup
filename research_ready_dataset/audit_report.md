# PHASE 1 — Data Audit Report

*Source: `football.db` — 18 tables.*

## 1.1 Table Overview

| table | rows | cols | dup% | avg null% |
|---|---|---|---|---|
| elo_ratings | 18142 | 4 | 0.0% | 0.1% |
| fifa_rankings | 67261 | 4 | 0.0% | 0.0% |
| goalscorers | 47601 | 8 | 0.17% | 0.1% |
| injuries | 0 | 5 | 0.0% | 100.0% |
| market_values | 48 | 6 | 0.0% | 0.7% |
| matches | 49353 | 14 | 0.0% | 20.0% |
| odds | 0 | 9 | 0.0% | 100.0% |
| player_match_stats | 0 | 12 | 0.0% | 100.0% |
| player_tournament_stats | 0 | 8 | 0.0% | 100.0% |
| players | 18127 | 22 | 0.0% | 3.1% |
| squads | 12948 | 6 | 0.0% | 16.8% |
| team_match_features | 98562 | 30 | 0.0% | 7.3% |
| team_match_stats | 0 | 13 | 0.0% | 100.0% |
| venues | 16 | 7 | 0.0% | 4.5% |
| wc2026_fixtures | 104 | 9 | 0.0% | 25.6% |
| wc2026_qualified_teams | 49 | 3 | 0.0% | 0.7% |
| wc_matches_history | 900 | 15 | 0.0% | 8.7% |
| wc_tournaments | 21 | 10 | 0.0% | 0.0% |


## 1.2 Cardinality Analysis

Unique-value ratio per column (uniq / rows); ~1.0 ⇒ identifier, ~0 ⇒ constant.


**matches**

| column | n_unique | uniq_ratio |
|---|---|---|
| match_id | 49353 | 1.0 |
| date | 16459 | 0.333 |
| competition | 198 | 0.004 |
| stage | 23 | 0.0 |
| home_team | 327 | 0.007 |
| away_team | 321 | 0.007 |
| home_score | 26 | 0.001 |
| away_score | 22 | 0.0 |
| neutral | 2 | 0.0 |
| city | 2139 | 0.043 |
| country | 269 | 0.005 |
| venue | 2139 | 0.043 |
| referee | 0 | 0.0 |
| attendance | 0 | 0.0 |

**team_match_features**

| column | n_unique | uniq_ratio |
|---|---|---|
| match_id | 49281 | 0.5 |
| date | 16442 | 0.167 |
| team | 336 | 0.003 |
| opponent | 336 | 0.003 |
| is_home | 2 | 0.0 |
| tournament | 198 | 0.002 |
| stage | 23 | 0.0 |
| stage_weight | 6 | 0.0 |
| rivalry | 2 | 0.0 |
| neutral | 2 | 0.0 |
| gf | 26 | 0.0 |
| ga | 26 | 0.0 |
| result | 3 | 0.0 |
| days_rest | 1459 | 0.015 |
| result_streak_in | 77 | 0.001 |
| wc_appearances_before | 51 | 0.001 |
| h2h_win_pct_l10 | 33 | 0.0 |
| h2h_gf_avg_l10 | 268 | 0.003 |
| win_pct_l5 | 11 | 0.0 |
| win_pct_l10 | 33 | 0.0 |
| win_pct_l20 | 127 | 0.001 |
| gf_avg_l5 | 90 | 0.001 |
| gf_avg_l10 | 200 | 0.002 |
| gf_avg_l20 | 558 | 0.006 |
| ga_avg_l5 | 139 | 0.001 |
| ga_avg_l10 | 295 | 0.003 |
| ga_avg_l20 | 793 | 0.008 |
| elo | 870 | 0.009 |
| fifa_rank | 211 | 0.002 |
| fifa_points | 3 | 0.0 |

**players**

| column | n_unique | uniq_ratio |
|---|---|---|
| player_id | 18127 | 1.0 |
| name | 17364 | 0.958 |
| nationality | 158 | 0.009 |
| position | 700 | 0.039 |
| dob | 6179 | 0.341 |
| primary_club | 673 | 0.037 |
| long_name | 18102 | 0.999 |
| overall | 46 | 0.003 |
| potential | 47 | 0.003 |
| value_eur | 251 | 0.014 |
| wage_eur | 132 | 0.007 |
| age | 28 | 0.002 |
| height_cm | 49 | 0.003 |
| weight_kg | 54 | 0.003 |
| international_reputation | 5 | 0.0 |
| pace | 69 | 0.004 |
| shooting | 72 | 0.004 |
| passing | 66 | 0.004 |
| dribbling | 67 | 0.004 |
| defending | 76 | 0.004 |
| physic | 61 | 0.003 |
| nationality_norm | 158 | 0.009 |


## 1.3 Team-Name Inconsistencies

| conflicting names | issue |
|---|---|
| USA / United States | alias collision — must map to one team_id |
| Korea Republic / South Korea | alias collision — must map to one team_id |
| IR Iran / Iran | alias collision — must map to one team_id |
| Turkey / Türkiye | alias collision — must map to one team_id |
| Czech Republic / Czechia | alias collision — must map to one team_id |
| Côte d'Ivoire / Ivory Coast | alias collision — must map to one team_id |
| Cabo Verde / Cape Verde | alias collision — must map to one team_id |
| Congo DR / DR Congo | alias collision — must map to one team_id |
| Curacao / Curaçao | alias collision — must map to one team_id |
| Korea DPR / North Korea | alias collision — must map to one team_id |


Total distinct team strings across all tables: **626** → Phase 2 `dim_team` collapses these to canonical IDs.


## 1.4 Date Inconsistencies

_All dates parse and fall within plausible bounds._


## 1.5 Leakage Detection

Columns that encode the match outcome (or are only known post-match). These **must be excluded** from `ml_match_features`:

| table | leakage columns |
|---|---|
| fifa_rankings | points |
| matches | home_score, away_score, attendance |
| team_match_features | gf, ga, result |
| wc2026_fixtures | HomeTeamScore, AwayTeamScore |
| wc_matches_history | home_score, away_score, outcome, win_conditions, winning_team, losing_team |
| wc_tournaments | attendance |


⚠ `team_match_features.fifa_points` has only 3 unique values (join artifact) — flagged low-quality, drop from feature set.


## 1.6 Outlier Detection

| table | col | rule | n_flagged | extreme |
|---|---|---|---|---|
| elo_ratings | elo | outside 500-2500 | 139 | 2214 |
| matches | home_score | >15 goals | 26 | 31.0 |
| matches | away_score | >15 goals | 18 | 21.0 |
| team_match_features | gf | >15 goals | 44 | 31.0 |
| team_match_features | ga | >15 goals | 44 | 31.0 |
| team_match_features | days_rest | >2000 days | 261 | 31872.0 |


## 1.7 Structural Null Notes (expected, not errors)
- `matches.stage` 79.9% null — non-tournament friendlies have no stage.
- `team_match_features.elo` 59.9% / `fifa_rank` 45.6% null — ratings only exist from 1901/1992 onward and as-of-prior matches.
- `players` attribute axes 11.2% null — goalkeepers lack outfield ratings.
- Empty tables (`odds`, `injuries`, `team_match_stats`, `player_match_stats`, `player_tournament_stats`) — blocked/unavailable sources.