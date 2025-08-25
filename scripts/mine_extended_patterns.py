#!/usr/bin/env python3
"""
Extended FP-Growth post-processing:
- Read transactions (items per doc) + mined itemsets (per class)
- Compute discriminative metrics per class:
  support (in/out class), confidence, lift, growth rate, WRAcc, odds ratio,
  chi-square (p-value), and mutual information (information gain)
- Select top patterns per class with optional "mixed" constraint (token + tag:*),
  size limits, and support floors
- Build BEN-ready sparse feature matrix: X (docs × patterns), y, label map

Usage:
  cd geospatial-tagging-thesis/scripts
  python mine_extended_patterns.py \
      --tx ./output/fpg/transactions.csv \
      --itemsets ./output/fpg/fpg_by_class_itemsets.csv \
      --out_dir ./output/efpg \
      --require_mixed true \
      --min_support_total 0.01 \
      --max_len 3 \
      --top_k_per_class 200

Notes:
- If you don't have fpg_by_class_itemsets.csv, you can pass the report file
  ./output/fpg_report/mixed_itemsets_by_class.csv instead via --itemsets.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd

# Optional SciPy for chi-square and sparse output
HAVE_SCIPY = True
try:
    from scipy.sparse import csr_matrix, save_npz
    from scipy.stats import chi2_contingency
except Exception:
    HAVE_SCIPY = False
    csr_matrix = None
    save_npz = None
    chi2_contingency = None


def split_items_pipe(s: str) -> List[str]:
    if not isinstance(s, str):
        return []
    return [x for x in s.split("|") if x]


def is_tag_item(it: str) -> bool:
    return isinstance(it, str) and it.startswith("tag:")


def load_transactions(tx_path: Path) -> Tuple[pd.DataFrame, Dict[str, int], Dict[int, Set[int]], Dict[str, List[int]]]:
    """
    Returns:
      tx_df: columns [id, class_label, items(list)]
      label_map: class_label -> class_id
      item_docs: item -> set(doc_ids)
      class_docs: class_label -> list(doc_ids)
    """
    df = pd.read_csv(tx_path, encoding="utf-8")
    if "items_json" not in df.columns or "class_label" not in df.columns or "id" not in df.columns:
        raise RuntimeError("transactions.csv must have columns: id, class_label, items_json")

    def parse_items(s):
        try:
            xs = json.loads(s)
            return [str(x) for x in xs] if isinstance(xs, list) else []
        except Exception:
            return []

    df["items"] = df["items_json"].apply(parse_items)
    df = df[["id", "class_label", "items"]].copy()
    df["id"] = df["id"].astype(int)

    labels = sorted(df["class_label"].unique().tolist())
    label_map = {lbl: i for i, lbl in enumerate(labels)}

    # Build inverted index: item -> set(doc_ids)
    item_docs: Dict[str, Set[int]] = defaultdict(set)
    for i, row in df.iterrows():
        doc_id = int(row["id"])
        for it in set(row["items"]):
            item_docs[it].add(doc_id)

    # Class -> doc ids
    class_docs: Dict[str, List[int]] = {lbl: sorted(df.loc[df["class_label"] == lbl, "id"].astype(int).tolist())
                                        for lbl in labels}

    return df, label_map, item_docs, class_docs


def pattern_docset(items: Sequence[str], item_docs: Dict[str, Set[int]]) -> Set[int]:
    if not items:
        return set()
    # intersect postings
    sets = []
    for it in items:
        s = item_docs.get(it)
        if not s:
            return set()
        sets.append(s)
    out = set(sets[0])
    for s in sets[1:]:
        out &= s
        if not out:
            break
    return out


def metrics_for_class(N: int, class_size: int, supp_c: int, supp_total: int, alpha: float = 0.5) -> Dict[str, float]:
    """Compute discriminative metrics for binary P (pattern) vs class C (one-vs-rest)."""
    supp_not_c = supp_total - supp_c
    n_not_c = N - class_size

    p_c = class_size / N
    p_not_c = 1.0 - p_c
    p_p = supp_total / N
    p_not_p = 1.0 - p_p

    eps = 1e-12

    # Confidence and lift
    conf_c_given_p = supp_c / max(supp_total, eps)
    lift = conf_c_given_p / max(p_c, eps)

    # Growth-rate: [P in class] / [P outside class]
    growth = (supp_c / max(class_size, eps)) / max(supp_not_c / max(n_not_c, eps), eps)

    # WRAcc = P(P) * (P(C|P) - P(C))
    wracc = (supp_total / N) * (conf_c_given_p - p_c)

    # Odds ratio (Laplace-smoothed)
    or_num = (supp_c + alpha) / max(class_size - supp_c + alpha, eps)
    or_den = (supp_not_c + alpha) / max(n_not_c - supp_not_c + alpha, eps)
    odds_ratio = or_num / max(or_den, eps)

    # Chi-square (2x2)
    if chi2_contingency:
        table = np.array([
            [supp_c, class_size - supp_c],
            [supp_not_c, n_not_c - supp_not_c]
        ], dtype=float)
        chi2, p = chi2_contingency(table, correction=False)[:2]
    else:
        chi2, p = float("nan"), float("nan")

    # Mutual Information (bits) between P and C
    # Joint probs
    p11 = supp_c / N                          # P=1, C=1
    p10 = (supp_total - supp_c) / N           # P=1, C=0
    p01 = (class_size - supp_c) / N           # P=0, C=1
    p00 = 1.0 - p11 - p10 - p01               # P=0, C=0

    # Marginals
    pP1, pP0 = p_p, p_not_p
    pC1, pC0 = p_c, p_not_c

    ig = 0.0
    for pxy, px, py in [(p11, pP1, pC1), (p10, pP1, pC0), (p01, pP0, pC1), (p00, pP0, pC0)]:
        if pxy > 0:
            ig += pxy * math.log2(pxy / max(px * py, eps))

    return {
        "conf": conf_c_given_p,
        "lift": lift,
        "growth": growth,
        "wracc": wracc,
        "odds_ratio": odds_ratio,
        "chi2": float(chi2),
        "p_value": float(p),
        "ig": float(ig),
        "supp_not_c": int(supp_not_c),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="./output/fpg/transactions.csv", help="transactions.csv path")
    ap.add_argument("--itemsets", default="./output/fpg/fpg_by_class_itemsets.csv",
                    help="Per-class itemsets CSV (or report/mixed_itemsets_by_class.csv)")
    ap.add_argument("--out_dir", default="./output/efpg", help="Directory for outputs")
    ap.add_argument("--require_mixed", type=str, default="true", help="Require both token and tag:* in pattern")
    ap.add_argument("--min_len", type=int, default=1, help="Min itemset size")
    ap.add_argument("--max_len", type=int, default=3, help="Max itemset size")
    ap.add_argument("--min_support_total", type=float, default=0.01, help="Min global support fraction")
    ap.add_argument("--min_support_count", type=int, default=5, help="Absolute min global support count")
    ap.add_argument("--top_k_per_class", type=int, default=200, help="Select at most K patterns per class")
    ap.add_argument("--score", default="wracc", choices=["wracc", "lift", "growth", "ig", "chi2"],
                    help="Ranking metric for selection")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load transactions and inverted index
    tx_df, label_map, item_docs, class_docs = load_transactions(Path(args.tx))
    N = len(tx_df)
    labels = sorted(label_map.keys())
    class_sizes = {lbl: len(class_docs[lbl]) for lbl in labels}

    # Load itemsets (per-class)
    is_df = pd.read_csv(args.itemsets, encoding="utf-8")
    if "class_label" not in is_df.columns:
        # If user passed global file, derive classless; we will evaluate for every class
        is_df["class_label"] = "GLOBAL"
    # Ensure items column present
    if "items" not in is_df.columns and "items_readable" in is_df.columns:
        is_df["items"] = is_df["items_readable"].astype(str).str.replace(", ", "|")
    if "k" not in is_df.columns:
        is_df["k"] = is_df["items"].astype(str).apply(lambda s: len(split_items_pipe(s)))

    # Filter by size
    is_df = is_df[(is_df["k"] >= args.min_len) & (is_df["k"] <= args.max_len)].copy()
    req_mixed = str(args.require_mixed).strip().lower() in ("1", "true", "yes", "y")

    # Score patterns per class
    rows = []
    seen = set()  # dedup identical (class, frozenset(items))
    for _, r in is_df.iterrows():
        # Items
        items = split_items_pipe(str(r["items"]))
        if not items:
            continue
        if req_mixed:
            has_tag = any(is_tag_item(x) for x in items)
            has_tok = any(not is_tag_item(x) for x in items)
            if not (has_tag and has_tok):
                continue

        # Global support (from coverage)
        docs = pattern_docset(items, item_docs)
        supp_total = len(docs)
        if supp_total < max(int(math.ceil(args.min_support_total * N)), args.min_support_count):
            continue

        # Evaluate for every class (discriminative patterns are class-specific)
        for cls in labels:
            key = (cls, tuple(sorted(items)))
            if key in seen:
                continue
            seen.add(key)

            # In-class support = |docs ∩ class_docs|
            docs_c = set(class_docs[cls])
            supp_c = len(docs & docs_c)

            mets = metrics_for_class(N, class_sizes[cls], supp_c, supp_total)
            row = {
                "class_label": cls,
                "k": int(len(items)),
                "items": "|".join(sorted(items)),
                "support_total": int(supp_total),
                "support_in_class": int(supp_c),
                "support_frac_total": round(supp_total / N, 6),
                "support_frac_in_class": round(supp_c / max(class_sizes[cls], 1), 6),
            }
            row.update(mets)
            rows.append(row)

    scored = pd.DataFrame(rows)
    if scored.empty:
        raise SystemExit("No patterns passed the filters. Lower thresholds or disable --require_mixed.")

    # Rank and select per class
    sort_cols = {
        "wracc": ["wracc", "lift", "conf", "support_in_class"],
        "lift": ["lift", "wracc", "support_in_class"],
        "growth": ["growth", "wracc", "support_in_class"],
        "ig": ["ig", "wracc", "support_in_class"],
        "chi2": ["chi2", "wracc", "support_in_class"],
    }[args.score]
    scored_sorted = scored.sort_values(["class_label"] + sort_cols, ascending=[True] + [False] * len(sort_cols))
    scored_sorted.to_csv(out_dir / "patterns_scored.csv", index=False, encoding="utf-8")

    # Simple redundancy pruning: keep first K per class by score, drop exact-coverage duplicates
    selected_rows = []
    for cls, g in scored_sorted.groupby("class_label", sort=False):
        kept = []
        coverage_seen = set()
        for _, r in g.iterrows():
            if len(kept) >= args.top_k_per_class:
                break
            items = split_items_pipe(r["items"])
            docs = pattern_docset(items, item_docs)
            # Dedup exact coverage in this class
            cov_key = (cls, frozenset(docs & set(class_docs[cls])))
            if cov_key in coverage_seen:
                continue
            coverage_seen.add(cov_key)
            kept.append(r)
        if kept:
            selected_rows.append(pd.DataFrame(kept))

    selected = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()
    selected.to_csv(out_dir / "patterns_selected.csv", index=False, encoding="utf-8")

    # Build feature matrix for selected patterns
    patterns = selected.reset_index(drop=True)
    patterns["pattern_id"] = np.arange(len(patterns))
    patterns = patterns[["pattern_id", "class_label", "k", "items", "support_total",
                         "support_in_class", "support_frac_total", "support_frac_in_class",
                         "conf", "lift", "growth", "wracc", "odds_ratio", "chi2", "p_value", "ig"]]
    patterns.to_csv(out_dir / "feature_index.csv", index=False, encoding="utf-8")

    # Prepare y and label map
    label_map = {lbl: i for i, lbl in enumerate(sorted(tx_df["class_label"].unique()))}
    with open(out_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    y = tx_df["class_label"].map(label_map).to_numpy(dtype=np.int32)
    np.save(out_dir / "y.npy", y)

    # Build CSR by accumulating (row, col) for docs covered by each pattern
    rows, cols, data = [], [], []
    doc_count = len(tx_df)
    for _, r in patterns.iterrows():
        j = int(r["pattern_id"])
        items = split_items_pipe(r["items"])
        docs = pattern_docset(items, item_docs)
        for i in docs:
            rows.append(i)
            cols.append(j)
            data.append(1)

    if HAVE_SCIPY:
        X = csr_matrix((data, (rows, cols)), shape=(doc_count, len(patterns)), dtype=np.uint8)
        save_npz(out_dir / "X_patterns.npz", X)
        coverage = float(X.nnz) / (doc_count * max(len(patterns), 1))
    else:
        # Fallback to dense CSV (not recommended for large P)
        mat = np.zeros((doc_count, len(patterns)), dtype=np.uint8)
        for i, j in zip(rows, cols):
            mat[i, j] = 1
        pd.DataFrame(mat).to_csv(out_dir / "X_patterns_dense.csv", index=False, encoding="utf-8")
        coverage = float(np.count_nonzero(mat)) / (doc_count * max(len(patterns), 1))

    # Coverage stats
    cov_stats = {
        "n_docs": int(doc_count),
        "n_patterns": int(len(patterns)),
        "avg_density": coverage,
        "class_sizes": {k: int(v) for k, v in class_sizes.items()},
    }
    (out_dir / "coverage_stats.json").write_text(json.dumps(cov_stats, indent=2), encoding="utf-8")

    # Run info
    run_info = {
        "tx": str(Path(args.tx).resolve()),
        "itemsets": str(Path(args.itemsets).resolve()),
        "out_dir": str(out_dir.resolve()),
        "params": {
            "require_mixed": bool(req_mixed),
            "min_len": args.min_len,
            "max_len": args.max_len,
            "min_support_total": args.min_support_total,
            "min_support_count": args.min_support_count,
            "top_k_per_class": args.top_k_per_class,
            "score": args.score,
            "have_scipy": HAVE_SCIPY,
        }
    }
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")

    print("\n[ok] Extended FP patterns scored:", len(scored_sorted))
    print("[ok] Selected patterns:", len(patterns))
    print("[ok] Feature matrix:", "X_patterns.npz" if HAVE_SCIPY else "X_patterns_dense.csv")
    print("[ok] y.npy and label_map.json written.")
    print("[ok] Coverage stats:", json.dumps(cov_stats, indent=2))


if __name__ == "__main__":
    main()