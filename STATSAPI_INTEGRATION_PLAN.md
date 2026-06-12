# StatsAPI Integration Plan

Date: 2026-06-12

## Run status

The maximum-value collector was implemented and run in discovery and collect modes, but outbound sockets to both TheStatsAPI and API-Football are blocked in this workspace. The raw export files were created, but all high-signal data files have zero rows.

Actual manifest:

| Dataset | File | Rows collected | Date range | Competitions covered |
|---|---|---:|---|---|
| Matches | `data_collection_pipeline/collected_data/raw/statsapi_matches.csv` | 0 | n/a | n/a |
| Odds | `data_collection_pipeline/collected_data/raw/statsapi_odds.csv` | 0 | n/a | n/a |
| Team stats | `data_collection_pipeline/collected_data/raw/statsapi_team_stats.csv` | 0 | n/a | n/a |
| Player stats | `data_collection_pipeline/collected_data/raw/statsapi_player_stats.csv` | 0 | n/a | n/a |
| Lineups | `data_collection_pipeline/collected_data/raw/statsapi_lineups.csv` | 0 | n/a | n/a |
| Injuries | `data_collection_pipeline/collected_data/raw/statsapi_injuries.csv` | 0 | n/a | n/a |
| Competitions | `data_collection_pipeline/collected_data/raw/statsapi_competitions.csv` | 0 | n/a | n/a |
| Seasons | `data_collection_pipeline/collected_data/raw/statsapi_seasons.csv` | 0 | n/a | n/a |

## How to produce the real collection

Run from a network-unblocked environment:

```powershell
$env:STATSAPI_KEY = "<key>"
$env:APIFOOTBALL_KEY = "<key>"
python data_collection_pipeline\src\s12_statsapi_max_collect.py all
```

The script is designed to:

1. Fetch all competitions.
2. Filter target international competitions.
3. Fetch seasons/groups/standings.
4. Fetch all matches for target competition-season pairs.
5. For every discovered match, fetch odds, team stats, player stats, lineups, and injuries.
6. Write both flattened CSVs and raw JSONL response archives.

## Dataset integration details

### `statsapi_matches.csv`

- Current rows: 0.
- Expected join keys: `date/kickoff`, `home_team`, `away_team`, provider `id`/`match_id`.
- Existing project join target: `fifa_wc_data/db/football.db::matches` and `research_ready_dataset/team_mapping.csv`.
- Expected feature additions:
  - API-native match IDs for downstream stats/odds joins.
  - Competition and season IDs for filtering World Cup, qualifiers, Euro, Copa America, Nations League, and friendlies.
  - Live/final status fields for the live loop.
- Estimated log-loss impact: indirect, 0.000 to 0.005 by itself.
- Priority: P0 because all other StatsAPI tables need stable match IDs.

### `statsapi_odds.csv`

- Current rows: 0.
- Expected join keys: `match_id`, `bookmaker`, `market`, `last_update`, plus home/away/date for project match join.
- Existing project join target: `odds_implied_recent`, future `odds_implied`, simulator market benchmark.
- Expected feature additions:
  - Closing or last-seen 1X2 implied probabilities.
  - Opening 1X2 implied probabilities.
  - Odds movement: open-to-close delta, market entropy, bookmaker disagreement.
  - Pinnacle/Betfair fair-price benchmark.
  - Totals/AH market context for Dixon-Coles calibration.
- Estimated log-loss impact: 0.020 to 0.060 if 2016-2026 international coverage is broad; highest-value dataset.
- Priority: P0.

### `statsapi_team_stats.csv`

- Current rows: 0.
- Expected join keys: `match_id`, `team_id`, `team`, plus side inference against match home/away.
- Existing project join target: `team_match_stats`, feature builder rolling-form tables.
- Expected feature additions:
  - xG for/against rolling averages.
  - npxG for/against rolling averages.
  - xG shot quality and finishing delta.
  - Shots, shots on target, possession, passes, corners, cards.
  - Recent form independent of goals-only noise.
- Estimated log-loss impact: 0.010 to 0.030, larger for 2025-2026 deployment rows.
- Priority: P1 after odds.

### `statsapi_player_stats.csv`

- Current rows: 0.
- Expected join keys: `match_id`, `team_id`, `player_id`, player name.
- Existing project join target: `player_match_stats`, scorer model, squad aggregates.
- Expected feature additions:
  - Player xG/npxG/xA, shots, minutes, cards.
  - Team attacking-quality aggregation weighted by current squad minutes/form.
  - Star-player availability and form indicators.
- Estimated log-loss impact: 0.003 to 0.015 for match outcome; higher for scorer props.
- Priority: P2.

### `statsapi_lineups.csv`

- Current rows: 0.
- Expected join keys: `match_id`, `team_id`, `player_id`, shirt number/name.
- Existing project join target: `starting_lineups`, live update pipeline.
- Expected feature additions:
  - Confirmed starters count.
  - Formation features.
  - Missing-core-player flags.
  - Team chemistry/club-overlap features using actual XI rather than full squad.
- Estimated log-loss impact: 0.003 to 0.012 pre-match; highest for live matchday updates.
- Priority: P2, P1 during WC 2026 matchdays.

### `statsapi_injuries.csv`

- Current rows: 0.
- Expected join keys: `team_id`, `player_id`, player name, injury/status date; sometimes `match_id`.
- Existing project join target: `injuries`, `availability_overrides.csv` if created later.
- Expected feature additions:
  - Player unavailable/doubtful/suspended flags.
  - Star availability penalty based on caps, goals, club quality, or player xG contribution.
- Estimated log-loss impact: 0.002 to 0.010; spike impact for individual matches.
- Priority: P3, upgraded to P1 for live WC matchdays.

## Recommended execution order once network is unblocked

1. Run `discover` and verify at least `/football/competitions`, `/football/matches`, `/football/matches/{id}/stats`, and `/football/matches/{id}/odds` return HTTP 200.
2. Run `all` against TheStatsAPI.
3. If TheStatsAPI target international coverage is thin, run API-Football discovery and use it for fixtures, lineups, injuries, and generic match statistics.
4. Only after raw exports are non-empty, build a separate normalization/join step. Do not fold normalization into raw collection.

## Integration acceptance checks

- `statsapi_matches.csv` contains international competitions from at least 2016-2026.
- `statsapi_odds.csv` contains 1X2 market rows from at least one sharp source: Pinnacle or Betfair Exchange.
- `statsapi_team_stats.csv` has non-null xG or npxG columns for target matches.
- Team names are mapped through `research_ready_dataset/team_mapping.csv`.
- No forbidden model leakage fields are used as pre-match features: goals for/against, result, points, score, attendance, outcome.

