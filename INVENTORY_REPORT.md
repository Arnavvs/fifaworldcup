# FIFA World Cup 2026 — Dataset Inventory & Coverage Report

*Generated from `fifa_wc_data/db/football.db` (18 tables, ~30 MB) and `processed/` CSVs.*
*Snapshot date context: 2026-06-02.*

---

## 1. Per-Table Inventory

Legend: **PK** = primary key, **null%** measured on populated tables. Empty tables are schema-only placeholders for blocked/unavailable sources.

### `matches` — canonical match table
| # | Property | Value |
|---|----------|-------|
| 1 | Rows | **49,353** |
| 2 | Cols | 14 |
| 3 | Columns | match_id, date, competition, stage, home_team, away_team, home_score, away_score, neutral, city, country, venue, referee, attendance |
| 4 | Types | match_id int, date object, scores float, neutral int, rest object |
| 5 | Null % | stage **79.9%**, home/away_score 0.1% (future fixtures), referee **100%**, attendance **100%**, rest ~0% |
| 6 | Dates | 1872-11-30 → 2026-06-27 |
| 7 | PK | `match_id` |
| 8 | FKs | ← `team_match_features.match_id`; (string) home/away_team join to elo/rankings/market_values |
| 9 | Targets | `home_score`, `away_score` (Poisson), result derived (W/D/L), total goals O/U |
| 10 | Features | competition, stage, neutral, city/country (venue context) |
| 11 | Leakage | **home_score, away_score, attendance** (post-match) |
| 12 | Missing | referee (100% null), attendance (100% null), kickoff time, xG |

### `team_match_features` — derived analytical core
| # | Property | Value |
|---|----------|-------|
| 1 | Rows | **98,562** (one per team-per-match) |
| 2 | Cols | 30 |
| 3 | Columns | match_id, date, team, opponent, is_home, tournament, stage, stage_weight, rivalry, neutral, gf, ga, result, days_rest, result_streak_in, wc_appearances_before, h2h_win_pct_l10, h2h_gf_avg_l10, win_pct_l{5,10,20}, gf_avg_l{5,10,20}, ga_avg_l{5,10,20}, elo, fifa_rank, fifa_points |
| 5 | Null % | elo **59.9%**, fifa_rank **45.6%**, h2h **15.2%**, form windows 0.3%, days_rest 0.3% |
| 6 | Dates | 1872-11-30 → 2026-05-31 |
| 7 | PK | composite (`match_id`, `team`) |
| 8 | FKs | match_id → matches; team/opponent → string team keys |
| 9 | Targets | **`result`** (W/D/L multiclass), `gf`/`ga` (Poisson), `points` |
| 10 | Features | elo, fifa_rank, form (win%/gf/ga L5-20), h2h, days_rest, is_home, neutral, stage_weight, rivalry, result_streak_in, wc_appearances_before |
| 11 | Leakage | **gf, ga, result, points** (same-match outcomes — exclude from X). `fifa_points` is **suspect** (only 3 unique values — a join artifact; drop it) |
| 12 | Missing | xG/xGA rolling, squad-value diff, rest/travel for non-WC matches, lineup strength |

### `players` — FIFA-game attribute layer (proxy)
| # | Value |
|---|-------|
| Rows / Cols | **18,127** / 22 |
| Columns | player_id, name, nationality, position, dob, primary_club, long_name, overall, potential, value_eur, wage_eur, age, height_cm, weight_kg, international_reputation, pace, shooting, passing, dribbling, defending, physic, nationality_norm |
| Null % | pace/shooting/passing/dribbling/defending/physic **11.2%** (goalkeepers have no outfield ratings), value_eur 0.5% |
| PK | `player_id` |
| FK | ← `squads.player_id` |
| Targets | (not a target table) |
| Features | overall, potential, value_eur, age, position, the 6 FIFA attribute axes |
| Leakage | none (static pre-tournament attributes) |
| Missing | real match stats, caps, current form, club minutes, injury flag |

### `squads` — WC-2026 national talent pool
| # | Value |
|---|-------|
| Rows / Cols | **12,948** / 6 (≈ all FIFA-rated nationals of the 48 teams, **not** official 26-man lists) |
| Columns | tournament, team, player_id, age_at_tournament, caps_at_tournament, market_value |
| Null % | **caps_at_tournament 100%**, market_value 0.6% |
| PK | composite (tournament, team, player_id) |
| FK | player_id → players; team → wc2026_qualified_teams |
| Missing | official squad selection, caps, shirt number, starter/bench role |

### `elo_ratings`
| Rows/Cols | **18,142** / 4 — date, team, elo, elo_change |
| Null % | team 0.2%; Dates 1901-12-31 → 2026-06-02; 295 teams |
| PK | composite (date, team) |
| Note | **year-end granularity** (not per-match); as-of-joined into features |
| Leakage | none (prior ratings) |

### `fifa_rankings`
| Rows/Cols | **67,261** / 4 — date, team, ranking, points |
| Dates | 1992-12-31 → **2024-04-04** (⚠ ~2 yr stale; missing 2024-05 → 2026) |
| PK | composite (date, team); 216 teams |

### `goalscorers`
| Rows/Cols | **47,601** / 8 — date, home_team, away_team, team, scorer, minute, own_goal, penalty |
| Dates | 1916-07-02 → 2026-03-31; 15,334 distinct scorers |
| PK | none (event-level; composite date+teams+scorer+minute) |
| FK | → matches (by date+teams, no id) |
| Use | derive scorer form, goal-timing, set-piece/penalty rates |

### `market_values`
| Rows/Cols | **48** / 6 — date, team, total_value, avg_value, median_value, n_players |
| Dates | single snapshot **2022-09-01** (FIFA23) |
| PK | team |
| Missing | historical WC-year values, real Transfermarkt €, time series |

### `venues`
| Rows/Cols | **16** / 7 — venue_id, name, city, country, lat, lng, altitude_m |
| Null % | 6.2% (Guadalajara failed geocode) |
| PK | venue_id; **WC-2026 only** (no historical venue coords) |
| Highlight | altitude captured (Mexico City 2,287 m) |

### `wc2026_fixtures` / `wc2026_qualified_teams`
| `wc2026_fixtures` | 104 rows / 9 cols; 2026-06-11 → 2026-07-19; scores 100% null (future). PK MatchNumber |
| `wc2026_qualified_teams` | 49 rows (48 teams + 1 "To be announced" playoff slot); team, group, tournament |

### `wc_matches_history` / `wc_tournaments`
| `wc_matches_history` | **900** / 15; 1930-2018; full stage, win_conditions, winner/loser. PK composite |
| `wc_tournaments` | 21 / 10; host, winner, top-4, goals, teams, games, attendance |

### Empty tables (blocked/unavailable sources — schema-only)
| Table | Cols | Reason |
|-------|------|--------|
| `team_match_stats` | 13 | FBref Cloudflare-blocked (xG, SCA, possession…) |
| `player_match_stats` | 12 | FBref Cloudflare-blocked |
| `player_tournament_stats` | 8 | depends on FBref |
| `injuries` | 5 | Transfermarkt anti-bot-blocked |
| `odds` | 9 | football-data.co.uk has no intl odds feed |

---

## 2. Cross-Table Key Map

```
matches(match_id) ─1:2─ team_match_features(match_id, team)
players(player_id) ─1:N─ squads(player_id)
wc2026_qualified_teams(team) ─1:N─ squads(team), ─1:1─ market_values(team)
matches(home/away_team,date) ─*─ goalscorers(home/away_team,date)   [string/date join, no enforced FK]
team names ─*─ elo_ratings(team), fifa_rankings(team)               [string as-of join on date]
wc2026_fixtures(Location) ─*─ venues(name)                          [string join]
```
⚠ Most cross-source links are **string team-name joins**, not integer FKs — a normalization/`dim_team` table is the single highest-leverage schema fix.

---

## 3. Modelling Readiness

**Best-supported targets (today):**
1. `result` — W/D/L multiclass (full history, leakage-safe features exist).
2. `gf` / `ga` — bivariate Poisson / Dixon-Coles (goal-based simulation).
3. Total goals Over/Under 2.5.
4. WC progression / winner (tournament-level via Monte Carlo over the match model).

**Clean feature set (leakage-safe, available now):** `elo`, `fifa_rank`, `win_pct_l{5,10,20}`, `gf_avg_l*`, `ga_avg_l*`, `h2h_win_pct_l10`, `h2h_gf_avg_l10`, `days_rest`, `is_home`, `neutral`, `stage_weight`, `rivalry`, `result_streak_in`, `wc_appearances_before`, squad `total_value`/`avg overall`.

**Must-exclude (leakage):** `gf`, `ga`, `result`, `points`, `home_score`, `away_score`, `attendance`, `winning_team`/`losing_team`/`outcome`/`win_conditions` (WC history), `HomeTeamScore`/`AwayTeamScore`, and the artifact `fifa_points`.

---

## 4. Football Analytics Coverage Matrix

| Category | Rating | Evidence / Gap |
|----------|:------:|----------------|
| Match results | **COMPLETE** | 49,353 matches 1872→2026, scores, neutral flag |
| Team strength | **GOOD** | ELO (annual) + FIFA rank + rolling form; lacks per-match ELO & xG-based strength |
| Player performance | **PARTIAL** | FIFA-game ratings only; no real match stats (FBref empty) |
| Squad data | **PARTIAL** | National pools, not official 26-man squads; caps 100% null |
| Injuries | **MISSING** | table empty (Transfermarkt blocked) |
| Market values | **PARTIAL** | FIFA `value_eur` proxy, single 2022 snapshot; no TM history |
| Rankings | **GOOD** | FIFA 1992→2024 (⚠ ~2 yr stale, missing 2024-26) |
| ELO | **GOOD** | 1901→2026 but **year-end only**, not per-match |
| Betting odds | **MISSING** | table empty; no intl odds source wired |
| Venues | **PARTIAL** | 2026 venues geocoded + altitude; no historical venue coords/capacity |
| Travel | **MISSING** | not computed; no team-base → venue distances |
| Weather | **MISSING** | none |
| Referees | **MISSING** | `referee` column 100% null |
| Tactical styles | **MISSING** | no formation/PPDA/possession data |
| Starting lineups | **MISSING** | none |
| Club performance | **MISSING** | players' `primary_club` known, but no club match results/form |
| Player availability | **MISSING** | no suspensions/fitness/selection data |
| Expected goals (xG) | **MISSING** | FBref/StatsBomb empty |
| Tournament simulations | **MISSING** | no sim engine yet (feasible from match model) |

**Scoreboard:** COMPLETE 1 · GOOD 3 · PARTIAL 4 · MISSING 11.

---

## 5. Top 20 Datasets to Add (ranked by prediction lift)

Predictive value scale: ★★★★★ = transformative … ★ = marginal. Difficulty: Easy / Med / Hard. "Pre-train?" = needed before first serious model.

| # | Dataset | Predictive value | Difficulty | Pre-train? |
|---|---------|:---------------:|:----------:|:----------:|
| 1 | **Bookmaker closing odds** (intl + WC) — the market is the single strongest baseline | ★★★★★ | Med | **Yes** |
| 2 | **FBref/StatsBomb xG & shot data** (team + player, per match) | ★★★★★ | Hard | **Yes** |
| 3 | **Official 26-man WC-2026 squads + caps + minutes** | ★★★★☆ | Med | **Yes** |
| 4 | **Per-match ELO** (clubelo/eloratings full series) | ★★★★☆ | Med | **Yes** |
| 5 | **Live FIFA rankings 2024→2026** (close the staleness gap) | ★★★★☆ | Easy | **Yes** |
| 6 | **Transfermarkt squad market values (time series + WC years)** | ★★★★☆ | Hard | Yes |
| 7 | **Player club form/minutes the season before WC** (fatigue/sharpness) | ★★★★☆ | Med | Yes |
| 8 | **Injuries & suspensions / availability feed** | ★★★★☆ | Hard | Yes |
| 9 | **Starting lineups + formations** (historical) | ★★★★☆ | Hard | No |
| 10 | **Travel distances + time-zone shift per match** (compute from venues) | ★★★☆☆ | Easy | No |
| 11 | **Venue altitude/capacity for all historical venues** | ★★★☆☆ | Med | No |
| 12 | **Weather at kickoff** (temp, humidity, precip) | ★★★☆☆ | Med | No |
| 13 | **Referee profiles** (cards/penalties/home-bias tendencies) | ★★★☆☆ | Med | No |
| 14 | **Set-piece & penalty conversion rates** (from goalscorers + event data) | ★★★☆☆ | Easy | No |
| 15 | **Manager/coach history & tenure** | ★★★☆☆ | Med | No |
| 16 | **Club competition load** (UCL/league congestion proxy) | ★★★☆☆ | Med | No |
| 17 | **Tactical style metrics** (PPDA, possession, pressing) | ★★★☆☆ | Hard | No |
| 18 | **Qualification-campaign performance** (strength-of-schedule adj.) | ★★★☆☆ | Easy | No |
| 19 | **Goal-timing / game-state sequences** | ★★☆☆☆ | Med | No |
| 20 | **Fan/attendance & home-advantage intensity** | ★★☆☆☆ | Med | No |

**Biggest immediate wins:** #1 odds, #5 live rankings, #4 per-match ELO, #10 travel — all high-value and Easy/Med, and three of them are computable from data already present.

---

## 6. Proposed Dataset Tiers

### A) Minimal Viable Dataset (ship a credible model this week)
- ✅ `matches`, `team_match_features` (already built)
- ✅ ELO + FIFA rank as-of features (built)
- ➕ **Live FIFA rankings 2024→2026** (#5, Easy)
- ➕ **Travel distance + rest** for fixtures (#10, compute from `venues`)
- ➕ **Closing match odds** as a benchmark/feature (#1)
- **Target:** W/D/L + Poisson goals → Monte-Carlo WC simulation.
- *Good enough to beat ELO-only baselines and calibrate against the market.*

### B) Strong Portfolio Dataset (competitive, defensible)
- Everything in A, plus:
- ➕ **xG / shot data** team-level (#2) — rolling xG-for/against
- ➕ **Per-match ELO** (#4) and **squad market-value time series** (#6)
- ➕ **Official 26-man squads + caps/minutes** (#3) and **club form** (#7)
- ➕ **Injuries/availability** (#8), **travel/altitude/weather** (#10-12)
- *Multi-signal model: strength + form + availability + context. Portfolio-grade.*

### C) Professional Betting-Grade Dataset
- Everything in B, plus:
- ➕ **Player-level event data & lineups** (#2, #9, #17) for lineup-aware strength
- ➕ **Full odds history across books** (open→close line movement, #1) for value detection & devigging
- ➕ **Referee models** (#13), **set-piece/penalty models** (#14), **manager effects** (#15)
- ➕ **Live availability & weather feeds** at kickoff; **calibration + CLV tracking**
- *Lineup-conditional bivariate-Poisson / GBM ensemble, market-calibrated, with staking. This is the tier where edge over the closing line becomes plausible.*

---

## 7. Three Things To Fix First (cheap, high-impact)
1. **Add a `dim_team` normalization table** so every source joins on a `team_id` (kills the string-join fragility that already capped ELO match at 47/48).
2. **Refresh FIFA rankings to 2026** and **wire closing odds** — the two easiest high-value gaps.
3. **Drop `fifa_points`** (join artifact, 3 unique values) and **document the leakage exclusion list** in the feature pipeline.
