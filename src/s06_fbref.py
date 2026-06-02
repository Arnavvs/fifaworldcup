"""
Stage 06 - FBref team + player stats (advanced: xG, SCA/GCA, passing, defense).

FBref sits behind Cloudflare and serves most stat tables inside HTML comments.
This module implements the *correct* extraction pipeline:
  - browser-like session w/ long randomised delays (FBref allows ~1 req / 6s)
  - optional Selenium fallback (FBREF_SELENIUM=1) to clear the JS challenge
  - un-commenting of `<!-- <table> -->` blocks before parsing
  - pd.read_html(header=[0,1]) multi-index parse + column flattening
  - per-team checkpointing so the (long) run is resumable

It targets the WC-2026 qualified teams (raw/worldcup/wc2026_qualified_teams.csv)
to keep the crawl bounded. Where Cloudflare blocks plain HTTP (no Selenium /
non-residential IP), each team is logged as 'fail' and skipped -- never fatal.

Outputs -> raw/fbref/team_match_stats.csv, raw/fbref/player_season_stats.csv
"""
from __future__ import annotations

import io
import os
import re
import sys

import pandas as pd

from common import (RAW, polite_get, get_logger, log_attempt, save_df,
                    checkpoint_done, mark_done)

log = get_logger("s06_fbref")
OUT = RAW / "fbref"

# team name -> FBref 3-letter country code (extend as needed)
FBREF_CODE = {
    "Argentina": "ARG", "Brazil": "BRA", "France": "FRA", "England": "ENG",
    "Spain": "ESP", "Germany": "GER", "Portugal": "POR", "Netherlands": "NED",
    "Belgium": "BEL", "Italy": "ITA", "Croatia": "CRO", "Uruguay": "URU",
    "Mexico": "MEX", "USA": "USA", "United States": "USA", "Canada": "CAN",
    "Morocco": "MAR", "Senegal": "SEN", "Japan": "JPN", "South Korea": "KOR",
    "Korea Republic": "KOR", "Switzerland": "SUI", "Denmark": "DEN",
    "Colombia": "COL", "Ecuador": "ECU", "Poland": "POL", "Serbia": "SRB",
    "Australia": "AUS", "Iran": "IRN", "IR Iran": "IRN", "Ghana": "GHA",
    "Cameroon": "CMR", "Nigeria": "NGA", "Egypt": "EGY", "Algeria": "ALG",
    "Tunisia": "TUN", "Saudi Arabia": "KSA", "Qatar": "QAT", "Wales": "WAL",
    "Austria": "AUT", "Ukraine": "UKR", "Sweden": "SWE", "Norway": "NOR",
    "Chile": "CHI", "Peru": "PER", "Paraguay": "PAR", "Costa Rica": "CRC",
    "South Africa": "RSA", "New Zealand": "NZL", "Jordan": "JOR", "Uzbekistan": "UZB",
    "Scotland": "SCO", "Turkey": "TUR", "Czechia": "CZE", "Hungary": "HUN",
    "Greece": "GRE", "Slovakia": "SVK", "Slovenia": "SVN", "Romania": "ROU",
    "Ivory Coast": "CIV", "Panama": "PAN", "Honduras": "HON", "Cape Verde": "CPV",
    "Curacao": "CUW", "Haiti": "HAI", "Jamaica": "JAM",
}

_COMMENT_TABLE = re.compile(r"<!--(.*?)-->", re.DOTALL)


def _selenium_get(url: str) -> str | None:
    """Optional Cloudflare-clearing fetch; only used if FBREF_SELENIUM=1."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import time
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        drv = webdriver.Chrome(options=opts)
        try:
            drv.get(url)
            time.sleep(8)  # let the JS challenge resolve
            return drv.page_source
        finally:
            drv.quit()
    except Exception as e:
        log.warning(f"selenium unavailable: {str(e).splitlines()[0]}")
        return None


def fetch_html(url: str) -> str | None:
    if os.environ.get("FBREF_SELENIUM") == "1":
        html = _selenium_get(url)
        if html and "Just a moment" not in html:
            return html
    resp = polite_get(url, source="fbref", min_delay=6, max_delay=9, retries=2)
    if resp is None:
        return None
    if "Just a moment" in resp.text or resp.status_code == 403:
        return None
    return resp.text


def all_tables(html: str) -> list[pd.DataFrame]:
    """Parse every table, including the comment-wrapped ones FBref hides."""
    blocks = [html] + _COMMENT_TABLE.findall(html)
    frames = []
    for b in blocks:
        if "<table" not in b:
            continue
        try:
            for t in pd.read_html(io.StringIO(b)):
                frames.append(t)
        except Exception:
            continue
    return frames


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            (b if (not str(a) or str(a).startswith("Unnamed")) else f"{a}_{b}")
            for a, b in df.columns
        ]
    return df


def scrape_team(team: str, code: str) -> tuple[int, int]:
    base = f"https://fbref.com/en/country/mens/{code}/{team.replace(' ', '-')}-Football"
    html = fetch_html(base)
    if html is None:
        log_attempt("fbref", base, "fail", 0, "cloudflare/403 - no html")
        return 0, 0
    frames = all_tables(html)
    team_rows = player_rows = 0
    for i, fr in enumerate(frames):
        fr = flatten(fr)
        cols = [str(c).lower() for c in fr.columns]
        fr["team"] = team
        # heuristics: a player table has 'player', a results table has 'opponent'/'date'
        if any("player" in c for c in cols):
            save_df(fr, OUT / f"players/{code}_players_{i}.csv")
            player_rows += len(fr)
        elif any(c in ("date", "opponent", "comp") for c in cols):
            save_df(fr, OUT / f"matches/{code}_matches_{i}.csv")
            team_rows += len(fr)
    log_attempt("fbref", base, "ok", team_rows + player_rows,
                f"{team_rows} match-rows, {player_rows} player-rows")
    return team_rows, player_rows


def target_teams() -> list[str]:
    q = RAW / "worldcup" / "wc2026_qualified_teams.csv"
    if q.exists():
        teams = pd.read_csv(q)["team"].dropna().astype(str).tolist()
        return [t for t in teams if t in FBREF_CODE]
    return list(FBREF_CODE)[:16]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    teams = target_teams()
    log.info(f"FBref targets ({len(teams)} teams): {teams}")
    tot_t = tot_p = blocked = 0
    for team in teams:
        code = FBREF_CODE[team]
        if checkpoint_done("fbref", code):
            log.info(f"skip (done): {team}")
            continue
        t, p = scrape_team(team, code)
        if t == 0 and p == 0:
            blocked += 1
        else:
            tot_t += t; tot_p += p
            mark_done("fbref", code)
    log.info(f"stage 06 (fbref) complete: {tot_t} team-rows, {tot_p} player-rows, "
             f"{blocked}/{len(teams)} teams blocked")
    if blocked == len(teams):
        log.warning("FBref fully blocked from this host (Cloudflare JS challenge). "
                    "Re-run with FBREF_SELENIUM=1 on a host with Chrome, or a residential IP. "
                    "Advanced xG/SCA stats remain a known gap; FIFA-game ratings (stage 07) "
                    "serve as the player-attribute proxy in the meantime.")


if __name__ == "__main__":
    sys.exit(main())
