"""
track.py - progress tracker updater for dashboard/progress.html

Usage:
  python track.py update                  # regenerate dashboard/progress_data.js
  python track.py done <task_id> [note]   # mark a task done (+update)
  python track.py start <task_id>         # mark in_progress (+update)
  python track.py log "<message>"         # append an activity-log line (+update)

The HTML reads window.PROGRESS from progress_data.js (works from file://).
Run `update` after every experiment / data run so the page stays current.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

from common import DB_PATH, ROOT

DASH = ROOT / "dashboard"
TASKS = DASH / "tasks.json"
LOGF = DASH / "activity_log.json"
OUT = ROOT / "research_ready_dataset"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def update():
    tasks = load_json(TASKS, [])
    logs = load_json(LOGF, [])

    # experiments ledger -> best logloss
    exps, best = [], None
    led = OUT / "experiments.csv"
    if led.exists():
        df = pd.read_csv(led)
        df = df.dropna(subset=["logloss_test"])
        df = df.sort_values("logloss_test")
        ours = df[df["decision"] != "BENCHMARK"]
        best = float(ours["logloss_test"].min()) if len(ours) else None
        exps = df.head(15).fillna("").to_dict("records")

    # db table counts
    db = []
    try:
        con = sqlite3.connect(DB_PATH)
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            db.append([t, con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]])
        wc_played = con.execute(
            "SELECT COUNT(*) FROM wc2026_fixtures WHERE HomeTeamScore IS NOT NULL").fetchone()[0]
        con.close()
    except Exception:
        wc_played = 0

    # elo coverage on the v2 dataset (cheap check via davidson params)
    dav = load_json(OUT / "davidson_params.json", {})
    elo_cov = f"{dav.get('coverage', 0)*100:.0f}%" if dav else "n/a"

    # git
    try:
        run_id = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         cwd=ROOT, text=True).strip()
    except Exception:
        run_id = "-"

    data = {
        "updated": now(), "run_id": run_id, "best_logloss": best,
        "elo_coverage": elo_cov, "wc_played": wc_played,
        "experiments": exps, "tasks": tasks, "db_tables": db, "log": logs[-60:],
    }
    (DASH / "progress_data.js").write_text(
        "window.PROGRESS = " + json.dumps(data, indent=1, default=str) + ";",
        encoding="utf-8")
    print(f"progress_data.js updated ({now()}); best LL={best}; tasks done="
          f"{sum(1 for t in tasks if t['status']=='done')}/{len(tasks)}")


def set_status(task_id: str, status: str, note: str = ""):
    tasks = load_json(TASKS, [])
    hit = False
    for t in tasks:
        if t["id"].lower() == task_id.lower():
            t["status"] = status
            if note:
                t["note"] = note
            hit = True
    if not hit:
        print(f"task {task_id} not found in tasks.json")
        return
    TASKS.write_text(json.dumps(tasks, indent=1), encoding="utf-8")
    add_log(f"{task_id} -> {status}" + (f" ({note})" if note else ""))


def add_log(msg: str):
    logs = load_json(LOGF, [])
    logs.append({"ts": now(), "msg": msg})
    LOGF.write_text(json.dumps(logs, indent=1), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "done":
        set_status(sys.argv[2], "done", " ".join(sys.argv[3:]))
    elif cmd == "start":
        set_status(sys.argv[2], "in_progress", " ".join(sys.argv[3:]))
    elif cmd == "log":
        add_log(" ".join(sys.argv[2:]))
    update()
