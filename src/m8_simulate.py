"""
m8 - WC2026 Monte-Carlo tournament simulator.  (Roadmap §6, TODO C4)

Engine: Dixon-Coles deploy fit (models/m4_deploy.pkl) gives each pairing an
11x11 score matrix; outcomes are sampled per simulation. Hosts (USA/Mexico/
Canada) receive home advantage; all other matches are neutral.

Format: 12 groups of 4 -> top 2 + 8 best thirds -> R32 using the feed's slot
codes ('1A','2B','3ABCDF' = third from allowed groups, assigned by
most-constrained-first matching). R16+ pairing uses sequential winner pairing
(v1 approximation, flagged in meta). Knockout draws -> ET (Poisson lambda/3)
-> penalties (0.5 +/- 0.03 by ELO edge from elo_current).

Played matches (scores in wc2026_fixtures) are LOCKED in every simulation.

Outputs:
  artifacts/run_<ts>/sim_results.json   (+ copy to dashboard/data/)
  artifacts/prediction_history.csv      (champion-prob snapshot appended)
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from common import DB_PATH, ROOT, get_logger
from m4_dixon_coles import lambdas, score_matrix, MAX_G

log = get_logger("m8_sim")
N_SIMS = 50_000
SEED = 2026
HOSTS = {"USA", "Mexico", "Canada"}
ART = ROOT / "artifacts"
DASH = ROOT / "dashboard" / "data"

# ELO form blend: weight on current ELO vs recent-form ELO
ELO_FORM_BLEND = 0.15  # 15% recent-form, 85% current


def load():
    con = sqlite3.connect(DB_PATH)
    fx = pd.read_sql("SELECT * FROM wc2026_fixtures ORDER BY MatchNumber", con)
    elo = dict(pd.read_sql("SELECT team, elo FROM elo_current", con).values)
    con.close()
    tm = pd.read_csv(ROOT / "research_ready_dataset" / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    fx["h"] = fx["HomeTeam"].map(lambda t: canon.get(str(t), str(t)))
    fx["a"] = fx["AwayTeam"].map(lambda t: canon.get(str(t), str(t)))
    model = joblib.load(ROOT / "models" / "m4_deploy.pkl")
    return fx, elo, model


def compute_recent_form_elo(team: str, n_matches: int = 10) -> float:
    """Compute a recent-form ELO from the last N matches (2024-2026)."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT e.elo_home_pre, e.elo_away_pre, m.home_team, m.home_score, m.away_score
        FROM matches m
        JOIN elo_match e ON m.match_id = e.match_id
        WHERE (m.home_team = ? OR m.away_team = ?)
          AND m.date >= '2024-01-01'
          AND m.home_score IS NOT NULL
        ORDER BY m.date DESC
        LIMIT ?
    """, (team, team, n_matches)).fetchall()
    con.close()
    if not rows:
        return None
    # Average of pre-match ELOs for this team
    vals = []
    for eh, ea, ht, hs, aws in rows:
        if ht == team:
            vals.append(float(eh))
        else:
            vals.append(float(ea))
    return np.mean(vals) if vals else None


def blend_elo(elo_current: float, recent_form: float | None) -> float:
    """Blend current ELO with recent-form ELO."""
    if recent_form is None:
        return elo_current
    return (1 - ELO_FORM_BLEND) * elo_current + ELO_FORM_BLEND * recent_form


def sample_scores(M, n, rng):
    flat = M.flatten()
    idx = rng.choice(len(flat), size=n, p=flat / flat.sum())
    return idx // (MAX_G + 1), idx % (MAX_G + 1)        # (home, away) goals


def wdl_from_matrix(M):
    return float(np.triu(M, 1).sum()), float(np.trace(M)), float(np.tril(M, -1).sum())
    # (p_away_win? careful) -- see note in simulate(): rows=home goals, cols=away.


def _load_host_bonus() -> float:
    try:
        host_params = json.loads((ROOT / "research_ready_dataset" / "host_bonus_params.json").read_text())
        return host_params.get("host_bonus", 0.0)
    except Exception:
        return 0.0


def match_matrix(model, home, away, host_bonus=0.0):
    neutral = 0 if home in HOSTS else 1
    lh, la = lambdas(model, home, away, neutral)
    if home in HOSTS and host_bonus != 0.0:
        # Apply host bonus to home lambda (adds in log-space)
        lh = lh * np.exp(host_bonus / 400.0)
    return score_matrix(lh, la, model["rho"]), lh, la


def main():
    rng = np.random.default_rng(SEED)
    fx, elo, model = load()
    host_bonus = _load_host_bonus()
    log.info(f"Host bonus: {host_bonus:.1f} ELO points")
    groups = sorted(fx.loc[fx["Group"].notna(), "Group"].unique())
    gteams = {g: sorted(set(fx.loc[fx["Group"] == g, "h"]) | set(fx.loc[fx["Group"] == g, "a"]))
              for g in groups}
    teams = sorted({t for ts in gteams.values() for t in ts})
    log.info(f"groups={len(groups)} teams={len(teams)} sims={N_SIMS}")

    # ---------------- group stage ----------------
    gfx = fx[fx["RoundNumber"] <= 3]
    match_probs, hs_all, as_all = [], {}, {}
    chaos_H = 0.0
    surprisal = np.zeros(N_SIMS)
    for r in gfx.itertuples(index=False):
        M, lh, la = match_matrix(model, r.h, r.a, host_bonus)
        # rows = home goals, cols = away goals
        p_win = float(np.tril(M, -1).sum())   # home > away
        p_draw = float(np.trace(M))
        p_loss = float(np.triu(M, 1).sum())
        if pd.notna(r.HomeTeamScore):          # locked real result
            hs = np.full(N_SIMS, int(r.HomeTeamScore))
            as_ = np.full(N_SIMS, int(r.AwayTeamScore))
            locked = True
        else:
            hs, as_ = sample_scores(M, N_SIMS, rng)
            locked = False
        hs_all[r.MatchNumber], as_all[r.MatchNumber] = hs, as_
        p3 = np.array([p_loss, p_draw, p_win])
        chaos_H += float(-(p3 * np.log(p3)).sum())
        out = np.select([hs > as_, hs == as_], [2, 1], default=0)
        surprisal += -np.log(np.clip(p3[out], 1e-12, 1))
        match_probs.append({
            "match_number": int(r.MatchNumber), "round": int(r.RoundNumber),
            "group": r.Group, "home": r.h, "away": r.a, "locked": locked,
            "p": [round(p_loss, 4), round(p_draw, 4), round(p_win, 4)],
            "exp_goals": [round(lh, 2), round(la, 2)],
        })

    # standings per sim
    pts = {g: np.zeros((N_SIMS, 4), dtype=np.int16) for g in groups}
    gd = {g: np.zeros((N_SIMS, 4), dtype=np.int16) for g in groups}
    gfor = {g: np.zeros((N_SIMS, 4), dtype=np.int16) for g in groups}
    for r in gfx.itertuples(index=False):
        g = r.Group
        ih, ia = gteams[g].index(r.h), gteams[g].index(r.a)
        hs, as_ = hs_all[r.MatchNumber], as_all[r.MatchNumber]
        pts[g][:, ih] += np.where(hs > as_, 3, np.where(hs == as_, 1, 0)).astype(np.int16)
        pts[g][:, ia] += np.where(as_ > hs, 3, np.where(hs == as_, 1, 0)).astype(np.int16)
        gd[g][:, ih] += (hs - as_).astype(np.int16); gd[g][:, ia] += (as_ - hs).astype(np.int16)
        gfor[g][:, ih] += hs.astype(np.int16);       gfor[g][:, ia] += as_.astype(np.int16)

    rank = {}      # rank[g][:, pos] = team index
    for g in groups:
        key = (pts[g].astype(np.int64) * 10**8 + (gd[g] + 200).astype(np.int64) * 10**4
               + gfor[g] + rng.integers(0, 9, (N_SIMS, 4)))
        rank[g] = np.argsort(-key, axis=1)

    # best thirds: rank 12 third-placed teams, take 8
    tkey = np.zeros((N_SIMS, len(groups)), dtype=np.int64)
    tteam = np.zeros((N_SIMS, len(groups)), dtype=np.int32)   # global team idx
    t_glob = {t: i for i, t in enumerate(teams)}
    for j, g in enumerate(groups):
        third = rank[g][:, 2]
        rows = np.arange(N_SIMS)
        tkey[:, j] = (pts[g][rows, third].astype(np.int64) * 10**8
                      + (gd[g][rows, third] + 200).astype(np.int64) * 10**4
                      + gfor[g][rows, third] + rng.integers(0, 9, N_SIMS))
        tteam[:, j] = [t_glob[gteams[g][k]] for k in third]
    third_order = np.argsort(-tkey, axis=1)        # group indices best->worst

    # ---------------- knockout ----------------
    r32 = fx[fx["RoundNumber"] == 4].sort_values("MatchNumber")
    slots = [(r.MatchNumber, str(r.HomeTeam), str(r.AwayTeam)) for r in r32.itertuples(index=False)]
    gi = {g[-1]: g for g in groups}                # 'A' -> 'Group A'

    def resolve_slot(code, sim_thirds_assign, s):
        code = code.strip()
        if code[0] in "12" and len(code) == 2:
            g = gi[code[1]]
            pos = int(code[0]) - 1
            return gteams[g][rank[g][s, pos]]
        return sim_thirds_assign.get(code)          # third slot

    # per-sim third assignment: most-constrained-first greedy
    third_codes = [c for _, h, a in slots for c in (h, a) if c.startswith("3")]
    champion = np.zeros(len(teams), dtype=np.int64)
    reach = {rd: np.zeros(len(teams), dtype=np.int64) for rd in
             ["r32", "r16", "qf", "sf", "final", "champion"]}
    # Blend current ELO with recent-form ELO (last 10 matches, 2024-2026)
    elo_arr = {}
    for t in teams:
        current = elo.get(t, 1500.0)
        recent = compute_recent_form_elo(t, n_matches=10)
        blended = blend_elo(current, recent)
        elo_arr[t] = blended
        if recent is not None:
            log.debug(f"{t}: current={current:.0f} recent={recent:.0f} blended={blended:.0f}")
    log.info(f"ELO blended with {ELO_FORM_BLEND*100:.0f}% recent-form weight for {len(teams)} teams")
    pair_cache: dict[tuple, np.ndarray] = {}

    def ko_winner(home, away, s_rng):
        key = (home, away)
        if key not in pair_cache:
            M, _, _ = match_matrix(model, home, away, host_bonus)
            pair_cache[key] = M
        M = pair_cache[key]
        hs, as_ = sample_scores(M, 1, s_rng)
        if hs[0] != as_[0]:
            return home if hs[0] > as_[0] else away
        lh, la = lambdas(model, home, away, 0 if home in HOSTS else 1)
        # Apply host bonus to extra time lambda
        if home in HOSTS:
            lh = lh * np.exp(host_bonus / 400.0)
        eh, ea = s_rng.poisson(lh / 3), s_rng.poisson(la / 3)
        if eh != ea:
            return home if eh > ea else away
        # Fitted penalty model from 572 shootouts (TASK 2 PENS)
        # p_higher = sigmoid(0.0185 + 0.6265 * |elo_diff|/400)
        # Add host_bonus to ELO diff for host nations
        effective_elo_diff = elo_arr[home] - elo_arr[away]
        if home in HOSTS:
            effective_elo_diff += host_bonus
        z = 0.0185 + 0.6265 * abs(effective_elo_diff) / 400.0
        p_higher = 1.0 / (1.0 + np.exp(-z))
        p_home = p_higher if effective_elo_diff > 0 else (1.0 - p_higher)
        return home if s_rng.random() < p_home else away

    log.info("running knockout sims...")
    for s in range(N_SIMS):
        qual_groups = third_order[s, :8]            # group idxs whose third advances
        qual_letters = {groups[j][-1]: teams[tteam[s, j]] for j in qual_groups}
        # assign thirds to slots, most constrained first
        assign = {}
        used = set()
        for code in sorted(set(third_codes), key=lambda c: len(c)):
            for L in code[1:]:
                if L in qual_letters and L not in used:
                    assign[code] = qual_letters[L]; used.add(L); break
            else:                                   # fallback: any unused qualifier
                for L, t in qual_letters.items():
                    if L not in used:
                        assign[code] = t; used.add(L); break
        cur = []
        for _, hcode, acode in slots:
            h = resolve_slot(hcode, assign, s)
            a = resolve_slot(acode, assign, s)
            cur.append((h, a))
        for h, a in cur:
            reach["r32"][t_glob[h]] += 1; reach["r32"][t_glob[a]] += 1
        rd_names = ["r16", "qf", "sf", "final"]
        ri = 0
        while len(cur) > 1:
            winners = [ko_winner(h, a, rng) for h, a in cur]
            rd = rd_names[min(ri, 3)]
            for w in winners:
                reach[rd][t_glob[w]] += 1
            cur = [(winners[i], winners[i + 1]) for i in range(0, len(winners) - 1, 2)]
            ri += 1
        champ = ko_winner(*cur[0], rng)
        reach["champion"][t_glob[champ]] += 1
        champion[t_glob[champ]] += 1

    # ---------------- outputs ----------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    run_dir = ART / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    DASH.mkdir(parents=True, exist_ok=True)

    def probs(arr):
        return {teams[i]: round(float(arr[i]) / N_SIMS, 4)
                for i in np.argsort(-arr) if arr[i] > 0}

    exp_tables = {}
    for g in groups:
        rows = []
        for k, t in enumerate(gteams[g]):
            p_win_g = float((rank[g][:, 0] == k).mean())
            p_adv = float(((rank[g][:, 0] == k) | (rank[g][:, 1] == k)).mean()
                          ) + float(((rank[g][:, 2] == k)
                                     & np.isin(np.full(N_SIMS, groups.index(g)),
                                               third_order[:, :8].T).any(0)).mean() * 0
                                    )  # third-adv added below
            rows.append({"team": t, "exp_pts": round(float(pts[g][:, k].mean()), 2),
                         "p_win_group": round(p_win_g, 4), "p_top2": round(p_adv, 4)})
        exp_tables[g] = rows

    locked_n = int(fx["HomeTeamScore"].notna().sum())
    out = {
        "meta": {"n_sims": N_SIMS, "seed": SEED, "as_of": ts,
                 "engine": "dixon_coles_deploy", "locked_matches": locked_n,
                 "approximations": ["R16+ pairing = sequential winner pairing",
                                     "thirds->slots greedy most-constrained-first",
                                     "group tiebreak skips head-to-head (pts/GD/GF/random)"]},
        "champion": probs(reach["champion"]),
        "reach_final": probs(reach["final"]), "reach_sf": probs(reach["sf"]),
        "reach_qf": probs(reach["qf"]), "reach_r16": probs(reach["r16"]),
        "reach_r32": probs(reach["r32"]),
        "group_tables_expected": exp_tables,
        "match_probs": match_probs,
        "chaos": {"expected_total_surprisal_H": round(chaos_H, 2),
                  "sim_surprisal_p10": round(float(np.percentile(surprisal, 10)), 2),
                  "sim_surprisal_p50": round(float(np.percentile(surprisal, 50)), 2),
                  "sim_surprisal_p90": round(float(np.percentile(surprisal, 90)), 2)},
    }
    (run_dir / "sim_results.json").write_text(json.dumps(out, indent=1))
    shutil.copy(run_dir / "sim_results.json", DASH / "sim_results.json")
    # JS wrapper so dashboard pages work from file:// (fetch of local json is CORS-blocked)
    (ROOT / "dashboard" / "sim_data.js").write_text(
        "window.SIM = " + json.dumps(out) + ";", encoding="utf-8")

    hist = ART / "prediction_history.csv"
    new = not hist.exists()
    with open(hist, "a", encoding="utf-8") as f:
        if new:
            f.write("ts,kind,team,prob\n")
        for t, p in out["champion"].items():
            f.write(f"{ts},CHAMPION,{t},{p}\n")

    top = list(out["champion"].items())[:10]
    log.info("TOP-10 CHAMPION ODDS: " + ", ".join(f"{t} {p:.1%}" for t, p in top))
    log.info(f"m8 complete -> {run_dir}")


if __name__ == "__main__":
    main()
