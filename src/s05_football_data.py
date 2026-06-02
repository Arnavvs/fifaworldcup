"""
Stage 05 - football-data.co.uk odds + results (best-effort).

football-data.co.uk's core product is domestic leagues; it does not publish a
clean international-results CSV feed (the internationals page returns no
downloadable links). We therefore: (1) attempt to discover any CSV links on the
internationals page, and (2) harvest the major-tournament CSVs they DO host
(World Cup / Euro fixture files when available). Anything found is normalised to
the odds schema. If nothing is available the stage logs the gap and exits
cleanly -- the rest of the pipeline does not depend on it.
Output -> raw/football_data/odds.csv
"""
from __future__ import annotations

import re
import sys
from io import StringIO

import pandas as pd

from common import RAW, polite_get, get_logger, log_attempt, save_df

log = get_logger("s05_fdata")
OUT = RAW / "football_data"

ODDS_COLS = {
    "B365H": "home", "B365D": "draw", "B365A": "away",
    "BWH": "home", "BWD": "draw", "BWA": "away",
    "PSH": "home", "PSD": "draw", "PSA": "away",
    "WHH": "home", "WHD": "draw", "WHA": "away",
    "VCH": "home", "VCD": "draw", "VCA": "away",
}


def discover_csv_links() -> list[str]:
    base = "https://www.football-data.co.uk/"
    resp = polite_get(base + "internationals.php", source="football_data", retries=2)
    links: list[str] = []
    if resp is not None and resp.status_code == 200:
        for m in re.findall(r'href=[\"\']([^\"\']+\.csv)[\"\']', resp.text, re.I):
            links.append(m if m.startswith("http") else base + m.lstrip("/"))
    return sorted(set(links))


def normalise_odds(df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    rows = []
    home_col = next((c for c in ("HomeTeam", "Home") if c in df.columns), None)
    away_col = next((c for c in ("AwayTeam", "Away") if c in df.columns), None)
    date_col = next((c for c in ("Date",) if c in df.columns), None)
    for _, r in df.iterrows():
        base = {
            "date": r.get(date_col) if date_col else None,
            "home_team": r.get(home_col) if home_col else None,
            "away_team": r.get(away_col) if away_col else None,
        }
        # group bookmaker triplets
        for bm, prefix in [("B365", "B365"), ("BW", "BW"), ("PS", "PS"), ("WH", "WH"), ("VC", "VC")]:
            h, d, a = f"{prefix}H", f"{prefix}D", f"{prefix}A"
            if h in df.columns:
                rows.append({**base, "bookmaker": bm,
                             "home_odds": r.get(h), "draw_odds": r.get(d), "away_odds": r.get(a),
                             "over25_odds": r.get(f"{prefix}>2.5"), "under25_odds": r.get(f"{prefix}<2.5")})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    links = discover_csv_links()
    log.info(f"football-data: discovered {len(links)} csv links")
    frames = []
    for url in links:
        resp = polite_get(url, source="football_data", retries=2)
        if resp is None:
            continue
        try:
            df = pd.read_csv(StringIO(resp.text))
            if any(c in df.columns for c in ODDS_COLS):
                frames.append(normalise_odds(df, url))
                log_attempt("football_data", url, "ok", len(df))
            else:
                log_attempt("football_data", url, "skip", len(df), "no odds cols")
        except Exception as e:
            log_attempt("football_data", url, "fail", 0, str(e)[:120])

    if frames:
        out = pd.concat(frames, ignore_index=True).dropna(how="all")
        save_df(out, OUT / "odds.csv")
        log.info(f"football-data odds: {len(out)} rows")
    else:
        log.warning("football-data: no international odds CSVs available "
                    "(site publishes club leagues only) -- odds table left empty")
        # write an empty schema file so downstream join is well-defined
        pd.DataFrame(columns=["date", "home_team", "away_team", "bookmaker",
                              "home_odds", "draw_odds", "away_odds",
                              "over25_odds", "under25_odds"]).to_csv(OUT / "odds.csv", index=False)
        log_attempt("football_data", "internationals", "empty", 0, "no intl odds feed")
    log.info("stage 05 (football-data) complete")


if __name__ == "__main__":
    sys.exit(main())
