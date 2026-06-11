"""
Stage 06 — Scrape national team manager tenure from Wikipedia.
For each WC 2026 qualified team, fetch manager name + appointment date
from the team's Wikipedia page infobox or national team page.
Outputs: processed/manager_tenure.csv
"""
import sys
import re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, save_csv, PROCESSED_DIR, get_session,
    should_run, save_checkpoint, finalize_stage,
)

TEAM_QUERY = """
SELECT DISTINCT team FROM wc2026_qualified_teams WHERE team != 'To be announced'
"""

TOURNAMENT_DATE = pd.Timestamp("2026-06-11")  # WC2026 opening match


def _clean_manager(name: str) -> str:
    """Strip footnotes, parentheticals and trailing role text from a name."""
    s = re.sub(r"\[[^\]]*\]", "", str(name))
    s = re.sub(r"\([^)]*\)", "", s)
    return s.strip(" ,;-")


def scrape_appointment(manager: str):
    """
    From the manager's own Wikipedia page, read the 'Teams managed' infobox and
    return the start year of the current (open-ended) role, e.g. '2018–'.
    Returns (year:int|None, team:str|None).
    """
    if not manager:
        return None, None
    slug = _clean_manager(manager).replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{slug}"
    s = get_session()
    try:
        r = s.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        info = soup.find("table", {"class": re.compile(r"infobox")})
        if not info:
            return None, None
        best = None
        for tr in info.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            m = re.match(r"^(\d{4})\s*[–—-]\s*$", tds[0].get_text(strip=True))
            if m:
                best = (int(m.group(1)), tds[1].get_text(strip=True))
        return best if best else (None, None)
    except Exception as e:
        logger.debug(f"[s06] appointment lookup failed for {manager}: {e}")
        return None, None

def scrape_manager_for_team(team: str):
    """
    Try the national team Wikipedia page, e.g.:
    https://en.wikipedia.org/wiki/Argentina_national_football_team
    Look for infobox 'Head coach' or 'Manager' row.
    """
    slug = team.replace(" ", "_")
    # Some exceptions
    slug_map = {
        "USA": "United_States_men%27s_national_soccer_team",
        "Korea Republic": "South_Korea_national_football_team",
        "Korea DPR": "North_Korea_national_football_team",
        "Bosnia and Herzegovina": "Bosnia_and_Herzegovina_national_football_team",
        "Czechia": "Czech_Republic_national_football_team",
        "Czech Republic": "Czech_Republic_national_football_team",
        "Côte d'Ivoire": "Ivory_Coast_national_football_team",
        "Cabo Verde": "Cape_Verde_national_football_team",
        "Congo DR": "DR_Congo_national_football_team",
        "IR Iran": "Iran_national_football_team",
    }
    if team in slug_map:
        slug = slug_map[team]
    else:
        slug = f"{slug}_national_football_team"

    url = f"https://en.wikipedia.org/wiki/{slug}"
    s = get_session()
    try:
        r = s.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        infobox = soup.find("table", {"class": re.compile(r"infobox")})
        if not infobox:
            return None, None, None
        rows = infobox.find_all("tr")
        manager_name = None
        appointment = None
        for tr in rows:
            th = tr.find("th")
            if not th:
                continue
            header_text = th.get_text(strip=True).lower()
            if any(k in header_text for k in ["head coach", "manager", "coach"]):
                td = tr.find("td")
                if td:
                    manager_name = td.get_text(strip=True)
                    # Try to find appointment date in same cell or next row
                    # Heuristic: look for a date pattern
                    m = re.search(r"\((\d{1,2}\s+[A-Za-z]+\s+20\d{2}|20\d{2}-\d{2}-\d{2})\)", manager_name)
                    if m:
                        appointment = m.group(1)
                    else:
                        # Try next row
                        next_tr = tr.find_next_sibling("tr")
                        if next_tr:
                            ntxt = next_tr.get_text(strip=True)
                            m2 = re.search(r"(20\d{2}[–-]\d{2}[–-]\d{2}|\d{1,2}\s+[A-Za-z]+\s+20\d{2})", ntxt)
                            if m2:
                                appointment = m2.group(1)
                break
        # If no manager found, try broader search
        if not manager_name:
            # Look for 'Head coach' heading in page
            h2s = soup.find_all("h2")
            for h2 in h2s:
                if "coach" in h2.get_text(strip=True).lower() or "manager" in h2.get_text(strip=True).lower():
                    # next table might have personnel
                    nxt = h2.find_next("table")
                    if nxt:
                        txt = nxt.get_text()
                        m = re.search(r"Head coach\s*(.+?)(\n|\r|$)", txt)
                        if m:
                            manager_name = m.group(1).strip()
                    break
        return team, manager_name, appointment
    except Exception as e:
        logger.warning(f"[s06] Failed for {team}: {e}")
        return team, None, None


def collect_managers():
    if not should_run("s06_manager_tenure"):
        logger.info("[s06] Already done. Skipping.")
        return

    logger.info("[s06] Scraping manager tenure from Wikipedia...")
    conn = db_conn()
    teams = pd.read_sql_query(TEAM_QUERY, conn)["team"].tolist()
    conn.close()

    results = []
    for team in teams:
        if pd.isna(team) or str(team).strip() in ("", "nan"):
            continue
        logger.info(f"[s06] Fetching manager for {team}...")
        t, mgr, _ = scrape_manager_for_team(team)
        mgr = _clean_manager(mgr) if mgr else None
        appt_year, appt_team = scrape_appointment(mgr) if mgr else (None, None)
        tenure_years = None
        if appt_year:
            tenure_years = round((TOURNAMENT_DATE - pd.Timestamp(year=appt_year, month=1, day=1)).days / 365.25, 1)
        results.append({
            "team": t,
            "manager": mgr,
            "appointment_year": appt_year,
            "appointment_team": appt_team,
            "tenure_years_at_wc": tenure_years,
        })

    df = pd.DataFrame(results)
    n_mgr = int(df["manager"].notna().sum())
    n_appt = int(df["appointment_year"].notna().sum())
    logger.info(f"[s06] Managers: {n_mgr}/{len(df)}; appointment dates: {n_appt}/{len(df)}.")

    out = PROCESSED_DIR / "manager_tenure.csv"
    # Allow up to ~40% missing appointment years (some federations lack clean pages).
    finalize_stage(
        "s06_manager_tenure", df, out,
        min_rows=40,
        required_cols=["team", "manager", "appointment_year", "tenure_years_at_wc"],
        non_null_cols=["manager", "appointment_year"],
        max_null_frac=0.4,
        extra_meta={"managers_found": n_mgr, "appointments_found": n_appt},
    )


if __name__ == "__main__":
    collect_managers()
