"""
Shared infrastructure for the FIFA WC 2026 dataset pipeline.

Provides: path constants, structured logging, a rate-limited + retrying HTTP
session, checkpoint helpers, and small dataframe/IO utilities.

All scrapers import from here so behaviour (delays, retries, UA rotation,
logging) is consistent and configured in one place.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "fifa_wc_data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
DB_DIR = DATA / "db"
LOGS = DATA / "logs"
DB_PATH = DB_DIR / "football.db"
CHECKPOINT_PATH = LOGS / "checkpoints.json"

for _p in (RAW, PROCESSED, DB_DIR, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Logging  (one shared file + per-run console)
# --------------------------------------------------------------------------- #
_LOG_FILE = LOGS / "pipeline.log"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s")

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


log = get_logger("common")

# --------------------------------------------------------------------------- #
# Scrape-attempt ledger  (one CSV row per attempt -> data-quality report)
# --------------------------------------------------------------------------- #
_ATTEMPTS_FILE = LOGS / "scrape_attempts.csv"


def log_attempt(source: str, url: str, status: str, rows: int = 0, note: str = "") -> None:
    """Append a single scrape attempt record (success/fail/skip)."""
    new = not _ATTEMPTS_FILE.exists()
    note = (note or "").replace("\n", " ").replace(",", ";")[:300]
    with open(_ATTEMPTS_FILE, "a", encoding="utf-8") as f:
        if new:
            f.write("ts,source,status,rows,url,note\n")
        ts = datetime.now(timezone.utc).isoformat()
        f.write(f"{ts},{source},{status},{rows},{url},{note}\n")


# --------------------------------------------------------------------------- #
# User agents
# --------------------------------------------------------------------------- #
_FALLBACK_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

try:
    from fake_useragent import UserAgent

    _UA = UserAgent()

    def random_ua() -> str:
        try:
            return _UA.random
        except Exception:
            return random.choice(_FALLBACK_UAS)
except Exception:  # pragma: no cover

    def random_ua() -> str:
        return random.choice(_FALLBACK_UAS)


# --------------------------------------------------------------------------- #
# Rate-limited, retrying HTTP fetch
# --------------------------------------------------------------------------- #
_LAST_HIT: dict[str, float] = {}


def _domain(url: str) -> str:
    try:
        return url.split("/")[2]
    except Exception:
        return url


def polite_get(
    url: str,
    *,
    source: str = "http",
    min_delay: float = 3.0,
    max_delay: float = 5.0,
    retries: int = 3,
    timeout: int = 30,
    headers: dict | None = None,
    session: requests.Session | None = None,
) -> requests.Response | None:
    """
    GET with per-domain rate limiting, UA rotation, and exponential-backoff
    retries. Returns the Response on success, or None on persistent failure
    (logged, never raised — so the pipeline keeps going).
    """
    dom = _domain(url)
    # rate limit per domain
    elapsed = time.time() - _LAST_HIT.get(dom, 0.0)
    wait = random.uniform(min_delay, max_delay) - elapsed
    if wait > 0:
        time.sleep(wait)

    sess = session or requests
    base_headers = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    if headers:
        base_headers.update(headers)

    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, headers=base_headers, timeout=timeout)
            _LAST_HIT[dom] = time.time()
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 403, 503):
                backoff = min(60, (2 ** attempt) * random.uniform(2, 4))
                log.warning(f"{resp.status_code} on {url} -> backoff {backoff:.0f}s (try {attempt}/{retries})")
                time.sleep(backoff)
                base_headers["User-Agent"] = random_ua()
                continue
            log.warning(f"HTTP {resp.status_code} on {url}")
            return None
        except requests.RequestException as e:
            backoff = (2 ** attempt) * random.uniform(1, 2)
            log.warning(f"err {e!r} on {url} -> retry in {backoff:.0f}s ({attempt}/{retries})")
            time.sleep(backoff)
            _LAST_HIT[dom] = time.time()
    log_attempt(source, url, "fail", 0, "max retries exceeded")
    return None


# --------------------------------------------------------------------------- #
# Checkpointing
# --------------------------------------------------------------------------- #
def _load_ckpt() -> dict:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def checkpoint_done(stage: str, key: str) -> bool:
    return key in _load_ckpt().get(stage, [])


def mark_done(stage: str, key: str) -> None:
    ck = _load_ckpt()
    ck.setdefault(stage, [])
    if key not in ck[stage]:
        ck[stage].append(key)
        CHECKPOINT_PATH.write_text(json.dumps(ck, indent=2), encoding="utf-8")


def save_df(df, path: Path, **kw) -> None:
    """Persist a dataframe to CSV (creating parents), logging the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", **kw)
    log.info(f"wrote {len(df):>6} rows -> {path.relative_to(ROOT)}")
