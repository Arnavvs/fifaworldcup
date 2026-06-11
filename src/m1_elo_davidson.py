"""
m1 - Per-match ELO rebuild + Davidson draw baseline.   (Roadmap §4-m1)

Fixes the audit's #1 defect: year-end ELO joined onto only ~17-25% of modern
matches. Here ELO is computed from our own complete `matches` table, so every
match gets a true PRE-MATCH rating for both sides (100% coverage by
construction), plus a rolling ELO trend. Outputs:

  DB table  elo_match    (match_id, elo_home_pre, elo_away_pre, elo_diff_pre,
                          elo_trend_home, elo_trend_away, k_used)
  DB table  elo_current  (team, elo, n_matches, last_date)  -- for 2026 sims
  research_ready_dataset/davidson_params.json  (nu, home_adv, train NLL)
  ledger row in experiments.csv

ELO spec (roadmap §4-m1):
  R' = R + K*G*(W - W_e),  W_e = 1/(1+10^(-dr/400)),  dr = R_h - R_a + 100*home
  K: 60 WC finals, 50 continental finals, 40 qualifiers/Nations League,
     20 friendlies, 30 other.  G: 1 (margin<=1), 1.5 (=2), (11+margin)/8 (>=3).
Davidson (1970) W/D/L from ratings:
  pi = 10^((Rh - Ra + H*(1-neutral))/400)
  D = pi + 1 + nu*sqrt(pi);  p_home = pi/D; p_away = 1/D; p_draw = nu*sqrt(pi)/D
  (nu, H) fitted by MLE on the train era only; evaluated on the test era.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict, deque
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from common import DB_PATH, ROOT, get_logger

log = get_logger("m1_elo")
OUT = ROOT / "research_ready_dataset"

TRAIN_END = "2011-01-17"   # split boundaries verified in PROJECT_STATUS.md §3
VAL_END = "2018-10-11"


def k_factor(comp: str) -> int:
    c = (comp or "").lower()
    if "fifa world cup" in c and "qual" not in c:
        return 60
    if any(x in c for x in ("euro", "copa am", "africa cup", "african cup",
                            "gold cup", "asian cup", "confederations", "oceania nations")) \
            and "qual" not in c:
        return 50
    if "qual" in c or "nations league" in c:
        return 40
    if "friendly" in c:
        return 20
    return 30


def goal_mult(margin: int) -> float:
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11 + margin) / 8.0


def build_elo(con) -> pd.DataFrame:
    m = pd.read_sql(
        "SELECT match_id, date, competition, home_team, away_team, "
        "home_score, away_score, neutral FROM matches ORDER BY date, match_id", con)
    # canonical names so e.g. West Germany -> Germany keeps rating continuity
    tm = pd.read_csv(OUT / "team_mapping.csv")
    canon = dict(zip(tm["raw_name"], tm["canonical_name"]))
    m["h"] = m["home_team"].map(lambda t: canon.get(t, t))
    m["a"] = m["away_team"].map(lambda t: canon.get(t, t))

    R: dict[str, float] = defaultdict(lambda: 1500.0)
    hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=6))  # last 6 pre-elos
    nmatch: dict[str, int] = defaultdict(int)
    last_date: dict[str, str] = {}
    rows = []
    for r in m.itertuples(index=False):
        eh, ea = R[r.h], R[r.a]
        # trend = current pre-elo minus pre-elo 5 of own matches ago
        th = eh - hist[r.h][0] if len(hist[r.h]) == 6 else np.nan
        ta = ea - hist[r.a][0] if len(hist[r.a]) == 6 else np.nan
        k = k_factor(r.competition)
        rows.append((r.match_id, round(eh, 1), round(ea, 1), round(eh - ea, 1),
                     None if np.isnan(th) else round(th, 1),
                     None if np.isnan(ta) else round(ta, 1), k))
        hist[r.h].append(eh)
        hist[r.a].append(ea)
        if pd.notna(r.home_score) and pd.notna(r.away_score):
            dr = eh - ea + (0 if r.neutral else 100)
            we = 1.0 / (1.0 + 10 ** (-dr / 400.0))
            hs, as_ = int(r.home_score), int(r.away_score)
            w = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
            g = goal_mult(abs(hs - as_))
            delta = k * g * (w - we)
            R[r.h] = eh + delta
            R[r.a] = ea - delta
            nmatch[r.h] += 1
            nmatch[r.a] += 1
            last_date[r.h] = last_date[r.a] = r.date

    elo_match = pd.DataFrame(rows, columns=[
        "match_id", "elo_home_pre", "elo_away_pre", "elo_diff_pre",
        "elo_trend_home", "elo_trend_away", "k_used"])
    cur = pd.DataFrame([(t, round(v, 1), nmatch[t], last_date.get(t)) for t, v in R.items()],
                       columns=["team", "elo", "n_matches", "last_date"]) \
        .sort_values("elo", ascending=False)
    return m, elo_match, cur


def davidson_nll(params, dr, y):
    """params=(nu, H); dr = Rh-Ra (pre, no home adv); y in {0 loss,1 draw,2 win}."""
    nu, H = params
    if nu <= 0:
        return 1e9
    pi = 10 ** ((dr + H) / 400.0)
    sq = np.sqrt(pi)
    D = pi + 1.0 + nu * sq
    p = np.stack([1.0 / D, nu * sq / D, pi / D], axis=1)  # [loss, draw, win]
    p = np.clip(p, 1e-12, 1)
    return -np.mean(np.log(p[np.arange(len(y)), y]))


def main():
    con = sqlite3.connect(DB_PATH)
    m, elo_match, cur = build_elo(con)
    elo_match.to_sql("elo_match", con, if_exists="replace", index=False)
    cur.to_sql("elo_current", con, if_exists="replace", index=False)
    con.commit()
    cov = elo_match["elo_diff_pre"].notna().mean()
    log.info(f"elo_match: {len(elo_match)} rows, coverage {cov:.1%}; "
             f"top-5 current: {cur.head(5)[['team','elo']].values.tolist()}")

    # ---- Davidson fit (train era) + test-era evaluation ----
    full = m.merge(elo_match[["match_id", "elo_diff_pre"]], on="match_id")
    full = full.dropna(subset=["home_score", "away_score"])
    full["home_adv"] = np.where(full["neutral"] == 1, 0.0, 1.0)
    gd = full["home_score"] - full["away_score"]
    y = np.select([gd < 0, gd == 0], [0, 1], default=2)

    tr = full["date"] <= TRAIN_END
    te = full["date"] > VAL_END
    # home adv applies only when not neutral -> fold into dr per-row during fit
    def nll_with_neutral(params, sub, ysub):
        nu, H = params
        dr = sub["elo_diff_pre"].values + H * sub["home_adv"].values
        return davidson_nll((nu, 0.0), dr, ysub)

    res = minimize(nll_with_neutral, x0=[0.9, 80.0],
                   args=(full[tr], y[tr.values]), method="Nelder-Mead")
    nu, H = res.x
    test_ll = nll_with_neutral((nu, H), full[te], y[te.values])
    train_ll = res.fun
    log.info(f"Davidson: nu={nu:.3f} home_adv={H:.0f} | train NLL {train_ll:.4f} "
             f"| TEST log-loss {test_ll:.4f} (n={int(te.sum())})")

    (OUT / "davidson_params.json").write_text(json.dumps(
        {"nu": nu, "home_adv": H, "train_nll": train_ll, "test_logloss": test_ll,
         "fitted": datetime.utcnow().isoformat(), "coverage": cov}, indent=2))

    # ledger
    ledger = OUT / "experiments.csv"
    if not ledger.exists():
        ledger.write_text("exp_id,date,module,model,features_desc,n_train,logloss_test,"
                          "brier_test,rps_test,acc_test,ece_test,beats_baseline,decision,notes\n")
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(f"m1_davidson,{datetime.utcnow():%Y-%m-%d},m1_elo_davidson,"
                f"elo_davidson,per-match elo only,{int(tr.sum())},{test_ll:.4f},,,,,"
                f"{'yes' if test_ll < 1.0397 else 'no'},KEEP,"
                f"nu={nu:.3f} H={H:.0f} coverage={cov:.3f}\n")
    con.close()
    log.info("m1 complete")


if __name__ == "__main__":
    main()
