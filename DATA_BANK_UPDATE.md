# Data Bank Update — Priority Collection Round

*Run date 2026-06-02. Free sources only (no paid API). 6 new tables added → DB now has 27 tables.*

## What got collected this round

| # | Objective | Status | What landed | Table(s) |
|---|-----------|:------:|-------------|----------|
| 2 | **Official WC2026 squads** | ✅ **DONE** | 1,246 players, **all 48 teams** — shirt no., position, player, DOB/age, **caps**, goals, **club** | `official_squads_2026` |
| 5 | **Starting lineups** | ✅ **DONE (WC 2018+2022)** | 2,816 starter rows — real starting XIs w/ position + jersey | `starting_lineups` |
| 6 | **xG** | ✅ **DONE (WC 2018+2022)** | real StatsBomb xG: 255 team-match rows, 1,757 player-match rows (xG, shots, goals) | `sb_team_match_stats`, `sb_player_match_stats` |
| — | StatsBomb match meta | ✅ | 128 WC matches w/ stage, stadium, **referee** | `sb_matches` |
| 1 | **Historical odds** | 🟡 **PARTIAL** | 479,440 closing 1X2 rows (avg+max, H/D/A), **2005–2015**, 818 comps incl. ~63.7k international/cup rows | `odds_bank` |
| 3 | Injuries / availability | ❌ **MISSING** | blocked source | `injuries` (still 0) |
| 4 | Player form DB (23/24→25/26) | ❌ **MISSING** | no real club-season stats yet | — |

## Detail & honest caveats

**#2 Squads — complete.** Source: Wikipedia "2026 FIFA World Cup squads". This is the *real* 26-man lists (not the FIFA-game nationality pool), with caps and current club. Replaces the `squads` proxy for tournament modelling.

**#5 Lineups & #6 xG — complete for the two most recent World Cups only.** StatsBomb open data covers WC 2018 + 2022 (and 1958–1990) with full event-level xG and starting XIs. This is genuine, high-quality data. It does **not** cover qualifiers, friendlies, or 2026 (future), and StatsBomb's free intl coverage stops at WC tournaments.

**#1 Odds — useful but dated.** The free "beat-the-bookie" bank gives closing 1X2 odds across 818 competitions but only **2005–2015**. It covers WC 2006/2010/2014 + qualifiers + AFCON etc. — good for *training/calibration on older cycles* — but has **nothing for 2016–2026**, and the match-linked `odds` table is still empty (needs name-normalised join to `matches`).

**#3 Injuries** — `injuries` still empty. Transfermarkt/physioroom are anti-bot blocked from plain HTTP.

**#4 Player form** — still only the static FIFA-game ratings (`players`, 18k) as a proxy + StatsBomb per-match player xG for WC18/22. No real 2023/24–2025/26 club-season stat lines yet (FBref/Understat blocked without a browser).

## What's still missing → next actions

| Gap | Why still missing | How to get it (free) | Effort |
|-----|-------------------|----------------------|:------:|
| **Recent odds 2016–2026 + WC18/22/26** | no free recent intl feed | **OddsPortal via Playwright** (OddsHarvester) | Med |
| **Link odds → matches** | team-name mismatch | normalise `odds_bank` teams via `dim_team`, join on date+teams | Easy |
| **Injuries / availability** | Cloudflare/anti-bot | **Playwright** on Transfermarkt injury pages; or news scrape | Med/Hard |
| **Player season form 23/24→25/26** | FBref/Understat blocked | **`soccerdata`** (wraps FBref/Understat, handles block) or `statsbombpy` for more comps | Med |
| **xG for qualifiers/friendlies** | StatsBomb free = WC only | FBref/Understat via `soccerdata` | Med |
| **2026 lineups** | matches not played yet | pull live during tournament (API-Football free tier / scrape) | n/a until June 11 |

### Recommended next step
Install the browser stack — `pip install playwright soccerdata statsbombpy` + `playwright install chromium` — then:
1. **OddsHarvester → OddsPortal** for 2016–2026 + WC odds (fills #1 properly).
2. **soccerdata → FBref/Understat** for player season form + qualifier xG (fills #4 and extends #6).
3. **Playwright → Transfermarkt** injuries (fills #3).

These three close every remaining gap without a paid subscription. #1's recent odds is the highest-value next target.


---

## Update 2026-06-12 — missing-data recovery round
| gap | result | detail |
|---|---|---|
| D-RANK FIFA rankings 2024-07→2026 | ✅ **CLOSED** | Wayback Machine archived fifa.com's ranking JSON API; harvested every release 2024-07→2026 (211 teams each), validated (women's + German-locale captures scrubbed by s16b), appended to DB + f1 override refreshed |
| D-XG (partial) | 🟡 **EXPANDED** | StatsBomb open data had 4 more tournaments: Euro 2024/2020, Copa America 2024, AFCON 2023 (+partial 1958-90 WCs). sb tables now 333 matches / 665 team-xG / 4,592 player-xG / 7,326 lineup rows. New features xg_pm_diff/xga_pm_diff/xg_net_diff cover **39/48 WC2026 teams** |
| FBref full xG | ❌ still blocked | stealth playwright alone fails (Cloudflare challenge persists); needs VPN — user data-day task |
| D-AVAIL lineups/injuries | ❌ needs API key | API-Football signup required |
| D-ODDS 2016-26 odds | ❌ needs VPN | OddsPortal TCP-blocks this host |

Effect on models: global test LL unchanged (xG/rank coverage is concentrated on 2025-26 rows,
a sliver of the test set) — the gain shows up where it matters: **2026 fixture inference**
(simulator + ensemble deployment now see fresh ranks + real attacking quality for 39/48 teams).
