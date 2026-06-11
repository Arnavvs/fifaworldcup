"""
Stage 02 — Fetch weather forecasts for WC 2026 venues via Open-Meteo (free, no API key).
Uses venue lat/lng from existing DB. Fetches daily max temp, humidity, precipitation, wind.
Outputs: processed/weather_forecasts.csv
Note: Open-Meteo provides forecasts up to ~16 days. For dates beyond that,
      we fetch the *climatological* historical averages (open-meteo climate API)
      which is the best free proxy for June/July weather in 2026.
"""
import sys
from pathlib import Path
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    logger, db_conn, save_csv, PROCESSED_DIR, get_session,
    should_run, save_checkpoint, finalize_stage,
)

OPENMETEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_CLIMATE = "https://climate-api.open-meteo.com/v1/climate"

# WC 2026 date ranges (approximate)
# For forecast API, we can only get ~14 days ahead. Since the tournament
# is in the future, we will use the ENSEMBLE climate API which returns
# historical daily normals for a given date range.


def fetch_climate_normals(lat, lng, start_date="2026-06-11", end_date="2026-07-19"):
    """
    Uses Open-Meteo Climate API to get daily normals (temperature, humidity, precip, wind)
    for the tournament window. Returns a list of dicts per day.
    """
    params = {
        "latitude": lat,
        "longitude": lng,
        "start_date": start_date,
        "end_date": end_date,
        "models": "MRI_AGCM3_2_S",  # valid Open-Meteo climate downscaled model
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_mean",
            "precipitation_sum",
            "wind_speed_10m_max",
        ]),
        "timezone": "auto",
    }
    s = get_session()
    try:
        r = s.get(OPENMETEO_CLIMATE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return []
        rows = []
        for i, d in enumerate(dates):
            rows.append({
                "date": d,
                "temp_max_c": daily.get("temperature_2m_max", [None] * len(dates))[i],
                "temp_min_c": daily.get("temperature_2m_min", [None] * len(dates))[i],
                "rel_humidity_pct": daily.get("relative_humidity_2m_mean", [None] * len(dates))[i],
                "precip_mm": daily.get("precipitation_sum", [None] * len(dates))[i],
                "wind_max_kmh": daily.get("wind_speed_10m_max", [None] * len(dates))[i],
            })
        return rows
    except Exception as e:
        logger.error(f"Open-Meteo climate fetch failed for ({lat},{lng}): {e}")
        return []


def compute_wbgt_approx(temp_c, humidity_pct):
    """Very approximate WBGT (Wet Bulb Globe Temperature) using simple formula."""
    if temp_c is None or humidity_pct is None:
        return None
    # WBGT ≈ 0.567*T + 0.393*e + 3.94  (simplified)
    # where e = vapor pressure (hPa)
    # We'll use a much simpler proxy: heat index style
    return round(0.7 * temp_c + 0.3 * (humidity_pct / 100.0) * temp_c, 2)


def fetch_weather():
    if not should_run("s02_weather"):
        logger.info("[s02] Already done. Skipping.")
        return

    logger.info("[s02] Fetching climate normals for WC 2026 venues from Open-Meteo...")
    conn = db_conn()
    venues = pd.read_sql_query("SELECT venue_id, name, city, lat, lng, altitude_m FROM venues", conn)
    conn.close()

    # Fix Guadalajara
    venues.loc[venues["name"] == "Guadalajara Stadium", "lat"] = 20.6767
    venues.loc[venues["name"] == "Guadalajara Stadium", "lng"] = -103.3475
    venues.loc[venues["name"] == "Guadalajara Stadium", "altitude_m"] = 1566.0
    venues.loc[venues["name"] == "Guadalajara Stadium", "city"] = "Guadalajara"

    all_rows = []
    for _, v in venues.iterrows():
        if pd.isna(v["lat"]) or pd.isna(v["lng"]):
            continue
        logger.info(f"[s02] Fetching climate for {v['name']} ({v['lat']:.3f}, {v['lng']:.3f})...")
        rows = fetch_climate_normals(v["lat"], v["lng"])
        for r in rows:
            r["venue_id"] = v["venue_id"]
            r["venue_name"] = v["name"]
            r["venue_city"] = v["city"]
            r["venue_altitude_m"] = v["altitude_m"]
            r["wbgt_approx"] = compute_wbgt_approx(r["temp_max_c"], r["rel_humidity_pct"])
            # Heat stress flag
            r["heat_stress_flag"] = 1 if (r["wbgt_approx"] and r["wbgt_approx"] > 28) else 0
            all_rows.append(r)

    if not all_rows:
        logger.error("[s02] No weather data fetched.")
        save_checkpoint("s02_weather", status="failed", meta={"reason": "no_data"})
        return

    df = pd.DataFrame(all_rows)
    # Reorder columns
    cols = ["venue_id", "venue_name", "venue_city", "date", "temp_max_c", "temp_min_c",
            "rel_humidity_pct", "precip_mm", "wind_max_kmh", "wbgt_approx", "heat_stress_flag", "venue_altitude_m"]
    df = df[[c for c in cols if c in df.columns]]

    out = PROCESSED_DIR / "weather_forecasts.csv"
    ok = finalize_stage(
        "s02_weather", df, out,
        min_rows=200,                       # ~16 venues x ~39 days
        required_cols=["venue_name", "date", "temp_max_c", "rel_humidity_pct"],
        non_null_cols=["temp_max_c", "rel_humidity_pct"],
        extra_meta={"venues": int(df["venue_name"].nunique())},
    )
    if ok:
        logger.info(f"[s02] {len(df)} venue-day rows from {df['venue_name'].nunique()} venues.")


if __name__ == "__main__":
    fetch_weather()
