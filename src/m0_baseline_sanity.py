"""
M0 - Baseline sanity train. Proves the dataset trains end-to-end and pins the
numbers every future model must beat.

Models (all sklearn, no new installs):
  1. elo_only   : multinomial logistic on elo_expected_home alone  (the ELO bar)
  2. logreg     : multinomial logistic on all 39 features (median-impute+scale)
  3. histgb     : HistGradientBoostingClassifier (native NaN handling)
  4. ensemble   : 0.5*logreg + 0.5*histgb, isotonic-calibrated per class on val

Eval: log-loss / multiclass Brier / accuracy on the chronological test split,
plus the modern-era (date>=2010) test subset. Writes
research_ready_dataset/baseline_metrics.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from common import ROOT, get_logger

log = get_logger("m0_baseline")
OUT = ROOT / "research_ready_dataset"
CLASSES = ["home_loss", "draw", "home_win"]          # fixed order everywhere


def brier_multi(y_true_idx, proba):
    onehot = np.eye(proba.shape[1])[y_true_idx]
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def calibrate_isotonic(p_val, y_val_idx, p_test):
    """Per-class isotonic on val probs, renormalised."""
    out_val_fit = []
    p_test_cal = np.zeros_like(p_test)
    for k in range(p_val.shape[1]):
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p_val[:, k], (y_val_idx == k).astype(float))
        p_test_cal[:, k] = iso.predict(p_test[:, k])
    p_test_cal = np.clip(p_test_cal, 1e-6, 1)
    return p_test_cal / p_test_cal.sum(axis=1, keepdims=True)


def main():
    df = pd.read_csv(OUT / "classification_dataset.csv", parse_dates=["date"])
    df = df[df["split"].isin(["train", "val", "test"])].copy()
    df = df.dropna(subset=["home_win_draw_loss"])
    y = df["home_win_draw_loss"].map({c: i for i, c in enumerate(CLASSES)}).values

    drop = ["match_id", "date", "team_home", "team_away", "team_id_home",
            "team_id_away", "split", "home_win_draw_loss"]
    feats = [c for c in df.columns if c not in drop]
    X = df[feats].astype(float).values

    tr = df["split"].values == "train"
    va = df["split"].values == "val"
    te = df["split"].values == "test"
    modern_te = te & (df["date"].values >= np.datetime64("2010-01-01"))
    log.info(f"rows train={tr.sum()} val={va.sum()} test={te.sum()} "
             f"(modern test={modern_te.sum()}) features={len(feats)}")

    results = {}

    def evaluate(name, p_test):
        m = {
            "logloss_test": float(log_loss(y[te], p_test, labels=[0, 1, 2])),
            "brier_test": brier_multi(y[te], p_test),
            "acc_test": float(accuracy_score(y[te], p_test.argmax(1))),
        }
        pm = p_test[modern_te[te]] if p_test.shape[0] == te.sum() else None
        if pm is not None and pm.shape[0]:
            m["logloss_test_2010plus"] = float(log_loss(y[modern_te], pm, labels=[0, 1, 2]))
        results[name] = m
        log.info(f"{name:9} | LL {m['logloss_test']:.4f} | Brier {m['brier_test']:.4f} "
                 f"| acc {m['acc_test']:.3f} | LL(2010+) {m.get('logloss_test_2010plus', float('nan')):.4f}")

    # ---- 1. ELO-only bar ----
    elo_col = feats.index("elo_expected_home")
    Xe = X[:, [elo_col]]
    elo_pipe = make_pipeline(SimpleImputer(strategy="median"),
                             LogisticRegression(max_iter=1000))
    elo_pipe.fit(Xe[tr], y[tr])
    evaluate("elo_only", elo_pipe.predict_proba(Xe[te]))

    # ---- 2. logistic on everything ----
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=2000, C=0.5))
    lr.fit(X[tr], y[tr])
    evaluate("logreg", lr.predict_proba(X[te]))

    # ---- 3. hist gradient boosting ----
    gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06,
                                        max_leaf_nodes=63, l2_regularization=1.0,
                                        early_stopping=True, validation_fraction=0.1,
                                        random_state=0)
    gb.fit(X[tr], y[tr])
    evaluate("histgb", gb.predict_proba(X[te]))

    # ---- 4. blended + calibrated ensemble ----
    p_val = 0.5 * lr.predict_proba(X[va]) + 0.5 * gb.predict_proba(X[va])
    p_te = 0.5 * lr.predict_proba(X[te]) + 0.5 * gb.predict_proba(X[te])
    evaluate("blend_raw", p_te)
    evaluate("blend_cal", calibrate_isotonic(p_val, y[va], p_te))

    (OUT / "baseline_metrics.json").write_text(json.dumps(results, indent=2))
    log.info(f"wrote {OUT/'baseline_metrics.json'}")


if __name__ == "__main__":
    main()
