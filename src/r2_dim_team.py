"""
PHASE 2 - Team normalization.

Collects every distinct team string across all tables, resolves aliases to a
single canonical name, assigns a stable team_id, fifa_code and continent, and
writes the `dim_team` table + research_ready_dataset/team_mapping.csv.
Also materialises `matches_norm` with home_team_id / away_team_id so downstream
joins use integer ids instead of fragile strings.
"""
from __future__ import annotations

import sqlite3
import unicodedata

import pandas as pd

from common import DB_PATH, ROOT

OUT = ROOT / "research_ready_dataset"
OUT.mkdir(exist_ok=True)

# raw string -> canonical name (only the ones that differ; identity otherwise)
ALIASES = {
    "United States": "USA", "US": "USA", "USMNT": "USA",
    "South Korea": "Korea Republic", "Korea, South": "Korea Republic", "Korea": "Korea Republic",
    "Iran": "IR Iran",
    "Turkey": "Türkiye", "Turkiye": "Türkiye",
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire", "Cote d'Ivoire": "Côte d'Ivoire",
    "Cape Verde": "Cabo Verde", "Cape Verde Islands": "Cabo Verde",
    "DR Congo": "Congo DR", "Democratic Republic of the Congo": "Congo DR",
    "Congo Kinshasa": "Congo DR", "Zaire": "Congo DR",
    "Curacao": "Curaçao",
    "China": "China PR", "China PR": "China PR",
    "North Korea": "Korea DPR",
    "Republic of Ireland": "Ireland", "Eire": "Ireland",
    "Bosnia": "Bosnia and Herzegovina", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "West Germany": "Germany", "East Germany": "Germany",
    "Soviet Union": "Russia", "USSR": "Russia", "CIS": "Russia",
    "Serbia and Montenegro": "Serbia", "Yugoslavia": "Serbia", "FR Yugoslavia": "Serbia",
    "Macedonia": "North Macedonia", "FYR Macedonia": "North Macedonia",
    "UAE": "United Arab Emirates",
}

# canonical name -> (fifa_code, continent)
META = {
    "Argentina": ("ARG", "South America"), "Brazil": ("BRA", "South America"),
    "Uruguay": ("URU", "South America"), "Colombia": ("COL", "South America"),
    "Ecuador": ("ECU", "South America"), "Peru": ("PER", "South America"),
    "Paraguay": ("PAR", "South America"), "Chile": ("CHI", "South America"),
    "Bolivia": ("BOL", "South America"), "Venezuela": ("VEN", "South America"),
    "France": ("FRA", "Europe"), "Spain": ("ESP", "Europe"), "England": ("ENG", "Europe"),
    "Germany": ("GER", "Europe"), "Portugal": ("POR", "Europe"), "Netherlands": ("NED", "Europe"),
    "Belgium": ("BEL", "Europe"), "Italy": ("ITA", "Europe"), "Croatia": ("CRO", "Europe"),
    "Switzerland": ("SUI", "Europe"), "Denmark": ("DEN", "Europe"), "Poland": ("POL", "Europe"),
    "Serbia": ("SRB", "Europe"), "Austria": ("AUT", "Europe"), "Ukraine": ("UKR", "Europe"),
    "Sweden": ("SWE", "Europe"), "Norway": ("NOR", "Europe"), "Scotland": ("SCO", "Europe"),
    "Wales": ("WAL", "Europe"), "Türkiye": ("TUR", "Europe"), "Czechia": ("CZE", "Europe"),
    "Hungary": ("HUN", "Europe"), "Greece": ("GRE", "Europe"), "Slovakia": ("SVK", "Europe"),
    "Slovenia": ("SVN", "Europe"), "Romania": ("ROU", "Europe"), "Ireland": ("IRL", "Europe"),
    "Russia": ("RUS", "Europe"), "Bosnia and Herzegovina": ("BIH", "Europe"),
    "North Macedonia": ("MKD", "Europe"), "Iceland": ("ISL", "Europe"), "Finland": ("FIN", "Europe"),
    "Mexico": ("MEX", "North America"), "USA": ("USA", "North America"),
    "Canada": ("CAN", "North America"), "Costa Rica": ("CRC", "North America"),
    "Panama": ("PAN", "North America"), "Honduras": ("HON", "North America"),
    "Jamaica": ("JAM", "North America"), "Haiti": ("HAI", "North America"),
    "Curaçao": ("CUW", "North America"),
    "Morocco": ("MAR", "Africa"), "Senegal": ("SEN", "Africa"), "Ghana": ("GHA", "Africa"),
    "Cameroon": ("CMR", "Africa"), "Nigeria": ("NGA", "Africa"), "Egypt": ("EGY", "Africa"),
    "Algeria": ("ALG", "Africa"), "Tunisia": ("TUN", "Africa"), "Côte d'Ivoire": ("CIV", "Africa"),
    "South Africa": ("RSA", "Africa"), "Cabo Verde": ("CPV", "Africa"), "Congo DR": ("COD", "Africa"),
    "Japan": ("JPN", "Asia"), "Korea Republic": ("KOR", "Asia"), "IR Iran": ("IRN", "Asia"),
    "Saudi Arabia": ("KSA", "Asia"), "Qatar": ("QAT", "Asia"), "Australia": ("AUS", "Asia"),
    "Iraq": ("IRQ", "Asia"), "Jordan": ("JOR", "Asia"), "Uzbekistan": ("UZB", "Asia"),
    "China PR": ("CHN", "Asia"), "Korea DPR": ("PRK", "Asia"), "United Arab Emirates": ("UAE", "Asia"),
    "New Zealand": ("NZL", "Oceania"),
}


def canon(name: str) -> str:
    name = str(name).strip()
    return ALIASES.get(name, name)


def collect_names(con) -> set[str]:
    names: set[str] = set()
    sources = [
        ("matches", ["home_team", "away_team"]),
        ("team_match_features", ["team", "opponent"]),
        ("elo_ratings", ["team"]), ("fifa_rankings", ["team"]),
        ("market_values", ["team"]), ("squads", ["team"]),
        ("wc2026_qualified_teams", ["team"]),
    ]
    for tbl, cols in sources:
        try:
            df = pd.read_sql(f'SELECT {",".join(cols)} FROM "{tbl}"', con)
            for c in cols:
                names |= set(df[c].dropna().astype(str))
        except Exception:
            pass
    return names


def main():
    con = sqlite3.connect(DB_PATH)
    raw_names = collect_names(con)

    # build raw -> canonical
    mapping = {raw: canon(raw) for raw in raw_names}
    canon_names = sorted(set(mapping.values()))

    # assign ids + meta
    dim_rows = []
    for i, cn in enumerate(canon_names, 1):
        code, cont = META.get(cn, (None, "Other"))
        aliases = sorted({raw for raw, c in mapping.items() if c == cn and raw != cn})
        dim_rows.append({
            "team_id": i, "canonical_name": cn,
            "aliases": "|".join(aliases) if aliases else "",
            "fifa_code": code, "continent": cont,
        })
    dim = pd.DataFrame(dim_rows)
    name_to_id = dict(zip(dim["canonical_name"], dim["team_id"]))

    # team_mapping.csv : every raw string -> canonical + id
    tm = pd.DataFrame({"raw_name": sorted(raw_names)})
    tm["canonical_name"] = tm["raw_name"].map(mapping)
    tm["team_id"] = tm["canonical_name"].map(name_to_id)
    tm.to_csv(OUT / "team_mapping.csv", index=False, encoding="utf-8")
    dim.to_csv(OUT / "dim_team.csv", index=False, encoding="utf-8")

    # write dim_team to DB
    dim.to_sql("dim_team", con, if_exists="replace", index=False)

    # materialise matches_norm with integer team ids
    m = pd.read_sql('SELECT * FROM matches', con)
    raw2id = dict(zip(tm["raw_name"], tm["team_id"]))
    m["home_team_id"] = m["home_team"].map(raw2id)
    m["away_team_id"] = m["away_team"].map(raw2id)
    m.to_sql("matches_norm", con, if_exists="replace", index=False)

    con.commit()
    n_resolved = (tm["team_id"].notna()).mean() * 100
    n_collapsed = len(raw_names) - len(canon_names)
    con.close()

    print(f"dim_team: {len(dim)} canonical teams (from {len(raw_names)} raw strings; "
          f"collapsed {n_collapsed})")
    print(f"team_mapping.csv: {len(tm)} raw->id rows, {n_resolved:.1f}% resolved to an id")
    print(f"continents: {dim['continent'].value_counts().to_dict()}")
    print(f"with fifa_code: {dim['fifa_code'].notna().sum()}")


if __name__ == "__main__":
    main()
