"""
m11_scorelines.py — Scoreline prediction model.

For every WC2026 group-stage match, produces a full score-matrix with:
  - P(h_goals, a_goals) for all 0..6 x 0..6 scorelines
  - Top-10 most likely scorelines
  - Over/under probabilities (1.5, 2.5, 3.5)
  - BTTS (both teams to score)
  - Most likely exact score
  - Expected goals for each side

Method: Dixon-Coles score matrix TILTED to match ensemble W/D/L marginals.
  DC gives realistic scoreline shapes; ensemble gives best-calibrated outcome probs.
  We rescale: home-win cells * k_w, draw cells * k_d, away-win cells * k_l, then renorm.

Outputs:
  artifacts/run_<latest>/scorelines.json
  dashboard/data/scorelines_data.js
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, get_logger
from m4_dixon_coles import lambdas, score_matrix, MAX_G

log = get_logger("m11")
ART = ROOT / "artifacts"
DASH = ROOT / "dashboard" / "data"
HOSTS = {"USA", "Mexico", "Canada"}
DISPLAY_MAX = 7  # show 0..6 goals in the matrix


def tilt_matrix(M: np.ndarray, p_ensemble: list[float]) -> np.ndarray:
    """Rescale DC score matrix so W/D/L marginals match ensemble probs.

    p_ensemble = [p_loss, p_draw, p_win] (class order convention).
    M is (MAX_G+1 x MAX_G+1) where M[h][a] = P(home=h, away=a).
    """
    p_loss_dc = float(np.triu(M, 1).sum())  # home_goals < away_goals
    p_draw_dc = float(np.trace(M))
    p_win_dc = float(np.tril(M, -1).sum())  # home_goals > away_goals

    p_l, p_d, p_w = [max(x, 1e-8) for x in p_ensemble]

    k_l = p_l / max(p_loss_dc, 1e-8)
    k_d = p_d / max(p_draw_dc, 1e-8)
    k_w = p_w / max(p_win_dc, 1e-8)

    T = M.copy()
    n = M.shape[0]
    for h in range(n):
        for a in range(n):
            if h > a:
                T[h, a] *= k_w
            elif h == a:
                T[h, a] *= k_d
            else:
                T[h, a] *= k_l

    s = T.sum()
    if s > 0:
        T /= s
    return T


def extract_scorelines(M: np.ndarray, home: str, away: str, lh: float, la: float) -> dict:
    """Extract scoreline analytics from a (tilted) score matrix."""
    d = DISPLAY_MAX
    top_indices = np.argsort(M.flatten())[::-1]
    top10 = []
    for idx in top_indices[:15]:
        hg, ag = divmod(idx, M.shape[1])
        if hg <= d and ag <= d:
            top10.append({
                "score": f"{hg}-{ag}",
                "home_goals": int(hg),
                "away_goals": int(ag),
                "prob": round(float(M[hg, ag]), 4),
            })
            if len(top10) == 10:
                break

    total_goals_probs = {}
    for hg in range(M.shape[0]):
        for ag in range(M.shape[1]):
            t = hg + ag
            total_goals_probs[t] = total_goals_probs.get(t, 0) + M[hg, ag]

    p_over_15 = sum(v for k, v in total_goals_probs.items() if k >= 2)
    p_over_25 = sum(v for k, v in total_goals_probs.items() if k >= 3)
    p_over_35 = sum(v for k, v in total_goals_probs.items() if k >= 4)

    btts = float(M[1:, 1:].sum())
    clean_home = float(M[:, 0].sum())
    clean_away = float(M[0, :].sum())

    # Most likely exact score
    best_idx = np.argmax(M)
    best_h, best_a = divmod(best_idx, M.shape[1])

    # Matrix for display (0..DISPLAY_MAX)
    display = []
    for hg in range(d + 1):
        row = []
        for ag in range(d + 1):
            row.append(round(float(M[hg, ag]), 4))
        display.append(row)

    return {
        "home": home,
        "away": away,
        "exp_home_goals": round(float(lh), 2),
        "exp_away_goals": round(float(la), 2),
        "most_likely": f"{best_h}-{best_a}",
        "most_likely_prob": round(float(M[best_h, best_a]), 4),
        "top_scorelines": top10,
        "over_1_5": round(float(p_over_15), 4),
        "over_2_5": round(float(p_over_25), 4),
        "over_3_5": round(float(p_over_35), 4),
        "btts": round(float(btts), 4),
        "clean_sheet_home": round(float(clean_home), 4),
        "clean_sheet_away": round(float(clean_away), 4),
        "matrix": display,
    }


def main():
    model = joblib.load(ROOT / "models" / "m4_deploy.pkl")

    # Load latest sim for ensemble W/D/L
    runs = sorted(ART.glob("run_*"))
    if not runs:
        log.error("No simulator runs found. Run m8_simulate first.")
        return
    latest = runs[-1]
    sim = json.loads((latest / "sim_results.json").read_text(encoding="utf-8"))
    match_probs = {m["match_number"]: m for m in sim.get("match_probs", [])}

    results = []
    for mn, mp in sorted(match_probs.items()):
        home, away = mp["home"], mp["away"]
        p_ensemble = mp["p"]  # [loss, draw, win]

        neutral = 0 if home in HOSTS else 1
        try:
            lh, la = lambdas(model, home, away, neutral)
        except KeyError:
            log.warning(f"match {mn}: {home} or {away} not in DC model, skipping")
            continue

        M_dc = score_matrix(lh, la, model["rho"])
        M_tilted = tilt_matrix(M_dc, p_ensemble)
        info = extract_scorelines(M_tilted, home, away, lh, la)
        info["match_number"] = mn
        info["group"] = mp.get("group")
        info["locked"] = mp.get("locked", False)
        results.append(info)

    output = {
        "meta": {
            "as_of": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M"),
            "method": "dixon_coles_tilted_by_ensemble",
            "n_matches": len(results),
            "max_goals_display": DISPLAY_MAX,
        },
        "matches": results,
    }

    # Write to artifacts
    out_path = latest / "scorelines.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    log.info(f"scorelines.json: {len(results)} matches -> {out_path}")

    # Write dashboard JS
    DASH.mkdir(parents=True, exist_ok=True)
    js = DASH / "scorelines_data.js"
    js.write_text("window.SCORELINES = " + json.dumps(output) + ";", encoding="utf-8")
    log.info(f"scorelines_data.js written ({js.stat().st_size:,} bytes)")

    # Summary
    if results:
        top = max(results, key=lambda r: r["most_likely_prob"])
        log.info(f"highest-confidence scoreline: {top['home']} vs {top['away']} = "
                 f"{top['most_likely']} ({top['most_likely_prob']:.1%})")


if __name__ == "__main__":
    main()
