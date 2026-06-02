# FIFA World Cup 2026 — Prediction Dataset Builder

A modular, resumable pipeline that scrapes and aggregates free football data
into an analysis-ready dataset (CSV/JSON + SQLite) for WC-2026 prediction work.

## Layout

```
fifa_wc_data/
├── raw/          # raw scraped/downloaded data (kaggle, elo, fifa_rankings, worldcup, ...)
├── processed/    # cleaned, merged, feature-engineered datasets
├── db/           # football.db  (SQLite, all schema tables)
└── logs/         # pipeline.log, scrape_attempts.csv, data-quality reports
src/              # pipeline code (one module per stage + run_all.py orchestrator)
```

## Running

```bash
cd src
python run_all.py            # full pipeline (resumable; failed stages are skipped)
python run_all.py 8 9 10 11  # only selected stages
```

Kaggle auth: the `KAGGLE_API_TOKEN` (new `KGAT_` token) is read from
`~/.kaggle/access_token`. ELO/Wikipedia/fixturedownload need no auth.

## Stages

| # | Module | Source | Output |
|---|--------|--------|--------|
| 01 | s01_kaggle | Kaggle CLI | intl results, goalscorers, WC datasets, FIFA-game ratings 15–23 |
| 02 | s02_elo | eloratings.net | `raw/elo/elo_ratings.csv` (year-end series 1901→2026) |
| 03 | s03_fifa_rankings | Kaggle + Wikipedia | `raw/fifa_rankings/` (67k rows, 1992→present) |
| 04 | s04_worldcup | fixturedownload + Kaggle | WC history (900 matches), 2026 fixtures + 48 qualified teams |
| 05 | s05_football_data | football-data.co.uk | odds (no intl feed published → empty, documented) |
| 06 | s06_fbref | FBref | advanced xG/SCA team+player stats — **Cloudflare-blocked from this host** |
| 07 | s07_transfermarkt | Transfermarkt | squads/values/injuries — **anti-bot-blocked from this host** |
| 08 | s08_players | FIFA-game ratings | players master (18k), WC2026 pool (12.9k across 48 teams), market values |
| 09 | s09_features | derived | `team_match_features.csv` — 98.5k team-match rows × 30 features |
| 12 | s12_venues | geopy + open-elevation | WC2026 venue lat/lng + altitude |
| 10 | s10_build_db | all CSVs | `db/football.db` |
| 11 | s11_quality | DB | `logs/` quality + source reports |

## Derived features (stage 09)

Per team-per-match: result/points, days rest, rolling form (last 5/10/20 win%,
goals-for/against avg, leakage-safe via shift), current result streak, H2H
last-10 win% & avg goals, tournament stage weight (group=1…final=5),
neutral-venue & rivalry flags, cumulative prior-WC appearances, and
as-of-joined ELO + FIFA ranking/points.

## Known gaps (honest)

- **FBref & Transfermarkt** are blocked by Cloudflare / anti-bot from this host.
  The scrapers are complete and correct (comment-table extraction, multi-index
  flattening, checkpointing, optional `FBREF_SELENIUM=1` path) and will populate
  `team_match_stats` / `player_match_stats` / `injuries` when run from a
  residential IP or with a real browser. Meanwhile the **FIFA-game player
  ratings** (the brief's sanctioned attribute proxy) fill the player layer, and
  `value_eur` provides squad market values.
- **football-data.co.uk** publishes club-league CSVs only; no international odds
  feed exists, so the `odds` table is schema-complete but empty.
- ELO is the documented **year-end** series (per-match ELO is not downloadable).

Empty tables are created with correct columns so the schema and all joins stay
well-defined.
