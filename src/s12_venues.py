"""
Stage 12 - Venue geocoding + altitude for WC-2026 (contextual features).

Takes the distinct venue Locations from the 2026 fixtures, geocodes them with
geopy/Nominatim (1 req/s, polite user-agent), and looks up altitude from the
open-elevation API. Bounded (~16 venues) so it is fast and respectful.
Output -> processed/venues.csv  (venue_id, name, city, country, lat, lng, altitude_m)
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from common import RAW, PROCESSED, get_logger, log_attempt, save_df

log = get_logger("s12_venues")


def geocode_all(locations: list[str]) -> pd.DataFrame:
    from geopy.geocoders import Nominatim
    geo = Nominatim(user_agent="wc2026_dataset_builder")
    rows = []
    for i, loc in enumerate(locations, 1):
        lat = lng = city = country = None
        try:
            res = geo.geocode(loc, timeout=15, addressdetails=True, language="en")
            if res:
                lat, lng = res.latitude, res.longitude
                addr = (res.raw or {}).get("address", {})
                city = addr.get("city") or addr.get("town") or addr.get("state")
                country = addr.get("country")
                log_attempt("venues", loc, "ok", 1, f"{lat:.3f},{lng:.3f}")
            else:
                log_attempt("venues", loc, "empty", 0, "no geocode result")
        except Exception as e:
            log_attempt("venues", loc, "fail", 0, str(e)[:120])
        rows.append({"venue_id": i, "name": loc, "city": city, "country": country,
                     "lat": lat, "lng": lng})
        time.sleep(1.1)  # Nominatim usage policy
    return pd.DataFrame(rows)


def add_altitude(df: pd.DataFrame) -> pd.DataFrame:
    import requests
    pts = df.dropna(subset=["lat", "lng"])
    df["altitude_m"] = None
    if pts.empty:
        return df
    try:
        locs = [{"latitude": r.lat, "longitude": r.lng} for r in pts.itertuples()]
        resp = requests.post("https://api.open-elevation.com/api/v1/lookup",
                             json={"locations": locs}, timeout=40)
        if resp.status_code == 200:
            elevs = [d["elevation"] for d in resp.json()["results"]]
            df.loc[pts.index, "altitude_m"] = elevs
            log_attempt("venues", "open-elevation", "ok", len(elevs))
    except Exception as e:
        log_attempt("venues", "open-elevation", "fail", 0, str(e)[:120])
    return df


def main() -> None:
    fx = RAW / "worldcup" / "wc2026_fixtures.csv"
    if not fx.exists():
        log.warning("no 2026 fixtures; skipping venues")
        return
    locs = sorted(pd.read_csv(fx)["Location"].dropna().astype(str).unique())
    log.info(f"geocoding {len(locs)} WC2026 venues")
    df = geocode_all(locs)
    df = add_altitude(df)
    save_df(df, PROCESSED / "venues.csv")
    ok = df["lat"].notna().sum()
    log.info(f"stage 12 (venues) complete: {ok}/{len(df)} geocoded")


if __name__ == "__main__":
    sys.exit(main())
