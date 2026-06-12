"""
m6 + m7 - Stacking ensemble with temperature calibration.  (TODO C3)

Holdout-stacking design (no OOF complexity, fully time-honest):
  level-0 fitted on TRAIN  -> predictions on VAL   (meta training material)
  level-0 refit on TRAIN+VAL -> predictions on TEST (honest evaluation)
  meta-LR trained on val_a (first 70% of val), temperature T fitted on val_b.

Level-0 sources:
  davidson  : analytic probs from v2 elo_diff (params from m1 davidson_params.json)
  logreg    : impute+scale+multinomial LR on v2 features
  histgb    : HistGradientBoostingClassifier on v2 features
  dixon     : m4_probs.csv (val era from train-only fit, test era from train+val fit)

Outputs: models/ensemble_v1.pkl (meta + T + deploy-refit level-0), ledger row.
Acceptance: test LL < 0.855 (current best 0.8591).
"""
from __future__ import annotations

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import ROOT, get_logger

log = get_logger("m6_stack")
OUT = ROOT / "research_ready_dataset"
MODELS = ROOT / "models"
CLASSES = ["home_loss", "draw", "home_win"]
BAR = 0.8591


def davidson_probs(elo_diff, neutral, nu, H):
    pi = 10 ** ((elo_diff + H * (1 - neutral)) / 400.0)
    sq = np.sqrt(pi)
    D = pi + 1.0 + nu * sq
    return np.stack([1.0 / D, nu * sq / D, pi / D], axis=1)


def logits(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p[:, 1:] / p[:, [0]])      # 2 cols per model (draw,win vs loss)


def temp_scale(p, T):
    q = np.clip(p, 1e-12, 1) ** (1.0 / T)
    return q / q.sum(axis=1, keepdims=True)


def main():
    df = pd.read_csv(OUT / "classification_dataset_v2.csv", parse_dates=["date"])
    df = df[df["split"].isin(["train", "val", "test"])].dropna(subset=["home_win_draw_loss"])
    df = df.sort_values("date").reset_index(drop=True)
    y = df["home_win_draw_loss"].map({c: i for i, c in enumerate(CLASSES)}).values

    drop = ["match_id", "date", "team_home", "team_away", "team_id_home",
            "team_id_away", "split", "home_win_draw_loss", "tournament", "stage",
            "sample_weight"]
    feats = [c for c in df.columns if c not in drop]
    X = df[feats].astype(float).values
    sw = df["sample_weight"].values

    tr = (df["split"] == "train").values
    va = (df["split"] == "val").values
    te = (df["split"] == "test").values

    # ---- level-0: davidson (analytic, no fitting needed) ----
    dav = json.loads((OUT / "davidson_params.json").read_text())
    p_dav = davidson_probs(df["elo_diff"].values, df["neutral_flag"].values,
                           dav["nu"], dav["home_adv"])

    # ---- level-0: dixon-coles probs (precomputed honestly by m4) ----
    dc = pd.read_csv(OUT / "m4_probs.csv")
    df = df.merge(dc, on="match_id", how="left")
    dc_cov_val = df.loc[va, "dc_p_win"].notna().mean()
    dc_cov_te = df.loc[te, "dc_p_win"].notna().mean()
    log.info(f"DC coverage val {dc_cov_val:.1%} test {dc_cov_te:.1%} (missing -> davidson fallback)")
    p_dc = df[["dc_p_loss", "dc_p_draw", "dc_p_win"]].values
    miss = np.isnan(p_dc).any(axis=1)
    p_dc[miss] = p_dav[miss]

    # ---- level-0: logreg + histgb, two fits ----
    def fit_pair(idx_fit):
        lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                           LogisticRegression(max_iter=2000, C=0.5))
        gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06,
                                            max_leaf_nodes=63, l2_regularization=1.0,
                                            early_stopping=True, validation_fraction=0.1,
                                            random_state=0)
        lr.fit(X[idx_fit], y[idx_fit])
        gb.fit(X[idx_fit], y[idx_fit], sample_weight=sw[idx_fit])
        return lr, gb

    lr_t, gb_t = fit_pair(tr)                  # for val predictions
    lr_tv, gb_tv = fit_pair(tr | va)           # for test predictions

    def level0(idx, lr, gb):
        return np.hstack([
            logits(p_dav[idx]), logits(p_dc[idx]),
            logits(lr.predict_proba(X[idx])), logits(gb.predict_proba(X[idx])),
            df.loc[idx, ["stage_weight", "neutral_flag"]].values,
        ])

    # ---- meta on val_a, temperature on val_b ----
    val_idx = np.where(va)[0]
    cut = int(len(val_idx) * 0.7)
    va_a = np.zeros(len(df), bool); va_a[val_idx[:cut]] = True
    va_b = np.zeros(len(df), bool); va_b[val_idx[cut:]] = True

    Z_va_a = level0(va_a, lr_t, gb_t)
    meta = make_pipeline(SimpleImputer(strategy="median"),
                         LogisticRegression(max_iter=2000, C=1.0))
    meta.fit(Z_va_a, y[va_a])

    p_vb = meta.predict_proba(level0(va_b, lr_t, gb_t))
    res = minimize_scalar(lambda T: log_loss(y[va_b], temp_scale(p_vb, T), labels=[0, 1, 2]),
                          bounds=(0.5, 3.0), method="bounded")
    T = float(res.x)

    # ---- honest test evaluation ----
    p_te_raw = meta.predict_proba(level0(te, lr_tv, gb_tv))
    p_te = temp_scale(p_te_raw, T)
    ll_raw = log_loss(y[te], p_te_raw, labels=[0, 1, 2])
    ll = log_loss(y[te], p_te, labels=[0, 1, 2])
    onehot = np.eye(3)[y[te]]
    brier = float(np.mean(np.sum((p_te - onehot) ** 2, axis=1)))
    acc = float((p_te.argmax(1) == y[te]).mean())
    log.info(f"STACK test LL {ll_raw:.4f} -> {ll:.4f} after T={T:.3f} "
             f"| Brier {brier:.4f} | acc {acc:.3f} | bar {BAR}")

    # ---- deploy refit on ALL labelled data ----
    allm = tr | va | te
    lr_all, gb_all = fit_pair(allm)
    joblib.dump({"meta": meta, "T": T, "lr": lr_all, "gb": gb_all,
                 "feats": feats, "davidson": dav, "classes": CLASSES,
                 "note": "level0 order: davidson, dixon, logreg, histgb + stage,neutral"},
                MODELS / "ensemble_v1.pkl")

    with open(OUT / "experiments.csv", "a", encoding="utf-8") as f:
        f.write(f"m6_stack_cal,{datetime.utcnow():%Y-%m-%d},m6_stack,"
                f"stack(dav+dc+lr+gb)+temp,v2 features,{int(tr.sum())},{ll:.4f},"
                f"{brier:.4f},,{acc:.4f},,{'yes' if ll < BAR else 'no'},"
                f"{'KEEP' if ll < BAR else 'ITERATE'},T={T:.3f} raw={ll_raw:.4f}\n")
    log.info("m6 complete (models/ensemble_v1.pkl)")


if __name__ == "__main__":
    main()
