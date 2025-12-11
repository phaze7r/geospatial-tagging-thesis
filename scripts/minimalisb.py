#!/usr/bin/env python3
"""
OSM sampler for Islamabad with expanded tags and manageable size.

- BBOX: Islamabad urban area (s, w, n, e) = (33.66, 72.96, 33.78, 73.18)
- Elements: nodes + ways (+ relations where it matters), using 'out center' for area features
- Tags covered (as requested):
  amenity = cafe, restaurant, hospital, bank, school, marketplace (market/bazaar)
  mosque  = amenity=place_of_worship + religion=muslim OR building=mosque (normalized to amenity=mosque)
  shop    = supermarket, bakery, clothes
  highway = bus_stop
  leisure = park
  natural = water, tree
  tourism = hotel
  building= residential (sampled, can be heavy; ways only)
  historic= monument
  place   = locality (place-level points)

- Default per-value limits are tuned to yield a few hundred rows. If you want more/less, adjust the 'limit' in TAG_SPECS below.

Outputs (./output):
  - osm_isb_raw.json
  - osm_isb.csv
  - osm_isb.geojson

Requires: pip install requests pandas
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import requests
    import pandas as pd
except ImportError:
    print("Please install requirements:\n  pip install requests pandas")
    raise

# -----------------------------
# Config
# -----------------------------
# Islamabad bbox (south, west, north, east)
BBOX: Tuple[float, float, float, float] = (33.66, 72.96, 33.78, 73.18)

# Overpass API endpoint and client settings
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT_SEC = 180
MAX_RETRIES = 4
BACKOFF_SEC = 10

# Output
OUT_DIR = Path("output")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_JSON_PATH = OUT_DIR / "osm_isb_raw.json"
CSV_PATH = OUT_DIR / "osm_isb.csv"
GEOJSON_PATH = OUT_DIR / "osm_isb.geojson"
QL_PATH = OUT_DIR / "overpass_isb_query.ql"

# Tag specifications: each entry describes how to pull a family of features
# - group: higher-level grouping for your downstream pipeline
# - key: OSM tag key to match
# - values: list of OSM tag values to match for that key
# - types: which element types to fetch for these values: subset of {"node", "way", "relation"}
# - limit: per-value limit (applies to each requested type; keep modest to stay small)
# - extra_kv: optional dict of extra key=value filters for this spec (e.g., religion=muslim)
# - classify_as: optional override of classification to normalize to your taxonomy (e.g., amenity=mosque)
TAG_SPECS: List[Dict[str, Any]] = [
    # Amenity types
    {"group": "amenity", "key": "amenity", "values": ["cafe"], "types": ["node", "way"], "limit": 50},
    {"group": "amenity", "key": "amenity", "values": ["restaurant"], "types": ["node", "way"], "limit": 60},
    {"group": "amenity", "key": "amenity", "values": ["hospital"], "types": ["node", "way"], "limit": 40},
    {"group": "amenity", "key": "amenity", "values": ["bank"], "types": ["node", "way"], "limit": 40},
    {"group": "amenity", "key": "amenity", "values": ["school"], "types": ["node", "way"], "limit": 50},
    # Market/Bazaar (standard tag: amenity=marketplace)
    {"group": "amenity", "key": "amenity", "values": ["marketplace"], "types": ["node", "way"], "limit": 40},

    # Mosque normalization (two sources mapped to amenity=mosque)
    {"group": "amenity", "key": "amenity", "values": ["place_of_worship"], "extra_kv": {"religion": "muslim"},
     "types": ["node", "way"], "limit": 60, "classify_as": {"primary_key": "amenity", "primary_value": "mosque"}},
    {"group": "amenity", "key": "building", "values": ["mosque"],
     "types": ["node", "way"], "limit": 30, "classify_as": {"primary_key": "amenity", "primary_value": "mosque"}},

    # Shops
    {"group": "shop", "key": "shop", "values": ["supermarket"], "types": ["node", "way"], "limit": 50},
    {"group": "shop", "key": "shop", "values": ["bakery"], "types": ["node", "way"], "limit": 40},
    {"group": "shop", "key": "shop", "values": ["clothes"], "types": ["node", "way"], "limit": 40},

    # Transport
    {"group": "transport", "key": "highway", "values": ["bus_stop"], "types": ["node", "way"], "limit": 70},

    # Leisure / Park
    {"group": "leisure", "key": "leisure", "values": ["park"], "types": ["node", "way"], "limit": 50},

    # Natural
    {"group": "natural", "key": "natural", "values": ["tree"], "types": ["node"], "limit": 60},  # trees are usually nodes
    {"group": "natural", "key": "natural", "values": ["water"], "types": ["way", "relation"], "limit": 40},

    # Tourism
    {"group": "tourism", "key": "tourism", "values": ["hotel"], "types": ["node", "way"], "limit": 50},

    # Building (be careful; many). We sample only ways.
    {"group": "building", "key": "building", "values": ["residential"], "types": ["way"], "limit": 40},

    # Historic
    {"group": "historic", "key": "historic", "values": ["monument"], "types": ["node", "way"], "limit": 40},

    # Place-level
    {"group": "place", "key": "place", "values": ["locality"], "types": ["node"], "limit": 60},
]


# -----------------------------
# Build Overpass QL
# -----------------------------
def _kv_filters(key: str, value: str, extra_kv: Dict[str, str] | None) -> str:
    parts = [f'["{key}"="{value}"]']
    if extra_kv:
        for k, v in extra_kv.items():
            parts.append(f'["{k}"="{v}"]')
    return "".join(parts)


def build_overpass_query(
    specs: List[Dict[str, Any]],
    bbox: Tuple[float, float, float, float],
) -> str:
    s, w, n, e = bbox
    header = "[out:json][timeout:180];\n"
    lines: List[str] = []
    for spec in specs:
        key = spec["key"]
        values: List[str] = spec["values"]
        types: List[str] = spec["types"]
        limit: int = spec.get("limit", 50)
        extra_kv: Dict[str, str] | None = spec.get("extra_kv")

        for v in values:
            filt = _kv_filters(key, v, extra_kv)
            for t in types:
                if t == "node":
                    lines.append(f'node{filt}({s},{w},{n},{e}); out body {limit};')
                elif t == "way":
                    lines.append(f'way{filt}({s},{w},{n},{e}); out center {limit};')
                elif t == "relation":
                    lines.append(f'relation{filt}({s},{w},{n},{e}); out center {limit};')
                else:
                    raise ValueError(f"Unsupported type in spec: {t}")
    return header + "\n".join(lines)


# -----------------------------
# Fetch with retry
# -----------------------------
def fetch_overpass(query: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": "geospatial-thesis-sampler/2.0 (student use)",
        "Accept": "application/json",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                OVERPASS_ENDPOINT,
                data={"data": query},
                headers=headers,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            if resp.status_code == 200:
                try:
                    return resp.json()
                except json.JSONDecodeError:
                    raise RuntimeError(f"Non-JSON response: {resp.text[:300]}")
            if resp.status_code in (429, 502, 503, 504):
                wait = BACKOFF_SEC * attempt
                print(f"Overpass busy (HTTP {resp.status_code}). Retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Overpass HTTP {resp.status_code}: {resp.text[:500]}")
        except requests.RequestException as ex:
            wait = BACKOFF_SEC * attempt
            print(f"Network error: {ex}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to fetch Overpass after retries.")


# -----------------------------
# Classify + parse elements
# -----------------------------
def normalize_classification(
    tags: Dict[str, str],
    spec: Dict[str, Any],
    matched_key: str,
    matched_value: str,
) -> Tuple[str | None, str | None, str | None]:
    """
    Return (group, primary_key, primary_value) for downstream use.
    - Applies spec['classify_as'] override when present.
    - Normalizes mosque to amenity=mosque.
    """
    group = spec.get("group")

    # Spec override (e.g., mosque)
    if spec.get("classify_as"):
        pk = spec["classify_as"].get("primary_key")
        pv = spec["classify_as"].get("primary_value")
        return group, pk, pv

    # Heuristics for requested taxonomy
    amenity = tags.get("amenity")
    building = tags.get("building")

    # Mosque normalization if not covered by classify_as:
    if amenity == "place_of_worship" and tags.get("religion") == "muslim":
        return "amenity", "amenity", "mosque"
    if building == "mosque":
        return "amenity", "amenity", "mosque"

    # Otherwise use the matched key/value
    return group, matched_key, matched_value


def elements_to_records(
    data: Dict[str, Any],
    specs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # Build a quick lookup to infer group and classify by matched key/value
    # Key: (key, value) -> spec
    kv_to_spec: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for spec in specs:
        extra_kv = spec.get("extra_kv")
        for v in spec["values"]:
            # Combine extra_kv into the key only for lookup? No — we ignore extra_kv
            # during classification because we also check tags directly when needed.
            kv_to_spec[(spec["key"], v)] = spec

    records: List[Dict[str, Any]] = []
    seen = set()  # de-dup across repeated statements

    for el in data.get("elements", []):
        el_type = el.get("type")
        el_id = el.get("id")
        key = (el_type, el_id)
        if key in seen:
            continue
        seen.add(key)

        # Geometry
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center")
            if isinstance(center, dict):
                lat = center.get("lat")
                lon = center.get("lon")
        # If still missing, skip
        if lat is None or lon is None:
            continue

        tags: Dict[str, str] = el.get("tags", {}) or {}

        # Determine which requested (key, value) we matched (best-effort)
        matched_key = None
        matched_value = None
        for (k, v), spec in kv_to_spec.items():
            if tags.get(k) == v:
                # If spec had extra_kv, ensure they match for true classification
                extra_ok = True
                extra_kv = spec.get("extra_kv")
                if extra_kv:
                    for ek, ev in extra_kv.items():
                        if tags.get(ek) != ev:
                            extra_ok = False
                            break
                if extra_ok:
                    matched_key, matched_value = k, v
                    break

        # Normalize classification
        if matched_key is None and tags.get("building") == "mosque":
            # Special-case building=mosque even when not explicitly matched (some data mapped this way)
            spec_stub = {"group": "amenity", "classify_as": {"primary_key": "amenity", "primary_value": "mosque"}}
            group, pk, pv = normalize_classification(tags, spec_stub, "building", "mosque")
        else:
            spec_for_class = kv_to_spec.get((matched_key, matched_value), {}) if matched_key else {}
            group, pk, pv = normalize_classification(tags, spec_for_class, matched_key or None, matched_value or None)

        # Compose address
        addr_parts = []
        for addr_k in ("addr:street", "addr:housenumber", "addr:city", "addr:postcode"):
            if tags.get(addr_k):
                addr_parts.append(tags[addr_k])
        addr_full = ", ".join(addr_parts) if addr_parts else tags.get("addr:full")

        records.append(
            {
                "osm_id": el_id,
                "osm_type": el_type,
                "lat": lat,
                "lon": lon,
                "group": group,
                "primary_key": pk,
                "primary_value": pv,
                "name": tags.get("name"),
                "addr_full": addr_full,
                "all_tags_json": json.dumps(tags, ensure_ascii=False),
            }
        )

    return records


# -----------------------------
# Exporters
# -----------------------------
def export_csv(records: List[Dict[str, Any]], path: Path) -> None:
    df = pd.DataFrame.from_records(records)
    # Order columns
    cols = [
        "osm_id",
        "osm_type",
        "group",
        "primary_key",
        "primary_value",
        "name",
        "addr_full",
        "lat",
        "lon",
        "all_tags_json",
    ]
    for c in list(df.columns):
        if c not in cols:
            cols.append(c)
    df = df[cols]
    df.sort_values(by=["group", "primary_key", "primary_value", "name"], inplace=True, na_position="last")
    df.to_csv(path, index=False)
    print(f"Wrote CSV: {path} (rows={len(df)})")


def export_geojson(records: List[Dict[str, Any]], path: Path) -> None:
    features = []
    for r in records:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is None or lon is None:
            continue
        props = dict(r)
        props.pop("lat", None)
        props.pop("lon", None)
        features.append(
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [lon, lat]},
             "properties": props}
        )
    fc = {"type": "FeatureCollection", "features": features}
    with path.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"Wrote GeoJSON: {path} (features={len(features)})")


# -----------------------------
# Main
# -----------------------------
def main():
    print("Building Overpass QL for expanded tags...")
    query = build_overpass_query(TAG_SPECS, BBOX)
    QL_PATH.write_text(query, encoding="utf-8")
    print(f"Saved Overpass QL to: {QL_PATH}")

    print("Querying Overpass (may take some seconds)...")
    data = fetch_overpass(query)
    with RAW_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote raw JSON: {RAW_JSON_PATH}")

    print("Parsing elements...")
    records = elements_to_records(data, TAG_SPECS)
    if not records:
        print("No records parsed. Consider increasing per-value limits or widening the bbox.")
        return

    export_csv(records, CSV_PATH)
    export_geojson(records, GEOJSON_PATH)

    # Quick summary per group/value
    df = pd.DataFrame.from_records(records)
    print("\nCounts by group and value:")
    grp = df.groupby(["group", "primary_key", "primary_value"]).size().reset_index(name="count")
    for _, row in grp.iterrows():
        print(f"- {row['group']} :: {row['primary_key']}={row['primary_value']}: {row['count']}")

    print("\nDone. If you need more or fewer rows, adjust the 'limit' fields in TAG_SPECS.")


if __name__ == "__main__":
    main()