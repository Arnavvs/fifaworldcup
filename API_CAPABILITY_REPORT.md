# API Capability Report - TheStatsAPI and API-Football

Date: 2026-06-12

## Bottom line

TheStatsAPI is still the best-fit source for this project on paper: it advertises the exact combination we need: historical match data, xG/npxG/xA, match/team/player stats, lineups, and pre-match/live odds with opening and closing or last-seen prices.

However, the credentialed discovery run from this workspace could not reach either TheStatsAPI or API-Football. Every tested request failed before HTTP with:

`URLError(PermissionError(13, 'An attempt was made to access a socket in a way forbidden by its access permissions', None, 10013, None))`

So no credentialed API payload was returned and no real data rows were collected in this environment. Endpoint probes and sample error JSON files were saved under `data_collection_pipeline/collected_data/raw/statsapi_samples/`.

## Collection asset created

Script:

`data_collection_pipeline/src/s12_statsapi_max_collect.py`

Run from a network-unblocked shell with:

```powershell
$env:STATSAPI_KEY = "<key>"
$env:APIFOOTBALL_KEY = "<key>"
python data_collection_pipeline\src\s12_statsapi_max_collect.py all
```

The script exports raw CSVs and JSONL response archives. It does not modify models, dashboards, or the database.

## TheStatsAPI public capability check

Source URLs:

- https://www.thestatsapi.com/
- https://www.thestatsapi.com/coverage
- https://www.thestatsapi.com/odds-api

Public docs state:

- 27 football endpoints across competitions, teams, matches, players, and odds.
- 150 default competitions, up to 1,196 on request.
- 10 years of historical match data, with exact depth varying by competition.
- Match stats include shots, xG, possession, passes, cards, goals, and events.
- Advanced analytics include xG, npxG, xA, and deeper metrics.
- Odds include Bet365, Pinnacle, Betfair Exchange, and Kambi.
- Markets include 1X2, Asian handicap, totals, BTTS, DNB, and corners.
- Opening, live, last-seen, and closing-price proxy lines are included where captured.
- Live odds endpoint documented as `/football/matches/{match_id}/odds/live`.
- Pre-match odds endpoint documented as `/football/matches/{match_id}/odds`.
- Match stats demo endpoint documented as `/api/football/matches/mt_010249745/stats`.

## TheStatsAPI endpoint enumeration

The following endpoints were enumerated into `statsapi_endpoint_discovery.csv` and probed where possible:

| Category | Endpoint |
|---|---|
| Competitions | `/football/competitions` |
| Competitions | `/football/competitions/{competition_id}` |
| Competitions | `/football/competitions/{competition_id}/seasons` |
| Competitions | `/football/competitions/{competition_id}/seasons/{season_id}/groups` |
| Competitions | `/football/competitions/{competition_id}/seasons/{season_id}/standings` |
| Teams | `/football/teams` |
| Teams | `/football/teams/{team_id}` |
| Teams | `/football/teams/{team_id}/matches` |
| Teams | `/football/teams/{team_id}/players` |
| Teams | `/football/teams/{team_id}/squad` |
| Teams | `/football/teams/{team_id}/stats` |
| Matches | `/football/matches` |
| Matches | `/football/matches/{match_id}` |
| Matches | `/football/matches/{match_id}/stats` |
| Matches | `/football/matches/{match_id}/events` |
| Matches | `/football/matches/{match_id}/lineups` |
| Matches | `/football/matches/{match_id}/players` |
| Matches | `/football/matches/{match_id}/player-stats` |
| Matches | `/football/matches/{match_id}/injuries` |
| Odds | `/football/matches/{match_id}/odds` |
| Odds | `/football/matches/{match_id}/odds/live` |
| Odds | `/football/matches/{match_id}/odds/history` |
| Odds | `/football/odds` |
| Odds | `/football/odds/live` |
| Odds | `/football/odds/sports` |
| Players | `/football/players` |
| Players | `/football/players/{player_id}` |
| Players | `/football/players/{player_id}/stats` |
| Players | `/football/players/{player_id}/matches` |

Credentialed result from this workspace: all status `0`, socket blocked before HTTP.

## Competition coverage targets

TheStatsAPI public coverage page explicitly says default coverage includes international tournaments like the World Cup, Euros, and Copa America. Public docs do not confirm World Cup qualifiers, Nations League, or international friendlies by name in the static page text; the collector therefore discovers all competitions first and filters by:

- FIFA World Cup
- World Cup qualifiers
- Euro
- Copa America
- Nations League
- International friendlies

API-Football public coverage page lists broad coverage of 1,232 leagues/cups and has a detailed coverage table including fixture, player, standing, event, lineup, statistic, prediction, odds, and top-scorer coverage columns. It lists Copa America and Euro Championship in the international competition section. The static page also lists many global competitions, but credentialed coverage could not be tested locally.

## Feature availability matrix

| Data need | TheStatsAPI public docs | Credentialed test in this workspace | API-Football public docs | Credentialed test in this workspace |
|---|---|---|---|---|
| Closing odds | Yes, closing/last-seen where captured | Blocked before HTTP | Odds coverage exists; closing not confirmed | Blocked before HTTP |
| Opening odds | Yes | Blocked before HTTP | Not confirmed | Blocked before HTTP |
| Historical odds | Yes, archive/pre-match history | Blocked before HTTP | Odds endpoint exists; historical depth not verified | Blocked before HTTP |
| Bookmaker odds | Bet365, Pinnacle, Betfair Exchange, Kambi | Blocked before HTTP | Odds endpoint exists | Blocked before HTTP |
| xG | Yes | Blocked before HTTP | Not clearly confirmed in docs checked | Blocked before HTTP |
| npxG | Yes | Blocked before HTTP | Not confirmed | Blocked before HTTP |
| xA | Yes | Blocked before HTTP | Not confirmed | Blocked before HTTP |
| Shots | Yes | Blocked before HTTP | Fixture statistics endpoint exists | Blocked before HTTP |
| Possession | Yes | Blocked before HTTP | Fixture statistics endpoint exists | Blocked before HTTP |
| Cards | Yes | Blocked before HTTP | Events/statistics endpoints exist | Blocked before HTTP |
| Lineups | Yes | Blocked before HTTP | Fixture lineups endpoint exists | Blocked before HTTP |
| Injuries | Candidate endpoint probed; not publicly confirmed on static page | Blocked before HTTP | Injuries endpoint exists | Blocked before HTTP |
| Player statistics | Yes | Blocked before HTTP | Fixture players/players endpoints exist | Blocked before HTTP |

## Raw files created

The following files now exist under `data_collection_pipeline/collected_data/raw/`:

- `statsapi_matches.csv`
- `statsapi_odds.csv`
- `statsapi_team_stats.csv`
- `statsapi_player_stats.csv`
- `statsapi_lineups.csv`
- `statsapi_injuries.csv`
- `statsapi_competitions.csv`
- `statsapi_target_competitions.csv`
- `statsapi_seasons.csv`
- `statsapi_groups.csv`
- `statsapi_standings.csv`
- `statsapi_endpoint_discovery.csv`
- `statsapi_request_log.csv`
- `statsapi_run_manifest.json`
- `statsapi_collection_summary.json`

Because the local socket was blocked, these collection CSVs currently contain zero data rows.

