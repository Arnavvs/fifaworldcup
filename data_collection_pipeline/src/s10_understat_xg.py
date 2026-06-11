"""
Stage 10 — Club-season xG from Understat (top-5 European leagues).

Understat now renders its tables in the DOM (the old `var playersData =
JSON.parse(...)` embedding is gone) and sits behind anti-bot protection, so we
load each league page through the stealth Playwright helper and parse the
team-level xG table with pandas.read_html.

The team xG table is the high-value signal for national-team modelling (it
proxies the club strength of each nation's player pool). Columns:
  Team | M | W | D | L | G | GA | PTS | xG | xGA | xPTS
where xG/xGA/xPTS cells look like '77.49+6.49' (value + over/under delta).

Outputs: raw/understat_team_xg.csv
"""
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, RAW_DIR, should_run, save_checkpoint, finalize_stage, playwright_fetch,
)

SEASON = "2025"          # Understat season id == start year (2025/26)
SEASON_LABEL = "2025-26"
LEAGUES = {
    "EPL": "https://understat.com/league/EPL/2025",
    "La_liga": "https://understat.com/league/La_liga/2025",
    "Bundesliga": "https://understat.com/league/Bundesliga/2025",
    "Serie_A": "https://understat.com/league/Serie_A/2025",
    "Ligue_1": "https://understat.com/league/Ligue_1/2025",
}


def _lead_num(v):
    """Parse '77.49+6.49' / '28.80-1.80' -> 77.49 (the value before the delta)."""
    if pd.isna(v):
        return None
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else None


def _flatten(cols):
    out = []
    for c in cols:
        if isinstance(c, tuple):
            c = c[-1]
        out.append(str(c))
    return out


def _find_team_table(tables):
    for t in tables:
        cols = [c.lower() for c in _flatten(t.columns)]
        if "team" in cols and "xg" in cols and ("pts" in cols or "xpts" in cols):
            t = t.copy()
            t.columns = _flatten(t.columns)
            return t
    return None


def scrape_league(name: str, url: str):
    logger.info(f"[s10] {name} ...")
    html = playwright_fetch(url, wait_selector="table", scroll=True, aggressiveness="low")
    if not html:
        return pd.DataFrame()
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception as e:
        logger.warning(f"[s10] read_html failed for {name}: {e}")
        return pd.DataFrame()
    t = _find_team_table(tables)
    if t is None:
        logger.warning(f"[s10] No team xG table found for {name}.")
        return pd.DataFrame()

    rename = {"M": "matches", "G": "goals", "GA": "goals_against", "PTS": "pts"}
    t = t.rename(columns={k: v for k, v in rename.items() if k in t.columns})
    for col in ("xG", "xGA", "xPTS"):
        if col in t.columns:
            t[col.lower()] = t[col].map(_lead_num)
    keep = ["Team", "matches", "W", "D", "L", "goals", "goals_against", "pts",
            "xg", "xga", "xpts"]
    t = t[[c for c in keep if c in t.columns]].rename(columns={"Team": "team"})
    t["league"] = name
    t["season"] = SEASON_LABEL
    return t


def collect_understat():
    if not should_run("s10_understat_xg"):
        logger.info("[s10] Already done. Skipping.")
        return

    logger.info("[s10] Scraping Understat team xG via stealth browser...")
    frames = []
    for name, url in LEAGUES.items():
        df = scrape_league(name, url)
        if not df.empty:
            frames.append(df)
        time.sleep(2)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out = RAW_DIR / "understat_team_xg.csv"
    ok = finalize_stage(
        "s10_understat_xg", combined, out,
        min_rows=80,                       # 5 leagues x ~18-20 teams
        required_cols=["team", "league", "xg", "xga"],
        non_null_cols=["xg", "xga"],
        extra_meta={"leagues": len(frames), "season": SEASON_LABEL},
    )
    if ok:
        logger.info(f"[s10] {len(combined)} team-season xG rows from {len(frames)} leagues.")


if __name__ == "__main__":
    collect_understat()
