"""
Stage 12 - TheStatsAPI/API-Football maximum value collection.

This is a raw-data collector only. It discovers endpoint availability, then
prioritizes historical odds, match xG/team stats, player stats, lineups, and
injuries for international competitions. It does not train models or mutate the
project database.

Required environment variables:
  STATSAPI_KEY
Optional:
  APIFOOTBALL_KEY
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data_collection_pipeline" / "collected_data" / "raw"
SAMPLE_DIR = RAW_DIR / "statsapi_samples"
JSONL_DIR = RAW_DIR / "statsapi_jsonl"
RUN_ID = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")

STATSAPI_BASE = "https://api.thestatsapi.com/api"
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"

TARGET_PATTERNS = [
    ("FIFA World Cup", re.compile(r"\b(fifa\s+)?world cup\b(?!.*qual)", re.I)),
    ("World Cup qualifiers", re.compile(r"world cup.*qual|qual.*world cup", re.I)),
    ("Euro", re.compile(r"\b(euro|uefa european championship)\b", re.I)),
    ("Copa America", re.compile(r"copa america", re.I)),
    ("Nations League", re.compile(r"nations league", re.I)),
    ("International friendlies", re.compile(r"friendl|international", re.I)),
]

STATSAPI_CANDIDATES = [
    "/football/competitions",
    "/football/teams",
    "/football/players",
    "/football/matches",
    "/football/matches/{match_id}",
    "/football/matches/{match_id}/stats",
    "/football/matches/{match_id}/events",
    "/football/matches/{match_id}/lineups",
    "/football/matches/{match_id}/players",
    "/football/matches/{match_id}/player-stats",
    "/football/matches/{match_id}/odds",
    "/football/matches/{match_id}/odds/live",
    "/football/matches/{match_id}/odds/history",
    "/football/matches/{match_id}/injuries",
    "/football/competitions/{competition_id}",
    "/football/competitions/{competition_id}/seasons",
    "/football/competitions/{competition_id}/seasons/{season_id}/groups",
    "/football/competitions/{competition_id}/seasons/{season_id}/standings",
    "/football/teams/{team_id}",
    "/football/teams/{team_id}/matches",
    "/football/teams/{team_id}/players",
    "/football/teams/{team_id}/squad",
    "/football/teams/{team_id}/stats",
    "/football/players/{player_id}",
    "/football/players/{player_id}/stats",
    "/football/players/{player_id}/matches",
    "/football/odds",
    "/football/odds/live",
    "/football/odds/sports",
]

APIFOOTBALL_CANDIDATES = [
    "/status",
    "/leagues",
    "/fixtures",
    "/fixtures/statistics",
    "/fixtures/players",
    "/fixtures/lineups",
    "/injuries",
    "/odds",
    "/odds/live",
    "/teams",
    "/players",
]


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    JSONL_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:180]


def request_json(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    max_retries: int | None = None,
) -> tuple[int, dict[str, str], Any, str | None]:
    if max_retries is None:
        max_retries = int(os.environ.get("COLLECT_MAX_RETRIES", "2"))
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"

    req = urllib.request.Request(url, headers=headers)
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=float(os.environ.get("COLLECT_HTTP_TIMEOUT", "8"))) as res:
                body = res.read().decode("utf-8", "replace")
                data = json.loads(body) if body else None
                return res.status, dict(res.headers), data, None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < max_retries - 1:
                retry_after = e.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 10 + attempt * 10)
                continue
            try:
                data = json.loads(body) if body else None
            except json.JSONDecodeError:
                data = {"raw": body[:2000]}
            return e.code, dict(e.headers), data, None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 + attempt * 3)
                continue
            return 0, {}, None, repr(e)
    return 0, {}, None, "unreachable"


def unwrap_rows(data: Any) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "response", "results", "items", "matches", "odds", "statistics"):
            val = data.get(key)
            if isinstance(val, list):
                return val
        if isinstance(data.get("data"), dict):
            for key in ("data", "items", "results"):
                val = data["data"].get(key)
                if isinstance(val, list):
                    return val
        return [data]
    return [{"value": data}]


def pagination_meta(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    for key in ("meta", "pagination", "paging"):
        if isinstance(data.get(key), dict):
            return data[key]
    return {}


def total_pages(meta: dict[str, Any]) -> int | None:
    for key in ("total_pages", "last_page", "pages"):
        val = meta.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    current = meta.get("current_page") or meta.get("page")
    total = meta.get("total")
    per_page = meta.get("per_page") or meta.get("limit")
    if isinstance(current, int) and isinstance(total, int) and isinstance(per_page, int) and per_page:
        return max(current, (total + per_page - 1) // per_page)
    return None


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            name = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            if isinstance(val, dict):
                out.update(flatten(val, name))
            elif isinstance(val, list):
                out[name] = json.dumps(val, ensure_ascii=False, sort_keys=True)
            else:
                out[name] = val
    elif isinstance(obj, list):
        out[prefix or "value"] = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    else:
        out[prefix or "value"] = obj
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_jsonl(path: Path, record: Any) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def statsapi_headers() -> dict[str, str]:
    key = os.environ.get("STATSAPI_KEY")
    if not key:
        raise SystemExit("STATSAPI_KEY is required")
    return {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "worldcup-data-collector/1.0",
    }


def apifootball_headers() -> dict[str, str] | None:
    key = os.environ.get("APIFOOTBALL_KEY")
    if not key:
        return None
    return {
        "x-apisports-key": key,
        "Accept": "application/json",
        "User-Agent": "worldcup-data-collector/1.0",
    }


def fetch_paginated(path: str, params: dict[str, Any] | None = None, max_pages: int = 1000) -> tuple[list[Any], list[dict[str, Any]]]:
    headers = statsapi_headers()
    rows: list[Any] = []
    log: list[dict[str, Any]] = []
    params = dict(params or {})
    params.setdefault("per_page", 100)

    for page in range(1, max_pages + 1):
        params["page"] = page
        url = STATSAPI_BASE + path
        status, resp_headers, data, error = request_json(url, headers, params)
        log.append({
            "ts": now_iso(), "provider": "thestatsapi", "path": path, "page": page,
            "status": status, "error": error, "rate_remaining": resp_headers.get("x-ratelimit-remaining"),
        })
        append_jsonl(JSONL_DIR / f"{safe_name(path)}.jsonl", {"path": path, "params": params, "status": status, "data": data, "error": error})
        if status >= 400 or status == 0 or data is None:
            break
        page_rows = unwrap_rows(data)
        rows.extend(page_rows)
        meta = pagination_meta(data)
        pages = total_pages(meta)
        if pages is not None and page >= pages:
            break
        if not page_rows:
            break
        time.sleep(0.55)
    return rows, log


def classify_competition(comp: dict[str, Any]) -> str | None:
    text = " ".join(str(comp.get(k, "")) for k in ("name", "competition_name", "slug", "country", "region", "type"))
    for label, pattern in TARGET_PATTERNS:
        if pattern.search(text):
            return label
    return None


def first_id(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def discover_statsapi() -> dict[str, Any]:
    headers = statsapi_headers()
    discovery: list[dict[str, Any]] = []
    replacements = {
        "match_id": "mt_010249745",
        "competition_id": "comp_placeholder",
        "season_id": "season_placeholder",
        "team_id": "team_placeholder",
        "player_id": "player_placeholder",
    }

    for candidate in STATSAPI_CANDIDATES:
        path = candidate
        for key, val in replacements.items():
            path = path.replace("{" + key + "}", val)
        params = {"per_page": 1} if "{" not in candidate and path.endswith(("competitions", "matches", "teams", "players", "odds")) else None
        status, resp_headers, data, error = request_json(STATSAPI_BASE + path, headers, params)
        rows = unwrap_rows(data)
        sample_file = SAMPLE_DIR / f"thestatsapi_{safe_name(candidate)}.json"
        sample_file.write_text(json.dumps({"status": status, "path": candidate, "data": data, "error": error}, ensure_ascii=False, indent=2), encoding="utf-8")
        discovery.append({
            "provider": "thestatsapi", "endpoint": candidate, "tested_url_path": path,
            "status": status, "rows_in_sample": len(rows), "sample_file": str(sample_file.relative_to(ROOT)),
            "error": error, "rate_remaining": resp_headers.get("x-ratelimit-remaining"),
        })
        time.sleep(0.55)
    return {"endpoints": discovery}


def collect_statsapi() -> dict[str, Any]:
    manifest: dict[str, Any] = {"provider": "thestatsapi", "run_id": RUN_ID, "started_at": now_iso(), "errors": []}
    all_logs: list[dict[str, Any]] = []

    competitions_raw, logs = fetch_paginated("/football/competitions", {"per_page": 100}, max_pages=50)
    all_logs.extend(logs)
    competitions = [flatten(r) for r in competitions_raw]
    write_csv(RAW_DIR / "statsapi_competitions.csv", competitions)

    target_competitions = []
    for raw, flat in zip(competitions_raw, competitions):
        if not isinstance(raw, dict):
            continue
        label = classify_competition(raw)
        if label:
            flat["target_bucket"] = label
            target_competitions.append((raw, flat, label))
    write_csv(RAW_DIR / "statsapi_target_competitions.csv", [flat for _, flat, _ in target_competitions])

    seasons_rows: list[dict[str, Any]] = []
    groups_rows: list[dict[str, Any]] = []
    standings_rows: list[dict[str, Any]] = []
    matches_rows: list[dict[str, Any]] = []
    odds_rows: list[dict[str, Any]] = []
    team_stats_rows: list[dict[str, Any]] = []
    player_stats_rows: list[dict[str, Any]] = []
    lineups_rows: list[dict[str, Any]] = []
    injuries_rows: list[dict[str, Any]] = []

    for raw_comp, flat_comp, bucket in target_competitions:
        comp_id = first_id(flat_comp, ("id", "competition_id", "uuid"))
        if not comp_id:
            continue
        season_path = f"/football/competitions/{comp_id}/seasons"
        seasons_raw, logs = fetch_paginated(season_path, {"per_page": 100}, max_pages=20)
        all_logs.extend(logs)
        for season_raw in seasons_raw:
            season = flatten(season_raw)
            season["competition_id"] = comp_id
            season["competition_name"] = flat_comp.get("name") or flat_comp.get("competition_name")
            season["target_bucket"] = bucket
            seasons_rows.append(season)

        if not seasons_raw:
            seasons_raw = [{"id": None, "season_id": None}]

        for season_raw in seasons_raw:
            season_flat = flatten(season_raw)
            season_id = first_id(season_flat, ("id", "season_id", "uuid"))
            match_params = {"competition_id": comp_id, "per_page": 100}
            if season_id:
                match_params["season_id"] = season_id
                for sub_path, sink in (
                    (f"/football/competitions/{comp_id}/seasons/{season_id}/groups", groups_rows),
                    (f"/football/competitions/{comp_id}/seasons/{season_id}/standings", standings_rows),
                ):
                    sub_raw, logs = fetch_paginated(sub_path, {"per_page": 100}, max_pages=20)
                    all_logs.extend(logs)
                    for item in sub_raw:
                        flat = flatten(item)
                        flat["competition_id"] = comp_id
                        flat["season_id"] = season_id
                        flat["target_bucket"] = bucket
                        sink.append(flat)

            matches_raw, logs = fetch_paginated("/football/matches", match_params, max_pages=200)
            all_logs.extend(logs)
            for match_raw in matches_raw:
                match = flatten(match_raw)
                match["competition_id_query"] = comp_id
                match["season_id_query"] = season_id
                match["target_bucket"] = bucket
                matches_rows.append(match)

    write_csv(RAW_DIR / "statsapi_seasons.csv", seasons_rows)
    write_csv(RAW_DIR / "statsapi_groups.csv", groups_rows)
    write_csv(RAW_DIR / "statsapi_standings.csv", standings_rows)
    write_csv(RAW_DIR / "statsapi_matches.csv", matches_rows)

    seen_match_ids = []
    seen = set()
    for row in matches_rows:
        match_id = first_id(row, ("id", "match_id", "uuid"))
        if match_id and match_id not in seen:
            seen.add(match_id)
            seen_match_ids.append(match_id)

    for idx, match_id in enumerate(seen_match_ids, start=1):
        endpoints = [
            ("odds", f"/football/matches/{match_id}/odds", odds_rows),
            ("odds", f"/football/matches/{match_id}/odds/live", odds_rows),
            ("team_stats", f"/football/matches/{match_id}/stats", team_stats_rows),
            ("player_stats", f"/football/matches/{match_id}/players", player_stats_rows),
            ("lineups", f"/football/matches/{match_id}/lineups", lineups_rows),
            ("injuries", f"/football/matches/{match_id}/injuries", injuries_rows),
        ]
        for kind, path, sink in endpoints:
            status, resp_headers, data, error = request_json(STATSAPI_BASE + path, statsapi_headers())
            all_logs.append({
                "ts": now_iso(), "provider": "thestatsapi", "path": path,
                "status": status, "error": error, "rate_remaining": resp_headers.get("x-ratelimit-remaining"),
            })
            append_jsonl(JSONL_DIR / f"match_{kind}.jsonl", {"match_id": match_id, "path": path, "status": status, "data": data, "error": error})
            if 200 <= status < 300 and data is not None:
                for item in unwrap_rows(data):
                    flat = flatten(item)
                    flat["match_id"] = match_id
                    sink.append(flat)
            time.sleep(0.55)
        if idx % 100 == 0:
            write_csv(RAW_DIR / "statsapi_odds.csv", odds_rows)
            write_csv(RAW_DIR / "statsapi_team_stats.csv", team_stats_rows)
            write_csv(RAW_DIR / "statsapi_player_stats.csv", player_stats_rows)
            write_csv(RAW_DIR / "statsapi_lineups.csv", lineups_rows)
            write_csv(RAW_DIR / "statsapi_injuries.csv", injuries_rows)

    write_csv(RAW_DIR / "statsapi_odds.csv", odds_rows)
    write_csv(RAW_DIR / "statsapi_team_stats.csv", team_stats_rows)
    write_csv(RAW_DIR / "statsapi_player_stats.csv", player_stats_rows)
    write_csv(RAW_DIR / "statsapi_lineups.csv", lineups_rows)
    write_csv(RAW_DIR / "statsapi_injuries.csv", injuries_rows)
    write_csv(RAW_DIR / "statsapi_request_log.csv", all_logs)

    manifest.update({
        "finished_at": now_iso(),
        "competitions": len(competitions),
        "target_competitions": len(target_competitions),
        "seasons": len(seasons_rows),
        "matches": len(matches_rows),
        "odds": len(odds_rows),
        "team_stats": len(team_stats_rows),
        "player_stats": len(player_stats_rows),
        "lineups": len(lineups_rows),
        "injuries": len(injuries_rows),
    })
    (RAW_DIR / "statsapi_run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def discover_apifootball() -> dict[str, Any]:
    headers = apifootball_headers()
    if not headers:
        return {"endpoints": [], "note": "APIFOOTBALL_KEY not set"}
    endpoints = []
    for endpoint in APIFOOTBALL_CANDIDATES:
        params = {"current": "true"} if endpoint == "/leagues" else None
        status, resp_headers, data, error = request_json(APIFOOTBALL_BASE + endpoint, headers, params)
        sample_file = SAMPLE_DIR / f"apifootball_{safe_name(endpoint)}.json"
        sample_file.write_text(json.dumps({"status": status, "endpoint": endpoint, "data": data, "error": error}, ensure_ascii=False, indent=2), encoding="utf-8")
        endpoints.append({
            "provider": "api-football", "endpoint": endpoint, "status": status,
            "rows_in_sample": len(unwrap_rows(data)), "sample_file": str(sample_file.relative_to(ROOT)),
            "error": error, "requests_remaining": resp_headers.get("x-ratelimit-requests-remaining"),
        })
        time.sleep(1.0)
    return {"endpoints": endpoints}


def main() -> int:
    ensure_dirs()
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    results: dict[str, Any] = {"run_id": RUN_ID, "started_at": now_iso()}

    if mode in ("all", "discover"):
        results["statsapi_discovery"] = discover_statsapi()
        results["apifootball_discovery"] = discover_apifootball()
        endpoints = results["statsapi_discovery"]["endpoints"] + results["apifootball_discovery"].get("endpoints", [])
        write_csv(RAW_DIR / "statsapi_endpoint_discovery.csv", endpoints)

    if mode in ("all", "collect"):
        results["statsapi_collection"] = collect_statsapi()

    results["finished_at"] = now_iso()
    (RAW_DIR / "statsapi_collection_summary.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "run_id": RUN_ID,
        "mode": mode,
        "summary_file": str((RAW_DIR / "statsapi_collection_summary.json").relative_to(ROOT)),
        "manifest_file": str((RAW_DIR / "statsapi_run_manifest.json").relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
