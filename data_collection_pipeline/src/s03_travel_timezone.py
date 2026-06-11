"""
Stage 03 — Compute travel distances, timezone shifts, and altitude adaptation
from existing venue geocodes + team capital cities.
Outputs: processed/travel_features.csv
"""
import math
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import timezone, timedelta
import pytz

# allow import from pipeline src
import sys
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, save_csv, get_capital_coords,
    PROCESSED_DIR, should_run, save_checkpoint,
)

VENUES_QUERY = """
SELECT venue_id, name, city, country, lat, lng, altitude_m
FROM venues
"""

TEAMS_QUERY = """
SELECT DISTINCT team FROM wc2026_qualified_teams
WHERE team != 'To be announced'
"""


def haversine(lat1, lon1, lat2, lon2):
    """Distance in km."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def timezone_offset_hours(lat, lng):
    """Return approximate UTC offset using pytz timezones (best-effort)."""
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lng, lat=lat)
        if tz_name:
            tz = pytz.timezone(tz_name)
            now = pd.Timestamp.now(tz)
            offset = now.utcoffset()
            return offset.total_seconds() / 3600.0 if offset else 0.0
    except Exception:
        pass
    # Rough longitude-based fallback
    return round(lng / 15.0)


def compute_travel_features():
    if not should_run("s03_travel_timezone"):
        logger.info("[s03] Already done. Skipping.")
        return

    logger.info("[s03] Computing travel / timezone / altitude features...")
    conn = db_conn()
    venues = pd.read_sql_query(VENUES_QUERY, conn)
    teams = pd.read_sql_query(TEAMS_QUERY, conn)
    conn.close()

    # Fix Guadalajara manually (failed geocode in original pipeline)
    venues.loc[venues["name"] == "Guadalajara Stadium", "lat"] = 20.6767
    venues.loc[venues["name"] == "Guadalajara Stadium", "lng"] = -103.3475
    venues.loc[venues["name"] == "Guadalajara Stadium", "altitude_m"] = 1566.0
    venues.loc[venues["name"] == "Guadalajara Stadium", "city"] = "Guadalajara"
    venues.loc[venues["name"] == "Guadalajara Stadium", "country"] = "Mexico"

    # Pre-compute venue timezone offsets
    venue_tz = {}
    for _, v in venues.iterrows():
        if pd.notna(v["lat"]) and pd.notna(v["lng"]):
            try:
                venue_tz[v["venue_id"]] = timezone_offset_hours(v["lat"], v["lng"])
            except Exception:
                venue_tz[v["venue_id"]] = 0.0
        else:
            venue_tz[v["venue_id"]] = 0.0

    rows = []
    for _, t in teams.iterrows():
        team = t["team"]
        cap = get_capital_coords(team)
        if not cap:
            logger.warning(f"No capital coords for {team}; skipping.")
            continue
        cap_lat, cap_lng = cap
        cap_alt = 0.0  # sea-level default
        cap_tz = timezone_offset_hours(cap_lat, cap_lng)

        for _, v in venues.iterrows():
            vid = v["venue_id"]
            v_lat, v_lng = v["lat"], v["lng"]
            v_alt = v["altitude_m"] if pd.notna(v["altitude_m"]) else 0.0
            v_tz = venue_tz.get(vid, 0.0)

            if pd.isna(v_lat) or pd.isna(v_lng):
                continue

            dist_km = haversine(cap_lat, cap_lng, v_lat, v_lng)
            tz_delta = v_tz - cap_tz
            tdf = math.log(dist_km + 1) * abs(tz_delta)
            altitude_delta = v_alt - cap_alt
            # Eastward travel penalty factor (>0 = eastward, harder)
            eastward_penalty = max(0, tz_delta)

            rows.append({
                "team": team,
                "venue_id": vid,
                "venue_name": v["name"],
                "distance_km": round(dist_km, 2),
                "timezone_delta": round(tz_delta, 1),
                "travel_fatigue_index": round(tdf, 3),
                "altitude_delta_m": round(altitude_delta, 1),
                "eastward_penalty": round(eastward_penalty, 1),
            })

    df = pd.DataFrame(rows)
    out = PROCESSED_DIR / "travel_features.csv"
    save_csv(df, out)
    save_checkpoint("s03_travel_timezone", meta={"rows": len(df)})
    logger.info(f"[s03] Done. {len(df)} team-venue rows written.")


if __name__ == "__main__":
    compute_travel_features()
