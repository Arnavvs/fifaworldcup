"""
Stage 07 — Scrape FIFA World Cup 2026 qualification records from Wikipedia.

The main qualification page lists, per confederation, abbreviated standings
tables with columns: Pos | Team | Pld | Pts. (Full W/D/L/GF/GA tables live on
the six per-confederation sub-pages and are left as a future enrichment.)

For each team we capture its primary qualification group (the row with the
most games played, i.e. its deepest/final round) and derive:
  - qual_pos        finishing position in that group
  - qual_pld        games played
  - qual_pts        points
  - qual_ppg        points per game (strength proxy)
  - is_wc2026       whether the team is one of the 48 qualified finalists

Outputs: processed/qualification_strength.csv
"""
import io
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, PROCESSED_DIR, get_session,
    should_run, save_checkpoint, finalize_stage,
)

QUAL_PAGE = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_qualification"


# DB (FIFA-style) names vs Wikipedia common names -> shared canonical token.
_ALIASES = {
    "caboverde": "capeverde",
    "congodr": "drcongo",
    "czechia": "czechrepublic",
    "cotedivoire": "ivorycoast",
    "iriran": "iran",
    "korearepublic": "southkorea",
    "koreadpr": "northkorea",
    "turkiye": "turkey",
    "usa": "unitedstates",
}


def _norm(name: str) -> str:
    """Normalise a team name for matching (strip accents, markers, lowercase)."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"\[[^\]]*\]", "", s)          # footnotes [a], [1]
    s = re.sub(r"\([^)]*\)", "", s)           # (H), (R), (C)
    s = re.sub(r"\b(vte|v t e)\b", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    return _ALIASES.get(s, s)


def _clean_team(name: str) -> str:
    s = re.sub(r"\[[^\]]*\]", "", str(name))
    s = re.sub(r"\s*\((?:H|R|C|A|E|O|Q)\)\s*$", "", s).strip()
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
        logger.warning(f"[s07] Could not load qualified teams: {e}")
        return set()


def _is_standings(df: pd.DataFrame) -> bool:
    cols = " ".join(str(c).lower() for c in df.columns)
    return ("pld" in cols) and ("team" in cols) and ("pts" in cols or "pos" in cols)


def _extract_rows(df: pd.DataFrame):
    # Map the flattened wikitable columns to canonical names.
    colmap = {}
    for c in df.columns:
        lc = str(c).lower()
        if lc.startswith("pos"):
            colmap[c] = "qual_pos"
        elif lc.startswith("team"):
            colmap[c] = "team"
        elif lc == "pld":
            colmap[c] = "qual_pld"
        elif lc == "pts":
            colmap[c] = "qual_pts"
    df = df.rename(columns=colmap)
    if "team" not in df.columns or "qual_pld" not in df.columns:
        return []
    out = []
    for _, r in df.iterrows():
        team = _clean_team(r.get("team"))
        if not team or team.lower() in ("team", "nan"):
            continue
        pld = pd.to_numeric(r.get("qual_pld"), errors="coerce")
        pts = pd.to_numeric(r.get("qual_pts"), errors="coerce")
        pos = pd.to_numeric(r.get("qual_pos"), errors="coerce")
        if pd.isna(pld) or pld == 0:
            continue
        out.append({
            "team": team,
            "qual_pos": None if pd.isna(pos) else int(pos),
            "qual_pld": int(pld),
            "qual_pts": None if pd.isna(pts) else int(pts),
        })
    return out


def scrape_qualification_summary():
    if not should_run("s07_qualification_strength"):
        logger.info("[s07] Already done. Skipping.")
        return

    logger.info("[s07] Scraping qualification summary from Wikipedia...")
    s = get_session()
    try:
        r = s.get(QUAL_PAGE, timeout=25)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[s07] Failed to load qualification page: {e}")
        save_checkpoint("s07_qualification_strength", status="failed",
                        meta={"reason": str(e)})
        return

    try:
        tables = pd.read_html(io.StringIO(r.text))
    except Exception as e:
        logger.error(f"[s07] read_html failed: {e}")
        save_checkpoint("s07_qualification_strength", status="failed",
                        meta={"reason": f"read_html: {e}"})
        return

    records = []
    for t in tables:
        if _is_standings(t):
            records.extend(_extract_rows(t))

    df = pd.DataFrame(records)
    if df.empty:
        logger.error("[s07] No standings rows parsed.")
        save_checkpoint("s07_qualification_strength", status="failed",
                        meta={"reason": "no_rows"})
        return

    # Per team keep the row with the most games (its primary/final round).
    df["_n"] = df["team"].map(_norm)
    df = df.sort_values("qual_pld", ascending=False).groupby("_n", as_index=False).first()
    df["qual_ppg"] = (df["qual_pts"] / df["qual_pld"]).round(3)

    qualified = _qualified_teams()
    df["is_wc2026"] = df["_n"].isin(qualified)
    df = df.drop(columns=["_n"]).sort_values(
        ["is_wc2026", "qual_ppg"], ascending=[False, False]
    )

    n_wc = int(df["is_wc2026"].sum())
    out = PROCESSED_DIR / "qualification_strength.csv"
    ok = finalize_stage(
        "s07_qualification_strength", df, out,
        min_rows=40,
        required_cols=["team", "qual_pld", "qual_pts", "qual_ppg"],
        non_null_cols=["qual_pld", "qual_pts"],
        extra_meta={"wc2026_teams_matched": n_wc},
    )
    if ok:
        logger.info(f"[s07] {len(df)} teams parsed; {n_wc} matched to WC2026 finalists.")


if __name__ == "__main__":
    scrape_qualification_summary()
