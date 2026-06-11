"""
Stage 01 — FIFA Men's World Ranking, current full table (all ~210 teams).

fifa.com is behind Akamai bot protection, so plain HTTP gets a challenge page
and the public JSON API returns empty. We therefore drive a stealthed Chromium
to the ranking page (which sets the Akamai cookies) and call FIFA's own
ranking-overview API *from inside that browser session* for the latest release.

Primary : FIFA.com live (full current table, ~210 teams, rank + points).
Fallback: Kaggle `cashncarry/fifaworldranking` (full tables through 2024-06).

Outputs: processed/fifa_rankings_updated.csv
"""
import io
import re
import sys
import json
import glob
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, PROCESSED_DIR, RAW_DIR, should_run, save_checkpoint,
    finalize_stage, _STEALTH_JS, _UA,
)

RANKING_URL = "https://www.fifa.com/fifa-world-ranking/men"
API_TMPL = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId={did}"


def fetch_fifa_live(max_nav_retries: int = 3):
    """Return a DataFrame of the latest full FIFA ranking, or None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[s01] Playwright not installed.")
        return None

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
        try:
            ok = False
            for attempt in range(1, max_nav_retries + 1):
                try:
                    page.goto(RANKING_URL, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(4000)
                    ok = True
                    break
                except Exception as e:
                    logger.warning(f"[s01] nav attempt {attempt} failed: {e}")
                    time.sleep(3)
            if not ok:
                return None

            m = re.search(r'__NEXT_DATA__"[^>]*>(.+?)</script>', page.content(), re.S)
            if not m:
                logger.warning("[s01] __NEXT_DATA__ not found.")
                return None
            nd = json.loads(m.group(1))
            dates = nd["props"]["pageProps"]["pageData"]["ranking"]["dates"]
            date_id = dates[0]["dates"][0]["id"]
            date_iso = dates[0]["dates"][0].get("matchWindowEndDate")
            logger.info(f"[s01] latest ranking release: {date_id} ({date_iso})")

            js = (
                "async (did) => { const r = await fetch("
                "'https://inside.fifa.com/api/ranking-overview?locale=en&dateId='+did,"
                "{headers:{'Accept':'application/json'}}); return await r.text(); }"
            )
            txt = page.evaluate(js, date_id)
            data = json.loads(txt)
            rankings = data.get("rankings") or []
            if not rankings:
                logger.warning("[s01] API returned no rankings.")
                return None

            rows = []
            for item in rankings:
                team = item.get("rankingItem", {}) or {}
                rows.append({
                    "rank": item.get("rankingItem", {}).get("rank") or item.get("rank"),
                    "team": team.get("name") or team.get("countryName"),
                    "country_code": team.get("countryCode"),
                    "points": item.get("totalPoints") or item.get("points"),
                    "previous_points": item.get("previousPoints"),
                    "confederation": item.get("confederation") or team.get("confederation"),
                    "rank_date": date_iso,
                    "source": "fifa.com_live",
                })
            df = pd.DataFrame(rows)
            # Coerce numerics; drop rows missing core fields.
            df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
            df["points"] = pd.to_numeric(df["points"], errors="coerce")
            df = df.dropna(subset=["team", "rank"]).sort_values("rank")
            return df
        except Exception as e:
            logger.warning(f"[s01] FIFA live fetch failed: {e}")
            return None
        finally:
            browser.close()


def fetch_kaggle_fallback():
    """Download cashncarry/fifaworldranking and return the latest full snapshot."""
    logger.info("[s01] Falling back to Kaggle cashncarry/fifaworldranking ...")
    tmp = RAW_DIR / "kaggle_fifa_ranking"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        import kaggle  # noqa: F401  (auth via ~/.kaggle)
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi(); api.authenticate()
        api.dataset_download_files("cashncarry/fifaworldranking", path=str(tmp), unzip=True)
    except Exception as e:
        logger.error(f"[s01] Kaggle download failed: {e}")
        return None

    csvs = sorted(glob.glob(str(tmp / "*.csv")))
    if not csvs:
        return None
    # Concatenate, take the most recent release date's full table.
    frames = [pd.read_csv(c) for c in csvs]
    full = pd.concat(frames, ignore_index=True).drop_duplicates()
    latest_date = full["rank_date"].max()
    snap = full[full["rank_date"] == latest_date].copy()
    df = snap.rename(columns={
        "country_full": "team", "country_abrv": "country_code",
        "total_points": "points",
    })[["rank", "team", "country_code", "points", "previous_points",
        "confederation", "rank_date"]]
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["points"] = pd.to_numeric(df["points"], errors="coerce")
    df = df.dropna(subset=["team", "rank"]).sort_values("rank").reset_index(drop=True)
    df["source"] = "kaggle_cashncarry"
    logger.info(f"[s01] Kaggle latest full table: {latest_date}, {len(df)} teams.")
    return df


def update_fifa_rankings():
    if not should_run("s01_fifa_rankings"):
        logger.info("[s01] Already done. Skipping.")
        return

    logger.info("[s01] Updating FIFA rankings (live → Kaggle fallback)...")
    df = fetch_fifa_live()
    if df is None or df.empty or len(df) < 100:
        logger.warning("[s01] FIFA live insufficient; using Kaggle fallback.")
        df = fetch_kaggle_fallback()

    out = PROCESSED_DIR / "fifa_rankings_updated.csv"
    ok = finalize_stage(
        "s01_fifa_rankings", df, out,
        min_rows=100,
        required_cols=["rank", "team", "points"],
        non_null_cols=["rank", "team", "points"],
        extra_meta={"source": (df["source"].iloc[0] if df is not None and not df.empty else "none")},
    )
    if ok:
        logger.info(f"[s01] {len(df)} ranking rows saved (source={df['source'].iloc[0]}).")


if __name__ == "__main__":
    update_fifa_rankings()
