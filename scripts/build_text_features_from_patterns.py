#!/usr/bin/env python3
"""
Build text-only features from Extended FP selected patterns.

Reads:
  - transactions.csv (columns: id, items_json)
  - feature_index.csv (from mine_extended_patterns.py; 'items' is pipe-separated)

Outputs (to efpg out_dir):
  - X_textpat.npz            CSR binary [n_docs, n_text_patterns]
  - feature_index_text.csv   token-only patterns + metadata
  - text_feature_coverage.json
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Dict, List, Set
import numpy as np
import pandas as pd

try:
    from scipy.sparse import csr_matrix, save_npz
except Exception:
    raise SystemExit("Please 'pip install scipy' to build sparse matrices.")

# ---------- helpers ----------

def resolve_existing_file(primary: str, candidates: List[str]) -> Path:
    # Only accept actual files; skip blanks and directories
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
        # Prefer an existing efpg tree if found
        if p.exists():
            return p
    return Path("./scripts/output/efpg")

def is_tag(x: str) -> bool:
    return isinstance(x, str) and x.startswith("tag:")

def parse_items_json(s: str) -> List[str]:
    try:
        obj = json.loads(s)
        if isinstance(obj, list):
            return [str(x) for x in obj]
    except Exception:
        pass
    return []

def split_items_pipe(s: str) -> List[str]:
    if not isinstance(s, str):
        return []
    return [x for x in s.split("|") if x]

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="AUTO", help="Path to transactions.csv")
    ap.add_argument("--features", default="AUTO", help="Path to efpg/feature_index.csv")
    ap.add_argument("--out_dir", default="AUTO", help="Output directory for efpg artifacts")
    args = ap.parse_args()

    tx_path = resolve_existing_file(
        args.tx if args.tx != "AUTO" else "",
        [
            "./scripts/output/fpg/transactions.csv",
            "./output/fpg/transactions.csv",
            "output/fpg/transactions.csv",
        ],
    )
    feat_path = resolve_existing_file(
        args.features if args.features != "AUTO" else "",
        [
            "./scripts/output/efpg/feature_index.csv",
            "./output/efpg/feature_index.csv",
            "output/efpg/feature_index.csv",
        ],
    )
    out_dir = default_out_dir(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] Using transactions: {tx_path}")
    print(f"[info] Using feature index: {feat_path}")
    print(f"[info] Output dir: {out_dir}")

    # Load transactions and build token postings
    tx = pd.read_csv(tx_path, encoding="utf-8")
    if not {"id", "items_json"}.issubset(tx.columns):
        raise RuntimeError("transactions.csv must contain columns: id, items_json")

    token_sets: Dict[int, Set[str]] = {}
    token_to_docs: Dict[str, Set[int]] = {}
    for _, r in tx.iterrows():
        doc_id = int(r["id"])
        items = set(parse_items_json(r["items_json"]))
        toks = {it for it in items if not is_tag(it)}
        token_sets[doc_id] = toks
        for t in toks:
            token_to_docs.setdefault(t, set()).add(doc_id)

    # Map possibly non-contiguous doc IDs -> row indices [0..n_docs-1]
    doc_ids = sorted(token_sets.keys())
    row_of_doc = {doc_id: i for i, doc_id in enumerate(doc_ids)}
    n_docs = len(doc_ids)

    # Load selected patterns
    idx = pd.read_csv(feat_path, encoding="utf-8")
    if "items" not in idx.columns:
        raise RuntimeError("feature_index.csv must contain 'items' (pipe-separated)")

    if "pattern_id" not in idx.columns:
        idx["pattern_id"] = np.arange(len(idx), dtype=np.int32)

    # Token-only part of each pattern; drop patterns with no tokens
    idx["token_items"] = idx["items"].astype(str).apply(
        lambda s: [x for x in split_items_pipe(s) if not is_tag(x)]
    )
    idx = idx[idx["token_items"].apply(len) > 0].reset_index(drop=True)

    # Deduplicate identical token patterns (keep highest wracc if available)
    if "wracc" in idx.columns:
        idx.sort_values("wracc", ascending=False, inplace=True)
    seen = set()
    keep_rows = []
    for i, r in idx.iterrows():
        key = tuple(sorted(set(r["token_items"])))
        if key in seen:
            continue
        seen.add(key)
        keep_rows.append(i)
    idx = idx.loc[keep_rows].reset_index(drop=True)

    # Build sparse coverage via postings intersections
    rows, cols, data = [], [], []
    for j, toks in enumerate(idx["token_items"]):
        toks_set = set(toks)
        if not toks_set:
            continue
        postings = None
        for t in toks_set:
            docs = token_to_docs.get(t)
            if not docs:
                postings = set()
                break
            postings = set(docs) if postings is None else postings & docs
            if not postings:
                break
        if not postings:
            continue
        for doc_id in postings:
            rows.append(row_of_doc[doc_id])
            cols.append(j)
            data.append(1)

    X = csr_matrix((data, (rows, cols)), shape=(n_docs, len(idx)), dtype=np.uint8)
    save_npz(out_dir / "X_textpat.npz", X)

    # Save index
    keep_cols = [c for c in ["pattern_id", "class_label", "k", "items", "wracc", "lift", "conf", "ig", "chi2"] if c in idx.columns]
    idx_out = idx[keep_cols + ["token_items"]]
    idx_out.to_csv(out_dir / "feature_index_text.csv", index=False, encoding="utf-8")

    cov = float(X.nnz) / (X.shape[0] * max(X.shape[1], 1)) if X.shape[1] > 0 else 0.0
    (out_dir / "text_feature_coverage.json").write_text(
        json.dumps({"shape": [int(X.shape[0]), int(X.shape[1])], "density": cov}, indent=2),
        encoding="utf-8",
    )
    print(f"[ok] X_textpat.npz shape={X.shape}, density={cov:.4f}")
    print(f"[ok] feature_index_text.csv -> {(out_dir / 'feature_index_text.csv').resolve()}")

if __name__ == "__main__":
    main()