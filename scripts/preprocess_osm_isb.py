#!/usr/bin/env python3
"""
Preprocess OSM Islamabad sample to create a clean, normalized, NLP-ready dataset.

- Robust against missing columns (primary_key/value/group), malformed JSON, missing names.
- Normalizes your requested classes (amenity/shop/...).
- Deduplicates near-identical entries and caps per-class size.
- Produces stratified train/test splits.
- Always writes outputs to --out_dir (default: ./output).

Usage (from repo root):
    cd geospatial-tagging-thesis/scripts
    python preprocess_osm_isb.py --input_csv ./output/osm_isb.csv --out_dir ./output

Requires:
    pip install pandas
"""

import argparse
import json
import math
import os
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# -----------------------------
# Config / taxonomy
# -----------------------------
SELECTED_TAG_KEYS = [
    "amenity", "shop", "highway", "leisure", "natural", "tourism",
    "building", "historic", "place", "religion"
]

ALLOWED_CLASSES = {
    ("amenity", "cafe"),
    ("amenity", "restaurant"),
    ("amenity", "hospital"),
    ("amenity", "mosque"),        # normalized
    ("amenity", "bank"),
    ("amenity", "school"),
    ("amenity", "marketplace"),   # market/bazaar
    ("shop", "supermarket"),
    ("shop", "bakery"),
    ("shop", "clothes"),
    ("highway", "bus_stop"),
    ("leisure", "park"),
    ("natural", "water"),
    ("natural", "tree"),
    ("tourism", "hotel"),
    ("building", "residential"),
    ("historic", "monument"),
    ("place", "locality"),
}

FAMILY_MAP = {
    "amenity": "amenity",
    "shop": "shop",
    "highway": "transport",
    "leisure": "leisure",
    "natural": "natural",
    "tourism": "tourism",
    "building": "building",
    "historic": "historic",
    "place": "place",
}

BAZAAR_TERMS = ["bazaar", "bazar", "market", "mandi", "markaz"]


# -----------------------------
# Utils
# -----------------------------
def normalize_text(s: Optional[str]) -> Optional[str]:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s)
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else None


def safe_json_load(s: Any) -> Dict[str, Any]:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return {}
    if isinstance(s, dict):
        return s
    s = str(s)
    # Handle accidental single quotes or invalid
    try:
        return json.loads(s)
    except Exception:
        try:
            s2 = s.replace("'", '"')
            return json.loads(s2)
        except Exception:
            return {}


def round_coord(x: Any, decimals: int = 4) -> Optional[float]:
    try:
        xf = float(x)
        if math.isfinite(xf):
            return round(xf, decimals)
        return None
    except Exception:
        return None


def human_label(class_key: str, class_value: str) -> str:
    pretty = {
        ("highway", "bus_stop"): "bus stop",
        ("amenity", "marketplace"): "market/bazaar",
    }
    return pretty.get((class_key, class_value), f"{class_key}:{class_value}")


def stratified_split(df: pd.DataFrame, label_col: str, test_frac: float, seed: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    random.seed(seed)
    test_indices: List[int] = []
    for lbl, group in df.groupby(label_col):
        idxs = list(group.index)
        random.shuffle(idxs)
        n = len(idxs)
        # If very small, keep all in train, else sample test
        test_n = max(1, int(round(test_frac * n))) if n >= 5 else 0
        test_indices.extend(idxs[:test_n])
    test_set = df.loc[test_indices].copy()
    train_set = df.drop(index=test_set.index).copy()
    return train_set, test_set


# -----------------------------
# Classification
# -----------------------------
def derive_class(tags: Dict[str, Any],
                 primary_key: Optional[str],
                 primary_value: Optional[str],
                 name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Determine (family, class_key, class_value) with normalization.
    Priority:
      1) Mosque normalization (amenity=place_of_worship + religion=muslim OR building=mosque).
      2) Provided primary_key/primary_value if allowed.
      3) From tag keys in preferred order.
      4) Bazaar heuristic on name -> amenity=marketplace.
    """
    amenity = tags.get("amenity")
    religion = tags.get("religion")
    building = tags.get("building")

    # 1) Mosque normalization
    if (amenity == "place_of_worship" and religion == "muslim") or (building == "mosque"):
        return "amenity", "amenity", "mosque"

    # 2) Provided primary key/value
    if isinstance(primary_key, str) and isinstance(primary_value, str):
        if (primary_key, primary_value) in ALLOWED_CLASSES:
            return FAMILY_MAP.get(primary_key, primary_key), primary_key, primary_value

    # 3) Preferred keys
    preferred = ["amenity", "shop", "highway", "leisure", "natural", "tourism", "building", "historic", "place"]
    for k in preferred:
        v = tags.get(k)
        if isinstance(v, str) and (k, v) in ALLOWED_CLASSES:
            return FAMILY_MAP.get(k, k), k, v

    # 4) Bazaar heuristic from name
    if isinstance(name, str):
        nl = name.lower()
        if any(term in nl for term in BAZAAR_TERMS):
            return "amenity", "amenity", "marketplace"

    return None, None, None


# -----------------------------
# IO helpers
# -----------------------------
def read_csv_robust(path: Path) -> pd.DataFrame:
    # Try utf-8 then utf-8-sig
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to read CSV at {path} due to: {last_err}")


def ensure_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df


def to_geojson_points(df: pd.DataFrame) -> Dict[str, Any]:
    features = []
    for _, r in df.iterrows():
        lat = r.get("lat")
        lon = r.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        try:
            latf = float(lat)
            lonf = float(lon)
        except Exception:
            continue
        props = r.to_dict()
        props.pop("lat", None)
        props.pop("lon", None)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lonf, latf]},
            "properties": props
        })
    return {"type": "FeatureCollection", "features": features}


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", default="./output/osm_isb.csv", help="Path to the sampler CSV")
    ap.add_argument("--out_dir", default="./output", help="Directory to write outputs")
    ap.add_argument("--max_per_class", type=int, default=140, help="Cap instances per class after dedup")
    ap.add_argument("--test_frac", type=float, default=0.2, help="Test split fraction")
    ap.add_argument("--random_seed", type=int, default=42, help="Random seed")
    args = ap.parse_args()

    in_path = Path(args.input_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        # Try to auto-discover an osm_isb*.csv in ./output
        candidates = sorted(Path("./output").glob("osm_isb*.csv"))
        if candidates:
            print(f"[info] Provided input not found. Using discovered file: {candidates[0]}")
            in_path = candidates[0]
        else:
            print(f"[error] Input CSV not found: {args.input_csv}")
            print("Hint: run from geospatial-tagging-thesis/scripts and ensure ./output/osm_isb.csv exists.")
            sys.exit(1)

    print(f"[info] Reading: {in_path}")
    df = read_csv_robust(in_path)

    # Ensure expected columns exist (be defensive)
    expected = ["osm_id", "osm_type", "name", "addr_full", "lat", "lon", "all_tags_json", "primary_key", "primary_value"]
    df = ensure_columns(df, expected)

    # Clean name/addr
    df["name"] = df["name"].apply(normalize_text)
    df["addr_full"] = df["addr_full"].apply(normalize_text)

    # Coerce coords
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).copy()

    # Parse tags dict
    if "all_tags_json" not in df.columns:
        df["all_tags_json"] = "{}"
    df["_tags"] = df["all_tags_json"].apply(safe_json_load)

    # Expand selected tags into columns (overwrites if already present)
    for k in SELECTED_TAG_KEYS:
        df[k] = df["_tags"].apply(lambda d: d.get(k))

    # Derive normalized class
    families: List[Optional[str]] = []
    ckeys: List[Optional[str]] = []
    cvals: List[Optional[str]] = []
    for _, row in df.iterrows():
        tags = row["_tags"] if isinstance(row["_tags"], dict) else {}
        fam, ck, cv = derive_class(tags, row.get("primary_key"), row.get("primary_value"), row.get("name"))
        families.append(fam)
        ckeys.append(ck)
        cvals.append(cv)
    df["family"] = families
    df["class_key"] = ckeys
    df["class_value"] = cvals

    # Keep only allowed classes
    keep_mask = df["class_key"].notna() & df["class_value"].notna() & df.apply(
        lambda r: (r["class_key"], r["class_value"]) in ALLOWED_CLASSES, axis=1
    )
    df = df[keep_mask].copy()
    if df.empty:
        print("[warn] No rows matched the requested classes. Check your input CSV or increase sampling.")
        # Still write empty shells to avoid confusion
        empty_paths = [
            out_dir / "osm_isb_preprocessed.csv",
            out_dir / "osm_isb_nlp_corpus.csv",
            out_dir / "osm_isb_train.csv",
            out_dir / "osm_isb_test.csv",
        ]
        for p in empty_paths:
            pd.DataFrame().to_csv(p, index=False)
        (out_dir / "osm_isb_preprocessed.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
        (out_dir / "label_map.json").write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] Wrote empty outputs under {out_dir.resolve()}")
        sys.exit(0)

    # Canonical label
    df["class_label"] = df["class_key"] + ":" + df["class_value"]

    # Deduplicate by name+class+rounded coords
    df["name_lc"] = df["name"].str.lower().fillna("")
    df["lat_r"] = df["lat"].apply(lambda x: round_coord(x, 4))
    df["lon_r"] = df["lon"].apply(lambda x: round_coord(x, 4))
    before = len(df)
    df = df.sort_values(["class_label", "name_lc", "lat_r", "lon_r", "osm_type", "osm_id"]).drop_duplicates(
        subset=["class_label", "name_lc", "lat_r", "lon_r"], keep="first"
    )
    after = len(df)
    print(f"[info] Deduplicated: {before} -> {after}")

    # Cap per class
    capped_parts = []
    rng = random.Random(args.random_seed)
    for lbl, group in df.groupby("class_label", sort=False):
        if len(group) > args.max_per_class:
            capped = group.sample(n=args.max_per_class, random_state=args.random_seed)
        else:
            capped = group
        capped_parts.append(capped)
    df = pd.concat(capped_parts, ignore_index=True)

    # Human label and simple text
    df["human_label"] = df.apply(lambda r: human_label(r["class_key"], r["class_value"]), axis=1)

    def compose_text(r: pd.Series) -> str:
        city = "Islamabad"
        name = r.get("name")
        label = r.get("human_label")
        addr = r.get("addr_full")
        if name and addr:
            return f"{name} — {label} in {city}, {addr}"
        elif name:
            return f"{name} — {label} in {city}"
        elif addr:
            return f"{label} in {city}, {addr}"
        else:
            return f"{label} in {city}"

    df["text"] = df.apply(compose_text, axis=1)

    # Label map
    labels = sorted(df["class_label"].unique())
    label_to_id = {lbl: i for i, lbl in enumerate(labels)}
    df["label_id"] = df["class_label"].map(label_to_id)

    # Order columns for final output
    cols = [
        "osm_id", "osm_type",
        "family", "class_key", "class_value", "class_label", "label_id",
        "human_label", "name", "addr_full",
        "lat", "lon",
        "amenity", "shop", "highway", "leisure", "natural", "tourism",
        "building", "historic", "place", "religion",
        "text",
        "all_tags_json",
    ]
    existing_cols = [c for c in cols if c in df.columns]
    pre_df = df[existing_cols].sort_values(["class_label", "name"], na_position="last").reset_index(drop=True)

    # Write outputs
    pre_csv = out_dir / "osm_isb_preprocessed.csv"
    pre_df.to_csv(pre_csv, index=False, encoding="utf-8")
    print(f"[ok] Wrote: {pre_csv} (rows={len(pre_df)})")

    nlp_df = pre_df[["text", "class_label", "label_id"]].rename(columns={"class_label": "label"})
    nlp_csv = out_dir / "osm_isb_nlp_corpus.csv"
    nlp_df.to_csv(nlp_csv, index=False, encoding="utf-8")
    print(f"[ok] Wrote: {nlp_csv} (rows={len(nlp_df)})")

    train_df, test_df = stratified_split(pre_df, "class_label", args.test_frac, args.random_seed)
    train_csv = out_dir / "osm_isb_train.csv"
    test_csv = out_dir / "osm_isb_test.csv"
    train_df.to_csv(train_csv, index=False, encoding="utf-8")
    test_df.to_csv(test_csv, index=False, encoding="utf-8")
    print(f"[ok] Wrote: {train_csv} (rows={len(train_df)})")
    print(f"[ok] Wrote: {test_csv} (rows={len(test_df)})")

    gj = to_geojson_points(pre_df)
    gj_path = out_dir / "osm_isb_preprocessed.geojson"
    gj_path.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] Wrote: {gj_path} (features={len(gj.get('features', []))})")

    lm_path = out_dir / "label_map.json"
    lm_path.write_text(json.dumps(label_to_id, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] Wrote: {lm_path}")

    # Summary
    summary = (
        pre_df.groupby(["class_label"])
        .size().reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    print("\nPer-class counts:")
    for _, r in summary.iterrows():
        print(f"- {r['class_label']}: {r['count']}")


if __name__ == "__main__":
    main()