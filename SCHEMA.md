# Dataset Structure — SQLite Schema (`fifa_wc_data/db/football.db`)

*27 tables. The database itself is rebuilt by the pipeline (`python src/run_all.py`); this file documents its structure.*

### `dim_team`  —  575 rows, 5 columns

| column | type | pk |
|---|---|:--:|
| team_id | INTEGER |  |
| canonical_name | TEXT |  |
| aliases | TEXT |  |
| fifa_code | TEXT |  |
| continent | TEXT |  |

### `elo_ratings`  —  18,142 rows, 4 columns

| column | type | pk |
|---|---|:--:|
| date | TEXT |  |
| team | TEXT |  |
| elo | INTEGER |  |
| elo_change | INTEGER |  |

### `fifa_rankings`  —  67,261 rows, 4 columns

| column | type | pk |
|---|---|:--:|
| date | TEXT |  |
| team | TEXT |  |
| ranking | REAL |  |
| points | REAL |  |

### `goalscorers`  —  47,601 rows, 8 columns

| column | type | pk |
|---|---|:--:|
| date | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| team | TEXT |  |
| scorer | TEXT |  |
| minute | REAL |  |
| own_goal | INTEGER |  |
| penalty | INTEGER |  |

### `injuries`  —  0 rows, 5 columns

| column | type | pk |
|---|---|:--:|
| player_id | TEXT |  |
| injury_date | TEXT |  |
| return_date | TEXT |  |
| injury_type | TEXT |  |
| days_missed | TEXT |  |

### `market_values`  —  48 rows, 6 columns

| column | type | pk |
|---|---|:--:|
| date | TEXT |  |
| team | TEXT |  |
| total_value | REAL |  |
| avg_value | REAL |  |
| median_value | REAL |  |
| n_players | INTEGER |  |

### `matches`  —  49,353 rows, 14 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| date | TEXT |  |
| competition | TEXT |  |
| stage | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| home_score | REAL |  |
| away_score | REAL |  |
| neutral | INTEGER |  |
| city | TEXT |  |
| country | TEXT |  |
| venue | TEXT |  |
| referee | TEXT |  |
| attendance | TEXT |  |

### `matches_norm`  —  49,353 rows, 16 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| date | TEXT |  |
| competition | TEXT |  |
| stage | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| home_score | REAL |  |
| away_score | REAL |  |
| neutral | INTEGER |  |
| city | TEXT |  |
| country | TEXT |  |
| venue | TEXT |  |
| referee | TEXT |  |
| attendance | TEXT |  |
| home_team_id | INTEGER |  |
| away_team_id | INTEGER |  |

### `ml_match_features`  —  49,281 rows, 47 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| date | TIMESTAMP |  |
| team_id_home | INTEGER |  |
| team_id_away | INTEGER |  |
| team_home | TEXT |  |
| team_away | TEXT |  |
| tournament | TEXT |  |
| stage | TEXT |  |
| elo_diff | REAL |  |
| fifa_rank_diff | REAL |  |
| fifa_rank_ratio | REAL |  |
| form_diff_last_5 | REAL |  |
| form_diff_last_10 | REAL |  |
| form_diff_last_20 | REAL |  |
| goals_for_diff | REAL |  |
| goals_against_diff | REAL |  |
| h2h_win_pct_diff | REAL |  |
| h2h_goal_diff | REAL |  |
| days_rest_diff | REAL |  |
| wc_experience_diff | INTEGER |  |
| streak_diff | INTEGER |  |
| neutral_flag | INTEGER |  |
| stage_weight | INTEGER |  |
| rivalry_flag | INTEGER |  |
| home_field | INTEGER |  |
| elo_trend_diff | REAL |  |
| rank_trend_diff | REAL |  |
| goal_trend_diff | REAL |  |
| attack_rating_diff | REAL |  |
| defense_rating_diff | REAL |  |
| net_rating_diff | REAL |  |
| pedigree_diff | INTEGER |  |
| strength_ratio | REAL |  |
| relative_strength | REAL |  |
| elo_expected_home | REAL |  |
| upset_proxy | REAL |  |
| elo_diff_x_stage | REAL |  |
| elo_diff_x_homefield | REAL |  |
| formdiff10_x_elodiff | REAL |  |
| rankratio_x_formdiff10 | REAL |  |
| restdiff_x_stage | REAL |  |
| netrating_x_homefield | REAL |  |
| pedigree_x_stage | INTEGER |  |
| elo_home | REAL |  |
| elo_away | REAL |  |
| fifa_rank_home | REAL |  |
| fifa_rank_away | REAL |  |

### `odds`  —  0 rows, 9 columns

| column | type | pk |
|---|---|:--:|
| date | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| bookmaker | TEXT |  |
| home_odds | TEXT |  |
| draw_odds | TEXT |  |
| away_odds | TEXT |  |
| over25_odds | TEXT |  |
| under25_odds | TEXT |  |

### `odds_bank`  —  479,440 rows, 19 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| league | TEXT |  |
| match_date | TEXT |  |
| home_team | TEXT |  |
| home_score | INTEGER |  |
| away_team | TEXT |  |
| away_score | INTEGER |  |
| avg_odds_home_win | REAL |  |
| avg_odds_draw | REAL |  |
| avg_odds_away_win | REAL |  |
| max_odds_home_win | REAL |  |
| max_odds_draw | REAL |  |
| max_odds_away_win | REAL |  |
| top_bookie_home_win | TEXT |  |
| top_bookie_draw | TEXT |  |
| top_bookie_away_win | TEXT |  |
| n_odds_home_win | INTEGER |  |
| n_odds_draw | INTEGER |  |
| n_odds_away_win | INTEGER |  |

### `official_squads_2026`  —  1,246 rows, 8 columns

| column | type | pk |
|---|---|:--:|
| team | TEXT |  |
| shirt_no | INTEGER |  |
| position | TEXT |  |
| player | TEXT |  |
| dob_age | TEXT |  |
| caps | INTEGER |  |
| goals | INTEGER |  |
| club | TEXT |  |

### `player_match_stats`  —  0 rows, 12 columns

| column | type | pk |
|---|---|:--:|
| match_id | TEXT |  |
| player_id | TEXT |  |
| min | TEXT |  |
| gls | TEXT |  |
| ast | TEXT |  |
| xg | TEXT |  |
| npxg | TEXT |  |
| xag | TEXT |  |
| sca | TEXT |  |
| gca | TEXT |  |
| tkl | TEXT |  |
| int | TEXT |  |

### `player_tournament_stats`  —  0 rows, 8 columns

| column | type | pk |
|---|---|:--:|
| tournament | TEXT |  |
| player_id | TEXT |  |
| gp | TEXT |  |
| gls | TEXT |  |
| ast | TEXT |  |
| xg | TEXT |  |
| npxg | TEXT |  |
| xag | TEXT |  |

### `players`  —  18,127 rows, 22 columns

| column | type | pk |
|---|---|:--:|
| player_id | INTEGER |  |
| name | TEXT |  |
| nationality | TEXT |  |
| position | TEXT |  |
| dob | TEXT |  |
| primary_club | TEXT |  |
| long_name | TEXT |  |
| overall | INTEGER |  |
| potential | INTEGER |  |
| value_eur | REAL |  |
| wage_eur | REAL |  |
| age | INTEGER |  |
| height_cm | INTEGER |  |
| weight_kg | INTEGER |  |
| international_reputation | INTEGER |  |
| pace | REAL |  |
| shooting | REAL |  |
| passing | REAL |  |
| dribbling | REAL |  |
| defending | REAL |  |
| physic | REAL |  |
| nationality_norm | TEXT |  |

### `sb_matches`  —  128 rows, 10 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| tournament | TEXT |  |
| date | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| home_score | INTEGER |  |
| away_score | INTEGER |  |
| stage | TEXT |  |
| stadium | TEXT |  |
| referee | TEXT |  |

### `sb_player_match_stats`  —  1,757 rows, 7 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| tournament | TEXT |  |
| team | TEXT |  |
| player | TEXT |  |
| xg | REAL |  |
| shots | INTEGER |  |
| goals | INTEGER |  |

### `sb_team_match_stats`  —  255 rows, 6 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| tournament | TEXT |  |
| team | TEXT |  |
| xg | REAL |  |
| shots | INTEGER |  |
| goals | INTEGER |  |

### `squads`  —  12,948 rows, 6 columns

| column | type | pk |
|---|---|:--:|
| tournament | TEXT |  |
| team | TEXT |  |
| player_id | INTEGER |  |
| age_at_tournament | INTEGER |  |
| caps_at_tournament | TEXT |  |
| market_value | REAL |  |

### `starting_lineups`  —  2,816 rows, 7 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| tournament | TEXT |  |
| team | TEXT |  |
| player | TEXT |  |
| position | TEXT |  |
| jersey_number | INTEGER |  |
| starter | INTEGER |  |

### `team_match_features`  —  98,562 rows, 30 columns

| column | type | pk |
|---|---|:--:|
| match_id | INTEGER |  |
| date | TEXT |  |
| team | TEXT |  |
| opponent | TEXT |  |
| is_home | INTEGER |  |
| tournament | TEXT |  |
| stage | TEXT |  |
| stage_weight | INTEGER |  |
| rivalry | INTEGER |  |
| neutral | INTEGER |  |
| gf | REAL |  |
| ga | REAL |  |
| result | TEXT |  |
| days_rest | REAL |  |
| result_streak_in | INTEGER |  |
| wc_appearances_before | INTEGER |  |
| h2h_win_pct_l10 | REAL |  |
| h2h_gf_avg_l10 | REAL |  |
| win_pct_l5 | REAL |  |
| win_pct_l10 | REAL |  |
| win_pct_l20 | REAL |  |
| gf_avg_l5 | REAL |  |
| gf_avg_l10 | REAL |  |
| gf_avg_l20 | REAL |  |
| ga_avg_l5 | REAL |  |
| ga_avg_l10 | REAL |  |
| ga_avg_l20 | REAL |  |
| elo | REAL |  |
| fifa_rank | REAL |  |
| fifa_points | INTEGER |  |

### `team_match_stats`  —  0 rows, 13 columns

| column | type | pk |
|---|---|:--:|
| match_id | TEXT |  |
| team | TEXT |  |
| poss | TEXT |  |
| sh | TEXT |  |
| sot | TEXT |  |
| xg | TEXT |  |
| npxg | TEXT |  |
| sca | TEXT |  |
| gca | TEXT |  |
| tkl | TEXT |  |
| int | TEXT |  |
| touches | TEXT |  |
| passes_cmp | TEXT |  |

### `venues`  —  16 rows, 7 columns

| column | type | pk |
|---|---|:--:|
| venue_id | INTEGER |  |
| name | TEXT |  |
| city | TEXT |  |
| country | TEXT |  |
| lat | REAL |  |
| lng | REAL |  |
| altitude_m | REAL |  |

### `wc2026_fixtures`  —  104 rows, 9 columns

| column | type | pk |
|---|---|:--:|
| MatchNumber | INTEGER |  |
| RoundNumber | INTEGER |  |
| DateUtc | TEXT |  |
| Location | TEXT |  |
| HomeTeam | TEXT |  |
| AwayTeam | TEXT |  |
| Group | TEXT |  |
| HomeTeamScore | REAL |  |
| AwayTeamScore | REAL |  |

### `wc2026_qualified_teams`  —  49 rows, 3 columns

| column | type | pk |
|---|---|:--:|
| team | TEXT |  |
| group | TEXT |  |
| tournament | TEXT |  |

### `wc_matches_history`  —  900 rows, 15 columns

| column | type | pk |
|---|---|:--:|
| year | INTEGER |  |
| country | TEXT |  |
| city | TEXT |  |
| stage | TEXT |  |
| home_team | TEXT |  |
| away_team | TEXT |  |
| home_score | INTEGER |  |
| away_score | INTEGER |  |
| outcome | TEXT |  |
| win_conditions | TEXT |  |
| winning_team | TEXT |  |
| losing_team | TEXT |  |
| date | TEXT |  |
| month | TEXT |  |
| dayofweek | TEXT |  |

### `wc_tournaments`  —  21 rows, 10 columns

| column | type | pk |
|---|---|:--:|
| year | INTEGER |  |
| host | TEXT |  |
| winner | TEXT |  |
| second | TEXT |  |
| third | TEXT |  |
| fourth | TEXT |  |
| goals_scored | INTEGER |  |
| teams | INTEGER |  |
| games | INTEGER |  |
| attendance | INTEGER |  |
