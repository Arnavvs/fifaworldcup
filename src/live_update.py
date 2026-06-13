"""
live_update.py — WC2026 per-matchday update loop. (Roadmap §8, TASK 1 id:LIVE)

Workflow:
  1. Fetch scores from fixturedownload (primary) + Wikipedia group pages (fallback).
  2. Upsert into wc2026_fixtures and matches.
  3. For each NEW result, update elo_current (K=60, home adv only for USA/Mex/Can).
  4. Re-run m8_simulate → new artifacts/run_<ts>/.
  5. Compute realized surprisal for played matches using previous run's match_probs.
  6. Append to prediction_history.csv; write realized_surprisal.csv.
  7. Update dashboard/data files.

Idempotence: track ingested match_numbers in artifacts/ingested.json.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import re

import numpy as np
import pandas as pd
import requests

from common import DB_PATH, ROOT, get_logger, polite_get
from m1_elo_davidson import k_factor, goal_mult

log = get_logger("live")
ART = ROOT / "artifacts"
DASH = ROOT / "dashboard" / "data"
INGESTED = ART / "ingested.json"

FIXTURE_URL = "https://fixturedownload.com/feed/json/fifa-world-cup-2026"
GROUPS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
HOSTS = {"USA", "Mexico", "Canada"}


def load_ingested() -> set:
    if INGESTED.exists():
        return set(json.loads(INGESTED.read_text(encoding="utf-8")).get("match_numbers", []))
    return set()


def save_ingested(nums: set):
    INGESTED.parent.mkdir(parents=True, exist_ok=True)
    INGESTED.write_text(json.dumps({"match_numbers": sorted(nums), "updated": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")


def fetch_fixturedownload() -> pd.DataFrame:
    """Primary feed. Returns DataFrame with MatchNumber, HomeTeam, AwayTeam, HomeTeamScore, AwayTeamScore."""
    try:
        r = requests.get(FIXTURE_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return pd.DataFrame()
        rows = []
        for item in data:
            if item.get("HomeTeamScore") is not None and item.get("AwayTeamScore") is not None:
                rows.append({
                    "MatchNumber": int(item.get("MatchNumber", 0)),
                    "HomeTeam": str(item.get("HomeTeam", "")),
                    "AwayTeam": str(item.get("AwayTeam", "")),
                    "HomeTeamScore": int(item.get("HomeTeamScore")),
                    "AwayTeamScore": int(item.get("AwayTeamScore")),
                })
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"fixturedownload failed: {e}")
        return pd.DataFrame()


def fetch_wikipedia_group(group: str) -> pd.DataFrame:
    """Scrape one group page for result tables."""
    url = f"https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_{group}"
    resp = polite_get(url, source="wikipedia")
    if resp is None:
        return pd.DataFrame()
    try:
        tables = pd.read_html(resp.text)
    except Exception as e:
        log.warning(f"pd.read_html failed for Group {group}: {e}")
        return pd.DataFrame()

    rows = []
    for tbl in tables:
        cols = [str(c).lower() for c in tbl.columns]
        if any("home team" in c or "away team" in c or "score" in c for c in cols):
            for _, r in tbl.iterrows():
                vals = [str(v) for v in r.values]
                for i, v in enumerate(vals):
                    m = re.search(r"(\d+)[–-](\d+)", v)
                    if m:
                        home_score = int(m.group(1))
                        away_score = int(m.group(2))
                        home_team = vals[i-1] if i > 0 else None
                        away_team = vals[i+1] if i < len(vals)-1 else None
                        if home_team and away_team and home_team != away_team:
                            rows.append({"HomeTeam": home_team, "AwayTeam": away_team,
                                         "HomeTeamScore": home_score, "AwayTeamScore": away_score})
    return pd.DataFrame(rows)


def fetch_wikipedia_scores() -> pd.DataFrame:
    """Fallback: parse all group pages."""
    all_rows = []
    for g in GROUPS:
        df = fetch_wikipedia_group(g)
        if not df.empty:
            all_rows.append(df)
        time.sleep(1)
    if not all_rows:
        return pd.DataFrame()
    combined = pd.concat(all_rows, ignore_index=True)
    combined = combined.drop_duplicates(subset=["HomeTeam", "AwayTeam"])
    return combined


def canonicalize_team(name: str, canon: dict) -> str:
    return canon.get(name, name)


def load_canon() -> dict:
    tm = pd.read_csv(ROOT / "research_ready_dataset" / "team_mapping.csv")
    return dict(zip(tm["raw_name"], tm["canonical_name"]))


def upsert_scores(fx_df: pd.DataFrame, con: sqlite3.Connection, canon: dict, ingested_set: set) -> list:
    """Upsert scores into wc2026_fixtures and matches. Returns list of match numbers that need processing."""
    cur = con.cursor()
    cur.execute("SELECT MatchNumber, DateUtc, HomeTeam, AwayTeam, \"Group\" FROM wc2026_fixtures")
    fx_rows = {r[0]: (r[1], r[2], r[3], r[4]) for r in cur.fetchall()}

    # Get max match_id for generating new ones
    cur.execute("SELECT MAX(match_id) FROM matches")
    max_id = cur.fetchone()[0] or 0

    new = []
    for _, row in fx_df.iterrows():
        mn = int(row.get("MatchNumber", 0))
        if mn not in fx_rows:
            # Try match by team names
            ht = canonicalize_team(str(row["HomeTeam"]), canon)
            at = canonicalize_team(str(row["AwayTeam"]), canon)
            for fx_mn, (fx_date, fx_ht, fx_at, fx_group) in fx_rows.items():
                if fx_ht == ht and fx_at == at:
                    mn = fx_mn
                    break
        if mn not in fx_rows:
            log.warning(f"Could not match fixture: {row['HomeTeam']} vs {row['AwayTeam']}")
            continue

        date, ht, at, group = fx_rows[mn]
        ht = canonicalize_team(ht, canon)
        at = canonicalize_team(at, canon)
        hs = int(row["HomeTeamScore"])
        aws = int(row["AwayTeamScore"])

        # Check if score already in wc2026_fixtures
        cur.execute("SELECT HomeTeamScore FROM wc2026_fixtures WHERE MatchNumber=?", (mn,))
        existing = cur.fetchone()
        score_already_in_db = existing and existing[0] is not None

        if not score_already_in_db:
            # Upsert wc2026_fixtures
            cur.execute("UPDATE wc2026_fixtures SET HomeTeamScore=?, AwayTeamScore=? WHERE MatchNumber=?",
                        (hs, aws, mn))

        # Upsert matches — match on date + home + away
        cur.execute("SELECT match_id FROM matches WHERE date=? AND home_team=? AND away_team=?",
                    (date, ht, at))
        existing_match = cur.fetchone()
        if existing_match:
            match_id = existing_match[0]
            cur.execute("UPDATE matches SET home_score=?, away_score=? WHERE match_id=?",
                        (hs, aws, match_id))
        else:
            max_id += 1
            match_id = max_id
            # Determine neutral: true neutral unless host is home team
            neutral = 0 if ht in HOSTS else 1
            # Determine competition
            comp = "2026 FIFA World Cup"
            if group and "qual" in str(group).lower():
                comp = "2026 FIFA World Cup qualification"
            cur.execute("""
                INSERT INTO matches (match_id, date, competition, home_team, away_team,
                                     home_score, away_score, neutral, city, country)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, date, comp, ht, at, hs, aws, neutral, None, None))

        if not score_already_in_db:
            log.info(f"Ingested match {mn}: {ht} {hs}–{aws} {at}")

        if mn not in ingested_set:
            new.append(mn)

    con.commit()
    return new


def update_elo_for_match(mn: int, con: sqlite3.Connection, canon: dict):
    """Update ELO for a single newly played match (from wc2026_fixtures)."""
    cur = con.cursor()
    cur.execute('SELECT HomeTeam, AwayTeam, HomeTeamScore, AwayTeamScore, "Group" FROM wc2026_fixtures WHERE MatchNumber=?', (mn,))
    row = cur.fetchone()
    if not row:
        return
    ht, at, hs, aws, group = row
    ht = canonicalize_team(ht, canon)
    at = canonicalize_team(at, canon)
    hs = int(hs)
    aws = int(aws)

    cur.execute("SELECT elo FROM elo_current WHERE team=?", (ht,))
    r_h = cur.fetchone()
    cur.execute("SELECT elo FROM elo_current WHERE team=?", (at,))
    r_a = cur.fetchone()
    if not r_h or not r_a:
        log.warning(f"ELO missing for {ht} or {at}")
        return
    eh = float(r_h[0])
    ea = float(r_a[0])

    # Home advantage only for USA/Mexico/Canada
    home_adv = 100 if ht in HOSTS else 0
    dr = eh - ea + home_adv
    we = 1.0 / (1.0 + 10 ** (-dr / 400.0))
    w = 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
    g = goal_mult(abs(hs - aws))
    comp = "2026 FIFA World Cup"
    k = k_factor(comp)
    delta = k * g * (w - we)

    new_h = eh + delta
    new_a = ea - delta

    cur.execute("UPDATE elo_current SET elo=?, n_matches=n_matches+1, last_date=? WHERE team=?",
                (round(new_h, 1), datetime.now(timezone.utc).strftime("%Y-%m-%d"), ht))
    cur.execute("UPDATE elo_current SET elo=?, n_matches=n_matches+1, last_date=? WHERE team=?",
                (round(new_a, 1), datetime.now(timezone.utc).strftime("%Y-%m-%d"), at))
    con.commit()
    log.info(f"ELO updated: {ht} {eh:.0f}→{new_h:.0f}  {at} {ea:.0f}→{new_a:.0f}  (K={k} G={g} δ={delta:.1f})")


def find_latest_run() -> Path | None:
    """Find the most recent artifacts/run_* directory."""
    runs = sorted(ART.glob("run_*"))
    return runs[-1] if runs else None


def compute_realized_surprisal(new_match_numbers: list, con: sqlite3.Connection) -> list:
    """Compute I = -ln p(observed) for newly played matches using PREVIOUS run's match_probs."""
    prev_run = find_latest_run()
    if prev_run is None:
        log.warning("No previous run found for surprisal computation")
        return []
    sim_file = prev_run / "sim_results.json"
    if not sim_file.exists():
        return []
    sim = json.loads(sim_file.read_text(encoding="utf-8"))
    probs = {m["match_number"]: m["p"] for m in sim.get("match_probs", [])}

    cur = con.cursor()
    rows = []
    for mn in new_match_numbers:
        cur.execute("""
            SELECT HomeTeam, AwayTeam, HomeTeamScore, AwayTeamScore
            FROM wc2026_fixtures WHERE MatchNumber=?
        """, (mn,))
        row = cur.fetchone()
        if not row:
            continue
        ht, at, hs, aws = row
        hs = int(hs)
        aws = int(aws)
        outcome = 2 if hs > aws else (1 if hs == aws else 0)
        p = probs.get(mn)
        if not p:
            continue
        p_outcome = max(p[outcome], 1e-12)
        surprisal = -np.log(p_outcome)
        rows.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "match_number": mn,
            "home": ht,
            "away": at,
            "outcome": outcome,
            "p_outcome": round(p_outcome, 4),
            "surprisal": round(surprisal, 4),
        })
    return rows


def append_surprisal(rows: list):
    if not rows:
        return
    f = ART / "realized_surprisal.csv"
    new = not f.exists()
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ts", "match_number", "home", "away", "outcome", "p_outcome", "surprisal"])
        if new:
            w.writeheader()
        w.writerows(rows)
    log.info(f"Appended {len(rows)} rows to realized_surprisal.csv")


def main():
    ingested = load_ingested()
    canon = load_canon()

    # ---- 1. Fetch scores ----
    fx = fetch_fixturedownload()
    log.info(f"fixturedownload: {len(fx)} finished matches")
    if fx.empty:
        fx = fetch_wikipedia_scores()
        log.info(f"wikipedia fallback: {len(fx)} finished matches")

    if fx.empty:
        log.info("No new scores from external feeds.")

    # ---- 2. Upsert into DB ----
    con = sqlite3.connect(DB_PATH)
    new_matches = upsert_scores(fx, con, canon, ingested)

    # Also check DB for scores that were set externally but not yet ingested
    cur = con.cursor()
    cur.execute("SELECT MatchNumber FROM wc2026_fixtures WHERE HomeTeamScore IS NOT NULL")
    db_played = {r[0] for r in cur.fetchall()}
    not_ingested = db_played - ingested
    if not_ingested:
        log.info(f"Found {len(not_ingested)} matches with scores not yet ingested: {sorted(not_ingested)}")
        # Build a dataframe from the DB for these matches
        placeholders = ",".join("?" * len(not_ingested))
        cur.execute(f"SELECT MatchNumber, HomeTeam, AwayTeam, HomeTeamScore, AwayTeamScore FROM wc2026_fixtures WHERE MatchNumber IN ({placeholders})", tuple(not_ingested))
        rows = []
        for r in cur.fetchall():
            rows.append({"MatchNumber": r[0], "HomeTeam": r[1], "AwayTeam": r[2], "HomeTeamScore": r[3], "AwayTeamScore": r[4]})
        db_df = pd.DataFrame(rows)
        db_new = upsert_scores(db_df, con, canon, ingested)
        new_matches = list(set(new_matches) | set(db_new))

    if not new_matches:
        log.info("All scores already ingested — no-op.")
        con.close()
        return

    # ---- 3. Update ELO for new matches ----
    for mn in new_matches:
        update_elo_for_match(mn, con, canon)

    # Mark ingested
    ingested.update(new_matches)
    save_ingested(ingested)

    # ---- 4. Re-simulate ----
    log.info("Re-running simulator...")
    from m8_simulate import main as sim
    sim()

    # ---- 5. Realized surprisal ----
    surp_rows = compute_realized_surprisal(new_matches, con)
    append_surprisal(surp_rows)
    con.close()

    # ---- 6. Update dashboard data ----
    latest = find_latest_run()
    if latest:
        src = latest / "sim_results.json"
        if src.exists():
            DASH.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(src, DASH / "sim_results.json")
            data = json.loads(src.read_text(encoding="utf-8"))
            (ROOT / "dashboard" / "sim_data.js").write_text(
                "window.SIM = " + json.dumps(data) + ";", encoding="utf-8")

    # ---- 7. Track ----
    n_new = len(new_matches)
    if latest:
        data = json.loads((latest / "sim_results.json").read_text(encoding="utf-8"))
        champ = list(data.get("champion", {}).items())[0]
        log.info(f"live update: {n_new} new results, champion now {champ[0]} {champ[1]:.1%}")
    else:
        log.info(f"live update: {n_new} new results")

    subprocess.run(["python", str(ROOT / "src" / "track.py"), "log",
                  f"live update: {n_new} new results ingested"])

    # refresh the live model scorecard (accuracy.html) from played results
    subprocess.run(["python", str(ROOT / "src" / "scorecard.py")])


if __name__ == "__main__":
    main()
