"""
Stage 01 - Download Kaggle datasets.

Downloads and unzips a curated set of public football datasets into
fifa_wc_data/raw/kaggle/<slug>/. Each dataset is checkpointed so reruns skip
what is already present. Failures are logged and skipped, never fatal.
"""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

from common import RAW, get_logger, log_attempt, checkpoint_done, mark_done

log = get_logger("s01_kaggle")

# Kaggle auth: never hard-code the token. It is read from the KAGGLE_API_TOKEN
# env var, or falls back to ~/.kaggle/access_token (the kaggle lib reads either).
if not os.environ.get("KAGGLE_API_TOKEN"):
    _tok = Path.home() / ".kaggle" / "access_token"
    if _tok.exists():
        os.environ["KAGGLE_API_TOKEN"] = _tok.read_text(encoding="utf-8").strip()

KAGGLE_DIR = RAW / "kaggle"
KAGGLE_DIR.mkdir(parents=True, exist_ok=True)

# Curated datasets: (ref, why we want it)
DATASETS = [
    ("martj42/international-football-results-from-1872-to-2017", "all intl results+goalscorers+shootouts"),
    ("patateriedata/all-international-football-results", "intl results kept current"),
    ("abhijitdahatonde/fifa-world-cup-all-dataset", "WC matches/squads/goals"),
    ("evangower/fifa-world-cup", "WC matches + tournaments"),
    ("stefanoleone992/fifa-23-complete-player-dataset", "FIFA 23 player ratings (attrs proxy)"),
    ("stefanoleone992/fifa-22-complete-player-dataset", "FIFA 22 player ratings"),
    ("cashncarry/fifa-worldcup-2026-qualified-teams", "WC2026 qualified teams (if present)"),
]


def _api():
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api


def download(api, ref: str, note: str) -> None:
    slug = ref.split("/")[-1]
    dest = KAGGLE_DIR / slug
    if checkpoint_done("kaggle", ref) and dest.exists() and any(dest.iterdir()):
        log.info(f"skip (cached): {ref}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    try:
        log.info(f"downloading {ref} -- {note}")
        api.dataset_download_files(ref, path=str(dest), unzip=True, quiet=True)
        # some versions leave a zip behind
        for z in dest.glob("*.zip"):
            try:
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(dest)
                z.unlink()
            except Exception:
                pass
        files = [p.name for p in dest.rglob("*") if p.is_file()]
        log.info(f"  -> {len(files)} files: {files[:8]}{'...' if len(files) > 8 else ''}")
        log_attempt("kaggle", ref, "ok", len(files), note)
        mark_done("kaggle", ref)
    except Exception as e:
        msg = str(e).splitlines()[0] if str(e) else repr(e)
        log.warning(f"  FAILED {ref}: {msg}")
        log_attempt("kaggle", ref, "fail", 0, msg)


def main() -> None:
    try:
        api = _api()
    except Exception as e:
        log.error(f"Kaggle auth failed: {e}")
        log_attempt("kaggle", "auth", "fail", 0, str(e))
        return
    for ref, note in DATASETS:
        download(api, ref, note)
    log.info("stage 01 (kaggle) complete")


if __name__ == "__main__":
    sys.exit(main())
