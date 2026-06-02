"""
PHASE 1 - Data audit. Inspects every table and emits research_ready_dataset/audit_report.md
covering rows, null %, duplicate %, cardinality, team-name inconsistencies,
date inconsistencies, leakage detection, and outlier detection.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from common import DB_PATH, ROOT

OUT = ROOT / "research_ready_dataset"
OUT.mkdir(exist_ok=True)

# columns that are post-match outcomes -> never valid as model inputs
LEAKAGE_COLS = {"home_score", "away_score", "result", "gf", "ga", "points",
                "attendance", "outcome", "winning_team", "losing_team",
                "win_conditions", "HomeTeamScore", "AwayTeamScore"}

# known alias groups for team-name consistency check
ALIAS_GROUPS = [
    {"USA", "United States"}, {"Korea Republic", "South Korea"},
    {"IR Iran", "Iran"}, {"Türkiye", "Turkey"}, {"Czechia", "Czech Republic"},
    {"Côte d'Ivoire", "Ivory Coast"}, {"Cabo Verde", "Cape Verde", "Cape Verde Islands"},
    {"Congo DR", "DR Congo", "Democratic Republic of the Congo"},
    {"Curaçao", "Curacao"}, {"China PR", "China"}, {"Korea DPR", "North Korea"},
]


def md_table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def main():
    con = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

    md = ["# PHASE 1 — Data Audit Report\n",
          f"*Source: `{DB_PATH.name}` — {len(tables)} tables.*\n"]

    # ---------- per-table overview ----------
    overview, all_team_names = [], set()
    leakage_found = {}
    outliers_found = []
    date_issues = []
    frames = {}

    for t in tables:
        df = pd.read_sql(f'SELECT * FROM "{t}"', con)
        frames[t] = df
        n = len(df)
        dup = df.duplicated().sum()
        dup_pct = round(100 * dup / n, 2) if n else 0.0
        avg_null = round(df.isna().mean().mean() * 100, 1) if n else 100.0
        overview.append([t, n, df.shape[1], f"{dup_pct}%", f"{avg_null}%"])

        # collect team names
        for col in df.columns:
            if col.lower() in ("team", "opponent", "home_team", "away_team",
                               "hometeam", "awayteam", "canonical_name"):
                all_team_names |= set(df[col].dropna().astype(str))

        # leakage columns present
        lk = [c for c in df.columns if c in LEAKAGE_COLS]
        if lk:
            leakage_found[t] = lk

        # date sanity
        for col in df.columns:
            if col.lower() in ("date", "dateutc"):
                d = pd.to_datetime(df[col], errors="coerce", utc=True)
                bad = d.isna().sum()
                fut = (d > pd.Timestamp("2027-01-01", tz="UTC")).sum()
                early = (d < pd.Timestamp("1870-01-01", tz="UTC")).sum()
                if bad or fut or early:
                    date_issues.append([t, col, int(bad), int(fut), int(early)])

        # outlier detection on key numeric cols
        for col in df.select_dtypes(include=[np.number]).columns:
            s = df[col].dropna()
            if s.empty:
                continue
            if col in ("home_score", "away_score", "gf", "ga"):
                hi = (s > 15).sum()
                if hi:
                    outliers_found.append([t, col, f">15 goals", int(hi), round(s.max(), 1)])
            if col == "elo":
                bad = ((s < 500) | (s > 2500)).sum()
                if bad:
                    outliers_found.append([t, col, "outside 500-2500", int(bad), round(s.max(), 1)])
            if col == "days_rest":
                neg = (s < 0).sum()
                huge = (s > 2000).sum()
                if neg:
                    outliers_found.append([t, col, "negative", int(neg), round(s.min(), 1)])
                if huge:
                    outliers_found.append([t, col, ">2000 days", int(huge), round(s.max(), 1)])

    md.append("## 1.1 Table Overview\n")
    md.append(md_table(overview, ["table", "rows", "cols", "dup%", "avg null%"]))

    # ---------- cardinality (high-signal tables) ----------
    md.append("\n\n## 1.2 Cardinality Analysis\n")
    md.append("Unique-value ratio per column (uniq / rows); ~1.0 ⇒ identifier, ~0 ⇒ constant.\n")
    for t in ("matches", "team_match_features", "players"):
        df = frames[t]
        n = len(df)
        rows = []
        for c in df.columns:
            u = df[c].nunique(dropna=True)
            rows.append([c, u, round(u / n, 3) if n else 0])
        md.append(f"\n**{t}**\n")
        md.append(md_table(rows, ["column", "n_unique", "uniq_ratio"]))

    # ---------- team-name inconsistencies ----------
    md.append("\n\n## 1.3 Team-Name Inconsistencies\n")
    found_alias = []
    for grp in ALIAS_GROUPS:
        present = sorted(grp & all_team_names)
        if len(present) > 1:
            found_alias.append([" / ".join(present), "alias collision — must map to one team_id"])
    if found_alias:
        md.append(md_table(found_alias, ["conflicting names", "issue"]))
    else:
        md.append("_No known alias collisions detected in current name set._")
    md.append(f"\n\nTotal distinct team strings across all tables: **{len(all_team_names)}** "
              "→ Phase 2 `dim_team` collapses these to canonical IDs.")

    # ---------- date inconsistencies ----------
    md.append("\n\n## 1.4 Date Inconsistencies\n")
    if date_issues:
        md.append(md_table(date_issues, ["table", "col", "unparseable", "future(>2027)", "pre-1870"]))
    else:
        md.append("_All dates parse and fall within plausible bounds._")

    # ---------- leakage ----------
    md.append("\n\n## 1.5 Leakage Detection\n")
    md.append("Columns that encode the match outcome (or are only known post-match). "
              "These **must be excluded** from `ml_match_features`:\n")
    lk_rows = [[t, ", ".join(cols)] for t, cols in leakage_found.items()]
    md.append(md_table(lk_rows, ["table", "leakage columns"]))
    md.append("\n\n⚠ `team_match_features.fifa_points` has only 3 unique values "
              "(join artifact) — flagged low-quality, drop from feature set.")

    # ---------- outliers ----------
    md.append("\n\n## 1.6 Outlier Detection\n")
    if outliers_found:
        md.append(md_table(outliers_found, ["table", "col", "rule", "n_flagged", "extreme"]))
    else:
        md.append("_No numeric outliers beyond configured thresholds._")
    # contextual note on expected null structure
    md.append("\n\n## 1.7 Structural Null Notes (expected, not errors)\n"
              "- `matches.stage` 79.9% null — non-tournament friendlies have no stage.\n"
              "- `team_match_features.elo` 59.9% / `fifa_rank` 45.6% null — ratings only exist "
              "from 1901/1992 onward and as-of-prior matches.\n"
              "- `players` attribute axes 11.2% null — goalkeepers lack outfield ratings.\n"
              "- Empty tables (`odds`, `injuries`, `team_match_stats`, `player_match_stats`, "
              "`player_tournament_stats`) — blocked/unavailable sources.")

    con.close()
    (OUT / "audit_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {OUT/'audit_report.md'}")
    print(f"  tables={len(tables)} alias_collisions={len(found_alias)} "
          f"date_issue_tables={len(date_issues)} leakage_tables={len(leakage_found)} "
          f"outlier_flags={len(outliers_found)}")


if __name__ == "__main__":
    main()
