"""
Stage 08 — Continental tournament form (most recent cycle per confederation).

Sources (Wikipedia):
  - 2024 Copa America      (CONMEBOL)
  - UEFA Euro 2024         (UEFA)
  - 2023 AFCON             (CAF)
  - 2023 AFC Asian Cup     (AFC)
  - 2023 CONCACAF Gold Cup (CONCACAF)

For each team that appeared, we extract its group-stage record and a coarse
stage reached:
  - cont_pld / w / d / l / gf / ga / pts   group-stage totals
  - cont_ppg                               points per game
  - reached_stage                          Group stage | Knockout | Final | Winner
  - reached_ordinal                        1 | 3 | 4 | 5  (for modelling)

QF/SF granularity is intentionally left as a future enrichment; the reliable,
high-value signals are group performance + advancement + finalist/winner status.

Outputs: processed/continental_form.csv
"""
import io
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, PROCESSED_DIR, get_session,
    should_run, save_checkpoint, finalize_stage,
)

TOURNAMENTS = [
    ("2024 Copa America", "CONMEBOL", "https://en.wikipedia.org/wiki/2024_Copa_Am%C3%A9rica"),
    ("Euro 2024", "UEFA", "https://en.wikipedia.org/wiki/UEFA_Euro_2024"),
    ("AFCON 2023", "CAF", "https://en.wikipedia.org/wiki/2023_Africa_Cup_of_Nations"),
    ("AFC Asian Cup 2023", "AFC", "https://en.wikipedia.org/wiki/2023_AFC_Asian_Cup"),
    ("Gold Cup 2023", "CONCACAF", "https://en.wikipedia.org/wiki/2023_CONCACAF_Gold_Cup"),
]

_ALIASES = {
    "caboverde": "capeverde", "congodr": "drcongo", "czechia": "czechrepublic",
    "cotedivoire": "ivorycoast", "iriran": "iran", "korearepublic": "southkorea",
    "koreadpr": "northkorea", "turkiye": "turkey", "usa": "unitedstates",
}


def _norm(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\b(vte|v t e)\b", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    return _ALIASES.get(s, s)


def _clean_team(name: str) -> str:
    s = re.sub(r"\[[^\]]*\]", "", str(name))
    s = re.sub(r"\s*\([A-Z]\)\s*$", "", s).strip()
    return s


def _qualified_teams() -> set:
    try:
        conn = db_conn()
        rows = pd.read_sql_query(
            "SELECT DISTINCT team FROM wc2026_qualified_teams "
            "WHERE team != 'To be announced'", conn,
        )["team"].tolist()
        conn.close()
        return {_norm(t) for t in rows}
    except Exception as e:
        logger.warning(f"[s08] Could not load qualified teams: {e}")
        return set()


def _is_group_table(df: pd.DataFrame) -> bool:
    cols = " ".join(str(c).lower() for c in df.columns)
    return all(k in cols for k in ("pld", "gf", "ga")) and "team" in cols


def _col(df, *prefixes):
    for c in df.columns:
        lc = str(c).lower()
        for p in prefixes:
            if lc == p or lc.startswith(p):
                return c
    return None


def _parse_group_stats(tables):
    """Return {normalized_team: {stats, display_name}} from group standings."""
    out = {}
    for df in tables:
        if not _is_group_table(df):
            continue
        c_team = _col(df, "team")
        c_pld, c_w, c_d, c_l = _col(df, "pld"), _col(df, "w"), _col(df, "d"), _col(df, "l")
        c_gf, c_ga, c_pts = _col(df, "gf"), _col(df, "ga"), _col(df, "pts")
        c_qual = _col(df, "qualification", "final result")
        if not (c_team and c_pld):
            continue
        for _, r in df.iterrows():
            name = _clean_team(r.get(c_team))
            key = _norm(name)
            if not key or name.lower() in ("team", "nan"):
                continue
            pld = pd.to_numeric(r.get(c_pld), errors="coerce")
            if pd.isna(pld) or pld == 0:
                continue
            def num(c):
                return pd.to_numeric(r.get(c), errors="coerce") if c else None
            qual_txt = str(r.get(c_qual)) if c_qual else ""
            rec = {
                "display": name,
                "cont_pld": int(pld),
                "cont_w": num(c_w), "cont_d": num(c_d), "cont_l": num(c_l),
                "cont_gf": num(c_gf), "cont_ga": num(c_ga), "cont_pts": num(c_pts),
                "advanced": bool(re.search(r"advance|knockout|round of|quarter|stage\b(?!.*group)", qual_txt, re.I))
                            and "group stage" not in qual_txt.lower(),
            }
            # Keep the row with the most games if a team appears twice.
            if key not in out or rec["cont_pld"] > out[key]["cont_pld"]:
                out[key] = rec
    return out


def _infobox_winner_runnerup(html):
    soup = BeautifulSoup(html, "lxml")
    info = soup.find("table", {"class": re.compile(r"infobox")})
    winner = runner = None
    if not info:
        return winner, runner
    for tr in info.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        h = th.get_text(strip=True).lower()
        if "champion" in h and winner is None:
            winner = _norm(td.get_text(strip=True))
        elif ("runner" in h) and runner is None:
            runner = _norm(td.get_text(strip=True))
    return winner, runner


def scrape_tournament(name, confed, url):
    logger.info(f"[s08] {name} ...")
    s = get_session()
    try:
        html = s.get(url, timeout=25).text
        tables = pd.read_html(io.StringIO(html))
    except Exception as e:
        logger.warning(f"[s08] Failed {name}: {e}")
        return []
    stats = _parse_group_stats(tables)
    winner, runner = _infobox_winner_runnerup(html)
    records = []
    for key, rec in stats.items():
        stage, ordinal = "Group stage", 1
        if rec["advanced"]:
            stage, ordinal = "Knockout", 3
        if runner and key == runner:
            stage, ordinal = "Final", 4
        if winner and key == winner:
            stage, ordinal = "Winner", 5
        pts = rec["cont_pts"]
        records.append({
            "team": rec["display"],
            "tournament": name,
            "confederation": confed,
            "cont_pld": rec["cont_pld"],
            "cont_w": rec["cont_w"], "cont_d": rec["cont_d"], "cont_l": rec["cont_l"],
            "cont_gf": rec["cont_gf"], "cont_ga": rec["cont_ga"], "cont_pts": pts,
            "cont_ppg": round(pts / rec["cont_pld"], 3) if pd.notna(pts) else None,
            "reached_stage": stage,
            "reached_ordinal": ordinal,
        })
    logger.info(f"[s08] {name}: {len(records)} teams (winner={winner}, runner={runner}).")
    return records


def collect_continental_form():
    if not should_run("s08_continental_form"):
        logger.info("[s08] Already done. Skipping.")
        return

    logger.info("[s08] Collecting continental tournament form...")
    all_records = []
    for name, confed, url in TOURNAMENTS:
        all_records.extend(scrape_tournament(name, confed, url))

    df = pd.DataFrame(all_records)
    if df.empty:
        save_checkpoint("s08_continental_form", status="failed", meta={"reason": "no_data"})
        return

    qualified = _qualified_teams()
    df["is_wc2026"] = df["team"].map(lambda t: _norm(t) in qualified)
    df = df.sort_values(["is_wc2026", "reached_ordinal", "cont_ppg"],
                        ascending=[False, False, False])

    n_wc = int(df["is_wc2026"].sum())
    out = PROCESSED_DIR / "continental_form.csv"
    ok = finalize_stage(
        "s08_continental_form", df, out,
        min_rows=40,
        required_cols=["team", "tournament", "cont_pld", "cont_ppg", "reached_stage"],
        non_null_cols=["cont_pld"],
        extra_meta={"tournaments": len(TOURNAMENTS), "wc2026_teams_matched": n_wc},
    )
    if ok:
        logger.info(f"[s08] {len(df)} team-records; {n_wc} are WC2026 finalists.")


if __name__ == "__main__":
    collect_continental_form()
