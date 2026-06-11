# Data Collection Pipeline — FIFA World Cup 2026

## Purpose
This folder contains all **free-data** collection scripts, scrapers, and compute pipelines to close the P1/P2 gaps identified in `BRUTAL_GAP_ANALYSIS.md`. Everything here is designed to run without paid APIs, subscriptions, or user credentials.

## Architecture
```
data_collection_pipeline/
├── run_collection.py              # Master orchestrator (resumable, checkpointed)
├── checkpoints.json               # Tracks which stages finished / failed
├── pipeline.log                   # Detailed execution log
├── src/
│   ├── common.py                  # Shared utilities: HTTP, DB, CSV, geo, checkpoints
│   ├── s01_fifa_rankings.py       # Scrape FIFA rankings (2024→present)
│   ├── s02_weather.py             # Fetch Open-Meteo climate normals for venues
│   ├── s03_travel_timezone.py     # Compute travel distances + timezone shifts
│   ├── s04_squad_aggregates.py    # Compute squad aggregates from official_squads_2026
│   ├── s05_shared_club_matrix.py  # Build shared-club teammate matrices
│   ├── s06_manager_tenure.py      # Scrape national team managers from Wikipedia
│   ├── s07_qualification_strength.py # Scrape WC 2026 qualification records
│   ├── s08_continental_form.py    # Scrape Copa America / Euro / AFCON / Asian Cup
│   ├── s09_odds_scraper.py        # Attempt OddsPortal / football-data odds
│   ├── s10_understat_xg.py        # Scrape Understat club-season xG (2024-25)
│   └── s11_live_pipeline.py       # Architecture stub for live WC 2026 feeds
└── collected_data/
    ├── raw/                         # Scraped raw outputs (odds, xG, etc.)
    └── processed/                   # Computed features (travel, aggregates, weather)
```

## Quick Start

Runs in the **`minorproject`** conda env (Python 3.11). Required packages:
`requests bs4 lxml pandas geopy kaggle playwright` + `playwright install chromium`.

```powershell
conda activate minorproject
cd data_collection_pipeline
python run_collection.py              # run all missing stages
python run_collection.py 3 4 5        # run only stages 3, 4, 5
```

Every stage now validates its own output (`common.finalize_stage`): a stage is
only checkpointed `done` if it produced real, non-empty, non-null data. Empty or
malformed output is checkpointed `failed` with a reason — no more silent
"done-but-garbage" results.

## Stage Reference

| Stage | Name | Source (after refinement) | Status | Notes |
|---|---|---|---|---|
| 1 | FIFA Rankings | Kaggle `cashncarry` (full 210-team table); FIFA.com live attempted via stealth | ✅ 210 rows | FIFA.com live full table not free-extractable (API empty, DOM is a live widget); Kaggle through 2024-06 is the honest fallback |
| 2 | Weather (climate normals) | Open-Meteo Climate API (`MRI_AGCM3_2_S`) | ✅ 624 rows | 16 venues × ~39 tournament days; WBGT + heat-stress flag |
| 3 | Travel / timezone | computed (no network) | ✅ 752 rows | |
| 4 | Squad aggregates | DB `official_squads_2026` | ✅ 48 teams | age parser fixed (was ~17, now ~27) |
| 5 | Shared club matrix | DB | ✅ 48 teams | |
| 6 | Manager tenure | Wikipedia (team page + manager page) | ✅ 44 mgrs / 43 dates | appointment year now extracted → `tenure_years_at_wc` |
| 7 | Qualification strength | Wikipedia (`pandas.read_html`) | ✅ 147 teams / 44 finalists | Pld/Pts/PPG; GF/GA enrichment on sub-pages is future work |
| 8 | Continental form | Wikipedia (`pandas.read_html`) | ✅ 104 / 48 finalists | group stats + winner/finalist; QF/SF granularity future |
| 9 | Odds (closing) | **OddsPortal** (intl, via VPN) + football-data.co.uk (club) | ✅ 228 intl + 5330 club | OddsPortal needs a VPN/proxy (TCP-blocks datacenter IPs); with one it yields closing 1X2 for WC18/22, Euro20/24, Copa21. Club odds always available |
| 10 | Understat xG | Understat via **Playwright stealth** | ✅ 96 teams | team xG/xGA/xPTS, top-5 leagues 2025-26 |
| 11 | Live pipeline stub | — | architecture only | |

## Free Data Sources Used

- **Open-Meteo** (`open-meteo.com`) — free weather/climate API, no key required.
- **Wikipedia** — manager tenure, qualification tables, continental tournament results.
- **FIFA.com** — ranking tables (requests + fallback to Wikipedia).
- **Understat** (`understat.com`) — club-season xG and player stats.
- **OddsPortal** (`oddsportal.com`) — historical odds (Playwright, anti-bot risk).
- **Existing Project DB** — official squads, venues, fixtures, matches.

## Outputs (P1 & P2 Features)

All outputs land in `collected_data/processed/` as CSVs:

- `travel_features.csv` — distance_km, timezone_delta, travel_fatigue_index, altitude_delta
- `squad_aggregates.csv` — mean_age, mean_caps, mean_club_quality, n_elite_club_players
- `shared_club_matrix.csv` — shared_club_pairs, max_players_from_same_club, shared_pair_ratio
- `cross_team_club_overlap.csv` — shared_clubs between every pair of 48 teams
- `weather_forecasts.csv` — daily temp, humidity, precip, wind, WBGT approx, heat_stress_flag
- `fifa_rankings_updated.csv` — ranking rows from 2024→present (top-N from Wikipedia)
- `manager_tenure.csv` — manager name + appointment date per national team
- `qualification_strength.csv` — qualification games, wins, draws, goals, points
- `continental_form.csv` — most recent continental tournament stage reached + stats
- `odds_collected.csv` — best-effort historical odds (may be empty if blocked)
- `understat_xg.csv` — club-season player xG (2024-25 top 5 leagues)

## Live Tournament Mode (Post-June 11, 2026)

`s11_live_pipeline.py` documents the architecture for:

1. **Lineup feeds** — API-Football free tier or Playwright on WhoScored/FIFA
2. **Odds refresh** — Pinnacle REST API (requires free account) or Betfair Exchange
3. **Weather refresh** — Open-Meteo forecast API
4. **Injury alerts** — Transfermarkt news scrape + RSS curation
5. **In-play events** — Premium required for sub-second; free options are brittle

To activate live mode, implement the connectors in `s11_live_pipeline.py` and run:
```powershell
python src/s11_live_pipeline.py
```
(Schedulers like Windows Task Scheduler or cron can call `run_collection.py --live` every 15 minutes.)

## Failure Handling

Every stage is checkpointed. If a scraper fails (e.g., OddsPortal blocks the IP), the stage is marked `failed` in `checkpoints.json` and the pipeline continues. You can retry a failed stage later with:
```powershell
python run_collection.py 9
```

## Honest Limitations (verified 2026-06-08 from this host)

1. **FIFA Rankings (live 2025–26):** fifa.com is Akamai-protected. The stealth
   browser *loads* the page, but the ranking JSON API returns `{"rankings":[]}`
   even in-session and the DOM only renders a top-N live widget. No free path to
   the current full 210-team table succeeded → we serve the Kaggle `cashncarry`
   full table (through 2024-06). Refreshing 2025–26 needs a paid FIFA data
   partner or someone maintaining an up-to-date Kaggle mirror.
2. **Odds (internationals):** OddsPortal blocks **datacenter/default IPs at the
   TCP level** (connection refused — not a JS challenge, so stealth alone can't
   help). **Solved by running behind a VPN** (verified 2026-06-08, RO exit): the
   stealth browser then loads the rendered results pages and we parse closing 1X2
   odds → `odds_international.csv` (228 matches: WC18/22, Euro20/24, Copa21).
   Notes: OddsPortal intermittently serves a truncated ~5-row page, so the
   scraper retries per tournament; archived Copa America 2024 has no stable slug.
   `football-data.co.uk` still provides club closing odds (Bet365 + **Pinnacle**
   + Max/Avg + O/U 2.5) → `odds_club_closing.csv` for CLV machinery.
3. **Understat xG:** now solved via Playwright stealth (the old `JSON.parse`
   embedding is gone; data is parsed from the rendered DOM). Covers top-5 club
   leagues — proxies the club strength of each nation's player pool.
4. **Club Form / Minutes (FBref, Transfermarkt):** still the hardest. Cloudflare-
   blocked; not yet attempted with the stealth helper. Next candidate for the
   Playwright path, but expect heavier defences than Understat.
5. **Referee Data:** not consistently available free for internationals.

## Maintenance

- Re-run **Stage 2 (weather)** weekly as the tournament approaches to refresh forecasts.
- Re-run **Stage 1 (rankings)** monthly after FIFA releases new rankings.
- Re-run **Stage 6 (managers)** if any national team changes coach.
- Run **Stage 9 (odds)** periodically until a reliable source is found.

## Next Steps for Betting Grade

To reach betting-grade maturity, you still need:
- A **Pinnacle / sharp bookmaker account** for real-time odds (free to open, API access is free).
- **Playwright on a residential IP or cloud VM** to unblock FBref / Transfermarkt.
- A **Feast Feature Store** (Redis + S3 Parquet) for sub-millisecond feature serving.
- An **automated execution pipeline** (REST API to place bets). No code for this is included because it requires a funded betting account.

---
*Generated by AI — all scripts use free sources only. No paid subscriptions required.*
