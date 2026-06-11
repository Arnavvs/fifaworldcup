"""
Stage 09 — Match odds with closing lines.

Two outputs:
  * raw/odds_international.csv  — OddsPortal closing 1X2 odds for major national-team
    tournaments (the calibration signal the gap analysis asks for). Requires a
    non-blocked egress: OddsPortal refuses datacenter/default IPs at the TCP level,
    but works through a VPN / residential proxy. We drive it with the stealth
    Playwright helper and parse the rendered event rows.
  * raw/odds_club_closing.csv  — football-data.co.uk closing odds (Bet365 +
    Pinnacle + Max/Avg + O/U2.5) for top-5 club leagues. Always reachable; used to
    build/validate the CLV + sharp-vs-soft machinery.

The stage succeeds if EITHER source yields data; it records which sources worked.
"""
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, RAW_DIR, get_session, should_run, save_checkpoint,
    save_csv, finalize_stage, _STEALTH_JS, _UA,
)

# Major national-team tournaments (OddsPortal "results" pages show avg closing odds).
OP_TOURNAMENTS = [
    ("World Cup 2022", "https://www.oddsportal.com/football/world/world-cup-2022/results/"),
    ("World Cup 2018", "https://www.oddsportal.com/football/world/world-cup-2018/results/"),
    ("Euro 2024", "https://www.oddsportal.com/football/europe/euro-2024/results/"),
    ("Euro 2020", "https://www.oddsportal.com/football/europe/euro-2020/results/"),
    ("Copa America 2021", "https://www.oddsportal.com/football/south-america/copa-america-2021/results/"),
    # Note: Copa America 2024 has no stable OddsPortal archive slug (soft-404s);
    # add it here if/when the correct URL is found.
]

FD_BASE = "https://www.football-data.co.uk/mmz4281"
FD_LEAGUES = {"E0": "EPL", "SP1": "La_Liga", "D1": "Bundesliga",
              "I1": "Serie_A", "F1": "Ligue_1"}
FD_SEASONS = ["2223", "2324", "2425"]
ODDS_MAP = {
    "B365H": "b365_open_h", "B365D": "b365_open_d", "B365A": "b365_open_a",
    "B365CH": "b365_close_h", "B365CD": "b365_close_d", "B365CA": "b365_close_a",
    "PSH": "pin_open_h", "PSD": "pin_open_d", "PSA": "pin_open_a",
    "PSCH": "pin_close_h", "PSCD": "pin_close_d", "PSCA": "pin_close_a",
    "MaxH": "max_h", "MaxD": "max_d", "MaxA": "max_a",
    "AvgH": "avg_h", "AvgD": "avg_d", "AvgA": "avg_a",
    "B365>2.5": "b365_over25", "B365<2.5": "b365_under25",
}


# ---------------------------------------------------------------------------
# OddsPortal (international closing odds)
# ---------------------------------------------------------------------------
def _parse_event_row(text: str):
    toks = [t.strip() for t in text.split("\n") if t.strip()]
    if "–" not in toks:
        return None
    odds = [t for t in toks if re.match(r"^\d{1,2}\.\d{2}$", t)]
    if len(odds) < 3:
        return None
    dm = re.search(r"(\d{1,2} [A-Za-z]{3} \d{4})", text)
    i = toks.index("–")
    try:
        home, hs, as_, away = toks[i - 2], toks[i - 1], toks[i + 1], toks[i + 2]
    except IndexError:
        return None
    if not re.match(r"^\d+$", hs) or not re.match(r"^\d+$", as_):
        return None
    return {
        "date": dm.group(1) if dm else None,
        "home": home, "away": away,
        "home_score": int(hs), "away_score": int(as_),
        "close_h": float(odds[-3]), "close_d": float(odds[-2]), "close_a": float(odds[-1]),
    }


def _wait_rows_stable(page, min_ticks: int = 6, max_ticks: int = 28):
    """
    Scroll and poll until the eventRow count stops growing. Patient: requires the
    count to hold steady for 4 consecutive ticks and never accepts before
    min_ticks (avoids latching onto a transient partially-rendered count).
    """
    prev, stable = -1, 0
    for tick in range(max_ticks):
        page.wait_for_timeout(1000)
        page.mouse.wheel(0, 1500)
        n = len(page.query_selector_all("div.eventRow"))
        stable = stable + 1 if n == prev else 0
        prev = n
        if tick >= min_ticks and stable >= 4 and n > 0:
            break
    return prev


def _scrape_op_page(page, url):
    """Load a results page with a full SPA reset + patient lazy-load wait."""
    out, seen = [], set()
    try:
        page.goto("about:blank")                 # reset SPA router/hash state
        page.wait_for_timeout(500)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
    except Exception as e:
        logger.warning(f"[s09] nav failed {url}: {e}")
        return out
    _wait_rows_stable(page)
    for r in page.query_selector_all("div.eventRow"):
        rec = _parse_event_row(r.inner_text())
        if not rec:
            continue
        key = (rec["date"], rec["home"], rec["away"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def scrape_oddsportal():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[s09] Playwright not installed.")
        return None
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage", "--no-sandbox"],
        )
        ctx = browser.new_context(user_agent=_UA, locale="en-US",
                                  timezone_id="America/New_York",
                                  viewport={"width": 1366, "height": 900})
        ctx.add_init_script(_STEALTH_JS)
        page = ctx.new_page()
        for name, url in OP_TOURNAMENTS:
            logger.info(f"[s09] OddsPortal: {name} ...")
            # OddsPortal intermittently serves a partial (~5-row) page; retry when
            # the result looks truncated and keep the best attempt.
            best = []
            for attempt in range(1, 4):
                recs = _scrape_op_page(page, url)
                if len(recs) > len(best):
                    best = recs
                if len(best) >= 20:
                    break
                logger.info(f"[s09]   attempt {attempt}: {len(recs)} rows (retrying)...")
                time.sleep(3)
            for r in best:
                r["tournament"] = name
            logger.info(f"[s09]   {len(best)} matches.")
            records.extend(best)
            time.sleep(2)
        browser.close()
    if not records:
        return None
    df = pd.DataFrame(records)
    df["source"] = "oddsportal"
    # implied closing probabilities (vig-inclusive)
    for side in ("h", "d", "a"):
        df[f"imp_{side}"] = (1 / df[f"close_{side}"]).round(4)
    return df


# ---------------------------------------------------------------------------
# football-data.co.uk (club closing odds)
# ---------------------------------------------------------------------------
def fetch_football_data():
    s = get_session()
    frames = []
    for season in FD_SEASONS:
        for div, league in FD_LEAGUES.items():
            url = f"{FD_BASE}/{season}/{div}.csv"
            try:
                r = s.get(url, timeout=30)
                r.raise_for_status()
                df = pd.read_csv(io.StringIO(r.text), encoding="latin-1")
            except Exception as e:
                logger.warning(f"[s09] football-data {season}/{div} failed: {e}")
                continue
            if "HomeTeam" not in df.columns:
                continue
            base = pd.DataFrame({
                "league": league, "season": f"20{season[:2]}-{season[2:]}",
                "date": df.get("Date"), "home": df.get("HomeTeam"),
                "away": df.get("AwayTeam"), "fthg": df.get("FTHG"),
                "ftag": df.get("FTAG"), "ftr": df.get("FTR"),
            })
            for src, dst in ODDS_MAP.items():
                if src in df.columns:
                    base[dst] = pd.to_numeric(df[src], errors="coerce")
            frames.append(base.dropna(subset=["home", "away"]))
            time.sleep(0.5)
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "football-data.co.uk"
    return out


def collect_odds():
    if not should_run("s09_odds_scraper"):
        logger.info("[s09] Already done. Skipping.")
        return

    logger.info("[s09] Collecting odds (OddsPortal international + football-data club)...")

    intl = None
    try:
        intl = scrape_oddsportal()
    except Exception as e:
        logger.warning(f"[s09] OddsPortal scrape errored: {e}")
    n_intl = 0
    if intl is not None and not intl.empty:
        save_csv(intl, RAW_DIR / "odds_international.csv")
        n_intl = len(intl)
        logger.info(f"[s09] OddsPortal: {n_intl} international matches w/ closing 1X2.")
    else:
        logger.warning("[s09] OddsPortal returned nothing (egress still blocked?).")

    club = fetch_football_data()
    n_club = 0
    if club is not None and not club.empty:
        save_csv(club, RAW_DIR / "odds_club_closing.csv")
        n_club = len(club)

    # Stage succeeds if either source produced data; validate the richer one.
    if n_intl >= 100:
        finalize_stage(
            "s09_odds_scraper", intl, RAW_DIR / "odds_international.csv",
            min_rows=100,
            required_cols=["tournament", "home", "away", "close_h", "close_a"],
            non_null_cols=["close_h", "close_d", "close_a"],
            extra_meta={"source": "oddsportal", "intl_matches": n_intl,
                        "club_matches": n_club,
                        "tournaments": intl["tournament"].nunique()},
        )
    elif n_club >= 1000:
        logger.warning("[s09] International odds unavailable; club-only this run.")
        finalize_stage(
            "s09_odds_scraper", club, RAW_DIR / "odds_club_closing.csv",
            min_rows=1000, required_cols=["league", "home", "away"],
            non_null_cols=["home", "away"],
            extra_meta={"source": "football-data.co.uk", "intl_matches": n_intl,
                        "club_matches": n_club,
                        "note": "OddsPortal yielded no intl odds (egress blocked?)."},
        )
    else:
        save_checkpoint("s09_odds_scraper", status="failed",
                        meta={"reason": "both_sources_empty"})


if __name__ == "__main__":
    collect_odds()
