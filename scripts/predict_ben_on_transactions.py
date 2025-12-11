#!/usr/bin/env python3
"""
Predict with the trained BEN model on a transactions.csv.

Inputs:
  --tx           Path to transactions.csv (columns: id, items_json)
  --efpg_dir     Folder with feature_index_text.csv and label_map.json
  --ben_dir      Folder with model.joblib and feature_names.json
  --rules_csv    (optional) token_tag_rules_by_class.csv to build rule features
  --min_conf     (optional) min confidence for rules (default 0.30)
  --min_lift     (optional) min lift for rules (default 1.05)
  --out_path     Where to write predictions CSV

Outputs:
  - <out_path> (CSV with id, pred_label, pred_id, top3 labels+probs)
  - <out_path>.probs.npy (N x K float32)
  - <out_path>.preds.json (metadata)
"""

from __future__ import annotations
import argparse, json, ast
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import numpy as np
import pandas as pd
from joblib import load

try:
    from scipy.sparse import csr_matrix, hstack
except Exception:
    raise SystemExit("Please 'pip install scipy' to run predictions.")

def parse_items_json(s: str) -> List[str]:
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return []

def is_tag(x: str) -> bool:
    return isinstance(x, str) and x.startswith("tag:")

def parse_list_literal(s: str):
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return None

def build_text_matrix(tx_path: Path, feat_idx_text: Path) -> Tuple[csr_matrix, List[int]]:
    tx = pd.read_csv(tx_path, encoding="utf-8")
    if not {"id", "items_json"}.issubset(tx.columns):
        raise RuntimeError("transactions.csv must contain columns: id, items_json")
    doc_ids = [int(x) for x in tx["id"].tolist()]
    tokens_by_doc: Dict[int, Set[str]] = {}
    for _, r in tx.iterrows():
        did = int(r["id"])
        items = set(parse_items_json(r["items_json"]))
        toks = {it for it in items if not is_tag(it)}
        tokens_by_doc[did] = toks

    idx_text = pd.read_csv(feat_idx_text, encoding="utf-8")
    token_items = []
    for j in range(len(idx_text)):
        li = parse_list_literal(idx_text.loc[j, "token_items"]) if "token_items" in idx_text.columns else None
        token_items.append([t for t in (li or [])])

    rows, cols, data = [], [], []
    row_of_doc = {did: i for i, did in enumerate(doc_ids)}
    for j, toks in enumerate(token_items):
        tset = set(toks)
        if not tset:
            continue
        for did, doc_toks in tokens_by_doc.items():
            if tset.issubset(doc_toks):
                rows.append(row_of_doc[did]); cols.append(j); data.append(1)

    Xp = csr_matrix((data, (rows, cols)), shape=(len(doc_ids), len(token_items)), dtype=np.uint8)
    return Xp, doc_ids

def build_rule_matrix(tx_path: Path, rules_csv: Path, min_conf=0.30, min_lift=1.05):
    tx = pd.read_csv(tx_path, encoding="utf-8")
    tokens_by_doc: Dict[int, Set[str]] = {}
    for _, r in tx.iterrows():
        did = int(r["id"])
        items = set(parse_items_json(r["items_json"]))
        toks = {it for it in items if not is_tag(it)}
        tokens_by_doc[did] = toks
    doc_ids = [int(x) for x in tx["id"].tolist()]
    row_of_doc = {did: i for i, did in enumerate(doc_ids)}
    n_docs = len(doc_ids)

    rf = pd.read_csv(rules_csv, encoding="utf-8")
    if "scope" in rf.columns and "class_label" not in rf.columns:
        rf.rename(columns={"scope": "class_label"}, inplace=True)
    required = {"token", "tag", "conf_tag_given_token", "lift", "class_label"}
    if not required.issubset(rf.columns):
        raise SystemExit(f"Rules CSV must include columns: {sorted(required)}")

    rf = rf[(rf["conf_tag_given_token"] >= min_conf) & (rf["lift"] >= min_lift)].copy()
    if rf.empty:
        return csr_matrix((n_docs, 0), dtype=np.float32), [], doc_ids

    classes = sorted(rf["class_label"].unique().tolist())
    cls_to_idx = {c: i for i, c in enumerate(classes)}

    rules = defaultdict(dict)  # class -> token -> (conf, lift)
    for _, r in rf.iterrows():
        c = r["class_label"]; t = str(r["token"])
        rules[c][t] = (float(r["conf_tag_given_token"]), float(r["lift"]))

    feature_names = []
    for c in classes:
        for name in ["count", "sum_conf", "sum_lift", "max_conf", "max_lift"]:
            feature_names.append(f"{c}|{name}")
    p = len(feature_names)

    rows, cols, data = [], [], []
    for did, toks in tokens_by_doc.items():
        row = row_of_doc[did]
        for c in classes:
            vals = [rules[c][t] for t in toks if t in rules[c]]
            if not vals:
                continue
            confs = [v[0] for v in vals]
            lifts = [v[1] for v in vals]
            feats = [float(len(vals)), float(sum(confs)), float(sum(lifts)), float(max(confs)), float(max(lifts))]
            base = 5 * cls_to_idx[c]
            for k, v in enumerate(feats):
                rows.append(row); cols.append(base + k); data.append(v)

    Xr = csr_matrix((data, (rows, cols)), shape=(n_docs, p), dtype=np.float32)
    return Xr, feature_names, doc_ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", required=True)
    ap.add_argument("--efpg_dir", default="scripts/output/efpg")
    ap.add_argument("--ben_dir", default="scripts/output/ben_run")
    ap.add_argument("--rules_csv", default="")
    ap.add_argument("--min_conf", type=float, default=0.30)
    ap.add_argument("--min_lift", type=float, default=1.05)
    ap.add_argument("--out_path", default="scripts/output/ben_run/predictions.csv")
    args = ap.parse_args()

    tx_path = Path(args.tx)
    efpg = Path(args.efpg_dir)
    ben = Path(args.ben_dir)
    out_csv = Path(args.out_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    model = load(ben / "model.joblib")
    with open(efpg / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2lbl = {v: k for k, v in label_map.items()}

    Xp, doc_ids = build_text_matrix(tx_path, efpg / "feature_index_text.csv")
    names = []
    if (ben / "feature_names.json").exists():
        names = json.loads((ben / "feature_names.json").read_text(encoding="utf-8"))
    else:
        names = [f"PAT_{j}" for j in range(Xp.shape[1])]

    X = Xp
    if args.rules_csv:
        Xr, rule_names, _ = build_rule_matrix(tx_path, Path(args.rules_csv), args.min_conf, args.min_lift)
        X = hstack([Xp, Xr], format="csr")
        names = names + [f"RULE:{n}" for n in rule_names]

    probs = model.predict_proba(X)
    preds = probs.argmax(axis=1)
    pred_labels = [id2lbl[i] for i in preds]

    topk = 3
    top3_idx = np.argsort(-probs, axis=1)[:, :topk]
    top3_labels = [[id2lbl[j] for j in row] for row in top3_idx]
    top3_probs = [[float(probs[i, j]) for j in row] for i, row in enumerate(top3_idx)]

    rows = []
    for i, did in enumerate(doc_ids):
        rows.append({
            "id": did,
            "pred_id": int(preds[i]),
            "pred_label": pred_labels[i],
            "top3_labels": "|".join(top3_labels[i]),
            "top3_probs": "|".join(f"{p:.4f}" for p in top3_probs[i]),
            "max_prob": float(np.max(probs[i])),
        })
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8")

    np.save(out_csv.with_suffix(".probs.npy"), probs.astype(np.float32))
    meta = {"n_docs": len(doc_ids), "n_classes": len(id2lbl), "out_csv": str(out_csv)}
    out_csv.with_suffix(".preds.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[ok] Wrote predictions -> {out_csv.resolve()}")

if __name__ == "__main__":
    main()