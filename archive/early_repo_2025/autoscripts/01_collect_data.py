import os
import json
import time
import yaml
import uuid
import random
import logging
import requests
import csv
from datetime import datetime

# --- Configuration & Setup ---
random.seed(42)

# Define paths relative to the script location or project root
# Assuming script is in /autoscripts/ and we want to write to /data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
BBOX_CONFIG = os.path.join(CONFIG_DIR, "islamabad_bbox.yaml")
LABELS_CONFIG = os.path.join(CONFIG_DIR, "labels_pk.yaml")

# Create output directories
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Logging Setup
log_filename = os.path.join(PROCESSED_DIR, f"collection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

# Overpass API Endpoints
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter"
]

# --- Helper Functions ---

def load_yaml_or_default(path, default_dict):
    """Load YAML config or return default if failed."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f)
            except Exception as e:
                logging.warning(f"Failed to parse {path}: {e}. Using defaults.")
                return default_dict
    else:
        logging.warning(f"{path} not found. Using defaults.")
        return default_dict

def flatten_label_pairs(labels_dict):
    """Convert nested labels dict to list of (key, value) tuples."""
    pairs = []
    for group, keyvals in labels_dict.items():
        for k, vals in keyvals.items():
            for v in vals:
                pairs.append((k, v))
    return pairs

def tile_bbox(min_lon, min_lat, max_lon, max_lat, tiles_per_side=6):
    """Split bbox into a grid of smaller bboxes."""
    lon_step = (max_lon - min_lon) / tiles_per_side
    lat_step = (max_lat - min_lat) / tiles_per_side
    tiles = []
    for i in range(tiles_per_side):
        tl_min_lon = min_lon + i * lon_step
        tl_max_lon = min_lon + (i + 1) * lon_step
        for j in range(tiles_per_side):
            tl_min_lat = min_lat + j * lat_step
            tl_max_lat = min_lat + (j + 1) * lat_step
            tiles.append([tl_min_lon, tl_min_lat, tl_max_lon, tl_max_lat])
    return tiles

def build_overpass_query(bbox, tag_pairs):
    """Construct Overpass QL query."""
    min_lon, min_lat, max_lon, max_lat = bbox
    header = '[out:json][timeout:180];'
    body = "(\n"
    for k, v in tag_pairs:
        body += f'  node["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
        body += f'  way["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
        body += f'  relation["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
    body += ");\n"
    footer = "out center qt;"
    return header + body + footer

def overpass_request(query, endpoints, max_retries=5, base_backoff=2.0):
    """Execute Overpass query with retries and exponential backoff."""
    for attempt in range(max_retries):
        endpoint = endpoints[attempt % len(endpoints)]
        try:
            resp = requests.post(endpoint, data={"data": query}, timeout=300)
            if resp.status_code in (429, 504, 502, 503):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            delay = base_backoff * (2 ** attempt) + random.uniform(0, 0.5)
            logging.warning(f"Attempt {attempt+1} failed at {endpoint}: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
    raise RuntimeError("All Overpass retries failed.")

def flatten_element(elem, target_tag_pairs):
    """Flatten OSM element to canonical schema."""
    osm_geom_type = elem.get("type", "")
    osm_id = elem.get("id", None)
    tags = elem.get("tags", {}) or {}
    
    # Coordinate extraction
    lat, lon = None, None
    if "lat" in elem and "lon" in elem:
        lat, lon = elem["lat"], elem["lon"]
    elif "center" in elem:
        lat, lon = elem["center"].get("lat"), elem["center"].get("lon")

    # Tag matching
    matched_k, matched_v = "", ""
    for k, v in target_tag_pairs:
        if tags.get(k) == v:
            matched_k, matched_v = k, v
            break

    # Construct row
    row = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"osm:{osm_geom_type}:{osm_id}")),
        "osm_id": osm_id,
        "osm_geom_type": osm_geom_type,
        "osm_tag_key": matched_k,
        "osm_tag_value": matched_v,
        "name": tags.get("name", ""),
        "name_ur": tags.get("name:ur", ""),
        "alt_name": tags.get("alt_name", ""),
        "description_raw": tags.get("description", ""),
        "description_final": "", 
        "description_source": "OSM",
        "wikipedia_title": tags.get("wikipedia", "").split(":")[1] if ":" in tags.get("wikipedia", "") else "",
        "wikipedia_url": "",
        "lat": lat,
        "lon": lon,
        "city": "Islamabad",
        "province": "Islamabad Capital Territory",
        "country": "Pakistan",
        "language": "",
        "dedup_group_id": "",
        "brand": tags.get("brand", ""),
        "operator": tags.get("operator", ""),
        "wikidata": tags.get("wikidata", "")
    }
    return row

# --- Main Execution ---

def main():
    logging.info("Starting Data Collection Script (Autoscript 01)...")
    
    # Load Configurations
    bbox_cfg = load_yaml_or_default(BBOX_CONFIG, {
        "name": "Islamabad", "bbox": [72.8, 33.5, 73.4, 33.9]
    })
    labels_cfg = load_yaml_or_default(LABELS_CONFIG, {
        "core": {"amenity": ["mosque"]} # fast fallbacks
    })
    
    target_tags = flatten_label_pairs(labels_cfg)
    bbox = bbox_cfg["bbox"]
    
    logging.info(f"Target Region: {bbox_cfg['name']} {bbox}")
    logging.info(f"Tag Pairs Count: {len(target_tags)}")

    # Prepare Tiles
    tiles = tile_bbox(*bbox, tiles_per_side=6)
    
    # Files
    raw_jsonl_path = os.path.join(RAW_DIR, "islamabad_overpass_raw.jsonl")
    csv_path = os.path.join(PROCESSED_DIR, "descriptions_raw.csv")
    json_log_path = os.path.join(PROCESSED_DIR, "collection_log.json")

    logging.info(f"Writing raw data to: {raw_jsonl_path}")
    logging.info(f"Writing CSV to: {csv_path}")

    # Collection Loop
    seen_ids = set()
    total_elements = 0
    tile_stats = []
    errors = 0

    with open(raw_jsonl_path, "w", encoding="utf-8") as f_out:
        for idx, tile in enumerate(tiles):
            logging.info(f"Processing Tile {idx+1}/{len(tiles)}...")
            query = build_overpass_query(tile, target_tags)
            
            try:
                data = overpass_request(query, OVERPASS_ENDPOINTS)
                elements = data.get("elements", [])
                
                new_count = 0
                for elem in elements:
                    uid = (elem.get("type"), elem.get("id"))
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        f_out.write(json.dumps(elem, ensure_ascii=False) + "\n")
                        total_elements += 1
                        new_count += 1
                
                tile_stats.append({"tile": idx, "bbox": tile, "count": new_count})
                time.sleep(1.0) # Rate limiting
                
            except Exception as e:
                logging.error(f"Failed tile {idx}: {e}")
                errors += 1
                tile_stats.append({"tile": idx, "error": str(e)})
                time.sleep(5.0)

    # Flatten and Save CSV
    logging.info(f"Collection complete. Total elements: {total_elements}. Flattening to CSV...")
    
    kept_rows = 0
    rows = []
    
    # Read back and flatten
    with open(raw_jsonl_path, "r", encoding="utf-8") as f_in:
        for line in f_in:
            elem = json.loads(line)
            row = flatten_element(elem, target_tags)
            if row["osm_tag_key"] and row["osm_tag_value"]:
                rows.append(row)

    # Field Definitions
    fieldnames = [
        "id", "osm_id", "osm_geom_type", "osm_tag_key", "osm_tag_value",
        "name", "name_ur", "alt_name",
        "description_raw", "description_final", "description_source",
        "wikipedia_title", "wikipedia_url",
        "lat", "lon", "city", "province", "country",
        "language", "dedup_group_id",
        "brand", "operator", "wikidata"
    ]

    with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
            kept_rows += 1

    # Save Log
    final_log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "bbox": bbox,
        "total_elements": total_elements,
        "kept_rows": kept_rows,
        "errors": errors,
        "tile_stats": tile_stats
    }
    
    with open(json_log_path, "w", encoding="utf-8") as f_log:
        json.dump(final_log, f_log, indent=2)

    logging.info(f"Process Complete. Kept Rows: {kept_rows}. Logs saved.")

if __name__ == "__main__":
    main()
