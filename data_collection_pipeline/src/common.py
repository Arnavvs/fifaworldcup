"""
Common utilities for the data collection pipeline.
Handles: logging, SQLite DB access, checkpointing, HTTP retries, path constants.
"""
import os
import sys
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import time
import requests
from requests.adapters import HTTPAdapter, Retry

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(r"C:\Users\HP\OneDrive\Desktop\worldCup")
PIPELINE_ROOT = PROJECT_ROOT / "data_collection_pipeline"
SRC_DIR = PIPELINE_ROOT / "src"
RAW_DIR = PIPELINE_ROOT / "collected_data" / "raw"
PROCESSED_DIR = PIPELINE_ROOT / "collected_data" / "processed"
CHECKPOINT_PATH = PIPELINE_ROOT / "checkpoints.json"
DB_PATH = PROJECT_ROOT / "fifa_wc_data" / "db" / "football.db"
LOG_PATH = PIPELINE_ROOT / "pipeline.log"

# Ensure dirs exist
for d in (RAW_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("data_pipeline")

# ---------------------------------------------------------------------------
# Checkpointing (resumable stages)
# ---------------------------------------------------------------------------
def load_checkpoints() -> Dict[str, Any]:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(stage: str, status: str = "done", meta: Optional[Dict] = None):
    cp = load_checkpoints()
    cp[stage] = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "meta": meta or {},
    }
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(cp, f, indent=2)


def should_run(stage: str) -> bool:
    cp = load_checkpoints()
    return cp.get(stage, {}).get("status") != "done"


# ---------------------------------------------------------------------------
# Output validation — a stage may only be marked "done" if it produced
# real data. This prevents empty/garbage results being silently trusted
# by downstream feature engineering.
# ---------------------------------------------------------------------------
class ValidationError(Exception):
    """Raised when a stage's output fails its quality checks."""


def validate_df(
    df: Any,
    min_rows: int = 1,
    required_cols: Optional[list] = None,
    non_null_cols: Optional[list] = None,
    max_null_frac: float = 0.5,
) -> None:
    """
    Validate a DataFrame before it is allowed to checkpoint as 'done'.

    - min_rows:       reject if fewer rows than this.
    - required_cols:  columns that must exist.
    - non_null_cols:  columns where the fraction of nulls must be <= max_null_frac.
    Raises ValidationError on any failure.
    """
    import pandas as pd  # local import keeps module import cheap
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValidationError("output is not a DataFrame")
    if len(df) < min_rows:
        raise ValidationError(f"got {len(df)} rows, need >= {min_rows}")
    if required_cols:
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValidationError(f"missing required columns: {missing}")
    for col in (non_null_cols or []):
        if col not in df.columns:
            raise ValidationError(f"non-null check column absent: {col}")
        null_frac = df[col].isna().mean()
        if null_frac > max_null_frac:
            raise ValidationError(
                f"column '{col}' is {null_frac:.0%} null (max {max_null_frac:.0%})"
            )


def finalize_stage(
    stage: str,
    df: Any,
    out_path: "Path",
    *,
    min_rows: int = 1,
    required_cols: Optional[list] = None,
    non_null_cols: Optional[list] = None,
    max_null_frac: float = 0.5,
    extra_meta: Optional[Dict] = None,
) -> bool:
    """
    Validate `df`; if it passes, save to CSV and checkpoint 'done'.
    If it fails, save nothing as canonical, checkpoint 'failed' with the reason,
    and return False so the caller (and the run log) sees an honest result.
    """
    try:
        validate_df(
            df,
            min_rows=min_rows,
            required_cols=required_cols,
            non_null_cols=non_null_cols,
            max_null_frac=max_null_frac,
        )
    except ValidationError as e:
        logger.error(f"[{stage}] OUTPUT VALIDATION FAILED: {e}")
        meta = {"reason": f"validation_failed: {e}"}
        if extra_meta:
            meta.update(extra_meta)
        save_checkpoint(stage, status="failed", meta=meta)
        return False
    save_csv(df, out_path)
    meta = {"rows": len(df)}
    if extra_meta:
        meta.update(extra_meta)
    save_checkpoint(stage, status="done", meta=meta)
    logger.info(f"[{stage}] Validated & saved {len(df)} rows -> {out_path.name}")
    return True


# ---------------------------------------------------------------------------
# HTTP client with retries
# ---------------------------------------------------------------------------
def get_session(max_retries: int = 3, backoff: float = 1.0) -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
    })
    return s


# ---------------------------------------------------------------------------
# Playwright stealth fetch (for anti-bot sites: FIFA/Akamai, Understat/CF, OddsPortal)
# ---------------------------------------------------------------------------
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
window.chrome = {runtime: {}};
const _q = navigator.permissions && navigator.permissions.query;
if (_q) { navigator.permissions.query = (p) => (
  p && p.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : _q(p)
); }
"""

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def playwright_fetch(
    url: str,
    *,
    wait_selector: Optional[str] = None,
    wait_text: Optional[str] = None,
    scroll: bool = False,
    aggressiveness: str = "medium",
    headless: bool = True,
    timeout_ms: int = 60000,
) -> Optional[str]:
    """
    Fetch a page through a stealthed Chromium that mimics a human browser.
    Returns page HTML (after JS) or None on failure.

    aggressiveness tunes pacing/retries for tougher anti-bot:
      'low'    quick single load (Understat-class)
      'medium' load + settle + small jitter
      'high'   slow human-like: extra waits, mouse move, multi-settle (OddsPortal-class)
    """
    import random
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed: pip install playwright && playwright install chromium")
        return None

    waits = {"low": (0.5, 1.5), "medium": (1.5, 3.5), "high": (3.0, 7.0)}.get(
        aggressiveness, (1.5, 3.5)
    )
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ]
    html = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=launch_args)
        context = browser.new_context(
            user_agent=_UA,
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        context.add_init_script(_STEALTH_JS)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(random.uniform(*waits))
            if aggressiveness == "high":
                # human-ish mouse movement helps against behavioural checks
                for _ in range(3):
                    page.mouse.move(random.randint(0, 1200), random.randint(0, 800))
                    time.sleep(random.uniform(0.2, 0.6))
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms // 2)
                except Exception:
                    logger.debug(f"wait_selector '{wait_selector}' not found on {url}")
            if wait_text:
                try:
                    page.wait_for_function(
                        "t => document.documentElement.innerHTML.includes(t)",
                        arg=wait_text, timeout=timeout_ms // 2,
                    )
                except Exception:
                    logger.debug(f"wait_text '{wait_text}' not seen on {url}")
            if scroll:
                for _ in range(5):
                    page.mouse.wheel(0, random.randint(600, 1200))
                    time.sleep(random.uniform(0.4, 1.0))
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms // 3)
            except Exception:
                pass
            html = page.content()
        except Exception as e:
            logger.warning(f"playwright_fetch failed for {url}: {e}")
        finally:
            browser.close()
    return html


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def read_sql(query: str) -> Any:
    import pandas as pd
    conn = db_conn()
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def write_sql(df: Any, table: str, if_exists: str = "replace"):
    import pandas as pd
    conn = db_conn()
    try:
        df.to_sql(table, conn, if_exists=if_exists, index=False)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------
def get_capital_coords(country: str) -> Optional[tuple]:
    """
    Quick lookup for capital city lat/lng for national teams.
    Hardcoded common ones + geopy fallback.
    """
    hardcoded = {
        "Argentina": (-34.6037, -58.3816),
        "Brazil": (-15.7975, -47.8919),
        "Germany": (52.5200, 13.4050),
        "France": (48.8566, 2.3522),
        "Spain": (40.4168, -3.7038),
        "England": (51.5074, -0.1278),
        "Italy": (41.9028, 12.4964),
        "Portugal": (38.7223, -9.1393),
        "Netherlands": (52.3676, 4.9041),
        "Belgium": (50.8503, 4.3517),
        "Mexico": (19.4326, -99.1332),
        "USA": (38.9072, -77.0369),
        "Canada": (45.4215, -75.6972),
        "Uruguay": (-34.9011, -56.1645),
        "Croatia": (45.8150, 15.9819),
        "Morocco": (34.0209, -6.8416),
        "Japan": (35.6762, 139.6503),
        "Korea Republic": (37.5665, 126.9780),
        "Australia": (-35.2809, 149.1300),
        "Switzerland": (46.9480, 7.4474),
        "Poland": (52.2297, 21.0122),
        "Senegal": (14.7167, -17.4677),
        "Ecuador": (-0.1807, -78.4678),
        "Qatar": (25.2854, 51.5310),
        "Saudi Arabia": (24.7136, 46.6753),
        "Cameroon": (3.8480, 11.5021),
        "Ghana": (5.6037, -0.1870),
        "Tunisia": (36.8065, 10.1815),
        "Iran": (35.6892, 51.3890),
        "IR Iran": (35.6892, 51.3890),
        "Algeria": (36.7538, 3.0588),
        "Egypt": (30.0444, 31.2357),
        "Nigeria": (9.0820, 8.6753),
        "Colombia": (4.7110, -74.0721),
        "Chile": (-33.4489, -70.6693),
        "Peru": (-12.0464, -77.0428),
        "Paraguay": (-25.2637, -57.5759),
        "Bolivia": (-16.4897, -68.1193),
        "Venezuela": (10.4806, -66.9036),
        "Russia": (55.7558, 37.6173),
        "Ukraine": (50.4501, 30.5234),
        "Turkey": (39.9334, 32.8597),
        "Türkiye": (39.9334, 32.8597),
        "Côte d'Ivoire": (6.8276, -5.2893),
        "Czech Republic": (50.0755, 14.4378),
        "Czechia": (50.0755, 14.4378),
        "Austria": (48.2082, 16.3738),
        "Hungary": (47.4979, 19.0402),
        "Wales": (51.4816, -3.1791),
        "Scotland": (55.9533, -3.1883),
        "Northern Ireland": (54.5973, -5.9301),
        "Republic of Ireland": (53.3498, -6.2603),
        "Norway": (59.9139, 10.7523),
        "Sweden": (59.3293, 18.0686),
        "Denmark": (55.6761, 12.5683),
        "Finland": (60.1699, 24.9384),
        "Serbia": (44.7866, 20.4489),
        "Bosnia and Herzegovina": (43.8563, 18.4131),
        "Slovenia": (46.0569, 14.5058),
        "Slovakia": (48.1486, 17.1077),
        "Romania": (44.4268, 26.1025),
        "Bulgaria": (42.6977, 23.3219),
        "Greece": (37.9838, 23.7275),
        "Israel": (31.7683, 35.2137),
        "Jamaica": (17.9712, -76.7926),
        "Costa Rica": (9.9281, -84.0907),
        "Panama": (8.9833, -79.5167),
        "Honduras": (14.0723, -87.1894),
        "Guatemala": (14.6349, -90.5069),
        "El Salvador": (13.6929, -89.2182),
        "Haiti": (18.5944, -72.3074),
        "Curaçao": (12.1696, -68.9900),
        "Curaçao": (12.1224, -68.8824),
        "Trinidad and Tobago": (10.6549, -61.5019),
        "New Zealand": (-41.2865, 174.7762),
        "Fiji": (-18.1248, 178.4501),
        "Papua New Guinea": (-9.4438, 147.1803),
        "South Africa": (-25.7479, 28.2293),
        "Cabo Verde": (14.9164, -23.5087),
        "Congo DR": (-4.4419, 15.2663),
        "Mali": (12.6392, -8.0029),
        "Burkina Faso": (12.3714, -1.5197),
        "Guinea": (9.6412, -13.5784),
        "Uganda": (0.3476, 32.5825),
        "Kenya": (-1.2921, 36.8219),
        "Zambia": (-15.3875, 28.3228),
        "Zimbabwe": (-17.8252, 31.0335),
        "Madagascar": (-18.8792, 47.5079),
        "Angola": (-8.8368, 13.2344),
        "Mozambique": (-25.9692, 32.5732),
        "Malawi": (-13.9626, 33.7741),
        "Botswana": (-24.6282, 25.9231),
        "Namibia": (-22.5609, 17.0658),
        "Swaziland": (-26.3054, 31.1367),
        "Lesotho": (-29.6100, 27.9500),
        "Central African Republic": (4.3947, 18.5582),
        "Chad": (12.1348, 15.0557),
        "Niger": (13.5116, 2.1254),
        "Benin": (6.4969, 2.6283),
        "Togo": (6.1725, 1.2314),
        "Liberia": (6.3153, -10.8047),
        "Sierra Leone": (8.4844, -13.2344),
        "Guinea-Bissau": (11.8038, -15.1804),
        "Gambia": (13.4550, -16.5795),
        "Mauritania": (18.0735, -15.9582),
        "Sudan": (15.5007, 32.5599),
        "South Sudan": (4.8594, 31.5713),
        "Ethiopia": (9.0054, 38.7636),
        "Eritrea": (15.3229, 38.9251),
        "Djibouti": (11.5721, 43.1520),
        "Somalia": (2.0469, 45.3182),
        "Comoros": (-11.6455, 43.3333),
        "Seychelles": (-4.6796, 55.4920),
        "Mauritius": (-20.1609, 57.5012),
        "Rwanda": (-1.9706, 30.1044),
        "Burundi": (-3.3614, 29.3599),
        "Tanzania": (-6.7924, 39.2083),
        "Equatorial Guinea": (3.7500, 8.7833),
        "Gabon": (0.4162, 9.4673),
        "Sao Tome and Principe": (0.1864, 6.6131),
        "Cape Verde": (14.9164, -23.5087),
        "Libya": (32.8872, 13.1913),
        "Tunisia": (36.8065, 10.1815),
        "Algeria": (36.7538, 3.0588),
        "Morocco": (34.0209, -6.8416),
        "Egypt": (30.0444, 31.2357),
        "Iraq": (33.3152, 44.3661),
        "Jordan": (31.9454, 35.9284),
        "Lebanon": (33.8938, 35.5018),
        "Syria": (33.5138, 36.2765),
        "Oman": (23.5859, 58.4059),
        "Yemen": (15.3694, 44.1910),
        "Bahrain": (26.2285, 50.5860),
        "Kuwait": (29.3759, 47.9774),
        "United Arab Emirates": (24.4539, 54.3773),
        "Qatar": (25.2854, 51.5310),
        "Saudi Arabia": (24.7136, 46.6753),
        "Uzbekistan": (41.2995, 69.2401),
        "Kyrgyzstan": (42.8746, 74.5698),
        "Tajikistan": (38.5598, 68.7870),
        "Turkmenistan": (37.9601, 58.3261),
        "Kazakhstan": (51.1605, 71.4704),
        "Afghanistan": (34.5553, 69.2075),
        "India": (28.6139, 77.2090),
        "Pakistan": (33.6844, 73.0479),
        "Bangladesh": (23.8103, 90.4125),
        "Nepal": (27.7172, 85.3240),
        "Sri Lanka": (6.9271, 79.8612),
        "Maldives": (4.1755, 73.5093),
        "Bhutan": (27.4728, 89.6390),
        "Myanmar": (16.8661, 96.1951),
        "Thailand": (13.7563, 100.5018),
        "Vietnam": (21.0278, 105.8342),
        "Laos": (17.9757, 102.6331),
        "Cambodia": (11.5564, 104.9282),
        "Malaysia": (3.1390, 101.6869),
        "Singapore": (1.3521, 103.8198),
        "Indonesia": (-6.2088, 106.8456),
        "Philippines": (14.5995, 120.9842),
        "Brunei": (4.9031, 114.9398),
        "Timor-Leste": (-8.5569, 125.5603),
        "China": (39.9042, 116.4074),
        "North Korea": (39.0392, 125.7625),
        "South Korea": (37.5665, 126.9780),
        "Mongolia": (47.8864, 106.9057),
        "Japan": (35.6762, 139.6503),
        "Chinese Taipei": (25.0330, 121.5654),
        "Hong Kong": (22.3193, 114.1694),
        "Macau": (22.1987, 113.5439),
        "Guam": (13.4443, 144.7937),
        "Northern Mariana Islands": (15.1833, 145.7500),
        "American Samoa": (-14.2756, -170.7020),
        "Samoa": (-13.8507, -171.7514),
        "Tonga": (-21.1394, -175.2018),
        "Cook Islands": (-21.2367, -159.7777),
        "New Caledonia": (-22.2736, 166.4460),
        "Papua New Guinea": (-9.4438, 147.1803),
        "Solomon Islands": (-9.4456, 159.9729),
        "Vanuatu": (-17.7333, 168.3273),
        "Fiji": (-18.1248, 178.4501),
        "Tuvalu": (-8.5211, 179.1982),
        "Kiribati": (1.3291, 172.9780),
        "Nauru": (-0.5477, 166.9209),
        "Marshall Islands": (7.1164, 171.1840),
        "Micronesia": (6.9248, 158.1618),
        "Palau": (7.5149, 134.5825),
        "Belize": (17.2510, -88.7590),
        "Nicaragua": (12.1150, -86.2362),
        "Honduras": (14.0723, -87.1894),
        "El Salvador": (13.6929, -89.2182),
        "Guatemala": (14.6349, -90.5069),
        "Costa Rica": (9.9281, -84.0907),
        "Panama": (8.9833, -79.5167),
        "Dominica": (15.4150, -61.3710),
        "Saint Lucia": (14.0101, -60.9875),
        "Saint Vincent and the Grenadines": (13.1600, -61.2300),
        "Grenada": (12.1165, -61.6790),
        "Barbados": (13.1939, -59.5432),
        "Trinidad and Tobago": (10.6549, -61.5019),
        "Jamaica": (17.9712, -76.7926),
        "Haiti": (18.5944, -72.3074),
        "Cuba": (23.1136, -82.3666),
        "Dominican Republic": (18.4861, -69.9312),
        "Puerto Rico": (18.2208, -66.5901),
        "Antigua and Barbuda": (17.1274, -61.8468),
        "Saint Kitts and Nevis": (17.3578, -62.7820),
        "Suriname": (5.8520, -55.2038),
        "Guyana": (6.8013, -58.1541),
        "Venezuela": (10.4806, -66.9036),
        "Colombia": (4.7110, -74.0721),
        "Ecuador": (-0.1807, -78.4678),
        "Peru": (-12.0464, -77.0428),
        "Bolivia": (-16.4897, -68.1193),
        "Paraguay": (-25.2637, -57.5759),
        "Chile": (-33.4489, -70.6693),
        "Uruguay": (-34.9011, -56.1645),
        "Argentina": (-34.6037, -58.3816),
        "Brazil": (-15.7975, -47.8919),
        "Mexico": (19.4326, -99.1332),
        "United States": (38.9072, -77.0369),
        "Canada": (45.4215, -75.6972),
        "Gibraltar": (36.1408, -5.3536),
        "Faroe Islands": (62.0117, -6.7675),
        "Malta": (35.8989, 14.5146),
        "Cyprus": (35.1856, 33.3823),
        "Liechtenstein": (47.1410, 9.5209),
        "San Marino": (43.9424, 12.4578),
        "Andorra": (42.5063, 1.5218),
        "Monaco": (43.7384, 7.4246),
        "Luxembourg": (49.6116, 6.1319),
        "Estonia": (59.4370, 24.7536),
        "Latvia": (56.9496, 24.1052),
        "Lithuania": (54.6872, 25.2797),
        "Belarus": (53.9045, 27.5615),
        "Moldova": (47.0105, 28.8638),
        "Armenia": (40.1792, 44.4991),
        "Azerbaijan": (40.4093, 49.8671),
        "Georgia": (41.7151, 44.8271),
        "Kazakhstan": (51.1605, 71.4704),
        "Kosovo": (42.6629, 21.1655),
        "North Macedonia": (41.9981, 21.4254),
        "Albania": (41.3275, 19.8187),
        "Montenegro": (42.4410, 19.2641),
        "Bosnia and Herzegovina": (43.8563, 18.4131),
        "Iceland": (64.1466, -21.9426),
        "Turkey": (39.9334, 32.8597),
        "Russia": (55.7558, 37.6173),
        "Ukraine": (50.4501, 30.5234),
        "Poland": (52.2297, 21.0122),
        "Czech Republic": (50.0755, 14.4378),
        "Slovakia": (48.1486, 17.1077),
        "Hungary": (47.4979, 19.0402),
        "Romania": (44.4268, 26.1025),
        "Bulgaria": (42.6977, 23.3219),
        "Slovenia": (46.0569, 14.5058),
        "Croatia": (45.8150, 15.9819),
        "Serbia": (44.7866, 20.4489),
        "Montenegro": (42.4410, 19.2641),
        "Bosnia and Herzegovina": (43.8563, 18.4131),
        "North Macedonia": (41.9981, 21.4254),
        "Albania": (41.3275, 19.8187),
        "Kosovo": (42.6629, 21.1655),
    }
    if country in hardcoded:
        return hardcoded[country]
    # fallback to geopy Nominatim (rate limited, slow)
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut
        geolocator = Nominatim(user_agent="wc_pipeline", timeout=10)
        loc = geolocator.geocode(f"capital of {country}")
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception as e:
        logger.warning(f"Geocoding fallback failed for {country}: {e}")
    return None


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def save_csv(df: Any, path: Path):
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"Saved CSV: {path}")


def load_csv(path: Path) -> Any:
    import pandas as pd
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


if __name__ == "__main__":
    print("Common utilities loaded.")
