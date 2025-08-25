#!/usr/bin/env python3
"""
Validate Extended FP outputs are ready for BEN.
Checks:
- Required files exist
- Patterns per class and mixed-pattern ratio
- Feature matrix shape and density
- Coverage by class
Prints actionable suggestions if thresholds aren’t met.
"""

from __future__ import annotations
import argparse, json, os
from pathlib import Path
import numpy as np
import pandas as pd

HAVE_SCIPY = True
try:
    from scipy.sparse import load_npz
except Exception:
    HAVE_SCIPY = False
    load_npz = None

def is_tag_item(s: str) -> bool:
    return isinstance(s, str) and s.startswith("tag:")

def split_items(s: str):
    if not isinstance(s, str): return []
    return [x for x in s.split("|") if x]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--efpg_dir", default="./output/efpg")
    args = ap.parse_args()
    d = Path(args.efpg_dir)

    # Required files
    req = ["feature_index.csv", "label_map.json", "y.npy"]
    missing = [f for f in req if not (d / f).exists()]
    if missing:
        print("[fail] Missing:", ", ".join(missing))
        print("Hint: run mine_extended_patterns.py to generate EFPG artifacts.")
        return

    # Load feature index
    idx = pd.read_csv(d / "feature_index.csv", encoding="utf-8")
    if "items" not in idx.columns:
        print("[fail] feature_index.csv missing 'items' column.")
        return
    n_patterns = len(idx)
    print(f"[ok] feature_index.csv found with {n_patterns} patterns")

    # Patterns per class
    per_cls = idx["class_label"].value_counts().sort_index()
    print("\n[info] Patterns per class:")
    for cls, c in per_cls.items():
        print(f"  - {cls}: {int(c)}")

    # Mixed-pattern ratio
    def is_mixed(s: str):
        xs = split_items(s)
        return any(is_tag_item(x) for x in xs) and any(not is_tag_item(x) for x in xs)
    mixed_ratio = idx["items"].apply(is_mixed).mean()
    print(f"\n[info] Mixed-pattern ratio: {mixed_ratio:.3f}")

    # Load label map and y
    with open(d / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    y = np.load(d / "y.npy")
    n_docs = len(y)
    print(f"[ok] y.npy loaded: {n_docs} docs, {len(label_map)} classes")

    # Load X
    X_shape = None
    density = None
    if (d / "X_patterns.npz").exists() and HAVE_SCIPY:
        X = load_npz(d / "X_patterns.npz")
        X_shape = X.shape
        density = X.nnz / (X.shape[0] * max(X.shape[1], 1))
        print(f"[ok] X_patterns.npz loaded: shape={X.shape}, density={density:.4f}")
    elif (d / "X_patterns_dense.csv").exists():
        # Fallback
        df = pd.read_csv(d / "X_patterns_dense.csv")
        X_shape = (len(df), df.shape[1])
        nz = (df.values != 0).sum()
        density = nz / (X_shape[0] * max(X_shape[1], 1))
        print(f"[warn] Using dense CSV. shape={X_shape}, density={density:.4f}")
    else:
        print("[fail] No feature matrix found (X_patterns.npz or X_patterns_dense.csv).")
        print("Hint: install scipy (pip install scipy) and re-run mine_extended_patterns.py")
        return

    # Simple readiness gates
    suggestions = []
    if n_patterns < 200:
        suggestions.append("Increase features: lower --min_support_total (e.g., 0.005) or raise --top_k_per_class.")
    if mixed_ratio < 0.6:
        suggestions.append("Enforce/keep --require_mixed true or review token/tag generation.")
    if density is not None and density < 0.01:
        suggestions.append("Matrix too sparse: lower support or allow k<=2 patterns.")
    if per_cls.min() < 20:
        suggestions.append("Some classes have <20 patterns. Consider increasing --top_k_per_class or lowering thresholds.")

    if suggestions:
        print("\n[needs-attention]")
        for s in suggestions:
            print(" -", s)
    else:
        print("\n[ready] EFPG artifacts look good for BEN.")

if __name__ == "__main__":
    main()