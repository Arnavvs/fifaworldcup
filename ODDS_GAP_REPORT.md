# Odds Gap Report

Date: 2026-06-12

Goal: find the fastest path to filling the remaining 2016-2026 international 1X2 odds gap.

## Current project odds state

- Existing free odds bank: 479,440 rows, but only 2005-2015.
- Existing recent international odds: 228 rows from OddsPortal for major tournaments only.
- Remaining critical gap: broad 2016-2026 international matches, especially World Cup qualifiers, friendlies, Nations League, Copa America, Euro, AFCON, and WC 2026 live odds.

## Credentialed test result

Credentialed requests were attempted for:

- TheStatsAPI
- API-Football

Both failed locally before HTTP due to the workspace socket restriction:

`URLError(PermissionError(13, 'An attempt was made to access a socket in a way forbidden by its access permissions', None, 10013, None))`

Saved evidence:

- `data_collection_pipeline/collected_data/raw/statsapi_endpoint_discovery.csv`
- `data_collection_pipeline/collected_data/raw/statsapi_samples/`
- `data_collection_pipeline/collected_data/raw/statsapi_request_log.csv`

No successful authenticated odds sample was obtained from this local environment.

## Ranking for filling the 2016-2026 odds gap

| Rank | Source | Endpoint/API | Coverage fit | Effort | Verdict |
|---:|---|---|---|---:|---|
| 1 | TheStatsAPI | `/api/football/matches/{match_id}/odds`, `/api/football/matches/{match_id}/odds/live` | Best on paper: football-specific, bookmakers plus match stats, opening and closing/last-seen lines | 2 after network unblock | Primary path |
| 2 | The Odds API | `/v4/historical/sports/{sport}/odds`, `/v4/historical/sports/{sport}/events`, `/v4/historical/sports/{sport}/events/{eventId}/odds` | Good from 2020-06 onward if sport keys include target international competitions | 5 | Best paid fallback for 2020-2026 |
| 3 | OddsPapi | `/v4/historical-odds?fixtureId=...&bookmakers=pinnacle,bet365` | Strong for 2026+ only; docs say historical data since January 2026 | 4 | Best WC 2026/live gap fallback |
| 4 | API-Football | `/odds`, `/fixtures`, `/fixtures/statistics`, `/fixtures/lineups`, `/injuries` | Broad competition coverage; closing/opening odds not verified | 4 | Good enrichment fallback, weaker odds certainty |
| 5 | Oddspedia | Public website pages, undocumented XHR if discovered | Current odds and archived odds claim; no stable API verified | 7 | Last resort scraping path |

## Source details

### TheStatsAPI

Public docs:

- Odds sources: Bet365, Pinnacle, Betfair Exchange, Kambi.
- Markets: 1X2, Asian handicap, over/under, BTTS, DNB, corners.
- Includes opening and latest stored/closing-price proxy lines where captured.
- Pre-match odds endpoint: `/football/matches/{match_id}/odds`.
- Live odds endpoint: `/football/matches/{match_id}/odds/live`.
- Public sample object shows bookmaker-specific nested 1X2 odds.

Local test:

- Endpoint probes were attempted with the supplied key.
- All failed before HTTP due to local socket permissions.

Recommendation:

- Run the collector from an unblocked network first. If `statsapi_odds.csv` gets broad international rows, stop the odds hunt and normalize this dataset.

### The Odds API

Docs:

- Host: `https://api.the-odds-api.com`.
- Sports list: `GET /v4/sports/?apiKey={apiKey}`.
- Current odds: `GET /v4/sports/{sport}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}`.
- Historical odds snapshots: `GET /v4/historical/sports/{sport}/odds?apiKey={apiKey}&regions={regions}&markets={markets}&date={date}`.
- Historical events: `GET /v4/historical/sports/{sport}/events?apiKey={apiKey}&date={date}`.
- Historical event odds: `GET /v4/historical/sports/{sport}/events/{eventId}/odds?...&date={date}`.
- Historical odds available from 2020-06-06, 10-minute snapshots; 5-minute snapshots from 2022-09.
- Historical odds cost: 10 credits per region per market.

Blocker:

- Requires separate API key/paid historical access.
- Snapshot extraction is needed to approximate closing odds. Query one snapshot shortly before kickoff.

Recommendation:

- Use only if TheStatsAPI coverage is thin. For each target sport key, query historical events by date window, then h2h odds near kickoff.

### OddsPapi

Docs:

- Historical endpoint: `GET /v4/historical-odds`.
- Required params: `fixtureId`, `bookmakers`.
- Example: `/v4/historical-odds?fixtureId=id1000000758265379&bookmakers=pinnacle,bet365`.
- Historical odds data available since January 2026.
- Endpoint cooldown: 5000 ms.
- Response contains bookmaker -> market -> outcome -> player -> price timeline.

Blocker:

- Does not fill 2016-2025.
- Need fixture discovery and market/outcome ID mapping.

Recommendation:

- Use for WC 2026 live and near-term historical odds if TheStatsAPI misses odds or rate limits.

### API-Football

Docs:

- Public coverage page lists 1,232 leagues/cups and detailed coverage categories including fixtures, players, standings, events, lineups, statistics, predictions, odds, and top scorers.
- Coverage page lists international competitions such as Copa America and Euro Championship.
- Known endpoint families: `/fixtures`, `/fixtures/statistics`, `/fixtures/players`, `/fixtures/lineups`, `/injuries`, `/odds`.

Local test:

- `/status`, `/leagues`, `/fixtures`, `/fixtures/statistics`, `/fixtures/players`, `/fixtures/lineups`, `/injuries`, `/odds`, `/odds/live`, `/teams`, and `/players` were attempted.
- All failed before HTTP due to local socket permissions.

Recommendation:

- Use API-Football as an enrichment source for lineups, injuries, and generic stats if TheStatsAPI lacks them. Do not rely on it as the primary closing-odds source until actual odds payloads prove opening/closing availability.

### Oddspedia

Known from prior investigation:

- Current odds are visible in page HTML for some match pages.
- Oddspedia claims a large archived odds store.
- No official public API or exact historical odds endpoint was verified.

Recommendation:

- Do not spend the next 24 hours scraping Oddspedia unless both paid APIs fail. If used, inspect browser network from a normal desktop browser or the conda Playwright environment, then target finished match pages only after confirming closing 1X2 is present.

## Fastest path

1. Run `s12_statsapi_max_collect.py all` from an unblocked network.
2. Inspect `statsapi_odds.csv`.
3. If it contains bookmaker 1X2 prices for international matches, normalize that file and stop.
4. If TheStatsAPI has stats but thin odds, use OddsPapi for WC 2026 odds and The Odds API for 2020-2026 historical odds.
5. Use API-Football for lineups/injuries/stat enrichment, not as the first odds source.

## Success definition for the next successful network run

- At least 1,000 international `statsapi_matches.csv` rows from 2016-2026.
- At least 1,000 joined `statsapi_odds.csv` match-market rows with 1X2 prices.
- At least one sharp bookmaker source: Pinnacle or Betfair Exchange.
- For xG/stat enrichment, at least one of `xg`, `npxg`, `shots`, or `possession` non-null in `statsapi_team_stats.csv`.

