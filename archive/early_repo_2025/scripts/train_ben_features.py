#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import load_npz, hstack
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report, f1_score, accuracy_score, confusion_matrix

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--efpg_dir", default="./output/efpg")
    ap.add_argument("--use_ruleagg", type=str, default="true")
    ap.add_argument("--out_dir", default="./output/ben_run")
    args = ap.parse_args()

    use_rules = args.use_ruleagg.strip().lower() in ("1","true","yes","y")
    d = Path(args.efpg_dir); out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    Xp = load_npz(d / "X_textpat.npz")
    y = np.load(d / "y.npy")
    with open(d / "label_map.json","r",encoding="utf-8") as f:
        lbl = json.load(f)
    id2lbl = {v:k for k,v in lbl.items()}

    names = [f"PAT_{i}" for i in range(Xp.shape[1])]
    X = Xp
    if use_rules and (d / "X_ruleagg.npz").exists():
        Xr = load_npz(d / "X_ruleagg.npz")
        X = hstack([Xp, Xr], format="csr")
        with open(d / "rule_feature_names.json","r",encoding="utf-8") as f:
            rule_names = json.load(f)
        names.extend(rule_names)

    # Grid search (macro-F1)
    grid = [(C,l1) for C in [0.2,0.5,1.0,2.0,5.0] for l1 in [0.3,0.5,0.7,0.9]]
    best = None
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for C,l1 in grid:
        scores = []
        for tr, te in skf.split(X, y):
            clf = LogisticRegression(
                penalty="elasticnet", solver="saga", l1_ratio=l1, C=C,
                max_iter=4000, n_jobs=-1, class_weight="balanced", multi_class="multinomial", verbose=0
            )
            clf.fit(X[tr], y[tr])
            yhat = clf.predict(X[te])
            scores.append(f1_score(y[te], yhat, average="macro"))
        mean_f1 = float(np.mean(scores))
        if not best or mean_f1 > best["f1"]:
            best = {"C":C, "l1":l1, "f1":mean_f1}

    # Fit on full data with best params
    C, l1 = best["C"], best["l1"]
    clf = LogisticRegression(
        penalty="elasticnet", solver="saga", l1_ratio=l1, C=C,
        max_iter=6000, n_jobs=-1, class_weight="balanced", multi_class="multinomial", verbose=0
    )
    clf.fit(X, y)
    yhat = clf.predict(X)
    rep = classification_report(y, yhat, target_names=[id2lbl[i] for i in range(len(id2lbl))], zero_division=0, digits=3)
    cm = confusion_matrix(y, yhat)

    # Save
    (out / "classification_report.txt").write_text(rep, encoding="utf-8")
    pd.DataFrame(cm, index=[id2lbl[i] for i in range(len(id2lbl))], columns=[id2lbl[i] for i in range(len(id2lbl))]).to_csv(out / "confusion_matrix.csv", encoding="utf-8")
    (out / "best_params.json").write_text(json.dumps(best, indent=2), encoding="utf-8")

    # Non-zero features per class
    coefs = clf.coef_  # [n_classes, n_features]
    rows = []
    for ci in range(coefs.shape[0]):
        cls = id2lbl[ci]
        w = coefs[ci]
        nz = np.where(w != 0)[0]
        tops = sorted([(int(j), float(w[j])) for j in nz], key=lambda x: -abs(x[1]))
        for rank,(j,val) in enumerate(tops,1):
            rows.append({"class_label": cls, "rank": rank, "feat_idx": j, "weight": val, "feature_name": names[j]})
    pd.DataFrame(rows).to_csv(out / "selected_features_by_class.csv", index=False, encoding="utf-8")

    print("[ok] BEN-like training complete")
    print("[ok] Best params:", best)
    print("[ok] Report ->", (out / "classification_report.txt").resolve())

if __name__ == "__main__":
    main()