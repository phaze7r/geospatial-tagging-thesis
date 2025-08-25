#!/usr/bin/env python3
"""
Audit the preprocessed OSM Islamabad dataset:
- Basic stats, null rates, class distribution
- Duplicate checks (by OSM id and by name+class+nearby coords)
- Bounding-box sanity (rows outside bbox)
- Text quality (lengths, token counts, presence of Urdu/Arabic script)
- Optional plots

Usage:
    cd geospatial-tagging-thesis/scripts
    python audit_preprocessed.py --input_csv ./output/osm_isb_preprocessed.csv --out_dir ./output/reports

Requires:
    pip install pandas numpy
    Optional for plots: pip install matplotlib
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Try to enable plotting (optional)
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except Exception:
    HAS_MPL = False

# Default Islamabad bbox (south, west, north, east)
DEFAULT_BBOX = (33.66, 72.96, 33.78, 73.18)


def read_csv_robust(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path)


def ensure_cols(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df


def round_coord(x: Any, decimals: int = 4) -> float | None:
    try:
        xf = float(x)
        if math.isfinite(xf):
            return round(xf, decimals)
    except Exception:
        pass
    return None


def contains_urdu_arabic(s: str) -> bool:
    if not isinstance(s, str):
        return False
    # Arabic script unicode range (covers Urdu)
    return any('\u0600' <= ch <= '\u06FF' for ch in s)


def plot_class_counts(counts: pd.DataFrame, path: Path) -> None:
    if not HAS_MPL or counts.empty:
        return
    plt.figure(figsize=(10, max(3, 0.3 * len(counts))))
    plt.barh(counts["class_label"], counts["count"])
    plt.xlabel("Count")
    plt.ylabel("Class")
    plt.title("Class distribution")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_text_lengths(lengths: pd.Series, path: Path) -> None:
    if not HAS_MPL or lengths.empty:
        return
    plt.figure(figsize=(8, 4))
    plt.hist(lengths, bins=40, color="#4C78A8")
    plt.xlabel("Text length (chars)")
    plt.ylabel("Frequency")
    plt.title("Text length distribution")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", default="./output/osm_isb_preprocessed.csv", help="Path to preprocessed CSV")
    ap.add_argument("--out_dir", default="./output/reports", help="Directory to write the audit report")
    ap.add_argument("--bbox", default="33.66,72.96,33.78,73.18", help="BBox s,w,n,e to sanity-check coords")
    ap.add_argument("--near_round", type=int, default=4, help="Rounding decimals for near-duplicate check")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Parse bbox
    try:
        s, w, n, e = [float(x.strip()) for x in args.bbox.split(",")]
        bbox = (s, w, n, e)
    except Exception:
        bbox = DEFAULT_BBOX

    # Load
    in_path = Path(args.input_csv)
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")
    df = read_csv_robust(in_path)

    # Ensure expected columns
    df = ensure_cols(df, [
        "osm_id", "osm_type", "name", "addr_full", "lat", "lon",
        "class_key", "class_value", "class_label", "label_id", "text"
    ])

    # If class_label missing, try to compose from class_key/value
    if df["class_label"].isna().all() and ("class_key" in df.columns and "class_value" in df.columns):
        df["class_label"] = (df["class_key"].fillna("").astype(str) + ":" +
                             df["class_value"].fillna("").astype(str)).replace({":": np.nan})

    # Coerce coords
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    # Basic stats
    n_rows, n_cols = df.shape
    n_labels = df["class_label"].dropna().nunique()
    classes = sorted(df["class_label"].dropna().unique().tolist())

    # Null rates
    null_rates = df.isna().mean().reset_index()
    null_rates.columns = ["column", "null_rate"]
    null_rates.sort_values("null_rate", ascending=False, inplace=True)
    null_rates.to_csv(out_dir / "null_rates.csv", index=False, encoding="utf-8")

    # Class distribution
    class_counts = (
        df["class_label"]
        .dropna()
        .value_counts()
        .rename_axis("class_label")
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    class_counts.to_csv(out_dir / "class_distribution.csv", index=False, encoding="utf-8")

    # Samples per class (up to 5 each)
    samples_rows = []
    for cls, g in df.groupby("class_label"):
        head = g.head(5)[["class_label", "name", "addr_full", "text", "lat", "lon"]]
        samples_rows.append(head)
    samples_df = pd.concat(samples_rows, ignore_index=True) if samples_rows else pd.DataFrame()
    samples_df.to_csv(out_dir / "samples_by_class.csv", index=False, encoding="utf-8")

    # Duplicate checks
    dup_osm = (
        df[df.duplicated(subset=["osm_type", "osm_id"], keep=False)]
        .sort_values(["osm_type", "osm_id"])
    )
    dup_osm.to_csv(out_dir / "duplicates_by_osm.csv", index=False, encoding="utf-8")

    # Near duplicates by name + class + rounded coords
    df["name_lc"] = df["name"].astype(str).str.lower().fillna("")
    df["lat_r"] = df["lat"].apply(lambda x: round_coord(x, args.near_round))
    df["lon_r"] = df["lon"].apply(lambda x: round_coord(x, args.near_round))
    dup_near = df[df.duplicated(subset=["class_label", "name_lc", "lat_r", "lon_r"], keep=False)]
    dup_near = dup_near.sort_values(["class_label", "name_lc", "lat_r", "lon_r", "osm_type", "osm_id"])
    dup_near.to_csv(out_dir / "near_duplicates_by_name_class.csv", index=False, encoding="utf-8")

    # BBox sanity
    s, w, n, e = bbox
    outside = df[
        (~df["lat"].between(s, n)) | (~df["lon"].between(w, e))
    ][["class_label", "name", "lat", "lon", "addr_full"]]
    outside.to_csv(out_dir / "outside_bbox.csv", index=False, encoding="utf-8")

    # Text quality
    text = df["text"].fillna("").astype(str)
    df["text_len"] = text.str.len()
    df["token_count"] = text.str.split().apply(len)
    df["has_urdu"] = text.apply(contains_urdu_arabic)
    text_len_stats = {
        "min": int(df["text_len"].min()) if not df["text_len"].isna().all() else 0,
        "max": int(df["text_len"].max()) if not df["text_len"].isna().all() else 0,
        "median": float(df["text_len"].median()) if not df["text_len"].isna().all() else 0.0,
        "mean": float(df["text_len"].mean()) if not df["text_len"].isna().all() else 0.0,
        "pct_lt_20_chars": float((df["text_len"] < 20).mean()),
        "pct_has_urdu_script": float(df["has_urdu"].mean()),
    }

    # Plots (optional)
    if HAS_MPL:
        plot_class_counts(class_counts, out_dir / "class_counts.png")
        plot_text_lengths(df["text_len"], out_dir / "text_length_hist.png")

    # Summary JSON
    summary = {
        "input_csv": str(in_path.resolve()),
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "n_classes": int(n_labels),
        "classes": classes,
        "bbox_used": {"south": s, "west": w, "north": n, "east": e},
        "rows_outside_bbox": int(len(outside)),
        "duplicate_osm_rows": int(len(dup_osm)),
        "near_duplicate_rows": int(len(dup_near)),
        "null_rates_top5": [
            {"column": r["column"], "null_rate": float(r["null_rate"])}
            for _, r in null_rates.head(5).iterrows()
        ],
        "class_top5": [
            {"class_label": r["class_label"], "count": int(r["count"])}
            for _, r in class_counts.head(5).iterrows()
        ],
        "text_len_stats": text_len_stats,
        "plots": {
            "class_counts_png": str((out_dir / "class_counts.png").resolve()) if HAS_MPL else None,
            "text_length_hist_png": str((out_dir / "text_length_hist.png").resolve()) if HAS_MPL else None,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Console digest
    print("\n=== Audit summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nReport written to: {out_dir.resolve()}")
    print("Files:")
    for fn in [
        "summary.json",
        "class_distribution.csv",
        "null_rates.csv",
        "duplicates_by_osm.csv",
        "near_duplicates_by_name_class.csv",
        "outside_bbox.csv",
        "samples_by_class.csv",
        "class_counts.png" if HAS_MPL else "(no matplotlib: class_counts.png skipped)",
        "text_length_hist.png" if HAS_MPL else "(no matplotlib: text_length_hist.png skipped)",
    ]:
        print(" -", fn)


if __name__ == "__main__":
    main()