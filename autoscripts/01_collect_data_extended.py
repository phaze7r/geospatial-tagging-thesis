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

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
RAW_DIR = os.path.join(DATAREPORTED_DIR, "raw")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CITIES_CONFIG = os.path.join(CONFIG_DIR, "cities.yaml")
LABELS_CONFIG = os.path.join(CONFIG_DIR, "labels_pk.yaml")

# Create output directories
os.makedirs(RAW_DIR, exist_ok=True)

# Logging Setup
log_filename = os.path.join(RAW_DIR, f"collection_log_extended_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
    # Handle recursive structures (like sustain/amenity)
    def recurse(d, prefix=[]):
        for k, v in d.items():
            if isinstance(v, dict):
                recurse(v, prefix + [k])
            elif isinstance(v, list):
                # The key 'k' is the OSM tag key, 'v' is list of values
                for val in v:
                    pairs.append((k, val))
    
    recurse(labels_dict)
    return pairs

def tile_bbox(min_lon, min_lat, max_lon, max_lat, tiles_per_side=4):
    """Split bbox into a grid of smaller bboxes. Reduced tiles for efficiency."""
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
    # Optimization: Chunk tags if too many
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

def flatten_element(elem, target_tag_pairs, city_info):
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

    # Tag matching - Find FIRST matching key/value pair from our target list
    matched_k, matched_v = "", ""
    for k, v in target_tag_pairs:
        if tags.get(k) == v:
            matched_k, matched_v = k, v
            break
            
    # If no match found (unlikely if query worked), try to find any relevant tag
    if not matched_k:
        for k in ["amenity", "shop", "leisure", "tourism", "historic", "office", "natural", "building"]:
            if k in tags:
                matched_k = k
                matched_v = tags[k]
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
        # Keep name_en/name_pa if available
        "name_en": tags.get("name:en", ""), 
        "alt_name": tags.get("alt_name", ""),
        "description_raw": tags.get("description", ""),
        "lat": lat,
        "lon": lon,
        "city": city_info.get("name", "Unknown"),
        "province": city_info.get("province", "Unknown"),
        "country": "Pakistan",
        "brand": tags.get("brand", ""),
        "operator": tags.get("operator", ""),
        "wikidata": tags.get("wikidata", "")
    }
    return row

# --- Main Execution ---

def main():
    logging.info("Starting Extended Data Collection (Autoscript 01)...")
    
    # Load Configurations
    cities_cfg = load_yaml_or_default(CITIES_CONFIG, {
        "cities": []
    })
    
    labels_cfg = load_yaml_or_default(LABELS_CONFIG, {
        "core": {"amenity": ["mosque"]} 
    })
    
    target_tags = flatten_label_pairs(labels_cfg)
    
    cities = cities_cfg.get("cities", [])
    logging.info(f"Tag Pairs Count: {len(target_tags)}")
    logging.info(f"Target Cities ({len(cities)}): {[c['name'] for c in cities]}")

    for city_info in cities:
        city_name = city_info["name"]
        bbox = city_info["bbox"]
        
        logging.info(f"--- Processing City: {city_name} ---")
        logging.info(f"BBox: {bbox}")
        
        # Prepare Tiles
        tiles = tile_bbox(*bbox, tiles_per_side=4) 
        
        # Files
        safe_city_name = city_name.lower().replace(" ", "_")
        raw_jsonl_path = os.path.join(RAW_DIR, f"{safe_city_name}_raw.jsonl")
        csv_path = os.path.join(RAW_DIR, f"{safe_city_name}_raw.csv")
        
        # Collection Loop
        seen_ids = set()
        total_elements = 0
        tile_stats = []
        errors = 0

        logging.info(f"Writing raw data to: {raw_jsonl_path}")
        with open(raw_jsonl_path, "w", encoding="utf-8") as f_out:
            for idx, tile in enumerate(tiles):
                if (idx + 1) % 5 == 0:
                    logging.info(f"Processing Tile {idx+1}/{len(tiles)} for {city_name}...")
                
                query = build_overpass_query(tile, target_tags)
                
                try:
                    data = overpass_request(query, OVERPASS_ENDPOINTS)
                    elements = data.get("elements", [])
                    
                    new_count = 0
                    for elem in elements:
                        uid = (elem.get("type"), elem.get("id"))
                        if uid not in seen_ids:
                            seen_ids.add(uid)
                            json_line = json.dumps(elem, ensure_ascii=False)
                            f_out.write(json_line + "\n")
                            total_elements += 1
                            new_count += 1
                    
                    tile_stats.append({"tile": idx, "bbox": tile, "count": new_count})
                    time.sleep(0.5) 
                    
                except Exception as e:
                    logging.error(f"Failed tile {idx} in {city_name}: {e}")
                    errors += 1
                    tile_stats.append({"tile": idx, "error": str(e)})
                    time.sleep(2.0)

        # Flatten and Save CSV (Individual per city as requested)
        logging.info(f"Collection complete for {city_name}. Elements: {total_elements}. Flattening to CSV...")
        
        kept_rows = 0
        rows = []
        
        with open(raw_jsonl_path, "r", encoding="utf-8") as f_in:
            for line in f_in:
                elem = json.loads(line)
                row = flatten_element(elem, target_tags, city_info)
                # Keep row if it has tags (most probably due to filter)
                if row["osm_tag_key"] and row["osm_tag_value"]:
                    rows.append(row)

        fieldnames = [
            "id", "osm_id", "osm_geom_type", "osm_tag_key", "osm_tag_value",
            "name", "name_ur", "name_en", "alt_name",
            "description_raw", "lat", "lon", "city", "province", "country",
            "brand", "operator", "wikidata"
        ]

        with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
            writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
                kept_rows += 1
                
        logging.info(f"Saved {kept_rows} rows to {csv_path}")

    logging.info("Extended Data Collection Script Complete.")

if __name__ == "__main__":
    main()
