#!/usr/bin/env python3
"""
Summarize FP-Growth outputs into human-reviewable reports.

Inputs (from prepare_fp_items.py):
  - transactions.csv  (id, class_label, items_json)
  - fpg_by_class_itemsets.csv (class_label, k, support, support_frac, items, items_readable)
  - fpg_global_itemsets.csv   (k, support, support_frac, items, items_readable)

Outputs:
  - top_itemsets_by_class.csv
  - mixed_itemsets_by_class.csv           # itemsets that contain both tokens and tag:* items
  - token_tag_rules_by_class.csv          # token -> tag:* rules per class with support/conf/lift
  - global_token_tag_rules.csv            # token -> tag:* rules across all docs
  - items_per_class.csv                   # top tokens/tags per class
  - summary.json

Usage:
  cd geospatial-tagging-thesis/scripts
  python summarize_fp_results.py --in_dir ./output/fpg --out_dir ./output/fpg_report
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


def load_transactions(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    if "items_json" not in df.columns or "class_label" not in df.columns:
        raise RuntimeError(f"transactions.csv missing required columns at {path}")
    # Parse items
    def parse_items(s: str) -> List[str]:
        try:
            obj = json.loads(s)
            if isinstance(obj, list):
                return [str(x) for x in obj]
        except Exception:
            pass
        return []
    df["items"] = df["items_json"].apply(parse_items)
    return df[["id", "class_label", "items"]]


def load_itemsets(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    # Ensure items column exists (pipe-separated original items)
    if "items" not in df.columns and "items_readable" in df.columns:
        # Fallback: rebuild from items_readable (comma-separated)
        df["items"] = df["items_readable"].astype(str).str.replace(", ", "|")
    return df


def split_items_pipe(s: str) -> List[str]:
    if not isinstance(s, str):
        return []
    return [x for x in s.split("|") if x]


def is_tag_item(item: str) -> bool:
    return isinstance(item, str) and item.startswith("tag:")


def summarize_itemsets_by_class(fpg_by_class: pd.DataFrame, out_dir: Path) -> None:
    df = fpg_by_class.copy()
    # Parse items
    df["items_list"] = df["items"].apply(split_items_pipe)
    # Mixed = contains at least one tag:* and one token
    df["has_tag"] = df["items_list"].apply(lambda xs: any(is_tag_item(x) for x in xs))
    df["has_token"] = df["items_list"].apply(lambda xs: any(not is_tag_item(x) for x in xs))
    df["mixed"] = df["has_tag"] & df["has_token"]

    # Top itemsets per class, size 1–3, sorted by k desc, support desc
    top = df.sort_values(["class_label", "k", "support", "items"], ascending=[True, False, False, True])
    top.to_csv(out_dir / "top_itemsets_by_class.csv", index=False, encoding="utf-8")

    mixed = top[top["mixed"]].copy()
    mixed.to_csv(out_dir / "mixed_itemsets_by_class.csv", index=False, encoding="utf-8")


def build_counts_from_transactions(tx_df: pd.DataFrame):
    """
    Build document-frequency counts for tokens, tags, and token-tag pairs,
    globally and per-class.
    """
    N = len(tx_df)
    classes = sorted(tx_df["class_label"].unique())

    # Global DF
    token_df_g = Counter()
    tag_df_g = Counter()
    pair_df_g = Counter()  # (token, tag) -> df

    # Per-class DF
    token_df_c: Dict[str, Counter] = {c: Counter() for c in classes}
    tag_df_c: Dict[str, Counter] = {c: Counter() for c in classes}
    pair_df_c: Dict[str, Counter] = {c: Counter() for c in classes}
    class_sizes = {c: 0 for c in classes}

    for _, row in tx_df.iterrows():
        c = row["class_label"]
        items = set(row["items"])
        class_sizes[c] += 1

        tokens = {x for x in items if not is_tag_item(x)}
        tags = {x for x in items if is_tag_item(x)}

        for t in tokens: token_df_g[t] += 1
        for m in tags: tag_df_g[m] += 1
        for t in tokens: token_df_c[c][t] += 1
        for m in tags: tag_df_c[c][m] += 1

        # token-tag pairs present in this doc
        for t in tokens:
            for m in tags:
                pair_df_g[(t, m)] += 1
                pair_df_c[c][(t, m)] += 1

    return N, classes, class_sizes, token_df_g, tag_df_g, pair_df_g, token_df_c, tag_df_c, pair_df_c


def to_rules_df(pair_counts: Counter, token_df: Counter, tag_df: Counter, denom: int,
                min_pair_count: int, min_conf: float, min_lift: float, label: str) -> pd.DataFrame:
    rows = []
    for (t, m), co in pair_counts.items():
        if co < min_pair_count:
            continue
        ct = token_df.get(t, 0)
        cm = tag_df.get(m, 0)
        if ct == 0 or cm == 0:
            continue
        support = co / denom
        conf_m_given_t = co / ct
        conf_t_given_m = co / cm
        lift = (denom * co) / (ct * cm) if (ct * cm) else 0.0
        if conf_m_given_t >= min_conf and lift >= min_lift:
            rows.append({
                "scope": label,
                "token": t,
                "tag": m,
                "count_pair": int(co),
                "count_token": int(ct),
                "count_tag": int(cm),
                "support": round(support, 6),
                "conf_tag_given_token": round(conf_m_given_t, 6),
                "conf_token_given_tag": round(conf_t_given_m, 6),
                "lift": round(lift, 6),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["lift", "conf_tag_given_token", "count_pair"], ascending=[False, False, False])
    return df


def items_per_class(tx_df: pd.DataFrame, out_path: Path, top_n: int = 40) -> None:
    rows = []
    for cls, g in tx_df.groupby("class_label"):
        N = len(g)
        token_df = Counter()
        tag_df = Counter()
        for items in g["items"]:
            items = set(items)
            for it in items:
                if is_tag_item(it):
                    tag_df[it] += 1
                else:
                    token_df[it] += 1
        # add top tokens
        for it, c in token_df.most_common(top_n):
            rows.append({"class_label": cls, "type": "token", "item": it, "count": int(c), "frac": round(c / N, 6)})
        # add top tags
        for it, c in tag_df.most_common(top_n):
            rows.append({"class_label": cls, "type": "tag", "item": it, "count": int(c), "frac": round(c / N, 6)})
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", default="./output/fpg", help="Directory with FP outputs")
    ap.add_argument("--out_dir", default="./output/fpg_report", help="Directory to write reports")
    # Rule thresholds
    ap.add_argument("--min_pair_count_class", type=int, default=3)
    ap.add_argument("--min_conf_class", type=float, default=0.4)
    ap.add_argument("--min_lift_class", type=float, default=1.2)
    ap.add_argument("--min_pair_count_global", type=int, default=5)
    ap.add_argument("--min_conf_global", type=float, default=0.35)
    ap.add_argument("--min_lift_global", type=float, default=1.15)
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load inputs
    tx_df = load_transactions(in_dir / "transactions.csv")
    by_class = load_itemsets(in_dir / "fpg_by_class_itemsets.csv")
    global_sets = load_itemsets(in_dir / "fpg_global_itemsets.csv")

    # 1) Write itemset digests
    summarize_itemsets_by_class(by_class, out_dir)

    # 2) Build counts from transactions
    N, classes, class_sizes, token_df_g, tag_df_g, pair_df_g, token_df_c, tag_df_c, pair_df_c = build_counts_from_transactions(tx_df)

    # 3) Rules per class: token -> tag
    per_class_rows = []
    for cls in classes:
        df_rules = to_rules_df(
            pair_counts=pair_df_c[cls],
            token_df=token_df_c[cls],
            tag_df=tag_df_c[cls],
            denom=class_sizes[cls],
            min_pair_count=args.min_pair_count_class,
            min_conf=args.min_conf_class,
            min_lift=args.min_lift_class,
            label=cls,
        )
        if not df_rules.empty:
            per_class_rows.append(df_rules)
    if per_class_rows:
        pd.concat(per_class_rows, ignore_index=True).to_csv(out_dir / "token_tag_rules_by_class.csv", index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=[
            "scope","token","tag","count_pair","count_token","count_tag","support",
            "conf_tag_given_token","conf_token_given_tag","lift"
        ]).to_csv(out_dir / "token_tag_rules_by_class.csv", index=False, encoding="utf-8")

    # 4) Global rules
    global_rules = to_rules_df(
        pair_counts=pair_df_g,
        token_df=token_df_g,
        tag_df=tag_df_g,
        denom=N,
        min_pair_count=args.min_pair_count_global,
        min_conf=args.min_conf_global,
        min_lift=args.min_lift_global,
        label="GLOBAL",
    )
    global_rules.to_csv(out_dir / "global_token_tag_rules.csv", index=False, encoding="utf-8")

    # 5) Items per class (top tokens/tags)
    items_per_class(tx_df, out_dir / "items_per_class.csv", top_n=40)

    # 6) Summary JSON
    summary = {
        "n_docs": int(N),
        "n_classes": len(classes),
        "classes": classes,
        "thresholds": {
            "per_class": {
                "min_pair_count": args.min_pair_count_class,
                "min_conf": args.min_conf_class,
                "min_lift": args.min_lift_class,
            },
            "global": {
                "min_pair_count": args.min_pair_count_global,
                "min_conf": args.min_conf_global,
                "min_lift": args.min_lift_global,
            },
        },
        "paths": {
            "top_itemsets_by_class": str((out_dir / "top_itemsets_by_class.csv").resolve()),
            "mixed_itemsets_by_class": str((out_dir / "mixed_itemsets_by_class.csv").resolve()),
            "token_tag_rules_by_class": str((out_dir / "token_tag_rules_by_class.csv").resolve()),
            "global_token_tag_rules": str((out_dir / "global_token_tag_rules.csv").resolve()),
            "items_per_class": str((out_dir / "items_per_class.csv").resolve()),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n[ok] FP report written to:", out_dir.resolve())
    for k, v in summary["paths"].items():
        print("-", k, "->", v)


if __name__ == "__main__":
    main()