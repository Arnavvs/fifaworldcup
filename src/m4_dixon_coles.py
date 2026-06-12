"""
m4 - Dixon-Coles time-decayed goals model.   (Roadmap §4-m4, TODO C1)

Implementation: the standard two-row Poisson-GLM formulation. Every match
contributes two observations:
    home goals ~ exp(mu + home_adv*(1-neutral) + att[home] + def[away])
    away goals ~ exp(mu                        + att[away] + def[home])
fitted with sklearn PoissonRegressor on sparse one-hot attack/defense dummies,
sample-weighted by exponential time decay  w = exp(-xi * days_before_ref).
The Dixon-Coles low-score correction rho is then fitted by 1-D grid MLE on the
tau-adjusted score probabilities.

Teams with < MIN_MATCHES appearances since 1990 are pooled into a
"POOL_<continent>" pseudo-team (continent from dim_team).

Two fits are produced:
  models/m4_eval.pkl    fit on train+val era (date <= 2018-10-11, ref = that date)
                        -> honest TEST evaluation (ledger row)
  models/m4_deploy.pkl  fit on ALL data (ref = today) -> for the 2026 simulator
Acceptance (roadmap): test LL <= 0.92; mean predicted goals within 5% of actual.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import PoissonRegressor

from common import DB_PATH, ROOT, get_logger

log = get_logger("m4_dc")
OUT = ROOT / "research_ready_dataset"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

VAL_END = "2018-10-11"
XI = 0.0019            # / day  (~1-year half-life, roadmap value)
MIN_MATCHES = 30
MAX_G = 10             # score-matrix truncation


# --------------------------------------------------------------------------- #
def load_matches() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    m = pd.read_sql(
        "SELECT match_id, date, home_team, away_team, home_score, away_score, neutral "
        "FROM matches WHERE date >= '1990-01-01' AND home_score IS NOT NULL "
        "ORDER BY date", con)
    con.close()
    tm = pd.read_csv(OUT / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    m["h"] = m["home_team"].map(lambda t: canon.get(t, t))
    m["a"] = m["away_team"].map(lambda t: canon.get(t, t))
    m["home_score"] = m["home_score"].clip(0, MAX_G).astype(int)
    m["away_score"] = m["away_score"].clip(0, MAX_G).astype(int)
    m["date"] = pd.to_datetime(m["date"])
    return m


def continent_map() -> dict:
    d = pd.read_csv(OUT / "dim_team.csv")
    return dict(zip(d["canonical_name"], d["continent"].fillna("Other")))


def pool_names(m: pd.DataFrame, cmap: dict) -> dict:
    counts = pd.concat([m["h"], m["a"]]).value_counts()
    keep = set(counts[counts >= MIN_MATCHES].index)
    return {t: (t if t in keep else f"POOL_{cmap.get(t, 'Other')}")
            for t in counts.index}


# --------------------------------------------------------------------------- #
def fit_dc(m: pd.DataFrame, ref_date: pd.Timestamp, tag: str) -> dict:
    cmap = continent_map()
    pmap = pool_names(m, cmap)
    m = m.copy()
    m["H"] = m["h"].map(pmap)
    m["A"] = m["a"].map(pmap)
    days = (ref_date - m["date"]).dt.days.clip(lower=0)
    w = np.exp(-XI * days.values)

    teams = sorted(set(m["H"]) | set(m["A"]))
    tidx = {t: i for i, t in enumerate(teams)}
    n, T = len(m), len(teams)

    # two rows per match: [attack one-hot | defense one-hot | home_adv flag]
    def rows(att, dfn, home_flag):
        ai = np.array([tidx[t] for t in att])
        di = np.array([tidx[t] for t in dfn])
        r = np.arange(len(att))
        X = sparse.hstack([
            sparse.csr_matrix((np.ones(len(att)), (r, ai)), shape=(len(att), T)),
            sparse.csr_matrix((np.ones(len(att)), (r, di)), shape=(len(att), T)),
            sparse.csr_matrix(home_flag.reshape(-1, 1)),
        ]).tocsr()
        return X

    home_flag = (1 - m["neutral"].values).astype(float)
    Xh = rows(m["H"].values, m["A"].values, home_flag)
    Xa = rows(m["A"].values, m["H"].values, np.zeros(n))
    X = sparse.vstack([Xh, Xa]).tocsr()
    y = np.concatenate([m["home_score"].values, m["away_score"].values])
    sw = np.concatenate([w, w])

    glm = PoissonRegressor(alpha=1e-4, max_iter=400)
    glm.fit(X, y, sample_weight=sw)
    att = glm.coef_[:T]
    dfn = glm.coef_[T:2 * T]
    home_adv = glm.coef_[2 * T]
    mu = glm.intercept_

    # ---- rho grid (tau correction on the four low-score cells) ----
    lam_h = np.exp(mu + home_adv * home_flag + att[[tidx[t] for t in m["H"]]]
                   + dfn[[tidx[t] for t in m["A"]]])
    lam_a = np.exp(mu + att[[tidx[t] for t in m["A"]]]
                   + dfn[[tidx[t] for t in m["H"]]])
    hs, as_ = m["home_score"].values, m["away_score"].values

    def tau(rho):
        t = np.ones(n)
        i00 = (hs == 0) & (as_ == 0); t[i00] = 1 - lam_h[i00] * lam_a[i00] * rho
        i10 = (hs == 1) & (as_ == 0); t[i10] = 1 + lam_a[i10] * rho
        i01 = (hs == 0) & (as_ == 1); t[i01] = 1 + lam_h[i01] * rho
        i11 = (hs == 1) & (as_ == 1); t[i11] = 1 - rho
        return t

    grid = np.arange(-0.2, 0.201, 0.01)
    lls = []
    base = (hs * np.log(lam_h) - lam_h + as_ * np.log(lam_a) - lam_a)
    for r in grid:
        t = tau(r)
        ok = t > 1e-9
        lls.append(np.sum(w[ok] * (base[ok] + np.log(t[ok]))))
    rho = float(grid[int(np.argmax(lls))])

    model = {"teams": tidx, "att": att, "def": dfn, "mu": float(mu),
             "home_adv": float(home_adv), "rho": rho, "xi": XI,
             "ref_date": str(ref_date.date()), "pool_map": pmap,
             "continent_map": cmap}
    joblib.dump(model, MODELS / f"m4_{tag}.pkl")
    log.info(f"[{tag}] fitted: {T} entities, home_adv={home_adv:.3f}, "
             f"rho={rho:+.2f}, mu={mu:.3f}")
    return model


# --------------------------------------------------------------------------- #
def resolve(model: dict, team: str) -> int:
    """canonical team -> param index (own entry, else continent pool)."""
    t = model["pool_map"].get(team)
    if t is None:
        t = f"POOL_{model['continent_map'].get(team, 'Other')}"
    if t not in model["teams"]:
        t = "POOL_Other" if "POOL_Other" in model["teams"] else next(iter(model["teams"]))
    return model["teams"][t]


def lambdas(model: dict, home: str, away: str, neutral: int) -> tuple[float, float]:
    hi, ai = resolve(model, home), resolve(model, away)
    lh = np.exp(model["mu"] + model["home_adv"] * (1 - neutral)
                + model["att"][hi] + model["def"][ai])
    la = np.exp(model["mu"] + model["att"][ai] + model["def"][hi])
    return float(lh), float(la)


_FACT = np.array([float(__import__("math").factorial(k)) for k in range(MAX_G + 1)])


def score_matrix(lh: float, la: float, rho: float) -> np.ndarray:
    g = np.arange(MAX_G + 1)
    ph = np.exp(-lh) * lh ** g / _FACT
    pa = np.exp(-la) * la ** g / _FACT
    M = np.outer(ph, pa)
    M[0, 0] *= max(1 - lh * la * rho, 1e-9)
    M[1, 0] *= 1 + la * rho
    M[0, 1] *= 1 + lh * rho
    M[1, 1] *= 1 - rho
    return M / M.sum()


def wdl_probs(model: dict, home: str, away: str, neutral: int):
    lh, la = lambdas(model, home, away, neutral)
    M = score_matrix(lh, la, model["rho"])
    p_win = float(np.tril(M, -1).sum())   # home rows > away cols
    p_draw = float(np.trace(M))
    p_loss = float(np.triu(M, 1).sum())
    return np.array([p_loss, p_draw, p_win]), lh, la


# --------------------------------------------------------------------------- #
def main():
    m = load_matches()
    log.info(f"matches 1990+: {len(m)}")

    # ---- honest eval fit ----
    tr = m[m["date"] <= VAL_END]
    ev = fit_dc(tr, pd.Timestamp(VAL_END), "eval")
    te = m[m["date"] > VAL_END]
    P = np.zeros((len(te), 3)); LH = np.zeros(len(te)); LA = np.zeros(len(te))
    for i, r in enumerate(te.itertuples(index=False)):
        P[i], LH[i], LA[i] = wdl_probs(ev, r.h, r.a, int(r.neutral))
    gd = te["home_score"].values - te["away_score"].values
    y = np.select([gd < 0, gd == 0], [0, 1], default=2)
    P = np.clip(P, 1e-12, 1)
    ll = float(-np.mean(np.log(P[np.arange(len(y)), y])))
    goal_bias_h = LH.mean() / te["home_score"].mean()
    goal_bias_a = LA.mean() / te["away_score"].mean()
    log.info(f"TEST log-loss {ll:.4f} (n={len(te)}) | goal calib "
             f"home x{goal_bias_h:.3f} away x{goal_bias_a:.3f}")

    # per-match DC probs for the stacker (test era + val era from train-only fit)
    tr_only = m[m["date"] <= "2011-01-17"]
    ev_tr = fit_dc(tr_only, pd.Timestamp("2011-01-17"), "trainonly")
    va = m[(m["date"] > "2011-01-17") & (m["date"] <= VAL_END)]
    rows = []
    for sub, mod in [(va, ev_tr), (te, ev)]:
        for r in sub.itertuples(index=False):
            p, lh, la = wdl_probs(mod, r.h, r.a, int(r.neutral))
            rows.append((r.match_id, *p, lh, la))
    pd.DataFrame(rows, columns=["match_id", "dc_p_loss", "dc_p_draw", "dc_p_win",
                                "dc_lam_h", "dc_lam_a"]) \
        .to_csv(OUT / "m4_probs.csv", index=False)

    # ---- deployment fit on everything ----
    fit_dc(m, pd.Timestamp.today().normalize(), "deploy")

    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"m4_dixon_coles,{datetime.utcnow():%Y-%m-%d},m4_dixon_coles,"
                f"dixon_coles,team att/def + decay xi={XI},{len(tr)},{ll:.4f},,,,,"
                f"{'yes' if ll < 0.8777 else 'no'},KEEP,"
                f"rho fitted; goal calib h x{goal_bias_h:.2f} a x{goal_bias_a:.2f}\n")
    (OUT / "m4_summary.json").write_text(json.dumps(
        {"test_logloss": ll, "n_test": len(te), "goal_calib_home": goal_bias_h,
         "goal_calib_away": goal_bias_a}, indent=2))
    log.info("m4 complete (models/m4_eval.pkl, m4_trainonly.pkl, m4_deploy.pkl)")


if __name__ == "__main__":
    main()
