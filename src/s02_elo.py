"""
Stage 02 - ELO ratings time-series from eloratings.net.

eloratings.net exposes year-end ranking tables as TSV at
https://www.eloratings.net/{YEAR}.tsv and the current table at
https://www.eloratings.net/World.tsv. Each row encodes a team's year-end ELO.

Per-match ELO is not downloadable (the match pages are JS-rendered and the
site blocks bulk access), so we collect the documented year-end series
(date = YYYY-12-31) for every available year. elo_change is computed as the
year-over-year delta per team. Result -> raw/elo/elo_ratings.csv
"""
from __future__ import annotations

import re
import sys
from datetime import datetime

import pandas as pd

from common import RAW, polite_get, get_logger, log_attempt, save_df

log = get_logger("s02_elo")

ELO_DIR = RAW / "elo"
CODE_RE = re.compile(r"^[A-Z]{2,3}$")

# eloratings 2-letter codes -> team names. Names are aligned to the WC-2026
# qualified-team labels so downstream joins land cleanly. Others kept as code.
CODE_MAP = {
    "AR": "Argentina", "FR": "France", "ES": "Spain", "BR": "Brazil", "EN": "England",
    "BE": "Belgium", "NL": "Netherlands", "PT": "Portugal", "IT": "Italy", "DE": "Germany",
    "HR": "Croatia", "UY": "Uruguay", "CO": "Colombia", "MX": "Mexico", "US": "USA",
    "CH": "Switzerland", "DK": "Denmark", "MA": "Morocco", "SN": "Senegal", "JP": "Japan",
    "KR": "Korea Republic", "RS": "Serbia", "PL": "Poland", "WL": "Wales", "AT": "Austria",
    "UA": "Ukraine", "SE": "Sweden", "EC": "Ecuador", "PE": "Peru", "TN": "Tunisia",
    "CR": "Costa Rica", "AU": "Australia", "IR": "IR Iran", "GH": "Ghana", "CM": "Cameroon",
    "NG": "Nigeria", "EG": "Egypt", "DZ": "Algeria", "CL": "Chile", "PY": "Paraguay",
    "SCO": "Scotland", "TR": "Türkiye", "CZ": "Czechia", "NO": "Norway", "HU": "Hungary",
    "GR": "Greece", "SK": "Slovakia", "SI": "Slovenia", "RO": "Romania", "IE": "Ireland",
    "CA": "Canada", "QA": "Qatar", "SA": "Saudi Arabia", "RU": "Russia", "CI": "Côte d'Ivoire",
    # additional WC-2026 qualified nations
    "BA": "Bosnia and Herzegovina", "CV": "Cabo Verde", "CD": "Congo DR", "CW": "Curaçao",
    "HT": "Haiti", "IQ": "Iraq", "JO": "Jordan", "NZ": "New Zealand", "PA": "Panama",
    "UZ": "Uzbekistan", "ZA": "South Africa", "RSA": "South Africa", "JM": "Jamaica",
    "HN": "Honduras",
}


def parse_tsv(text: str, year_label: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        # find the 2-3 letter country code, then the next integer is the ELO
        code, elo = None, None
        for i, tok in enumerate(parts):
            if CODE_RE.match(tok.strip()):
                code = tok.strip()
                for nxt in parts[i + 1:]:
                    n = nxt.strip().replace("−", "-")
                    if re.fullmatch(r"\d{3,4}", n):
                        elo = int(n)
                        break
                break
        if code and elo and 400 <= elo <= 2500:
            rows.append({"code": code, "team": CODE_MAP.get(code, code), "elo": elo})
    return rows


def main() -> None:
    ELO_DIR.mkdir(parents=True, exist_ok=True)
    this_year = datetime.now().year
    all_rows: list[dict] = []

    # year-end tables: eloratings has data from 1901 onward reliably
    for year in range(1901, this_year):
        url = f"https://www.eloratings.net/{year}.tsv"
        resp = polite_get(url, source="elo", min_delay=0.6, max_delay=1.2, retries=2)
        if resp is None:
            log_attempt("elo", url, "fail", 0, "no response")
            continue
        rows = parse_tsv(resp.text, str(year))
        if not rows:
            log_attempt("elo", url, "empty", 0, "no parsable rows")
            continue
        date = f"{year}-12-31"
        for r in rows:
            r["date"] = date
        all_rows.extend(rows)
        log_attempt("elo", url, "ok", len(rows))
        log.info(f"{year}: {len(rows)} teams")

    # current snapshot
    resp = polite_get("https://www.eloratings.net/World.tsv", source="elo",
                      min_delay=0.6, max_delay=1.2, retries=2)
    if resp is not None:
        rows = parse_tsv(resp.text, "current")
        date = datetime.now().strftime("%Y-%m-%d")
        for r in rows:
            r["date"] = date
        all_rows.extend(rows)
        log_attempt("elo", "World.tsv", "ok", len(rows))
        log.info(f"current: {len(rows)} teams")

    if not all_rows:
        log.error("ELO: no data collected")
        return

    df = pd.DataFrame(all_rows)[["date", "code", "team", "elo"]]
    df = df.sort_values(["team", "date"]).reset_index(drop=True)
    # year-over-year change per team
    df["elo_change"] = df.groupby("team")["elo"].diff().fillna(0).astype(int)
    save_df(df, ELO_DIR / "elo_ratings.csv")
    log.info(f"stage 02 (elo) complete: {len(df)} rows, {df['team'].nunique()} teams, "
             f"{df['date'].min()}..{df['date'].max()}")


if __name__ == "__main__":
    sys.exit(main())
