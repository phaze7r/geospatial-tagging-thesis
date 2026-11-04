#!/usr/bin/env python3
"""
Build rule-aggregate features from token→tag rules (per class).

Inputs:
  - transactions.csv (columns: id, items_json)
  - token_tag_rules_by_class.csv (from summarize_fp_results.py)

Outputs (to efpg out_dir):
  - X_ruleagg.npz            CSR float32 [n_docs, 5 * n_rule_classes]
  - rule_feature_names.json
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
import numpy as np
import pandas as pd

try:
    from scipy.sparse import csr_matrix, save_npz
except Exception:
    raise SystemExit("Please 'pip install scipy' to build sparse matrices.")

def resolve_existing_file(primary: str, candidates: List[str]) -> Path:
    if primary and Path(primary).is_file():
        return Path(primary)
    for c in candidates:
        p = Path(c)
        if p.is_file():
            return p
    raise FileNotFoundError(f"Could not resolve file. Tried: { [primary] + candidates }")

def default_out_dir(user: str | None) -> Path:
    if user and user != "AUTO":
        return Path(user)
    for c in ["./scripts/output/efpg", "./output/efpg", "output/efpg"]:
        p = Path(c)
        if p.exists():
            return p
    return Path("./scripts/output/efpg")

def parse_items_json(s: str) -> List[str]:
    try:
        obj = json.loads(s)
        if isinstance(obj, list):
            return [str(x) for x in obj]
    except Exception:
        pass
    return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="AUTO", help="Path to transactions.csv")
    ap.add_argument("--rules_csv", default="AUTO", help="Path to token_tag_rules_by_class.csv")
    ap.add_argument("--out_dir", default="AUTO", help="Output dir for efpg artifacts")
    ap.add_argument("--min_conf", type=float, default=0.30)
    ap.add_argument("--min_lift", type=float, default=1.05)
    args = ap.parse_args()

    tx_path = resolve_existing_file(
        args.tx if args.tx != "AUTO" else "",
        [
            "./scripts/output/fpg/transactions.csv",
            "./output/fpg/transactions.csv",
            "output/fpg/transactions.csv",
        ],
    )
    rules_path = resolve_existing_file(
        args.rules_csv if args.rules_csv != "AUTO" else "",
        [
            "./scripts/output/fpg_report/token_tag_rules_by_class.csv",
            "./scripts/output/fpg_reports/token_tag_rules_by_class.csv",
            "./output/fpg_report/token_tag_rules_by_class.csv",
            "./output/fpg_reports/token_tag_rules_by_class.csv",
        ],
    )
    out_dir = default_out_dir(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] Using transactions: {tx_path}")
    print(f"[info] Using rules: {rules_path}")
    print(f"[info] Output dir: {out_dir}")

    # Load doc tokens
    tx = pd.read_csv(tx_path, encoding="utf-8")
    if not {"id", "items_json"}.issubset(tx.columns):
        raise RuntimeError("transactions.csv must contain columns: id, items_json")

    tokens_by_doc: Dict[int, Set[str]] = {}
    for _, r in tx.iterrows():
        doc_id = int(r["id"])
        items = set(parse_items_json(r["items_json"]))
        toks = {it for it in items if not str(it).startswith("tag:")}
        tokens_by_doc[doc_id] = toks

    doc_ids = sorted(tokens_by_doc.keys())
    row_of_doc = {doc_id: i for i, doc_id in enumerate(doc_ids)}
    n_docs = len(doc_ids)

    # Load rules
    rf = pd.read_csv(rules_path, encoding="utf-8")
    if "scope" in rf.columns and "class_label" not in rf.columns:
        rf.rename(columns={"scope": "class_label"}, inplace=True)
    required = {"token", "tag", "conf_tag_given_token", "lift", "class_label"}
    if not required.issubset(rf.columns):
        raise SystemExit(f"Rules CSV must include columns: {sorted(required)}")

    rf = rf[(rf["conf_tag_given_token"] >= args.min_conf) & (rf["lift"] >= args.min_lift)].copy()
    if rf.empty:
        X = csr_matrix((n_docs, 0), dtype=np.float32)
        save_npz(out_dir / "X_ruleagg.npz", X)
        (out_dir / "rule_feature_names.json").write_text("[]", encoding="utf-8")
        print("[warn] No rules passed thresholds; wrote empty X_ruleagg.npz with 0 columns.")
        return

    classes = sorted(rf["class_label"].unique().tolist())
    cls_to_idx = {c: i for i, c in enumerate(classes)}

    # Per-class token→(conf, lift) dict
    rules = defaultdict(dict)
    for _, r in rf.iterrows():
        c = r["class_label"]; t = str(r["token"])
        rules[c][t] = (float(r["conf_tag_given_token"]), float(r["lift"]))

    # Feature names: 5 per class
    feature_names = []
    for c in classes:
        for name in ["count", "sum_conf", "sum_lift", "max_conf", "max_lift"]:
            feature_names.append(f"{c}|{name}")
    p = len(feature_names)

    rows, cols, data = [], [], []
    for doc_id in doc_ids:
        toks = tokens_by_doc[doc_id]
        row = row_of_doc[doc_id]
        for c in classes:
            vals = [rules[c][t] for t in toks if t in rules[c]]
            if not vals:
                continue
            confs = [v[0] for v in vals]
            lifts = [v[1] for v in vals]
            feats = [
                float(len(vals)),
                float(sum(confs)),
                float(sum(lifts)),
                float(max(confs)),
                float(max(lifts)),
            ]
            base = 5 * cls_to_idx[c]
            for k, v in enumerate(feats):
                rows.append(row); cols.append(base + k); data.append(v)

    X = csr_matrix((data, (rows, cols)), shape=(n_docs, p), dtype=np.float32)
    save_npz(out_dir / "X_ruleagg.npz", X)
    (out_dir / "rule_feature_names.json").write_text(json.dumps(feature_names, indent=2), encoding="utf-8")
    dens = X.nnz / (X.shape[0] * max(X.shape[1], 1)) if X.shape[1] > 0 else 0.0
    print(f"[ok] X_ruleagg.npz shape={X.shape}, density={dens:.4f}")
    print(f"[ok] Features: {len(feature_names)}")

if __name__ == "__main__":
    main()