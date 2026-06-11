"""
Stage 04 — Compute squad aggregates from official_squads_2026.
Outputs: processed/squad_aggregates.csv
"""
import re
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, save_csv, PROCESSED_DIR,
    should_run, save_checkpoint,
)


def parse_dob_age(s):
    """
    official_squads_2026 dob_age looks like:
    'May 17, 2000 (aged 26)'  or  '1987-06-24 (38)'.
    Returns (age_int, dob_iso or None)
    """
    if pd.isna(s):
        return None, None
    s = str(s)
    # Age is the parenthesised number, optionally prefixed with 'aged'.
    age = None
    m_age = re.search(r"\(\s*(?:aged\s+)?(\d{1,2})\s*\)", s)
    if m_age:
        age = int(m_age.group(1))
    # Date of birth: ISO (1987-06-24) or 'May 17, 2000'.
    dob = None
    m_iso = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m_iso:
        dob = m_iso.group(1)
    else:
        m_long = re.match(r"\s*([A-Za-z]+ \d{1,2}, \d{4})", s)
        if m_long:
            try:
                dob = pd.to_datetime(m_long.group(1)).strftime("%Y-%m-%d")
            except Exception:
                dob = None
    # If age still unknown but we have a DOB, derive it.
    if age is None and dob:
        try:
            age = int((pd.Timestamp("2026-06-11") - pd.Timestamp(dob)).days // 365.25)
        except Exception:
            pass
    return age, dob


def club_quality_proxy(club: str) -> int:
    """
    Very rough club quality proxy based on league reputation.
    5 = elite (Big 5 + UCL regulars)
    4 = strong (Portugal, Netherlands, top non-Big5)
    3 = mid (MLS, Brazil top, Argentina top, etc.)
    2 = lower
    1 = unknown
    """
    club_lower = str(club).lower()
    elite = [
        "manchester city", "manchester united", "liverpool", "chelsea", "arsenal",
        "tottenham", "real madrid", "barcelona", "atletico madrid", "bayern munich",
        "borussia dortmund", "paris saint-germain", "psg", "inter milan", "ac milan",
        "juventus", "napoli", "roma", "benfica", "porto", "ajax",
    ]
    strong = [
        "sporting cp", "braga", "feyenoord", "psv", "shakhtar donetsk",
        "rb leipzig", "bayer leverkusen", "villarreal", "real sociedad", "sevilla",
        "lazio", "atalanta", "newcastle", "aston villa", "brighton",
    ]
    mid = [
        "inter miami", "los angeles galaxy", "la galaxy", "la fc", "toronto fc",
        "flamengo", "palmeiras", "sao paulo", "corinthians", "river plate",
        "boca juniors", "racing club", "independiente", "cruz azul", "club america",
        "tigres", "monterrey", "al hilal", "al nassr", "al ittihad",
        " Celtic", "rangers", "anderlecht", "genk", "standard liege",
    ]

    for e in elite:
        if e in club_lower:
            return 5
    for s in strong:
        if s in club_lower:
            return 4
    for m in mid:
        if m in club_lower:
            return 3
    return 2  # default lower-mid


def compute_squad_aggregates():
    if not should_run("s04_squad_aggregates"):
        logger.info("[s04] Already done. Skipping.")
        return

    logger.info("[s04] Computing squad aggregates from official_squads_2026...")
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM official_squads_2026", conn)
    conn.close()

    if df.empty:
        logger.error("[s04] official_squads_2026 table is empty! Aborting.")
        return

    # Parse age
    parsed = df["dob_age"].apply(parse_dob_age)
    df["age"] = [p[0] for p in parsed]
    df["dob"] = [p[1] for p in parsed]

    # Ensure numeric caps/goals
    df["caps"] = pd.to_numeric(df["caps"], errors="coerce")
    df["goals"] = pd.to_numeric(df["goals"], errors="coerce")
    df["club_quality"] = df["club"].apply(club_quality_proxy)

    agg = df.groupby("team").agg(
        squad_size=("player", "count"),
        mean_age=("age", "mean"),
        median_age=("age", "median"),
        mean_caps=("caps", "mean"),
        median_caps=("caps", "median"),
        total_goals=("goals", "sum"),
        mean_goals=("goals", "mean"),
        mean_club_quality=("club_quality", "mean"),
        max_club_quality=("club_quality", "max"),
        n_elite_club_players=("club_quality", lambda x: (x == 5).sum()),
        n_strong_club_players=("club_quality", lambda x: (x == 4).sum()),
    ).reset_index()

    # Experience index: total caps / squad size (already mean_caps)
    # Star power: max FIFA overall of XI? We don't have FIFA overall in official_squads,
    # but we have club_quality proxy.

    out = PROCESSED_DIR / "squad_aggregates.csv"
    save_csv(agg, out)
    save_checkpoint("s04_squad_aggregates", meta={"teams": len(agg)})
    logger.info(f"[s04] Done. {len(agg)} team aggregates written.")


if __name__ == "__main__":
    compute_squad_aggregates()
