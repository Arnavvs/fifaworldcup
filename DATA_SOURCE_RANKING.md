# Data Source Ranking - odds and xG/statistics

Date checked: 2026-06-12

Objective: find the highest-value football odds and xG/statistics data that can realistically be collected in the next 24 hours with the least scraping effort.

## Current project baseline

Existing repo evidence:

- `data_collection_pipeline/src/s09_odds_scraper.py` already collected 228 international closing 1X2 rows from OddsPortal when run behind VPN/stealth, plus 5,330 club closing-odds rows from football-data.co.uk.
- `PROJECT_STATUS.md` and `DATA_BANK_UPDATE.md` show the DB already contains 479,440 older odds-bank rows, but the useful recent international gap remains 2016-2026.
- `data_collection_pipeline/src/s10_understat_xg.py` already collects top-5 club team xG from Understat via Playwright. This is useful as player-pool context but is not international match xG.
- StatsBomb open data is already the best free high-quality xG/event source in the repo for WC/major tournaments, but coverage is partial.

## Executive recommendation

Collect next, in this order:

1. **TheStatsAPI 7-day trial**: highest expected value if signup works. It advertises 10 years of match data, xG, pre-match odds, historical odds, opening/closing lines, World Cup coverage, and JSON REST endpoints. This is the closest match to the full data gap with minimal scraping.
2. **OddsPapi trial/free historical odds**: best candidate for 2026 odds and line movement. Historical coverage is only confirmed since January 2026, so it will not fill 2016-2025, but it can help immediately during WC 2026.
3. **The Odds API paid historical endpoint**: legally clean historical odds from June 2020 onward. It is snapshot-based, not a ready closing-odds CSV, and paid-only for historical data.
4. **API-Football free/pro key**: good fallback for fixtures, lineups, injuries, statistics, and some odds; weaker for true closing historical odds and xG.
5. **Oddspedia page scrape only as fallback**: current odds are visible in HTML and the site claims a huge archived-odds store, but no documented API was found and no historical-odds endpoint was verified.

Success target for the next 24 hours: obtain an API key/trial for **TheStatsAPI** and export one sample CSV covering all WC 2026 fixtures with 1X2 odds fields plus any match/team xG/stat fields available. If TheStatsAPI access fails, use OddsPapi for 2026 odds and keep existing StatsBomb/Understat xG.

## Top 5 odds sources

| Rank | Source | URL | Free/Paid | API or scraping | Historical coverage | Effort 1-10 | Model value 1-10 | Blockers |
|---:|---|---|---|---|---|---:|---:|---|
| 1 | TheStatsAPI | https://www.thestatsapi.com/ | Paid, 7-day trial advertised | REST API | Advertises 10 years of data, historical odds, pre-match/live odds, opening and closing lines | 2 | 10 | Requires account/key; actual international depth must be verified after signup |
| 2 | OddsPapi | https://oddspapi.io/us | Free historical data advertised, account required | REST API/WebSocket | Docs confirm historical odds since January 2026 | 3 | 8 | Does not fill 2016-2025; fixture IDs/bookmaker mapping needed |
| 3 | The Odds API | https://the-odds-api.com/liveapi/guides/v4/ | Paid for historical odds | REST API | Historical odds snapshots from 2020-06-06, 10-minute snapshots; 5-minute snapshots from 2022-09 | 4 | 8 | Paid-only; snapshot extraction required to infer closing; sport-key coverage for all intl comps must be checked |
| 4 | API-Football | https://www.api-football.com/ | Free 100 req/day; paid from $19/mo | REST API | Broad football coverage including World Cup, qualifiers, friendlies, odds/statistics endpoints | 3 | 7 | Free seasons limited; unclear if historical odds are closing lines; no clear xG signal found |
| 5 | Oddspedia | https://oddspedia.com/football | Free website, no public API found | HTML scrape / possible undocumented XHR | Site claims 5.6B archived odds and shows WC 2026 odds in rendered HTML | 6 | 7 | No documented API; no historical endpoint verified; ToS/legal risk; scraping durability unknown |

Honorable mention: football-data.co.uk is excellent free CSV odds data, but mostly club leagues, not international football. It is useful for calibration and closing-line tooling, not for the recent international gap.

## Top 5 xG / team-stat sources

| Rank | Source | URL | Free/Paid | API or scraping | Historical coverage | Effort 1-10 | Model value 1-10 | Blockers |
|---:|---|---|---|---|---|---:|---:|---|
| 1 | TheStatsAPI | https://www.thestatsapi.com/ | Paid, 7-day trial advertised | REST API | Advertises 10 years of match/player/team data, xG, npxG, xA, match stats | 2 | 10 | Need key; need verify international and WC 2026 data depth |
| 2 | StatsBomb Open Data | https://github.com/statsbomb/open-data | Free with attribution terms | JSON files / `statsbombpy` | Selected competitions, including recent major tournaments already partly imported | 2 | 8 | Limited competition coverage; not full qualifiers/friendlies/2026 live |
| 3 | SportMonks Football API | https://www.sportmonks.com/football-api/ | Paid, free/trial access advertised | REST API | Covers major tournaments and advertises xG, odds, lineups, World Cup, FIFA rankings | 3 | 8 | Paid plan/trial required; exact xG coverage by international comp must be verified |
| 4 | Understat | https://understat.com/league/EPL/2025 | Free website | Scrape/export UI | Club top leagues from 2014-15 to 2025-26 on page selector | 4 | 6 | Club only; no international teams; anti-bot/browser parsing required |
| 5 | Sofascore | https://www.sofascore.com/ | Free website, no official public API found | Undocumented JSON / scraping | Broad live and historical match stats; xG availability varies by match/competition | 6 | 6 | Undocumented; possible anti-bot/ToS risk; xG not guaranteed for international matches |

FotMob is a useful stat/xG fallback, but it explicitly says automated systematic use is not permitted on its site, so it should not be a primary collection target.

## Specific source investigation

### Oddspedia

- URL checked: https://oddspedia.com/football and https://oddspedia.com/football/bosnia-herzegovina-canada-1869934
- Free or paid: free website; no public API/pricing for data access found.
- API or scraping: current odds are visible in the HTML returned for normal pages. Example: the Canada vs Bosnia-Herzegovina page includes bookmaker-specific 1X2 prices in the page body.
- Historical coverage: Oddspedia footer claims 5,619,548,715 archived odds, 173 bookmakers, 6,934 competitions, and 1,352,866 current odds. This proves archive scale is advertised, not that bulk historical extraction is accessible.
- Embedded HTML: yes for current/upcoming odds. The match page HTML includes Full Time Result prices and bookmaker names.
- JSON/XHR: not verified in this environment. Browser automation was blocked locally and direct PowerShell/curl probes failed at TLS. No exact JSON endpoint was safely verified.
- Undocumented API: not verified. Guesses such as `/api/v1/getMatchList` and `/api/v1/getMatchOdds` were not confirmed.
- Historical odds collection: plausible but unproven. The public pages expose current odds; finished-match closing odds may be scrapeable page-by-page, but this needs a browser-network inspection from the conda Playwright environment or a normal desktop browser.
- Exact endpoints discovered: none beyond public page URLs.
- Blockers: legal/ToS uncertainty, no official data API, endpoint instability risk, browser/network inspection still needed.
- Effort: 6/10.
- Expected model value: 7/10 if historical closing 1X2 can be extracted; 4/10 if only upcoming WC odds.

### Understat

- URL: https://understat.com/
- Free or paid: free website.
- API or scraping: scraping/export UI; existing repo Playwright stage works for top-5 team-season xG.
- Historical coverage: visible season selector from 2014-15 through 2025-26 for EPL, La Liga, Bundesliga, Serie A, Ligue 1, RFPL.
- Model value: 6/10.
- Blockers: club only; not international match xG.

### Sofascore

- URL: https://www.sofascore.com/
- Free or paid: free website.
- API or scraping: undocumented API/scraping only.
- Historical coverage: broad football coverage; public page says 500+ leagues/cups/tournaments and match statistics.
- Model value: 6/10 for stats, 4/10 for odds.
- Blockers: undocumented, xG varies by match, legal/ToS and anti-bot risk.

### TheStatsAPI

- URL: https://www.thestatsapi.com/
- Free or paid: paid, 7-day trial advertised, $50/mo starter.
- API or scraping: REST API.
- Historical coverage: advertises 10 years of data, 150 competitions by default, 1,196 on request.
- Relevant fields: match stats, xG, npxG, xA, player/team stats, pre-match odds, historical odds, opening and closing lines.
- Example endpoint shown publicly: `GET /api/football/matches/mt_010249745/stats`.
- Model value: 10/10.
- Blockers: signup/key required; verify actual WC/international depth.

### OddsPapi

- URL: https://oddspapi.io/us
- Free or paid: free historical data advertised; account likely required.
- API or scraping: REST API/WebSocket.
- Historical coverage: docs state historical odds data since January 2026.
- Relevant endpoint: `GET /v4/historical-odds?fixtureId={fixtureId}&bookmakers=pinnacle,bet365`.
- Model value: 8/10 for WC 2026/live odds; 3/10 for 2016-2025 backfill.
- Blockers: only 2026+ confirmed; fixture discovery and market/outcome mapping required.

### API-Football

- URL: https://www.api-football.com/
- Free or paid: free 100 req/day; paid from $19/mo.
- API or scraping: REST API.
- Historical coverage: broad league/cup list; coverage page includes World Cup, World Cup qualifiers, friendlies, Euro, Copa America, AFCON, Nations League.
- Model value: 7/10 for live tournament enrichment; 5/10 for historical odds.
- Blockers: free plan season limits; no clear xG in public docs checked; odds may not be closing.

### SportMonks

- URL: https://www.sportmonks.com/football-api/
- Free or paid: paid plans from about EUR 29/mo with free/trial options advertised.
- API or scraping: REST API.
- Historical coverage: over 2,200 leagues worldwide; major international tournaments listed, including World Cup, Euros, AFCON, Copa America, Gold Cup, Nations League.
- Model value: 8/10.
- Blockers: paid/trial required; must verify xG/odds availability for target international competitions before purchase.

### FotMob

- URL: https://www.fotmob.com/
- Free or paid: free website.
- API or scraping: undocumented/scraping only.
- Historical coverage: broad football match coverage; xG is often available for major club/international matches.
- Model value: 5/10.
- Blockers: site footer explicitly says automated/systematic use is not permitted. Do not make this the primary source.

### WorldFootball.net

- URL: https://www.worldfootball.net/
- Free or paid: free website.
- API or scraping: HTML tables.
- Historical coverage: strong historical fixtures/results/team pages.
- Model value: 3/10.
- Blockers: no odds, no xG; mostly duplicates data already in project.

### Soccerway

- URL: https://int.soccerway.com/
- Free or paid: free website.
- API or scraping: HTML/JS scraping.
- Historical coverage: broad fixtures/results/standings and some match stats.
- Model value: 3/10.
- Blockers: no reliable odds/xG bulk access verified; likely ad/JS-heavy; mostly duplicates existing match data.

## Why the ranking is API-first

Historical closing odds are more valuable than raw match stats, but the useful requirement is not "any odds page"; it is reproducible, bulk, legally safer 1X2 closing odds for international football. A paid trial that delivers JSON is a better 24-hour target than fighting Cloudflare or reverse-engineering XHR.

For xG, international full coverage remains scarce. The practical approach is:

1. Use StatsBomb Open Data for high-quality tournament event/xG where available.
2. Use TheStatsAPI or SportMonks if API trial confirms international xG/stat coverage.
3. Keep Understat as club-strength context, not direct national-team match xG.

## Source evidence links

- Oddspedia football page: https://oddspedia.com/football
- Oddspedia Canada vs Bosnia-Herzegovina page: https://oddspedia.com/football/bosnia-herzegovina-canada-1869934
- TheStatsAPI: https://www.thestatsapi.com/
- OddsPapi historical odds docs: https://oddspapi.io/us/docs/get-historical-odds
- The Odds API historical docs: https://the-odds-api.com/liveapi/guides/v4/
- API-Football pricing and coverage: https://www.api-football.com/pricing and https://www.api-football.com/coverage
- SportMonks Football API: https://www.sportmonks.com/football-api/
- Understat EPL page: https://understat.com/league/EPL/2025
- StatsBomb Open Data: https://github.com/statsbomb/open-data
- football-data.co.uk data notes: https://www.football-data.co.uk/data.php
- FotMob footer/terms warning: https://www.fotmob.com/
