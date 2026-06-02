"""
Stage 14 - Official WC-2026 squads (Wikipedia).

Parses the '2026 FIFA World Cup squads' page: each team's official 26-man list
with shirt no., position, player, DOB/age, caps, goals, and club. Associates
every squad table with its team via the preceding section heading.
Outputs -> raw/squads_wc2026/official_squads.csv  + DB table official_squads_2026
"""
from __future__ import annotations

import re
import sqlite3
import sys
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup

from common import RAW, DB_PATH, polite_get, get_logger, log_attempt, save_df

log = get_logger("s14_squads")
OUT = RAW / "squads_wc2026"
URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"

SQUAD_COLS = {"Player", "Pos.", "Caps", "Club"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resp = polite_get(URL, source="wc2026_squads", min_delay=1, max_delay=2, retries=3)
    if resp is None:
        log.error("could not fetch squads page")
        log_attempt("wc2026_squads", URL, "fail", 0, "no response")
        return
    soup = BeautifulSoup(resp.text, "html.parser")

    frames = []
    for table in soup.find_all("table", class_="wikitable"):
        # quick header check
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not SQUAD_COLS.issubset(set(headers)):
            continue
        # find the team name: nearest preceding h2/h3/h4 headline
        team = None
        for prev in table.find_all_previous(["h4", "h3", "h2"]):
            span = prev.find("span", class_="mw-headline")
            name = (span.get_text(strip=True) if span else prev.get_text(strip=True))
            # skip generic group headings
            if name and not re.match(r"^(Group [A-L]|Squads?|Notes|References|Contents)$", name):
                team = name
                break
        try:
            df = pd.read_html(StringIO(str(table)))[0]
        except Exception:
            continue
        df.columns = [str(c) for c in df.columns]
        df["team"] = team
        frames.append(df)

    if not frames:
        log.error("no squad tables parsed")
        log_attempt("wc2026_squads", URL, "empty", 0, "0 squad tables")
        return

    allsq = pd.concat(frames, ignore_index=True)
    # normalise column names
    ren = {}
    for c in allsq.columns:
        lc = c.lower()
        if lc.startswith("no"): ren[c] = "shirt_no"
        elif lc.startswith("pos"): ren[c] = "position"
        elif lc == "player": ren[c] = "player"
        elif "birth" in lc: ren[c] = "dob_age"
        elif lc == "caps": ren[c] = "caps"
        elif lc == "goals": ren[c] = "goals"
        elif lc == "club": ren[c] = "club"
        elif lc == "team": ren[c] = "team"
    allsq = allsq.rename(columns=ren)
    keep = [c for c in ["team", "shirt_no", "position", "player", "dob_age",
                        "caps", "goals", "club"] if c in allsq.columns]
    allsq = allsq[keep].dropna(subset=["player"])
    allsq = allsq[allsq["player"].astype(str).str.len() > 1]

    save_df(allsq, OUT / "official_squads.csv")
    con = sqlite3.connect(DB_PATH)
    allsq.to_sql("official_squads_2026", con, if_exists="replace", index=False)
    con.commit(); con.close()

    n_teams = allsq["team"].nunique()
    log_attempt("wc2026_squads", URL, "ok", len(allsq), f"{n_teams} teams")
    log.info(f"official WC2026 squads: {len(allsq)} players across {n_teams} teams")
    log.info("sample teams: " + ", ".join(sorted(allsq['team'].dropna().unique())[:12]))


if __name__ == "__main__":
    sys.exit(main())
