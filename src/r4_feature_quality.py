"""
PHASE 4 - Feature quality precheck.

For every feature in ml_match_features computes: correlation with target
(Pearson vs goal-difference), mutual information (vs 3-class W/D/L), missing %,
variance, and a leakage-risk flag. Ranks features by a composite signal score.
Writes research_ready_dataset/feature_importance_precheck.csv
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

from common import DB_PATH, ROOT

OUT = ROOT / "research_ready_dataset"

# any feature directly derived from a single rating still pre-match; outcomes excluded
LOW_RISK = "Low (pre-match)"


def main():
    con = sqlite3.connect(DB_PATH)
    fs = pd.read_sql("SELECT * FROM ml_match_features", con)
    m = pd.read_sql("SELECT match_id, home_score, away_score FROM matches", con)
    con.close()

    df = fs.merge(m, on="match_id", how="left")
    df = df.dropna(subset=["home_score", "away_score"]).copy()   # drop future fixtures
    df["goal_diff"] = df["home_score"] - df["away_score"]
    df["wdl"] = np.select([df["goal_diff"] > 0, df["goal_diff"] == 0],
                          [2, 1], default=0)                     # 2=home win,1=draw,0=loss

    feat_cols = [c for c in fs.columns if c not in
                 ("match_id", "date", "team_id_home", "team_id_away",
                  "team_home", "team_away", "tournament", "stage")]

    X = df[feat_cols].astype(float)
    Xi = X.fillna(X.median(numeric_only=True))
    y = df["wdl"].astype(int)

    mi = mutual_info_classif(Xi, y, discrete_features=False, random_state=0)
    mi = pd.Series(mi, index=feat_cols)

    rows = []
    for c in feat_cols:
        corr = np.corrcoef(Xi[c], df["goal_diff"])[0, 1] if Xi[c].std() > 0 else 0.0
        miss = round(100 * X[c].isna().mean(), 2)
        var = float(np.nanvar(X[c]))
        # leakage heuristic: |corr| extremely high would be suspicious; none expected
        risk = "REVIEW (|corr|>0.95)" if abs(corr) > 0.95 else LOW_RISK
        if var == 0:
            risk = "DROP (zero variance)"
        rows.append({"feature": c, "corr_goaldiff": round(corr, 4),
                     "mutual_info": round(float(mi[c]), 5),
                     "missing_pct": miss, "variance": round(var, 4),
                     "leakage_risk": risk})

    res = pd.DataFrame(rows)
    # composite: rank-normalised |corr| + rank-normalised MI
    res["abs_corr"] = res["corr_goaldiff"].abs()
    res["signal_score"] = (res["abs_corr"].rank(pct=True) + res["mutual_info"].rank(pct=True)) / 2
    res = res.sort_values("signal_score", ascending=False).reset_index(drop=True)
    res.insert(0, "rank", res.index + 1)
    res = res.drop(columns=["abs_corr"])
    res.to_csv(OUT / "feature_importance_precheck.csv", index=False, encoding="utf-8")

    print(f"feature_importance_precheck.csv: {len(res)} features ranked "
          f"(on {len(df)} labelled matches)")
    print(res[["rank", "feature", "corr_goaldiff", "mutual_info",
               "missing_pct", "leakage_risk"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
